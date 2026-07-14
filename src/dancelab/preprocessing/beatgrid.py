"""Tempo estimation and beat tracking (beatgrid). STATUS: stable baseline.

Uses librosa.beat.beat_track (onset-envelope dynamic-programming beat tracker).
Accepts an optional user BPM hint (tightens the tempo prior). Downbeats are a
proxy: every 4th beat from the first (assumes 4/4 — true for virtually all the
electronic material here; real downbeat tracking is a later upgrade).

Deterministic: librosa's beat tracker is deterministic for a fixed signal.
Requires the [audio] extra.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.errors import MissingDependencyError
from dancelab.core.models import BeatGrid
from dancelab.preprocessing.tempo_precision import refine_bpm_from_beat_times

_DOUBLE_TIME_MAX_GRACE_BPM = 6.0
_DOUBLE_TIME_MIN_COVERAGE = 0.55
_DOUBLE_TIME_MIN_STRENGTH_RATIO = 0.35


def octave_fold_factor(bpm: float, tempo_min: float, tempo_max: float) -> float:
    """Power-of-2 factor that brings bpm into [tempo_min, tempo_max).

    Beat trackers commonly lock onto half/double time (house 124 → 62,
    DnB 175 → 88). Returns 2.0 if the tempo must be doubled, 0.5 if halved,
    1.0 if already in range. Guards against a degenerate range.
    """
    if bpm <= 0 or tempo_max <= tempo_min:
        return 1.0
    factor = 1.0
    guard = 0
    while bpm * factor < tempo_min and guard < 8:
        factor *= 2.0
        guard += 1
    while bpm * factor >= tempo_max and guard < 8:
        factor /= 2.0
        guard += 1
    return factor


def _refit_beats(beat_times: np.ndarray, factor: float) -> np.ndarray:
    """Resample tracked beats by a power-of-2 factor, preserving phase.

    factor > 1 (tempo doubled): subdivide each interval evenly.
    factor < 1 (tempo halved): decimate — keep every 1/factor-th beat.
    """
    if factor == 1.0 or len(beat_times) < 2:
        return beat_times
    if factor > 1:
        k = int(round(factor))  # subdivisions per original interval
        out = []
        for a, b in zip(beat_times[:-1], beat_times[1:]):
            out.extend(a + (b - a) * (j / k) for j in range(k))
        out.append(float(beat_times[-1]))
        return np.array(out)
    step = int(round(1.0 / factor))  # keep every step-th beat
    return beat_times[::step]


def _sample_curve_max(curve: np.ndarray, frame_indices: np.ndarray, radius: int = 1) -> np.ndarray:
    values = np.zeros(len(frame_indices), dtype=np.float64)
    if len(curve) == 0:
        return values
    last = len(curve) - 1
    for idx, frame in enumerate(frame_indices):
        center = int(np.clip(frame, 0, last))
        lo = max(0, center - radius)
        hi = min(last + 1, center + radius + 1)
        values[idx] = float(np.max(curve[lo:hi])) if hi > lo else 0.0
    return values


def _double_time_subdivision_supported(
    x: np.ndarray,
    sample_rate: int,
    hop_size: int,
    beat_times: np.ndarray,
) -> tuple[bool, dict[str, float]]:
    """Evidence gate for folding low/ambiguous tempos upward.

    A real slow track can live at 50-90 BPM. We only double it when the audio
    shows regular onset energy halfway between the current beats, which is the
    telltale sign that the tracker latched onto half-time.
    """
    beats = np.sort(np.asarray(beat_times, dtype=np.float64))
    beats = beats[np.isfinite(beats)]
    if len(beats) < 4 or sample_rate <= 0 or hop_size <= 0:
        return False, {"coverage": 0.0, "strength_ratio": 0.0}

    intervals = np.diff(beats)
    valid = intervals > 1e-6
    if not np.any(valid):
        return False, {"coverage": 0.0, "strength_ratio": 0.0}

    beats = beats[:-1][valid]
    intervals = intervals[valid]
    midpoints = beats + intervals / 2.0

    try:
        import librosa
    except ImportError:  # pragma: no cover - estimate_beatgrid already checks this.
        return False, {"coverage": 0.0, "strength_ratio": 0.0}

    envelope = librosa.onset.onset_strength(
        y=np.asarray(x, dtype=np.float32),
        sr=sample_rate,
        hop_length=hop_size,
    )
    envelope = np.nan_to_num(np.asarray(envelope, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    if len(envelope) == 0 or np.allclose(envelope, 0.0):
        return False, {"coverage": 0.0, "strength_ratio": 0.0}

    beat_frames = np.rint(beats * sample_rate / hop_size).astype(int)
    midpoint_frames = np.rint(midpoints * sample_rate / hop_size).astype(int)
    beat_strength = _sample_curve_max(envelope, beat_frames, radius=1)
    midpoint_strength = _sample_curve_max(envelope, midpoint_frames, radius=1)

    beat_ref = float(np.median(beat_strength[beat_strength > 0.0])) if np.any(beat_strength > 0.0) else 0.0
    if beat_ref <= 0.0:
        return False, {"coverage": 0.0, "strength_ratio": 0.0}

    midpoint_ref = float(np.median(midpoint_strength))
    global_floor = float(np.percentile(envelope, 75)) if len(envelope) else 0.0
    threshold = max(0.18 * beat_ref, 0.25 * global_floor)
    coverage = float(np.mean(midpoint_strength >= threshold)) if len(midpoint_strength) else 0.0
    strength_ratio = midpoint_ref / beat_ref
    supported = (
        coverage >= _DOUBLE_TIME_MIN_COVERAGE
        and strength_ratio >= _DOUBLE_TIME_MIN_STRENGTH_RATIO
    )
    return supported, {
        "coverage": round(coverage, 4),
        "strength_ratio": round(strength_ratio, 4),
    }


def _evidence_gated_octave_fold_factor(
    bpm: float,
    beat_times: np.ndarray,
    x: np.ndarray,
    sample_rate: int,
    hop_size: int,
    tempo_min: float,
    tempo_max: float,
) -> tuple[float, list[str]]:
    """Choose a DJ-usable tempo octave without blindly destroying real slow BPMs."""
    if bpm <= 0 or tempo_max <= tempo_min:
        return 1.0, []

    factor = 1.0
    flags: list[str] = []
    folded_bpm = float(bpm)
    folded_beats = np.asarray(beat_times, dtype=np.float64)
    upper_with_grace = tempo_max + _DOUBLE_TIME_MAX_GRACE_BPM

    # Double only when (a) the doubled tempo remains in a realistic DJ ceiling
    # and (b) the audio supports a regular midpoint pulse.
    guard = 0
    while folded_bpm * 2.0 <= upper_with_grace and guard < 4:
        supported, evidence = _double_time_subdivision_supported(
            x,
            sample_rate,
            hop_size,
            folded_beats,
        )
        if not supported:
            if folded_bpm < tempo_min:
                flags.append(
                    "low_bpm_preserved_no_double_time_evidence"
                    f"(coverage={evidence['coverage']:.2f},ratio={evidence['strength_ratio']:.2f})"
                )
            break
        factor *= 2.0
        folded_bpm *= 2.0
        folded_beats = _refit_beats(folded_beats, 2.0)
        flags.append(
            "octave_folded_x2_double_time_evidence"
            f"(coverage={evidence['coverage']:.2f},ratio={evidence['strength_ratio']:.2f})"
        )
        if folded_bpm >= tempo_min:
            break
        guard += 1

    guard = 0
    while folded_bpm > upper_with_grace and folded_bpm > 0 and guard < 8:
        factor /= 2.0
        folded_bpm /= 2.0
        guard += 1
        flags.append("octave_folded_x0.5_above_ceiling")

    return factor, flags


def _fixed_grid_diagnostics(beat_times: np.ndarray, bpm: float) -> dict[str, object]:
    """Measure whether tracked beats can safely become one fixed Rekordbox grid.

    Rekordbox XML export currently carries a constant-BPM TEMPO node. This
    diagnostic checks the exact risk that creates DJ "horses": tracked beats
    drifting away from the fixed grid that would be exported.
    """
    flags: list[str] = []
    if bpm <= 0:
        return {
            "reliable": False,
            "quality_score": 0.0,
            "interval_cv": None,
            "mean_grid_error_sec": None,
            "max_grid_error_sec": None,
            "bpm_mismatch_pct": None,
            "coverage_sec": None,
            "diagnostic_flags": ["invalid_bpm"],
        }

    beat_times = np.asarray(beat_times, dtype=float)
    beat_times = beat_times[np.isfinite(beat_times)]
    if len(beat_times) < 2:
        return {
            "reliable": False,
            "quality_score": 0.0,
            "interval_cv": None,
            "mean_grid_error_sec": None,
            "max_grid_error_sec": None,
            "bpm_mismatch_pct": None,
            "coverage_sec": 0.0,
            "diagnostic_flags": ["insufficient_beats"],
        }

    beat_times = np.sort(beat_times)
    intervals = np.diff(beat_times)
    if np.any(intervals <= 0):
        flags.append("non_monotonic_beats")
        intervals = intervals[intervals > 0]
    if len(intervals) == 0:
        flags.append("insufficient_intervals")
        return {
            "reliable": False,
            "quality_score": 0.0,
            "interval_cv": None,
            "mean_grid_error_sec": None,
            "max_grid_error_sec": None,
            "bpm_mismatch_pct": None,
            "coverage_sec": 0.0,
            "diagnostic_flags": flags,
        }

    beat_period = 60.0 / bpm
    phase = (beat_times - beat_times[0]) / beat_period
    errors = np.abs(phase - np.round(phase)) * beat_period
    mean_error = float(np.mean(errors))
    max_error = float(np.max(errors))
    coverage = float(beat_times[-1] - beat_times[0])
    interval_mean = float(np.mean(intervals))
    interval_median = float(np.median(intervals))
    interval_cv = float(np.std(intervals) / interval_mean) if interval_mean > 0 else None
    mean_error_beats = mean_error / beat_period
    max_error_beats = max_error / beat_period
    long_span = refine_bpm_from_beat_times(beat_times, bpm)
    inferred_bpm = (
        float(long_span["bpm"])
        if long_span["accepted"]
        else (60.0 / interval_median if interval_median > 0 else 0.0)
    )
    bpm_mismatch_pct = abs(inferred_bpm - bpm) / bpm * 100.0 if inferred_bpm > 0 else 100.0

    if len(beat_times) < 8:
        flags.append("insufficient_beats")
    if coverage < 16.0:
        flags.append("short_beat_coverage")
    if interval_cv is not None and interval_cv > 0.12:
        flags.append("irregular_beat_intervals")
    if bpm_mismatch_pct > 0.8:
        flags.append("grid_drift")
    if bpm_mismatch_pct > 0.8:
        flags.append("bpm_grid_mismatch")

    quality = 1.0
    quality -= min(0.45, bpm_mismatch_pct / 2.0)
    quality -= min(0.25, mean_error_beats * 0.6)
    quality -= min(0.15, max_error_beats * 0.2)
    if interval_cv is not None:
        quality -= min(0.35, interval_cv / 0.12 * 0.35)
    quality = max(0.0, min(1.0, quality))

    blocking = {"insufficient_beats", "irregular_beat_intervals", "grid_drift", "non_monotonic_beats"}
    return {
        "reliable": not bool(blocking.intersection(flags)),
        "quality_score": round(quality, 4),
        "interval_cv": round(interval_cv, 6) if interval_cv is not None else None,
        "mean_grid_error_sec": round(mean_error, 6),
        "max_grid_error_sec": round(max_error, 6),
        "bpm_mismatch_pct": round(bpm_mismatch_pct, 4),
        "coverage_sec": round(coverage, 4),
        "diagnostic_flags": flags,
    }


def estimate_beatgrid(
    signal: AudioSignal,
    hop_size: int = 512,
    bpm_hint: float | None = None,
    beats_per_bar: int = 4,
    tempo_min: float = 90.0,
    tempo_max: float = 180.0,
) -> BeatGrid:
    """Estimate BPM + beat times + (proxy) downbeats.

    bpm_hint, when given, is only librosa's start_bpm prior. It never disables
    octave handling; file tags are hints, not proof of the musical tempo.
    """
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - exercised only without [audio]
        raise MissingDependencyError(
            "librosa is required for beat tracking. Install: pip install 'dancelab-engine[audio]'"
        ) from exc

    x = np.asarray(signal.samples, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0)

    tempo, beat_frames = librosa.beat.beat_track(
        y=x, sr=signal.sample_rate, hop_length=hop_size,
        start_bpm=bpm_hint if bpm_hint else 120.0, units="frames",
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=signal.sample_rate, hop_length=hop_size)
    bpm = float(np.atleast_1d(tempo)[0])

    # Tags/hints inform the tracker but never bypass octave handling. Folding
    # upward is evidence-gated so real slow tracks (50/70/80 BPM) stay slow
    # unless the audio shows a regular double-time midpoint pulse.
    fold_factor, fold_flags = _evidence_gated_octave_fold_factor(
        bpm,
        beat_times,
        x,
        signal.sample_rate,
        hop_size,
        tempo_min,
        tempo_max,
    )
    if fold_factor != 1.0:
        bpm *= fold_factor
        beat_times = _refit_beats(beat_times, fold_factor)

    refinement = refine_bpm_from_beat_times(beat_times, bpm)
    if refinement["accepted"]:
        raw_bpm = bpm
        bpm = float(refinement["bpm"])
        fold_flags.append(
            "bpm_refined_from_32_beat_spans"
            f"(raw={raw_bpm:.4f},cv={refinement['robust_cv']:.5f})"
        )

    # AUD-M2: no detected beats → the 120 is a placeholder, not a measurement.
    # Keep a positive bpm (schema requires >0) but flag it unreliable so
    # downstream never treats fabricated silence as a real tempo.
    diagnostics = _fixed_grid_diagnostics(beat_times, bpm)
    diagnostics["diagnostic_flags"] = [
        *fold_flags,
        "downbeat_phase_unverified_proxy",
        *diagnostics["diagnostic_flags"],
    ]
    reliable = bool(diagnostics["reliable"])
    downbeats = [float(t) for t in beat_times[::beats_per_bar]]
    return BeatGrid(
        bpm=round(bpm, 2) if bpm > 0 else 120.0,
        beat_times_sec=[round(float(t), 4) for t in beat_times],
        downbeats_sec=[round(t, 4) for t in downbeats],
        downbeat_phase_verified=False,
        reliable=reliable,
        quality_score=diagnostics["quality_score"],
        interval_cv=diagnostics["interval_cv"],
        mean_grid_error_sec=diagnostics["mean_grid_error_sec"],
        max_grid_error_sec=diagnostics["max_grid_error_sec"],
        bpm_mismatch_pct=diagnostics["bpm_mismatch_pct"],
        coverage_sec=diagnostics["coverage_sec"],
        diagnostic_flags=diagnostics["diagnostic_flags"],
    )

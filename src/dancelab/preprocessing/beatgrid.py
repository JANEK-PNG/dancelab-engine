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


def estimate_beatgrid(
    signal: AudioSignal,
    hop_size: int = 512,
    bpm_hint: float | None = None,
    beats_per_bar: int = 4,
    tempo_min: float = 90.0,
    tempo_max: float = 180.0,
) -> BeatGrid:
    """Estimate BPM + beat times + (proxy) downbeats, octave-folded into
    [tempo_min, tempo_max).

    bpm_hint, when given, is librosa's start_bpm prior AND disables octave
    folding (the user's BPM is authoritative).
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

    # user hint is authoritative; otherwise fold octave errors into range
    if bpm_hint is None and bpm > 0:
        factor = octave_fold_factor(bpm, tempo_min, tempo_max)
        if factor != 1.0:
            bpm *= factor
            beat_times = _refit_beats(beat_times, factor)

    # AUD-M2: no detected beats → the 120 is a placeholder, not a measurement.
    # Keep a positive bpm (schema requires >0) but flag it unreliable so
    # downstream never treats fabricated silence as a real tempo.
    reliable = bpm > 0 and len(beat_times) >= 2
    downbeats = [float(t) for t in beat_times[::beats_per_bar]]
    return BeatGrid(
        bpm=round(bpm, 2) if bpm > 0 else 120.0,
        beat_times_sec=[round(float(t), 4) for t in beat_times],
        downbeats_sec=[round(t, 4) for t in downbeats],
        reliable=reliable,
    )

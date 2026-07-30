"""Host-side, phrase-locked transition preview rendering.

This module deliberately does not participate in engine scoring.  It turns
the engine's track identity, cue timing, BPM and beat-sync rate into a single
temporary WAV that the review surface can audition sample-accurately.

The three-band representation follows the low/mid/high model used by DJ
mixers and the MIR transition-analysis literature.  The curves below are
transparent preview templates, not recovered DJ ground truth or learned
corpus priors.  Every control knot is constrained to an eight-beat boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np


TRANSITION_PREVIEW_SCHEMA_VERSION = 4
DEFAULT_DURATION_BEATS = 64
DEFAULT_GRID_BEATS = 8
TRANSITION_DURATION_OPTIONS = (32, 64, 96, 128, 160, 192, 224, 256)
DEFAULT_WAVEFORM_BINS = 360
PREVIEW_CHANNELS = 2
PREVIEW_OUTPUT_SUBTYPE = "PCM_24"
PREVIEW_TIME_STRETCH_BACKEND = "librosa_phase_vocoder"
PREVIEW_VARISPEED_BACKEND = "librosa_soxr_varispeed"
SOURCE_SHORTFALL_TOLERANCE_SEC = 0.05


@dataclass(frozen=True)
class TransitionEnvelope:
    profile_id: str
    label: str
    description: str
    duration_beats: int
    grid_beats: int
    beat_positions: tuple[float, ...]
    fader_a: tuple[float, ...]
    fader_b: tuple[float, ...]
    low_a: tuple[float, ...]
    mid_a: tuple[float, ...]
    high_a: tuple[float, ...]
    low_b: tuple[float, ...]
    mid_b: tuple[float, ...]
    high_b: tuple[float, ...]
    low_independent: bool = False
    provenance: str = "research_inspired_template_v1"

    def curves(self) -> dict[str, tuple[float, ...]]:
        return {
            "fader_a": self.fader_a,
            "fader_b": self.fader_b,
            "low_a": self.low_a,
            "mid_a": self.mid_a,
            "high_a": self.high_a,
            "low_b": self.low_b,
            "mid_b": self.mid_b,
            "high_b": self.high_b,
        }


@dataclass(frozen=True)
class TransitionWaveform:
    minimum: tuple[float, ...]
    maximum: tuple[float, ...]


@dataclass(frozen=True)
class TransitionRenderResult:
    output_path: Path
    sample_rate: int
    duration_sec: float
    cue_a_sec: float
    cue_b_sec: float
    preview_bpm: float
    playback_rate_a: float
    playback_rate_b: float
    tempo_strategy: str
    envelope: TransitionEnvelope
    outgoing: TransitionWaveform
    mixed: TransitionWaveform
    incoming: TransitionWaveform
    peak_before_normalization: float
    normalization_gain: float
    channels: int
    output_subtype: str
    time_stretch_backend: str


@dataclass(frozen=True)
class TransitionDurationPlan:
    requested_beats: int
    selected_beats: int | None
    max_feasible_beats: float
    outgoing_guard_beats: int

    @property
    def shortened(self) -> bool:
        return self.selected_beats is not None and self.selected_beats < self.requested_beats


def plan_transition_duration(
    requested_beats: int,
    *,
    available_a_beats: float,
    available_b_beats: float,
    outgoing_guard_beats: int = DEFAULT_GRID_BEATS,
) -> TransitionDurationPlan:
    """Choose the longest requested phrase that fits both source files.

    The corpus supports 32-beat phrase multiples but not a deterministic rule
    that maps a long intro to one exact transition length. The host therefore
    keeps duration selection explicit and only applies a hard source-runway
    guardrail here.
    """
    if requested_beats not in TRANSITION_DURATION_OPTIONS:
        raise ValueError(f"requested_beats must be one of {TRANSITION_DURATION_OPTIONS}")
    if outgoing_guard_beats < 0:
        raise ValueError("outgoing_guard_beats must be non-negative")
    available = (float(available_a_beats), float(available_b_beats))
    if not all(np.isfinite(value) and value >= 0.0 for value in available):
        raise ValueError("available beat runways must be finite and non-negative")

    max_feasible = max(
        0.0,
        min(available[0] - float(outgoing_guard_beats), available[1]),
    )
    candidates = [
        beats
        for beats in TRANSITION_DURATION_OPTIONS
        if beats <= requested_beats and beats <= max_feasible + 1e-9
    ]
    return TransitionDurationPlan(
        requested_beats=requested_beats,
        selected_beats=max(candidates) if candidates else None,
        max_feasible_beats=max_feasible,
        outgoing_guard_beats=outgoing_guard_beats,
    )


PROFILE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("linear", "Linear baseline"),
    ("plain_blend", "Balanced blend"),
    ("bass_swap", "Bass swap"),
    ("tops_swap", "Tops swap"),
    ("contour_blend", "Contour blend"),
)


_PROFILE_DESCRIPTIONS = {
    "linear": "Reference crossfade with no EQ movement. Useful as a neutral baseline.",
    "plain_blend": "Equal-power crossfade; all three frequency bands remain open.",
    "bass_swap": "Low bands hand over at the central 8-beat boundary; mids and highs overlap.",
    "tops_swap": "Incoming hats and upper detail arrive first; bass hands over later.",
    "contour_blend": "Staggered low, mid and high handovers reduce full-spectrum overlap.",
}


def profile_description(profile_id: str) -> str:
    try:
        return _PROFILE_DESCRIPTIONS[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown transition preview profile: {profile_id}") from exc


def _as_curve(values: list[float] | np.ndarray, count: int) -> tuple[float, ...]:
    array = np.asarray(values, dtype=np.float64)
    if array.size != count:
        array = np.interp(
            np.linspace(0.0, 1.0, count),
            np.linspace(0.0, 1.0, array.size),
            array,
        )
    if not np.all(np.isfinite(array)):
        raise ValueError("transition curve contains a non-finite value")
    return tuple(float(value) for value in np.clip(array, 0.0, 1.0))


def build_transition_envelope(
    profile_id: str,
    *,
    duration_beats: int = DEFAULT_DURATION_BEATS,
    grid_beats: int = DEFAULT_GRID_BEATS,
    bass_open_at: float | None = None,
) -> TransitionEnvelope:
    """Build one transparent preview template on phrase-grid control knots.

    bass_open_at moves where the low band changes hands, as a fraction of the
    transition, and applies to the templates that swap bass at all. The stock
    bass_swap hands over at the midpoint, which is the textbook move; measured
    across 13 hand-verified seams from one DJ's own recordings the median was
    0.97 — the incoming bass stayed shut until the handover itself. That is a
    property of a player rather than of transitions in general, so it is a
    parameter and the template keeps its own timing by default.
    """
    if duration_beats <= 0 or grid_beats <= 0 or duration_beats % grid_beats:
        raise ValueError("duration_beats must be a positive multiple of grid_beats")
    labels = dict(PROFILE_OPTIONS)
    if profile_id not in labels:
        raise ValueError(f"unknown transition preview profile: {profile_id}")

    beats = np.arange(0, duration_beats + grid_beats, grid_beats, dtype=np.float64)
    count = int(beats.size)
    progress = beats / float(duration_beats)
    linear_a = 1.0 - progress
    linear_b = progress
    equal_power_a = np.cos(progress * np.pi / 2.0)
    equal_power_b = np.sin(progress * np.pi / 2.0)
    ones = np.ones(count, dtype=np.float64)

    if profile_id == "linear":
        fader_a, fader_b = linear_a, linear_b
        low_a = mid_a = high_a = ones
        low_b = mid_b = high_b = ones
    elif profile_id == "plain_blend":
        fader_a, fader_b = equal_power_a, equal_power_b
        low_a = mid_a = high_a = ones
        low_b = mid_b = high_b = ones
    elif profile_id == "bass_swap":
        fader_a, fader_b = equal_power_a, equal_power_b
        low_a = np.array([1, 1, 1, 0.92, 0.05, 0.03, 0, 0, 0], dtype=float)
        low_b = np.array([0, 0, 0.03, 0.08, 1, 1, 1, 1, 1], dtype=float)
        mid_a = np.array([1, 1, 0.96, 0.88, 0.72, 0.52, 0.30, 0.12, 0], dtype=float)
        mid_b = np.array([0, 0.12, 0.30, 0.52, 0.72, 0.88, 0.96, 1, 1], dtype=float)
        high_a, high_b = mid_a, mid_b
    elif profile_id == "tops_swap":
        fader_a, fader_b = equal_power_a, equal_power_b
        high_a = np.array([1, 1, 0.42, 0.08, 0.03, 0, 0, 0, 0], dtype=float)
        high_b = np.array([0, 0.18, 0.82, 1, 1, 1, 1, 1, 1], dtype=float)
        mid_a = np.array([1, 1, 0.94, 0.82, 0.64, 0.44, 0.24, 0.10, 0], dtype=float)
        mid_b = np.array([0, 0.10, 0.24, 0.44, 0.64, 0.82, 0.94, 1, 1], dtype=float)
        low_a = np.array([1, 1, 1, 1, 0.86, 0.58, 0.30, 0.10, 0], dtype=float)
        low_b = np.array([0, 0.03, 0.08, 0.18, 0.52, 0.82, 1, 1, 1], dtype=float)
    else:  # contour_blend
        fader_a, fader_b = equal_power_a, equal_power_b
        low_a = np.array([1, 1, 0.94, 0.68, 0.24, 0.08, 0, 0, 0], dtype=float)
        low_b = np.array([0, 0, 0.06, 0.24, 0.76, 0.94, 1, 1, 1], dtype=float)
        mid_a = np.array([1, 1, 1, 0.94, 0.72, 0.42, 0.20, 0.06, 0], dtype=float)
        mid_b = np.array([0, 0.08, 0.22, 0.48, 0.74, 0.92, 1, 1, 1], dtype=float)
        high_a = np.array([1, 0.96, 0.82, 0.64, 0.48, 0.28, 0.12, 0.04, 0], dtype=float)
        high_b = np.array([0, 0.16, 0.38, 0.62, 0.82, 0.94, 1, 1, 1], dtype=float)

    if bass_open_at is not None and profile_id in {"bass_swap", "tops_swap",
                                                   "contour_blend"}:
        if not 0.0 < bass_open_at <= 1.05:
            raise ValueError("bass_open_at must be a fraction in (0, 1.05]")
        # A knob turns over a beat or two, not instantly and not over the whole
        # phrase, so the handover keeps the width of one grid step wherever it is
        # placed. Built from `progress` rather than by reshaping the nine stock
        # knots, which cannot express a handover that lands near either end.
        width = max(grid_beats / float(duration_beats), 0.02)
        ramp = np.clip((progress - (bass_open_at - width / 2.0)) / width, 0.0, 1.0)
        low_b, low_a = ramp, 1.0 - ramp

    return TransitionEnvelope(
        profile_id=profile_id,
        label=labels[profile_id],
        description=profile_description(profile_id),
        duration_beats=duration_beats,
        grid_beats=grid_beats,
        beat_positions=tuple(float(value) for value in beats),
        fader_a=_as_curve(fader_a, count),
        fader_b=_as_curve(fader_b, count),
        low_a=_as_curve(low_a, count),
        mid_a=_as_curve(mid_a, count),
        high_a=_as_curve(high_a, count),
        low_b=_as_curve(low_b, count),
        low_independent=bass_open_at is not None,
        mid_b=_as_curve(mid_b, count),
        high_b=_as_curve(high_b, count),
    )


def _smooth_interpolate(
    knots: np.ndarray,
    values: np.ndarray,
    positions: np.ndarray,
) -> np.ndarray:
    indices = np.searchsorted(knots, positions, side="right") - 1
    indices = np.clip(indices, 0, knots.size - 2)
    starts = knots[indices]
    spans = np.maximum(knots[indices + 1] - starts, 1e-12)
    phase = np.clip((positions - starts) / spans, 0.0, 1.0)
    phase = phase * phase * (3.0 - 2.0 * phase)
    result = values[indices] + (values[indices + 1] - values[indices]) * phase
    result[positions <= knots[0]] = values[0]
    result[positions >= knots[-1]] = values[-1]
    return np.asarray(result, dtype=np.float32)


def sample_transition_envelope(
    envelope: TransitionEnvelope,
    sample_count: int,
) -> dict[str, np.ndarray]:
    if sample_count < 2:
        raise ValueError("sample_count must be at least two")
    positions = np.linspace(0.0, envelope.duration_beats, sample_count, dtype=np.float64)
    knots = np.asarray(envelope.beat_positions, dtype=np.float64)
    return {
        name: _smooth_interpolate(knots, np.asarray(values), positions)
        for name, values in envelope.curves().items()
    }


def transition_preview_cache_path(
    cache_dir: str | Path,
    *,
    source_a: str | Path,
    source_b: str | Path,
    track_id_a: str,
    track_id_b: str,
    cue_a_sec: float,
    cue_b_sec: float,
    playback_rate_b: float,
    profile_id: str,
    playback_rate_a: float = 1.0,
    preview_bpm: float | None = None,
    tempo_strategy: str = "follow_outgoing",
    duration_beats: int = DEFAULT_DURATION_BEATS,
) -> Path:
    def source_stamp(value: str | Path) -> Mapping[str, object]:
        path = Path(value).expanduser()
        stat = path.stat()
        return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

    payload = {
        "schema": TRANSITION_PREVIEW_SCHEMA_VERSION,
        "a": source_stamp(source_a),
        "b": source_stamp(source_b),
        "track_id_a": track_id_a,
        "track_id_b": track_id_b,
        "cue_a_sec": round(float(cue_a_sec), 4),
        "cue_b_sec": round(float(cue_b_sec), 4),
        "preview_bpm": round(float(preview_bpm), 6) if preview_bpm is not None else None,
        "playback_rate_a": round(float(playback_rate_a), 6),
        "playback_rate_b": round(float(playback_rate_b), 6),
        "tempo_strategy": str(tempo_strategy),
        "profile_id": profile_id,
        "duration_beats": int(duration_beats),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    destination = Path(cache_dir).expanduser() / "transition_previews"
    destination.mkdir(parents=True, exist_ok=True)
    return destination / f"transition-{digest}.wav"


def _as_preview_stereo(samples: np.ndarray) -> np.ndarray:
    """Return channel-first stereo without collapsing the source to mono."""
    matrix = np.asarray(samples, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix[np.newaxis, :]
    if matrix.ndim != 2:
        raise ValueError("transition preview audio must be mono or channel-first audio")
    if matrix.shape[0] == 1:
        matrix = np.repeat(matrix, PREVIEW_CHANNELS, axis=0)
    elif matrix.shape[0] > PREVIEW_CHANNELS:
        matrix = matrix[:PREVIEW_CHANNELS]
    return np.ascontiguousarray(matrix, dtype=np.float32)


def _fit_length(
    samples: np.ndarray,
    length: int,
    *,
    max_padding_frames: int = 0,
) -> np.ndarray:
    matrix = _as_preview_stereo(samples)
    frame_count = matrix.shape[-1]
    if frame_count >= length:
        return matrix[..., :length].copy()
    missing_frames = length - frame_count
    if missing_frames > max_padding_frames:
        raise ValueError(
            "transition audio ended before the requested phrase; "
            "choose an earlier cue or a shorter transition"
        )
    return np.pad(matrix, ((0, 0), (0, length - frame_count))).astype(
        np.float32,
        copy=False,
    )


def _read_audio_segment(
    source_path: str | Path,
    *,
    sample_rate: int,
    start_sec: float,
    duration_sec: float,
) -> np.ndarray:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - audio extra owns this
        raise RuntimeError("librosa is required for transition preview rendering") from exc
    source = Path(source_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(source)
    samples, _ = librosa.load(
        source,
        sr=sample_rate,
        mono=False,
        offset=max(float(start_sec), 0.0),
        duration=max(float(duration_sec), 0.01),
    )
    return _as_preview_stereo(samples)


def _read_at_playback_rate(
    source_path: str | Path,
    *,
    sample_rate: int,
    start_sec: float,
    output_duration_sec: float,
    playback_rate: float,
    output_samples: int,
    tempo_mode: str = "varispeed",
) -> np.ndarray:
    requested_source_sec = output_duration_sec * playback_rate
    source = _read_audio_segment(
        source_path,
        sample_rate=sample_rate,
        start_sec=start_sec,
        duration_sec=requested_source_sec,
    )
    expected_source_frames = int(round(requested_source_sec * sample_rate))
    tolerance_frames = max(1, int(round(SOURCE_SHORTFALL_TOLERANCE_SEC * sample_rate)))
    if source.shape[-1] + tolerance_frames < expected_source_frames:
        available_sec = source.shape[-1] / sample_rate
        raise ValueError(
            f"transition source {Path(source_path).name!r} has only "
            f"{available_sec:.2f}s after the cue but {requested_source_sec:.2f}s is required; "
            "choose an earlier cue or a shorter transition"
        )
    if not np.isclose(playback_rate, 1.0, rtol=0.0, atol=1e-5):
        try:
            import librosa
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("librosa is required for beat-synced preview rendering") from exc
        samples = np.asarray(source, dtype=np.float32)
        if tempo_mode == "stretch":
            # Phase vocoder: pitch is preserved, but transients smear and the
            # result reads as dull or over-compressed — Master Tempo on a CDJ.
            source = librosa.effects.time_stretch(samples, rate=float(playback_rate))
        else:
            # Varispeed: what a pitch fader does with Master Tempo off. Tempo and
            # pitch move together, which is what most DJs actually beatmatch with
            # and what the preview should therefore sound like.
            source = librosa.resample(
                samples,
                orig_sr=float(sample_rate),
                target_sr=float(sample_rate) / float(playback_rate),
                res_type="soxr_hq",
            )
    return _fit_length(
        source,
        output_samples,
        max_padding_frames=tolerance_frames,
    )


def _split_three_bands(samples: np.ndarray, sample_rate: int) -> tuple[np.ndarray, ...]:
    try:
        from scipy.signal import butter, sosfilt, sosfiltfilt
    except ImportError as exc:  # pragma: no cover - audio extra owns this
        raise RuntimeError("scipy is required for transition preview EQ rendering") from exc

    nyquist = sample_rate / 2.0
    low_cutoff = min(250.0, nyquist * 0.25)
    high_cutoff = min(2500.0, nyquist * 0.75)
    if high_cutoff <= low_cutoff:
        raise ValueError("sample rate is too low for the three-band transition preview")
    low_filter = butter(4, low_cutoff / nyquist, btype="lowpass", output="sos")
    high_filter = butter(4, high_cutoff / nyquist, btype="highpass", output="sos")
    filter_fn = sosfiltfilt if samples.shape[-1] > 64 else sosfilt
    low = np.asarray(filter_fn(low_filter, samples, axis=-1), dtype=np.float32)
    high = np.asarray(filter_fn(high_filter, samples, axis=-1), dtype=np.float32)
    # Residual construction makes the open-EQ bands reconstruct the source.
    mid = np.asarray(samples - low - high, dtype=np.float32)
    return low, mid, high


def _apply_deck_curves(
    bands: tuple[np.ndarray, np.ndarray, np.ndarray],
    curves: Mapping[str, np.ndarray],
    deck: str,
    low_independent: bool = False,
) -> np.ndarray:
    """One deck's contribution: its three bands, each at its own EQ position.

    low_independent takes the low band off the line fader, which is how a mixer
    behaves when the DJ leaves the fader up and swaps bass on the knob. With the
    fader in the chain a handover placed early drops the low end to whatever the
    incoming fader happens to be — a fifth of the way in that is a third of level,
    and the measured result was a twenty-five second hole where neither record had
    any bass. The DJ's own recording shows the incoming bass at 1.05 while its mids
    sat at 0.50, which only happens if the knob is independent of the fader.
    """
    low, mid, high = bands
    fader = curves[f"fader_{deck}"][np.newaxis, :]
    low_gain = curves[f"low_{deck}"][np.newaxis, :]
    return np.asarray(
        (low_gain if low_independent else fader * low_gain) * low
        + fader
        * (
            curves[f"mid_{deck}"][np.newaxis, :] * mid
            + curves[f"high_{deck}"][np.newaxis, :] * high
        ),
        dtype=np.float32,
    )


def _waveform_summary(samples: np.ndarray, bins: int = DEFAULT_WAVEFORM_BINS) -> TransitionWaveform:
    matrix = _as_preview_stereo(samples)
    frame_count = matrix.shape[-1]
    bins = max(32, min(int(bins), max(frame_count, 32)))
    edges = np.linspace(0, frame_count, bins + 1, dtype=np.int64)
    minimum = np.zeros(bins, dtype=np.float32)
    maximum = np.zeros(bins, dtype=np.float32)
    for index in range(bins):
        block = matrix[..., edges[index] : edges[index + 1]]
        if block.size:
            minimum[index] = float(block.min(initial=0.0))
            maximum[index] = float(block.max(initial=0.0))
    peak = float(max(np.max(np.abs(minimum)), np.max(np.abs(maximum)), 1e-9))
    return TransitionWaveform(
        minimum=tuple(float(value) for value in np.clip(minimum / peak, -1.0, 1.0)),
        maximum=tuple(float(value) for value in np.clip(maximum / peak, -1.0, 1.0)),
    )


def render_transition_preview(
    *,
    source_a: str | Path,
    source_b: str | Path,
    cue_a_sec: float,
    cue_b_sec: float,
    bpm_master: float,
    playback_rate_b: float,
    profile_id: str,
    output_path: str | Path,
    playback_rate_a: float = 1.0,
    tempo_strategy: str = "follow_outgoing",
    sample_rate: int = 44100,
    duration_beats: int = DEFAULT_DURATION_BEATS,
    grid_beats: int = DEFAULT_GRID_BEATS,
    tempo_mode: str = "varispeed",
    bass_open_at: float | None = None,
) -> TransitionRenderResult:
    """Render one phrase-locked A→B preview to a single sample-accurate WAV.

    tempo_mode: "varispeed" moves pitch with tempo, as a pitch fader does with
    Master Tempo off — clean, and what most DJs actually beatmatch with.
    "stretch" holds pitch through a phase vocoder, which smears transients and
    can read as dull or over-compressed.
    """
    if not np.isfinite(bpm_master) or bpm_master <= 0:
        raise ValueError("a positive outgoing BPM is required for a phrase-locked preview")
    if not np.isfinite(playback_rate_a) or playback_rate_a <= 0:
        raise ValueError("playback_rate_a must be positive")
    if not np.isfinite(playback_rate_b) or playback_rate_b <= 0:
        raise ValueError("playback_rate_b must be positive")
    if sample_rate < 8000:
        raise ValueError("sample_rate must be at least 8000 Hz")

    envelope = build_transition_envelope(
        profile_id,
        duration_beats=duration_beats,
        grid_beats=grid_beats,
        bass_open_at=bass_open_at,
    )
    duration_sec = duration_beats * 60.0 / float(bpm_master)
    output_samples = max(2, int(round(duration_sec * sample_rate)))
    outgoing = _read_at_playback_rate(
        source_a,
        sample_rate=sample_rate,
        start_sec=cue_a_sec,
        output_duration_sec=duration_sec,
        playback_rate=float(playback_rate_a),
        output_samples=output_samples,
        tempo_mode=tempo_mode,
    )

    incoming = _read_at_playback_rate(
        source_b,
        sample_rate=sample_rate,
        start_sec=cue_b_sec,
        output_duration_sec=duration_sec,
        playback_rate=float(playback_rate_b),
        output_samples=output_samples,
        tempo_mode=tempo_mode,
    )

    curves = sample_transition_envelope(envelope, output_samples)
    rendered_a = _apply_deck_curves(_split_three_bands(outgoing, sample_rate), curves,
                                    "a", envelope.low_independent)
    rendered_b = _apply_deck_curves(_split_three_bands(incoming, sample_rate), curves,
                                    "b", envelope.low_independent)
    mixed = np.asarray(rendered_a + rendered_b, dtype=np.float32)
    peak = float(np.max(np.abs(mixed), initial=0.0))
    normalization_gain = min(1.0, 0.98 / peak) if peak > 0 else 1.0
    mixed *= normalization_gain
    rendered_a *= normalization_gain
    rendered_b *= normalization_gain

    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("soundfile is required for transition preview rendering") from exc
    destination = Path(output_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    sf.write(
        temporary,
        mixed.T,
        sample_rate,
        format="WAV",
        subtype=PREVIEW_OUTPUT_SUBTYPE,
    )
    temporary.replace(destination)

    return TransitionRenderResult(
        output_path=destination,
        sample_rate=sample_rate,
        duration_sec=float(output_samples / sample_rate),
        cue_a_sec=float(cue_a_sec),
        cue_b_sec=float(cue_b_sec),
        preview_bpm=float(bpm_master),
        playback_rate_a=float(playback_rate_a),
        playback_rate_b=float(playback_rate_b),
        tempo_strategy=str(tempo_strategy),
        envelope=envelope,
        outgoing=_waveform_summary(rendered_a),
        mixed=_waveform_summary(mixed),
        incoming=_waveform_summary(rendered_b),
        peak_before_normalization=peak,
        normalization_gain=float(normalization_gain),
        channels=int(mixed.shape[0]),
        output_subtype=PREVIEW_OUTPUT_SUBTYPE,
        time_stretch_backend=(
            PREVIEW_TIME_STRETCH_BACKEND
            if not np.isclose(playback_rate_a, 1.0, rtol=0.0, atol=1e-5)
            or not np.isclose(playback_rate_b, 1.0, rtol=0.0, atol=1e-5)
            else "none"
        ),
    )

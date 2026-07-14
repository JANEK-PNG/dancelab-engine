"""Modern beat-synchronous CENS/MFCC extraction for DJ-mix validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.errors import MissingDependencyError
from dancelab.validation.djmix.models import BeatFeatureSequence


SUPPORTED_FEATURES = ("chroma", "mfcc")
NORMALIZATION_MODES = ("source_global", "per_dimension", "none")


@dataclass(frozen=True)
class CombinedFeatureMatrix:
    matrix: np.ndarray
    chroma_slice: slice | None


def _librosa():
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - only without the audio extra
        raise MissingDependencyError(
            "librosa is required for DJ-mix validation. "
            "Install: pip install 'dancelab-engine[audio]'"
        ) from exc
    return librosa


def _mono_samples(signal: AudioSignal) -> np.ndarray:
    samples = np.asarray(signal.samples, dtype=np.float32)
    if samples.ndim > 1:
        samples = samples.mean(axis=0)
    if samples.ndim != 1 or samples.size == 0:
        raise ValueError("audio signal must contain a non-empty mono/stereo sample array")
    return np.nan_to_num(samples, copy=False)


def _feature_intervals(
    beat_times_sec: Iterable[float],
    *,
    frame_count: int,
    sample_rate: int,
    hop_length: int,
) -> tuple[list[tuple[int, int]], tuple[float, ...]]:
    librosa = _librosa()
    times = np.asarray(tuple(beat_times_sec), dtype=np.float64)
    times = times[np.isfinite(times)]
    if times.size < 2:
        raise ValueError("at least two finite beat times are required")
    if np.any(np.diff(times) <= 0):
        raise ValueError("beat times must be strictly increasing")

    frames = librosa.time_to_frames(times, sr=sample_rate, hop_length=hop_length)
    intervals: list[tuple[int, int]] = []
    used_times: list[float] = []
    for index, (start_raw, end_raw) in enumerate(zip(frames, frames[1:], strict=False)):
        start = int(np.clip(start_raw, 0, frame_count))
        end = int(np.clip(end_raw, 0, frame_count))
        if end <= start:
            continue
        intervals.append((start, end))
        used_times.append(float(times[index]))
    if not intervals:
        raise ValueError("beat times do not span any feature frames")
    return intervals, tuple(used_times)


def _aggregate_block(block: np.ndarray, intervals: list[tuple[int, int]]) -> np.ndarray:
    columns = [block[:, start:end].mean(axis=1) for start, end in intervals]
    return np.asarray(columns, dtype=np.float32).T


def extract_beat_synchronous_features(
    signal: AudioSignal,
    beat_times_sec: Iterable[float],
    *,
    feature_names: Iterable[str] = SUPPORTED_FEATURES,
    hop_length: int = 512,
    n_mfcc: int = 12,
    beatgrid_reliable: bool | None = None,
    beatgrid_quality: float | None = None,
    warnings: Iterable[str] = (),
) -> BeatFeatureSequence:
    """Extract CENS chroma/MFCC and average each block between adjacent beats."""

    librosa = _librosa()
    names = tuple(dict.fromkeys(str(name).lower() for name in feature_names))
    unknown = sorted(set(names) - set(SUPPORTED_FEATURES))
    if not names or unknown:
        raise ValueError(f"feature_names must be drawn from {SUPPORTED_FEATURES}; unknown={unknown}")

    samples = _mono_samples(signal)
    raw_blocks: dict[str, np.ndarray] = {}
    if "chroma" in names:
        raw_blocks["chroma"] = librosa.feature.chroma_cens(
            y=samples,
            sr=signal.sample_rate,
            hop_length=hop_length,
        )
    if "mfcc" in names:
        raw_blocks["mfcc"] = librosa.feature.mfcc(
            y=samples,
            sr=signal.sample_rate,
            hop_length=hop_length,
            n_mfcc=n_mfcc,
        )

    frame_count = min(block.shape[1] for block in raw_blocks.values())
    intervals, used_times = _feature_intervals(
        beat_times_sec,
        frame_count=frame_count,
        sample_rate=signal.sample_rate,
        hop_length=hop_length,
    )
    blocks = {
        name: _aggregate_block(raw_blocks[name][:, :frame_count], intervals)
        for name in names
    }
    return BeatFeatureSequence(
        beat_times_sec=used_times,
        blocks=blocks,
        beatgrid_reliable=beatgrid_reliable,
        beatgrid_quality=beatgrid_quality,
        warnings=tuple(warnings),
    )


def _standardize(block: np.ndarray, mode: str) -> np.ndarray:
    values = np.asarray(block, dtype=np.float32)
    if not np.all(np.isfinite(values)):
        raise ValueError("feature blocks must contain only finite values")
    if mode == "none":
        return values.copy()
    if mode == "source_global":
        scale = float(values.std())
        if scale <= 1e-8:
            return np.zeros_like(values)
        return (values - float(values.mean())) / scale
    if mode == "per_dimension":
        mean = values.mean(axis=1, keepdims=True)
        scale = values.std(axis=1, keepdims=True)
        safe_scale = np.where(scale > 1e-8, scale, 1.0)
        standardized = (values - mean) / safe_scale
        standardized[scale[:, 0] <= 1e-8] = 0.0
        return standardized
    raise ValueError(f"normalization must be one of {NORMALIZATION_MODES}")


def combine_feature_blocks(
    sequence: BeatFeatureSequence,
    feature_names: Iterable[str] = SUPPORTED_FEATURES,
    *,
    normalization: str = "source_global",
) -> CombinedFeatureMatrix:
    """Stack selected normalized blocks and retain the chroma row location."""

    names = tuple(dict.fromkeys(str(name).lower() for name in feature_names))
    if normalization not in NORMALIZATION_MODES:
        raise ValueError(f"normalization must be one of {NORMALIZATION_MODES}")
    missing = [name for name in names if name not in sequence.blocks]
    if not names or missing:
        raise ValueError(f"feature blocks unavailable: {missing or names}")

    matrices: list[np.ndarray] = []
    chroma_slice: slice | None = None
    offset = 0
    beat_counts: set[int] = set()
    for name in names:
        matrix = _standardize(sequence.blocks[name], normalization)
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise ValueError(f"feature block '{name}' must be a non-empty 2D matrix")
        beat_counts.add(int(matrix.shape[1]))
        if name == "chroma":
            if matrix.shape[0] != 12:
                raise ValueError("CENS chroma block must have 12 pitch-class rows")
            chroma_slice = slice(offset, offset + 12)
        matrices.append(matrix)
        offset += int(matrix.shape[0])
    if len(beat_counts) != 1:
        raise ValueError("all feature blocks must have the same number of beats")

    return CombinedFeatureMatrix(
        matrix=np.concatenate(matrices, axis=0),
        chroma_slice=chroma_slice,
    )

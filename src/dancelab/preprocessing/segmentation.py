"""Structural segmentation → Segment entities. STATUS: candidate baseline.

Baseline: beat-synchronous feature novelty → agglomerative segmentation
(librosa.segment.agglomerative) over MFCC+chroma+RMS. Segment *type* labels
(intro/build/drop/breakdown/groove/outro) are a heuristic pass over each
segment's energy relative to the track — NOT validated (Validation Plan: segment
ratings pending). Boundaries are more trustworthy than labels.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.errors import MissingDependencyError
from dancelab.core.models import Segment, SegmentType


def segment_track(
    signal: AudioSignal,
    track_id: str,
    hop_size: int = 512,
    n_segments: int | None = None,
    min_len_sec: float = 8.0,
) -> list[Segment]:
    """Detect structural segments with heuristic type labels."""
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "librosa is required for segmentation. Install: pip install 'dancelab-engine[audio]'"
        ) from exc

    x = np.asarray(signal.samples, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0)
    sr = signal.sample_rate
    duration = len(x) / sr
    if duration < 2 * min_len_sec:
        return [Segment(segment_id=f"{track_id}_seg0", track_id=track_id,
                        start_sec=0.0, end_sec=round(duration, 3),
                        segment_type=SegmentType.unknown)]

    # stacked, normalized feature matrix for structural similarity
    mfcc = librosa.feature.mfcc(y=x, sr=sr, hop_length=hop_size, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=x, sr=sr, hop_length=hop_size)
    rms = librosa.feature.rms(y=x, hop_length=hop_size)
    feats = np.vstack([
        librosa.util.normalize(mfcc, axis=1),
        librosa.util.normalize(chroma, axis=1),
        librosa.util.normalize(rms, axis=1),
    ])

    if n_segments is None:
        n_segments = int(np.clip(duration / 30.0, 3, 10))  # ~1 segment / 30 s
    bounds = librosa.segment.agglomerative(feats, n_segments)
    bound_times = librosa.frames_to_time(bounds, sr=sr, hop_length=hop_size)
    edges = np.unique(np.concatenate([[0.0], bound_times, [duration]]))

    # energy per segment → heuristic labels relative to track
    seg_rms = librosa.util.normalize(rms.flatten(), norm=np.inf)
    seg_times = librosa.frames_to_time(np.arange(len(seg_rms)), sr=sr, hop_length=hop_size)

    segments: list[Segment] = []
    for i in range(len(edges) - 1):
        start, end = float(edges[i]), float(edges[i + 1])
        if end - start < min_len_sec and segments:  # merge tiny tail into previous
            update = {"end_sec": round(end, 3)}
            # AUD-L1: a merged final segment now ends the track, so the previous
            # segment inherits the outro label instead of the track losing it.
            if i == len(edges) - 2:
                update["segment_type"] = SegmentType.outro
            segments[-1] = segments[-1].model_copy(update=update)
            continue
        mask = (seg_times >= start) & (seg_times < end)
        energy = float(seg_rms[mask].mean()) if mask.any() else 0.0
        segments.append(Segment(
            segment_id=f"{track_id}_seg{len(segments)}",
            track_id=track_id, start_sec=round(start, 3), end_sec=round(end, 3),
            segment_type=_label_segment(i, len(edges) - 1, energy),
        ))
    return segments


def _label_segment(index: int, total: int, energy: float) -> SegmentType:
    """Heuristic (position + relative energy). Boundaries reliable, labels not."""
    if index == 0:
        return SegmentType.intro
    if index == total - 1:
        return SegmentType.outro
    if energy < 0.35:
        return SegmentType.breakdown
    if energy > 0.75:
        return SegmentType.drop
    return SegmentType.groove

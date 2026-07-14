"""Key-invariant mix-to-track subsequence DTW alignment."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from dancelab.core.errors import MissingDependencyError
from dancelab.validation.djmix.features import combine_feature_blocks
from dancelab.validation.djmix.models import AlignmentResult, BeatFeatureSequence


def _librosa():
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - only without the audio extra
        raise MissingDependencyError(
            "librosa is required for DJ-mix validation. "
            "Install: pip install 'dancelab-engine[audio]'"
        ) from exc
    return librosa


def _forward_path(path: np.ndarray) -> np.ndarray:
    points = np.asarray(path, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] == 0:
        raise ValueError("warping path must be a non-empty array of (track, mix) points")
    # librosa returns a backtracked path from the endpoint to the origin.
    if tuple(points[0]) > tuple(points[-1]):
        points = points[::-1]
    deltas = np.diff(points, axis=0)
    if np.any(deltas < 0):
        raise ValueError("warping path must be monotonic after orientation normalization")
    return points


def diagonal_match_rate(path: Iterable[tuple[int, int]] | np.ndarray) -> float:
    """Ratio of exact ``(1, 1)`` steps in a forward DTW path."""

    points = _forward_path(np.asarray(tuple(path) if not isinstance(path, np.ndarray) else path))
    if points.shape[0] < 2:
        return 0.0
    steps = np.diff(points, axis=0)
    diagonal = np.all(steps == np.array([1, 1]), axis=1)
    return float(diagonal.mean())


def align_feature_sequences(
    track: BeatFeatureSequence,
    mix: BeatFeatureSequence,
    *,
    feature_names: Iterable[str] = ("chroma", "mfcc"),
    key_invariant: bool = True,
    normalization: str = "source_global",
    metric: str = "euclidean",
    match_threshold: float = 0.4,
) -> AlignmentResult:
    """Align a whole track to the best subsequence of a DJ mix.

    The implementation preserves the public ISMIR demonstration's core method
    while adding explicit path orientation, finite-value checks, deterministic
    ties, and zero-length guards.
    """

    if not 0.0 <= match_threshold <= 1.0:
        raise ValueError("match_threshold must be between 0 and 1")
    names = tuple(dict.fromkeys(str(name).lower() for name in feature_names))
    track_combined = combine_feature_blocks(track, names, normalization=normalization)
    mix_combined = combine_feature_blocks(mix, names, normalization=normalization)
    if track_combined.matrix.shape[0] != mix_combined.matrix.shape[0]:
        raise ValueError("track and mix feature dimensions must match")
    if key_invariant and track_combined.chroma_slice is None:
        raise ValueError("key-invariant alignment requires the chroma feature block")

    librosa = _librosa()
    shifts = range(12) if key_invariant else (0,)
    candidates: list[tuple[float, int, np.ndarray]] = []
    shift_costs: list[float] = []
    for shift in shifts:
        track_matrix = track_combined.matrix.copy()
        if shift and track_combined.chroma_slice is not None:
            chroma_rows = track_combined.chroma_slice
            track_matrix[chroma_rows] = np.roll(
                track_matrix[chroma_rows],
                shift,
                axis=0,
            )

        accumulated_cost, raw_path = librosa.sequence.dtw(
            X=track_matrix,
            Y=mix_combined.matrix,
            metric=metric,
            subseq=True,
            backtrack=True,
        )
        path = _forward_path(raw_path)
        endpoint = int(path[-1, 1])
        total_cost = float(accumulated_cost[-1, endpoint])
        normalized_cost = total_cost / max(path.shape[0], 1)
        if not np.isfinite(normalized_cost):
            normalized_cost = float("inf")
        shift_costs.append(normalized_cost)
        candidates.append((normalized_cost, int(shift), path))

    # Stable ordering ensures a lower semitone shift wins an exact cost tie.
    best_cost, best_shift, best_path = min(candidates, key=lambda item: (item[0], item[1]))
    match_rate = diagonal_match_rate(best_path)
    return AlignmentResult(
        feature_names=names,
        normalization=normalization,
        key_invariant=key_invariant,
        key_shift_semitones=best_shift,
        normalized_cost=round(float(best_cost), 8),
        shift_costs=tuple(round(float(cost), 8) for cost in shift_costs),
        match_rate=round(match_rate, 8),
        match_threshold=float(match_threshold),
        matched=match_rate >= match_threshold,
        path=tuple((int(track_i), int(mix_i)) for track_i, mix_i in best_path),
    )

"""Cue evidence extracted from diagonal runs in a DTW warping path."""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

from dancelab.validation.djmix.models import CueCandidate


DEFAULT_CUE_TIERS = (32, 16, 8)


def _forward_points(path: Iterable[tuple[int, int]] | np.ndarray) -> np.ndarray:
    points = np.asarray(tuple(path) if not isinstance(path, np.ndarray) else path, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] == 0:
        raise ValueError("path must contain (track_beat, mix_beat) points")
    if tuple(points[0]) > tuple(points[-1]):
        points = points[::-1]
    if np.any(np.diff(points, axis=0) < 0):
        raise ValueError("path must be monotonic")
    return points


def _diagonal_runs(points: np.ndarray) -> list[tuple[int, int, int]]:
    """Return ``(start_point, end_point, diagonal_step_count)`` runs."""

    if points.shape[0] < 2:
        return []
    steps = np.diff(points, axis=0)
    diagonal = np.all(steps == np.array([1, 1]), axis=1)
    runs: list[tuple[int, int, int]] = []
    start: int | None = None
    for index, is_diagonal in enumerate(diagonal):
        if is_diagonal and start is None:
            start = index
        at_end = index == len(diagonal) - 1
        if start is not None and (not is_diagonal or at_end):
            final_step = index if is_diagonal and at_end else index - 1
            end_point = final_step + 1
            runs.append((start, end_point, final_step - start + 1))
            start = None
    return runs


def _time_at(times: Sequence[float] | None, index: int) -> float | None:
    if times is None:
        return None
    if index < 0 or index >= len(times):
        return None
    value = float(times[index])
    return value if np.isfinite(value) else None


def extract_cue_candidates(
    path: Iterable[tuple[int, int]] | np.ndarray,
    *,
    mix_beat_times_sec: Sequence[float] | None = None,
    track_beat_times_sec: Sequence[float] | None = None,
    tiers: Iterable[int] = DEFAULT_CUE_TIERS,
) -> tuple[CueCandidate, ...]:
    """Return explicit 32/16/8-beat cue tiers without recursive fallthrough.

    Cue-in uses the first qualifying stable diagonal run. Cue-out uses the end
    of the last qualifying run. A tier with no qualifying run is omitted.
    """

    points = _forward_points(path)
    runs = _diagonal_runs(points)
    normalized_tiers = tuple(dict.fromkeys(int(value) for value in tiers))
    if any(value <= 0 for value in normalized_tiers):
        raise ValueError("cue tiers must be positive beat counts")

    candidates: list[CueCandidate] = []
    for tier in normalized_tiers:
        qualifying = [run for run in runs if run[2] >= tier]
        if not qualifying:
            continue
        entry_run = qualifying[0]
        exit_run = qualifying[-1]
        entry_point = points[entry_run[0]]
        exit_point = points[exit_run[1]]
        track_in, mix_in = (int(entry_point[0]), int(entry_point[1]))
        track_out, mix_out = (int(exit_point[0]), int(exit_point[1]))
        candidates.append(CueCandidate(
            tier_beats=tier,
            mix_cue_in_beat=mix_in,
            mix_cue_out_beat=mix_out,
            track_cue_in_beat=track_in,
            track_cue_out_beat=track_out,
            mix_cue_in_sec=_time_at(mix_beat_times_sec, mix_in),
            mix_cue_out_sec=_time_at(mix_beat_times_sec, mix_out),
            track_cue_in_sec=_time_at(track_beat_times_sec, track_in),
            track_cue_out_sec=_time_at(track_beat_times_sec, track_out),
            cue_in_run_beats=entry_run[2],
            cue_out_run_beats=exit_run[2],
        ))
    return tuple(candidates)

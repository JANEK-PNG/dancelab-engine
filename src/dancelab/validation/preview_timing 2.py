"""Headless preview timing helpers used by validation and desktop hosts."""

from __future__ import annotations

import numpy as np

GRID_QUANTIZE_BEATS = 8
PREVIEW_LEAD_BEATS = 16


def snap_to_grid(
    t_sec: float,
    beat_times: list[float] | None,
    downbeats: list[float] | None = None,
    *,
    bars: bool = False,
    grid_beats: int = GRID_QUANTIZE_BEATS,
) -> float:
    """Snap a position to an N-beat grid boundary, defaulting to 8 beats."""
    if not beat_times:
        return t_sec
    beats = np.asarray(beat_times, dtype=np.float64)
    if beats.size == 0:
        return t_sec
    step = max(1, int(grid_beats))
    if bars:
        step = max(step, 4)
    if step <= 1:
        return float(beats[int(np.argmin(np.abs(beats - t_sec)))])

    anchor = float((downbeats or beat_times)[0])
    anchor_idx = int(np.argmin(np.abs(beats - anchor)))
    candidate_indexes = _grid_candidate_indexes(anchor_idx, step, len(beats))
    if candidate_indexes.size == 0:
        return float(beats[int(np.argmin(np.abs(beats - t_sec)))])
    candidates = beats[candidate_indexes]
    return float(candidates[int(np.argmin(np.abs(candidates - t_sec)))])


def quantized_cue_and_start(
    cue_sec: float,
    beat_times: list[float] | None,
    downbeats: list[float] | None = None,
    *,
    lead_beats: int = PREVIEW_LEAD_BEATS,
    grid_beats: int = GRID_QUANTIZE_BEATS,
) -> tuple[float, float, int]:
    """Return ``(cue_sec, preview_start_sec, actual_lead_beats)``."""
    if not beat_times:
        cue = max(float(cue_sec), 0.0)
        return cue, cue, 0
    beats = np.asarray(beat_times, dtype=np.float64)
    if beats.size == 0:
        cue = max(float(cue_sec), 0.0)
        return cue, cue, 0

    cue = snap_to_grid(
        max(float(cue_sec), 0.0),
        beat_times,
        downbeats,
        grid_beats=grid_beats,
    )
    cue_idx = int(np.argmin(np.abs(beats - cue)))
    anchor = float((downbeats or beat_times)[0])
    anchor_idx = int(np.argmin(np.abs(beats - anchor)))
    available = max(0, cue_idx - anchor_idx)
    step = max(1, int(grid_beats))
    actual_lead = min(max(0, int(lead_beats)), available)
    if step > 1:
        actual_lead = (actual_lead // step) * step
    start_idx = max(0, cue_idx - actual_lead)
    return float(beats[cue_idx]), float(beats[start_idx]), actual_lead


def _grid_candidate_indexes(anchor_idx: int, step: int, length: int) -> np.ndarray:
    indexes: list[int] = []
    current = anchor_idx
    while current >= 0:
        indexes.append(current)
        current -= step
    current = anchor_idx + step
    while current < length:
        indexes.append(current)
        current += step
    return np.asarray(sorted(set(indexes)), dtype=np.int64)

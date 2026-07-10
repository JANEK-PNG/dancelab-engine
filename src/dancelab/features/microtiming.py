"""Microtiming (spec §4). Status: candidate (Phase 2 heuristic coverage).

δ_i = t_i − t̂_i  (onset time vs predicted beat position)
M_micro = Var(δ_i)  or  MAD(δ_i)

Interpretation is style-conditioned later (context layer). This module also
provides a candidate syncopation proxy from beat-vs-offbeat onset distances.
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-9


def _beat_period(beat_times_sec: np.ndarray) -> float | None:
    beats = np.asarray(beat_times_sec, dtype=np.float64)
    if beats.size < 2:
        return None
    diffs = np.diff(beats)
    diffs = diffs[diffs > _EPS]
    if diffs.size == 0:
        return None
    return float(np.median(diffs))


def _nearest_distances(values: np.ndarray, anchors: np.ndarray) -> np.ndarray:
    if values.size == 0 or anchors.size == 0:
        return np.array([], dtype=np.float64)
    idx = np.searchsorted(anchors, values)
    prev_idx = np.clip(idx - 1, 0, len(anchors) - 1)
    next_idx = np.clip(idx, 0, len(anchors) - 1)
    prev_dist = np.abs(values - anchors[prev_idx])
    next_dist = np.abs(values - anchors[next_idx])
    return np.minimum(prev_dist, next_dist)


def _matched_deviations(
    onset_times_sec: np.ndarray,
    beat_times_sec: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float | None]:
    onsets = np.asarray(onset_times_sec, dtype=np.float64)
    beats = np.asarray(beat_times_sec, dtype=np.float64)
    beat_period = _beat_period(beats)
    if onsets.size == 0 or beats.size == 0 or beat_period is None:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64), beat_period

    idx = np.searchsorted(beats, onsets)
    prev_idx = np.clip(idx - 1, 0, len(beats) - 1)
    next_idx = np.clip(idx, 0, len(beats) - 1)
    prev_dist = np.abs(onsets - beats[prev_idx])
    next_dist = np.abs(onsets - beats[next_idx])
    use_next = next_dist < prev_dist
    nearest = beats[prev_idx]
    nearest[use_next] = beats[next_idx[use_next]]
    deviations = onsets - nearest

    # Syncopated off-beat onsets are not microtiming noise; keep only near-beat
    # events for the deviation proxy. AUD-H2: nearest-beat distance is ALWAYS
    # ≤ 0.5·beat_period by construction, so the old 0.5 tolerance admitted
    # everything (exact off-beats included) and saturated the proxy on
    # syncopated material. 0.15·beat_period keeps push/drag around the beat
    # (real microtiming) while excluding off-beat hits.
    tolerance = 0.15 * beat_period + _EPS
    mask = np.abs(deviations) <= tolerance
    return onsets[mask], deviations[mask], beat_period


def microtiming_deviations(onset_times_sec: np.ndarray, beat_times_sec: np.ndarray) -> np.ndarray:
    """δ_i per matched onset/beat pair."""
    _, deviations, _ = _matched_deviations(onset_times_sec, beat_times_sec)
    return deviations


def microtiming_proxy(deviations: np.ndarray, method: str = "mad") -> float:
    """Var or MAD of deviations."""
    delta = np.asarray(deviations, dtype=np.float64)
    if delta.size == 0:
        return 0.0
    if method == "mad":
        return float(np.median(np.abs(delta - np.median(delta))))
    if method == "var":
        return float(np.var(delta))
    raise ValueError("method must be 'mad' or 'var'")


def microtiming_profile(
    onset_times_sec: np.ndarray,
    beat_times_sec: np.ndarray,
    query_times_sec: np.ndarray,
    *,
    window_sec: float = 1.0,
    method: str = "mad",
) -> np.ndarray:
    """Per-window microtiming amount normalized to [0,1]."""
    queries = np.asarray(query_times_sec, dtype=np.float64)
    matched_onsets, deviations, beat_period = _matched_deviations(onset_times_sec, beat_times_sec)
    if queries.size == 0:
        return np.array([], dtype=np.float64)
    if deviations.size == 0 or beat_period is None:
        return np.zeros_like(queries)

    tolerance = max(0.18 * beat_period, _EPS)
    global_value = np.clip(microtiming_proxy(deviations, method=method) / tolerance, 0.0, 1.0)
    profile = np.full_like(queries, global_value)
    for idx, query in enumerate(queries):
        mask = (matched_onsets >= query) & (matched_onsets < query + window_sec)
        if mask.any():
            value = microtiming_proxy(deviations[mask], method=method)
            profile[idx] = np.clip(value / tolerance, 0.0, 1.0)
    return profile


def syncopation_profile(
    onset_times_sec: np.ndarray,
    beat_times_sec: np.ndarray,
    query_times_sec: np.ndarray,
    *,
    window_sec: float = 1.0,
) -> np.ndarray:
    """Per-window off-beat emphasis score in [0,1]."""
    onsets = np.asarray(onset_times_sec, dtype=np.float64)
    beats = np.asarray(beat_times_sec, dtype=np.float64)
    queries = np.asarray(query_times_sec, dtype=np.float64)
    beat_period = _beat_period(beats)
    if queries.size == 0:
        return np.array([], dtype=np.float64)
    if onsets.size == 0 or beats.size < 2 or beat_period is None:
        return np.zeros_like(queries)

    offbeats = (beats[:-1] + beats[1:]) / 2.0
    beat_dist = _nearest_distances(onsets, beats)
    offbeat_dist = _nearest_distances(onsets, offbeats)
    half_beat = max(0.5 * beat_period, _EPS)
    onset_scores = np.clip((beat_dist - offbeat_dist) / half_beat, 0.0, 1.0)

    profile = np.zeros_like(queries)
    for idx, query in enumerate(queries):
        mask = (onsets >= query) & (onsets < query + window_sec)
        if mask.any():
            profile[idx] = float(onset_scores[mask].mean())
    return profile

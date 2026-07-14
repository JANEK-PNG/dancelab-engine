"""Conservative sub-frame tempo refinement from an existing beat sequence."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

REFINEMENT_SPAN_BEATS = 32
REFINEMENT_MAX_ROBUST_CV = 0.01
REFINEMENT_MIN_SPANS = 8


def refine_bpm_from_beat_times(
    beat_times_sec: Sequence[float],
    raw_bpm: float,
    *,
    span_beats: int = REFINEMENT_SPAN_BEATS,
    min_spans: int = REFINEMENT_MIN_SPANS,
    max_robust_cv: float = REFINEMENT_MAX_ROBUST_CV,
    max_adjustment_fraction: float = 0.05,
) -> dict[str, Any]:
    """Estimate sub-frame tempo precision without changing metric level.

    Median elapsed time over 32-beat spans averages out frame quantization.
    A robust coefficient of variation gates expressive or unstable grids. The
    candidate is also bounded near the tracker's original metric level, so this
    helper cannot silently invent half-, double- or 3:2-time corrections.
    """
    beats = np.asarray(beat_times_sec, dtype=np.float64)
    beats = np.sort(beats[np.isfinite(beats)])
    if raw_bpm <= 0.0 or span_beats <= 0 or len(beats) < span_beats + min_spans:
        return {
            "accepted": False,
            "bpm": float(raw_bpm),
            "robust_cv": None,
            "span_count": 0,
            "reason": "insufficient_beat_spans",
        }

    periods = (beats[span_beats:] - beats[:-span_beats]) / span_beats
    periods = periods[np.isfinite(periods) & (periods > 0.0)]
    if len(periods) < min_spans:
        return {
            "accepted": False,
            "bpm": float(raw_bpm),
            "robust_cv": None,
            "span_count": int(len(periods)),
            "reason": "insufficient_beat_spans",
        }

    median_period = float(np.median(periods))
    mad = float(np.median(np.abs(periods - median_period)))
    robust_cv = 1.4826 * mad / median_period
    candidate = 60.0 / median_period
    adjustment_fraction = abs(candidate - raw_bpm) / raw_bpm
    if robust_cv > max_robust_cv:
        reason = "unstable_long_span_tempo"
    elif adjustment_fraction > max_adjustment_fraction:
        reason = "candidate_changes_metric_level"
    else:
        reason = "accepted"

    accepted = reason == "accepted"
    return {
        "accepted": accepted,
        "bpm": candidate if accepted else float(raw_bpm),
        "candidate_bpm": candidate,
        "robust_cv": robust_cv,
        "span_count": int(len(periods)),
        "adjustment_fraction": adjustment_fraction,
        "reason": reason,
    }

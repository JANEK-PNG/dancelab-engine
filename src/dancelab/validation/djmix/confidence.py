"""Transparent cue-evidence scoring for the offline M11 validator."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

import numpy as np

from dancelab.validation.djmix.models import (
    AlignmentResult,
    BeatFeatureSequence,
    BoundaryConfidence,
    CueCandidate,
)


# These equal weights are an explicit, untuned starting point. They must not be
# interpreted as learned probabilities or used by the production planner.
DEFAULT_CONFIDENCE_WEIGHTS = (
    ("cost_quality", 0.2),
    ("match_rate", 0.2),
    ("run_quality", 0.2),
    ("beatgrid_quality", 0.2),
    ("feature_coverage", 0.2),
)
REFERENCE_RUN_BEATS = 32


def _bounded(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _cost_quality(normalized_cost: float) -> float:
    """Map a non-negative DTW cost to a bounded diagnostic quality value."""

    if not np.isfinite(normalized_cost) or normalized_cost < 0.0:
        return 0.0
    return 1.0 / (1.0 + float(normalized_cost))


def _beatgrid_component(
    track: BeatFeatureSequence,
    mix: BeatFeatureSequence,
) -> tuple[float, bool, tuple[str, ...]]:
    values = (track.beatgrid_quality, mix.beatgrid_quality)
    if any(value is None or not np.isfinite(value) for value in values):
        return 0.0, False, ("missing_beatgrid_quality",)
    score = min(_bounded(float(value)) for value in values if value is not None)
    warnings: list[str] = []
    if track.beatgrid_reliable is False:
        warnings.append("track_beatgrid_unreliable")
    if mix.beatgrid_reliable is False:
        warnings.append("mix_beatgrid_unreliable")
    return score, True, tuple(warnings)


def assess_boundary_confidence(
    alignment: AlignmentResult,
    *,
    run_beats: int,
    track: BeatFeatureSequence,
    mix: BeatFeatureSequence,
    weights: tuple[tuple[str, float], ...] = DEFAULT_CONFIDENCE_WEIGHTS,
) -> BoundaryConfidence:
    """Combine visible M11 evidence without pretending it is calibrated truth."""

    if run_beats <= 0:
        raise ValueError("run_beats must be positive")
    weight_map = dict(weights)
    expected = {name for name, _ in DEFAULT_CONFIDENCE_WEIGHTS}
    if set(weight_map) != expected:
        raise ValueError(f"weights must define exactly {sorted(expected)}")
    if any(not np.isfinite(value) or value < 0.0 for value in weight_map.values()):
        raise ValueError("confidence weights must be finite and non-negative")
    weight_total = float(sum(weight_map.values()))
    if not np.isclose(weight_total, 1.0, atol=1e-9):
        raise ValueError("confidence weights must sum to 1.0")

    beatgrid_quality, beatgrid_complete, beatgrid_warnings = _beatgrid_component(track, mix)
    components = (
        ("cost_quality", _bounded(_cost_quality(alignment.normalized_cost))),
        ("match_rate", _bounded(alignment.match_rate)),
        ("run_quality", _bounded(run_beats / REFERENCE_RUN_BEATS)),
        ("beatgrid_quality", beatgrid_quality),
        ("feature_coverage", _bounded(alignment.feature_coverage)),
    )
    score = sum(value * weight_map[name] for name, value in components)
    warnings = list(beatgrid_warnings)
    if not alignment.matched:
        warnings.append("alignment_below_match_threshold")
    return BoundaryConfidence(
        score=round(_bounded(score), 8),
        components=tuple((name, round(value, 8)) for name, value in components),
        weights=tuple(weights),
        complete=beatgrid_complete,
        warnings=tuple(warnings),
    )


def score_cue_candidates(
    candidates: Iterable[CueCandidate],
    alignment: AlignmentResult,
    *,
    track: BeatFeatureSequence,
    mix: BeatFeatureSequence,
) -> tuple[CueCandidate, ...]:
    """Attach independent cue-in and cue-out evidence to extracted candidates."""

    scored: list[CueCandidate] = []
    for candidate in candidates:
        cue_in_run = candidate.cue_in_run_beats or candidate.tier_beats
        cue_out_run = candidate.cue_out_run_beats or candidate.tier_beats
        scored.append(replace(
            candidate,
            cue_in_confidence=assess_boundary_confidence(
                alignment,
                run_beats=cue_in_run,
                track=track,
                mix=mix,
            ),
            cue_out_confidence=assess_boundary_confidence(
                alignment,
                run_beats=cue_out_run,
                track=track,
                mix=mix,
            ),
        ))
    return tuple(scored)

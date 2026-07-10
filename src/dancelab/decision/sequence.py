"""Draft short-horizon sequence planning for Phase 3.

The first version chained only the top-1 `recommend_next` result greedily.
This version adds:

- short beam search over candidate branches
- explicit local arc scoring (step-to-step energy movement)
- explicit global arc scoring (prefix/full fit to a target energy profile)
- long-horizon lookahead scoring over remaining pool fit and terminal reachability
- bounded set-memory scoring over recent role/function and tension/release history

It is still a candidate planner, not a validated set-construction engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dancelab.core.config import DescriptorWeights, load_weights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    DecisionClass,
    EdgeDecision,
    ModelStatus,
    RecommendationPolicy,
    ScoredOutput,
    SetFunctionInput,
    SequenceDecision,
    SequenceStep,
    TransitionWindowInput,
)
from dancelab.core.provenance import guardrail_warnings, provenance_for
from dancelab.decision.edge_decision import build_edge_decision
from dancelab.decision.next_track import recommend_next
from dancelab.decision.rules import (
    best_effective_bpm,
    effective_bpm_delta_pct,
    energy_region,
    evaluate_recommendation_policy,
    evaluate_sequence_guardrails,
)
from dancelab.decision.set_function import classify_set_function
from dancelab.decision.set_builder import track_energy
from dancelab.decision.transition_windows import detect_transition_windows

MODEL_VERSION = "sequence_v0.1"
# AUD-M10: every weighted term resolves to a formula_terms.yaml entry (no
# anonymous variables). Test-enforced by test_every_sequence_component_has_a_term.
COMPONENTS = (
    "pair_score",
    "local_arc",
    "global_arc",
    "lookahead_arc",
    "terminal_arc",
    "set_memory",
    "transition_quality",
    "risk_penalty",
)
_DEFAULT_SEQUENCE_WEIGHTS = {
    "pair_score": 0.45,
    "local_arc": 0.20,
    "global_arc": 0.25,
    "transition_quality": 0.10,
    "risk_penalty": 0.15,
    "lookahead_arc": 0.10,
    "terminal_arc": 0.06,
    "set_memory": 0.08,
}
_BEAM_WIDTH = 5
_BRANCH_FACTOR = 4
_MAX_HISTORY_WINDOW = 8
_ROLE_STAGE = {
    "closer": 0.0,
    "opener": 0.2,
    "reset": 0.6,
    "builder": 1.2,
    "tool": 1.3,
    "bridge": 1.6,
    "peak": 2.6,
    "unknown": 1.2,
}


@dataclass
class _SequenceBranch:
    current: AnalysisResult
    remaining: list[AnalysisResult]
    history: list[AnalysisResult] = field(default_factory=list)
    sequence_track_ids: list[str] = field(default_factory=list)
    energies: list[float] = field(default_factory=list)
    steps: list[SequenceStep] = field(default_factory=list)
    step_scores: list[float] = field(default_factory=list)
    local_scores: list[float] = field(default_factory=list)
    global_scores: list[float] = field(default_factory=list)
    lookahead_scores: list[float] = field(default_factory=list)
    terminal_scores: list[float] = field(default_factory=list)
    set_memory_scores: list[float] = field(default_factory=list)
    bpms: list[float | None] = field(default_factory=list)
    effective_bpms: list[float | None] = field(default_factory=list)
    energy_regions: list[str] = field(default_factory=list)
    cumulative_risks: list[float] = field(default_factory=list)
    bpm_drift_spans: list[float] = field(default_factory=list)
    guardrail_flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def beam_value(self, horizon: int) -> float:
        if not self.step_scores:
            return 0.0
        mean_score = float(np.mean(self.step_scores))
        completion_bonus = 0.04 * (len(self.step_scores) / max(horizon, 1))
        lookahead_bonus = 0.08 * (
            float(np.mean(self.lookahead_scores[-2:])) if self.lookahead_scores else 0.5
        )
        terminal_bonus = 0.06 * (self.terminal_scores[-1] if self.terminal_scores else 0.5)
        return mean_score + completion_bonus + lookahead_bonus + terminal_bonus


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _sequence_weights(weights: DescriptorWeights) -> dict[str, float]:
    if weights.sequence is None:
        return dict(_DEFAULT_SEQUENCE_WEIGHTS)
    merged = dict(_DEFAULT_SEQUENCE_WEIGHTS)
    merged.update(weights.sequence.weights)
    return merged


def _mean_feature(analysis: AnalysisResult, name: str) -> float | None:
    values = [getattr(frame, name) for frame in analysis.features]
    values = [float(value) for value in values if value is not None]
    return float(np.mean(values)) if values else None


def _weighted_mean(values: list[float]) -> float | None:
    if not values:
        return None
    arr = np.asarray(values, dtype=np.float64)
    weights = np.linspace(1.0, 2.0, len(arr), dtype=np.float64)
    return float(np.average(arr, weights=weights))


def _series_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=np.float64)
    return float(np.polyfit(x, np.asarray(values, dtype=np.float64), 1)[0])


def _transition_windows(
    analysis: AnalysisResult,
    weights: DescriptorWeights,
    top_k: int,
):
    return detect_transition_windows(
        TransitionWindowInput(
            track_id=analysis.track.track_id,
            segments=analysis.segments,
            feature_frames=analysis.features,
            beatgrid=analysis.beatgrid,
        ),
        weights.transition_window,
        top_k=top_k,
    ).windows


def _role_stage(role_name: str | None) -> float:
    return _ROLE_STAGE.get((role_name or "unknown").lower(), _ROLE_STAGE["unknown"])


def _classify_set_function_label(
    analysis: AnalysisResult,
    context: ContextProfile | None,
    weights: DescriptorWeights,
    role_cache: dict[str, str],
    *,
    top_k: int = 3,
) -> str:
    track_id = analysis.track.track_id
    cached = role_cache.get(track_id)
    if cached is not None:
        return cached
    windows = _transition_windows(analysis, weights, top_k=top_k)
    label = classify_set_function(
        SetFunctionInput(
            track_analysis=analysis,
            context=context,
            transition_windows=windows,
        )
    ).primary_function.value
    role_cache[track_id] = label
    return label


def _history_function_summary(
    current: AnalysisResult,
    recent_history: list[AnalysisResult],
    context: ContextProfile | None,
    weights: DescriptorWeights,
    role_cache: dict[str, str],
) -> dict[str, float | str] | None:
    analyses = recent_history[-5:] + [current]
    if not analyses:
        return None

    labels: list[str] = []
    stages: list[float] = []
    for analysis in analyses:
        label = _classify_set_function_label(
            analysis,
            context,
            weights,
            role_cache,
        )
        labels.append(label)
        stages.append(_role_stage(label))

    return {
        "mean": _weighted_mean(stages) or stages[-1],
        "last": stages[-1],
        "last_label": labels[-1],
        "repeat_count": sum(1 for label in labels[-3:] if label == labels[-1]),
    }


def _history_function_progression_score(
    candidate: AnalysisResult,
    function_summary: dict[str, float | str] | None,
    context: ContextProfile | None,
    arc_mode: str,
    weights: DescriptorWeights,
    role_cache: dict[str, str],
) -> tuple[float, str]:
    if function_summary is None:
        return 0.5, "role memory unavailable — neutral"

    candidate_role = _classify_set_function_label(
        candidate,
        context,
        weights,
        role_cache,
    )
    candidate_stage = _role_stage(candidate_role)
    target_stage = float(function_summary["last"]) + {
        "build": 0.55,
        "flat": 0.00,
        "peak": 0.95,
        "closing": -0.85,
    }.get((arc_mode or "build").lower(), 0.20)
    target_stage = 0.60 * target_stage + 0.40 * float(function_summary["mean"])
    if context and context.set_role:
        target_stage = 0.55 * target_stage + 0.45 * _role_stage(context.set_role)

    score = float(np.clip(1.0 - abs(candidate_stage - target_stage) / 2.8, 0.0, 1.0))
    if (
        int(function_summary["repeat_count"]) >= 2
        and str(function_summary["last_label"]) == candidate_role
        and (arc_mode or "build").lower() != "flat"
    ):
        score = float(np.clip(score - 0.10, 0.0, 1.0))

    return score, (
        f"role memory target stage {target_stage:.2f} "
        f"(candidate role={candidate_role}, stage={candidate_stage:.2f})"
    )


def _history_tension_release_summary(
    current: AnalysisResult,
    recent_history: list[AnalysisResult],
) -> dict[str, float | None] | None:
    analyses = recent_history[-6:] + [current]
    tension_values = [
        value
        for value in (_mean_feature(analysis, "tension_proxy") for analysis in analyses)
        if value is not None
    ]
    release_values = [
        value
        for value in (_mean_feature(analysis, "release_proxy") for analysis in analyses)
        if value is not None
    ]
    if not tension_values and not release_values:
        return None

    return {
        "tension_last": tension_values[-1] if tension_values else None,
        "tension_mean": _weighted_mean(tension_values) if tension_values else None,
        "tension_slope": _series_slope(tension_values) if tension_values else None,
        "release_last": release_values[-1] if release_values else None,
        "release_mean": _weighted_mean(release_values) if release_values else None,
        "release_slope": _series_slope(release_values) if release_values else None,
    }


def _history_tension_release_score(
    candidate: AnalysisResult,
    summary: dict[str, float | None] | None,
    arc_mode: str,
) -> tuple[float, str]:
    if summary is None:
        return 0.5, "tension/release memory unavailable — neutral"

    candidate_tension = _mean_feature(candidate, "tension_proxy")
    candidate_release = _mean_feature(candidate, "release_proxy")
    mode = (arc_mode or "build").lower()
    tension_bias = {
        "build": 0.05,
        "flat": 0.00,
        "peak": 0.08,
        "closing": -0.07,
    }.get(mode, 0.02)
    release_bias = {
        "build": -0.02,
        "flat": 0.00,
        "peak": -0.01,
        "closing": 0.06,
    }.get(mode, 0.00)

    weighted_scores: list[tuple[float, float]] = []
    reason_parts: list[str] = []

    tension_last = summary.get("tension_last")
    tension_mean = summary.get("tension_mean")
    tension_slope = summary.get("tension_slope")
    if tension_last is not None and tension_mean is not None and candidate_tension is not None:
        predicted = float(np.clip(tension_last + tension_bias + 0.35 * (tension_slope or 0.0), 0.0, 1.0))
        anchor = float(np.clip(tension_mean + 0.70 * tension_bias, 0.0, 1.0))
        predicted_fit = float(np.clip(1.0 - abs(candidate_tension - predicted) / 0.24, 0.0, 1.0))
        anchor_fit = float(np.clip(1.0 - abs(candidate_tension - anchor) / 0.26, 0.0, 1.0))
        tension_score = float(np.clip(0.65 * predicted_fit + 0.35 * anchor_fit, 0.0, 1.0))
        weighted_scores.append((0.60, tension_score))
        reason_parts.append(
            f"tension {candidate_tension:.2f} vs target {predicted:.2f}"
        )

    release_last = summary.get("release_last")
    release_mean = summary.get("release_mean")
    release_slope = summary.get("release_slope")
    if release_last is not None and release_mean is not None and candidate_release is not None:
        predicted = float(np.clip(release_last + release_bias + 0.25 * (release_slope or 0.0), 0.0, 1.0))
        anchor = float(np.clip(release_mean + 0.70 * release_bias, 0.0, 1.0))
        predicted_fit = float(np.clip(1.0 - abs(candidate_release - predicted) / 0.22, 0.0, 1.0))
        anchor_fit = float(np.clip(1.0 - abs(candidate_release - anchor) / 0.24, 0.0, 1.0))
        release_score = float(np.clip(0.65 * predicted_fit + 0.35 * anchor_fit, 0.0, 1.0))
        weighted_scores.append((0.40, release_score))
        reason_parts.append(
            f"release {candidate_release:.2f} vs target {predicted:.2f}"
        )

    if not weighted_scores:
        return 0.5, "tension/release memory unavailable — neutral"

    total_weight = sum(weight for weight, _ in weighted_scores)
    score = sum(weight * value for weight, value in weighted_scores) / total_weight
    return float(np.clip(score, 0.0, 1.0)), "; ".join(reason_parts)


def _set_memory_score(
    current: AnalysisResult,
    candidate: AnalysisResult,
    recent_history: list[AnalysisResult],
    context: ContextProfile | None,
    arc_mode: str,
    weights: DescriptorWeights,
    role_cache: dict[str, str],
) -> tuple[float, str]:
    function_summary = _history_function_summary(
        current,
        recent_history,
        context,
        weights,
        role_cache,
    )
    role_score, role_reason = _history_function_progression_score(
        candidate,
        function_summary,
        context,
        arc_mode,
        weights,
        role_cache,
    )
    tension_summary = _history_tension_release_summary(current, recent_history)
    tension_score, tension_reason = _history_tension_release_score(
        candidate,
        tension_summary,
        arc_mode,
    )

    weighted_scores: list[tuple[float, float]] = []
    if function_summary is not None:
        weighted_scores.append((0.55, role_score))
    if tension_summary is not None:
        weighted_scores.append((0.45, tension_score))
    if not weighted_scores:
        return 0.5, "set memory unavailable — neutral"

    total_weight = sum(weight for weight, _ in weighted_scores)
    score = sum(weight * value for weight, value in weighted_scores) / total_weight
    return float(np.clip(score, 0.0, 1.0)), (
        f"role {role_score:.2f}; tension {tension_score:.2f} "
        f"({role_reason}; {tension_reason})"
    )


def _profile_basis(
    current: AnalysisResult,
    candidates: list[AnalysisResult],
    recent_history: list[AnalysisResult],
    horizon: int,
    arc_mode: str,
) -> tuple[list[float], list[float], float, float]:
    history_energies = [track_energy(analysis) for analysis in recent_history]
    candidate_energies = [track_energy(analysis) for analysis in candidates]
    current_energy = track_energy(current)
    all_energies = history_energies + [current_energy] + candidate_energies
    e_min = float(min(all_energies)) if all_energies else 0.0
    e_max = float(max(all_energies)) if all_energies else 1.0
    e_range = e_max - e_min or 1.0

    def norm(value: float) -> float:
        return float(np.clip((value - e_min) / e_range, 0.0, 1.0))

    current_norm = norm(current_energy)
    history_norm = float(np.mean([norm(value) for value in history_energies])) if history_energies else current_norm
    pool = [norm(value) for value in candidate_energies] or [current_norm]
    p25, p50, p65, p80 = np.percentile(pool, [25, 50, 65, 80])
    mode = (arc_mode or "build").lower()

    if mode == "peak":
        peak = float(np.clip(max(0.88, p80, current_norm + 0.20), 0.0, 1.0))
        target_norm = []
        for index in range(max(horizon, 1) + 1):
            t = index / max(horizon, 1)
            rise = t ** 0.75
            value = current_norm + (peak - current_norm) * rise
            if horizon >= 3 and index == horizon:
                value = max(current_norm, peak - 0.03)
            target_norm.append(float(np.clip(value, 0.0, 1.0)))
    elif mode == "flat":
        end = float(np.clip(0.7 * current_norm + 0.3 * p50, current_norm - 0.06, current_norm + 0.06))
        target_norm = [
            float(np.clip(current_norm + (end - current_norm) * (index / max(horizon, 1)), 0.0, 1.0))
            for index in range(max(horizon, 1) + 1)
        ]
    elif mode == "closing":
        end = min(current_norm - 0.18, float(p25))
        end = float(np.clip(end, 0.05, max(current_norm - 0.05, 0.05)))
        target_norm = [
            float(np.clip(current_norm + (end - current_norm) * ((index / max(horizon, 1)) ** 0.9), 0.0, 1.0))
            for index in range(max(horizon, 1) + 1)
        ]
    else:
        end = max(current_norm + 0.22, float(p65))
        if current_norm < history_norm:
            end = max(end, current_norm + 0.28)
        end = float(np.clip(end, current_norm + 0.05, 0.95))
        target_norm = [
            float(np.clip(current_norm + (end - current_norm) * ((index / max(horizon, 1)) ** 1.15), 0.0, 1.0))
            for index in range(max(horizon, 1) + 1)
        ]

    target_energy = [round(e_min + value * e_range, 4) for value in target_norm]
    return target_energy, target_norm, e_min, e_range


def _global_arc_score(
    energies: list[float],
    target_profile_norm: list[float],
    e_min: float,
    e_range: float,
) -> float:
    if not energies:
        return 0.5
    actual_norm = [float(np.clip((value - e_min) / e_range, 0.0, 1.0)) for value in energies]
    target_prefix = target_profile_norm[:len(actual_norm)]
    mae = float(np.mean(np.abs(np.array(actual_norm) - np.array(target_prefix))))
    return float(np.clip(1.0 - mae / 0.25, 0.0, 1.0))


def _local_arc_score(
    energies: list[float],
    target_profile_norm: list[float],
    e_min: float,
    e_range: float,
) -> float:
    if len(energies) < 2:
        return 0.5
    actual_norm = [float(np.clip((value - e_min) / e_range, 0.0, 1.0)) for value in energies]
    idx = len(actual_norm) - 1
    actual_delta = actual_norm[idx] - actual_norm[idx - 1]
    target_delta = target_profile_norm[idx] - target_profile_norm[idx - 1]
    return float(np.clip(1.0 - abs(actual_delta - target_delta) / 0.18, 0.0, 1.0))


def _norm_energy(value: float, e_min: float, e_range: float) -> float:
    return float(np.clip((value - e_min) / e_range, 0.0, 1.0))


def _lookahead_arc_score(
    energies: list[float],
    remaining: list[AnalysisResult],
    target_profile_norm: list[float],
    e_min: float,
    e_range: float,
    arc_mode: str,
) -> tuple[float, float]:
    next_index = len(energies)
    future_targets = target_profile_norm[next_index:]
    if not future_targets:
        return 1.0, 1.0

    remaining_norms = [_norm_energy(track_energy(candidate), e_min, e_range) for candidate in remaining]
    if not remaining_norms:
        return 0.0, 0.0

    available = list(remaining_norms)
    assigned: list[float] = []
    for target in future_targets[:len(available)]:
        idx = min(range(len(available)), key=lambda i: abs(available[i] - target))
        assigned.append(available.pop(idx))
    coverage = len(assigned) / max(len(future_targets), 1)
    if not assigned:
        return 0.0, 0.0

    future_fit = float(
        np.clip(
            1.0 - float(np.mean(np.abs(np.array(assigned) - np.array(future_targets[:len(assigned)])))) / 0.25,
            0.0,
            1.0,
        )
    )
    terminal_target = future_targets[-1]
    terminal_fit = float(
        np.clip(1.0 - min(abs(value - terminal_target) for value in remaining_norms) / 0.22, 0.0, 1.0)
    )

    mode = (arc_mode or "build").lower()
    if mode in {"build", "peak"}:
        envelope_gap = max(terminal_target - max(remaining_norms), 0.0)
        envelope_fit = float(np.clip(1.0 - envelope_gap / 0.24, 0.0, 1.0))
    elif mode == "closing":
        envelope_gap = max(min(remaining_norms) - terminal_target, 0.0)
        envelope_fit = float(np.clip(1.0 - envelope_gap / 0.24, 0.0, 1.0))
    else:
        envelope_fit = float(
            np.clip(1.0 - abs(float(np.mean(remaining_norms)) - float(np.mean(future_targets))) / 0.22, 0.0, 1.0)
        )

    score = float(np.clip(0.50 * future_fit + 0.25 * terminal_fit + 0.15 * envelope_fit + 0.10 * coverage, 0.0, 1.0))
    return score, terminal_fit


def _transition_quality_score(edge: EdgeDecision) -> float:
    class_score = {
        DecisionClass.strong_candidate: 1.0,
        DecisionClass.review_required: 0.72,
        DecisionClass.non_standard_strategy_required: 0.55,
        DecisionClass.reject_standard_blend: 0.25,
    }[edge.decision_class]
    return float(np.clip(0.6 * edge.core_dj_compatibility_score.value + 0.4 * class_score, 0.0, 1.0))


def _transition_risk_score(edge: EdgeDecision, risk_flags: list[str]) -> float:
    values = [
        {
            DecisionClass.strong_candidate: 0.10,
            DecisionClass.review_required: 0.35,
            DecisionClass.non_standard_strategy_required: 0.55,
            DecisionClass.reject_standard_blend: 0.85,
        }[edge.decision_class],
        min(len(risk_flags) / 6.0, 1.0),
    ]
    for value in (edge.harmonic_risk, edge.bass_conflict_risk, edge.vocal_clash_risk):
        if value is not None:
            values.append(value)
    return float(np.clip(np.mean(values), 0.0, 1.0))


def _step_total_score(
    pair_score: float,
    local_arc: float,
    global_arc: float,
    lookahead_arc: float,
    terminal_arc: float,
    set_memory: float,
    transition_quality: float,
    risk_score: float,
    weights: dict[str, float],
) -> float:
    # AUD-M6: the reward weights sum to >1 (1.24 at defaults), so an unnormalized
    # sum saturates past 1.0 and the final clip flattens every strong candidate to
    # a tie — the weighting stops discriminating exactly where it matters. Treat
    # the reward terms as a weighted AVERAGE (divide by their weight mass) so the
    # reward lands in [0,1] and relative weights are preserved; risk stays a
    # separate subtractive penalty, and the clip only guards its floor.
    reward_terms = (
        weights["pair_score"] * pair_score
        + weights["local_arc"] * local_arc
        + weights["global_arc"] * global_arc
        + weights["lookahead_arc"] * lookahead_arc
        + weights["terminal_arc"] * terminal_arc
        + weights["set_memory"] * set_memory
        + weights["transition_quality"] * transition_quality
    )
    reward_mass = (
        weights["pair_score"]
        + weights["local_arc"]
        + weights["global_arc"]
        + weights["lookahead_arc"]
        + weights["terminal_arc"]
        + weights["set_memory"]
        + weights["transition_quality"]
    )
    reward = reward_terms / reward_mass if reward_mass > 0 else 0.0
    raw = reward - weights["risk_penalty"] * risk_score
    return float(np.clip(raw, 0.0, 1.0))


def recommend_sequence(
    current: AnalysisResult,
    candidates: list[AnalysisResult],
    context: ContextProfile | None = None,
    *,
    weights: DescriptorWeights | None = None,
    recent_history: list[AnalysisResult] | None = None,
    arc_mode: str = "build",
    horizon: int = 3,
    top_k: int = 3,
) -> SequenceDecision:
    weights = weights or load_weights("configs/descriptor_weights.yaml")
    sequence_weights = _sequence_weights(weights)
    history = list(recent_history or [])
    history_ids = [track.track.track_id for track in history]
    beam_width = min(max(_BEAM_WIDTH, horizon + 1), 10)
    branch_factor = min(max(_BRANCH_FACTOR, horizon // 2 + 2), 6)
    history_window = min(max(6, horizon + 2), _MAX_HISTORY_WINDOW)

    remaining: list[AnalysisResult] = []
    seen: set[str] = {current.track.track_id}
    for candidate in candidates:
        track_id = candidate.track.track_id
        if track_id in seen or track_id in history_ids:
            continue
        remaining.append(candidate)
        seen.add(track_id)

    warnings: list[str] = []
    if horizon > len(remaining):
        warnings.append(
            f"requested horizon {horizon} exceeds available unique candidates ({len(remaining)})"
        )

    step_limit = min(max(horizon, 1), len(remaining))
    target_energy_profile, target_profile_norm, e_min, e_range = _profile_basis(
        current,
        remaining,
        history,
        step_limit,
        arc_mode,
    )
    role_cache: dict[str, str] = {}

    if horizon < 1 or not remaining:
        provenance = provenance_for("sequence")
        warnings += guardrail_warnings(
            has_context=context is not None,
            source_grounding=0.35,
            conflicting=False,
            risk_score=0.7,
        )
        return SequenceDecision(
            current_track_id=current.track.track_id,
            context_id=context.context_id if context else None,
            arc_mode=arc_mode,
            horizon=max(horizon, 1),
            recent_history_track_ids=history_ids,
            sequence_track_ids=[current.track.track_id],
            observed_energy_profile=[round(track_energy(current), 4)],
            target_energy_profile=target_energy_profile[:1],
            cumulative_risk_score=0.0,
            max_energy_region_streak=1,
            suppressed_transition_count=0,
            recommendation_policy=RecommendationPolicy.suppress,
            warnings=_dedupe(warnings + ["no candidate tracks available for sequence planning"]),
            provenance=provenance,
        )

    current_bpm = float(current.track.bpm_estimate) if current.track.bpm_estimate is not None else None
    current_energy = track_energy(current)
    current_region = energy_region(current_energy, e_min, e_range)
    beams = [
        _SequenceBranch(
            current=current,
            remaining=list(remaining),
            history=list(history),
            sequence_track_ids=[current.track.track_id],
            energies=[current_energy],
            bpms=[current_bpm],
            effective_bpms=[current_bpm],
            energy_regions=[current_region],
        )
    ]
    suppressed_transition_count = 0

    for step_index in range(1, step_limit + 1):
        expanded: list[_SequenceBranch] = []
        for branch in beams:
            recommendation = recommend_next(
                current=branch.current,
                candidates=branch.remaining,
                context=context,
                weights=weights,
                top_k=top_k,
                recent_history=branch.history,
                arc_mode=arc_mode,
            )
            if not recommendation.ranking:
                expanded.append(branch)
                continue

            ranking = recommendation.ranking[: min(branch_factor, len(recommendation.ranking))]
            remaining_by_id = {candidate.track.track_id: candidate for candidate in branch.remaining}
            for ranked in ranking:
                next_track = remaining_by_id[ranked.track_id]
                edge = build_edge_decision(
                    branch.current,
                    next_track,
                    weights,
                    context=context,
                    top_k=top_k,
                )
                next_energy = track_energy(next_track)
                energies = branch.energies + [next_energy]
                next_bpm = (
                    float(next_track.track.bpm_estimate)
                    if next_track.track.bpm_estimate is not None else None
                )
                previous_effective_bpm = branch.effective_bpms[-1] if branch.effective_bpms else None
                next_effective_bpm = best_effective_bpm(previous_effective_bpm, next_bpm)
                effective_bpms = branch.effective_bpms + [next_effective_bpm]
                energy_regions = branch.energy_regions + [energy_region(next_energy, e_min, e_range)]
                local_arc = _local_arc_score(energies, target_profile_norm, e_min, e_range)
                global_arc = _global_arc_score(energies, target_profile_norm, e_min, e_range)
                remaining_after_choice = [
                    candidate
                    for candidate in branch.remaining
                    if candidate.track.track_id != ranked.track_id
                ]
                lookahead_arc, terminal_arc = _lookahead_arc_score(
                    energies,
                    remaining_after_choice,
                    target_profile_norm,
                    e_min,
                    e_range,
                    arc_mode,
                )
                set_memory, set_memory_reason = _set_memory_score(
                    branch.current,
                    next_track,
                    branch.history,
                    context,
                    arc_mode,
                    weights,
                    role_cache,
                )
                transition_quality = _transition_quality_score(edge)
                combined_risks = _dedupe(ranked.risk_flags + edge.risks)
                risk_score = _transition_risk_score(edge, combined_risks)
                cumulative_risks = branch.cumulative_risks + [risk_score]
                guardrails = evaluate_sequence_guardrails(
                    cumulative_risks,
                    effective_bpms,
                    energy_regions,
                    arc_mode,
                )
                adjusted_score = _step_total_score(
                    ranked.score.value,
                    local_arc,
                    global_arc,
                    lookahead_arc,
                    terminal_arc,
                    set_memory,
                    transition_quality,
                    risk_score,
                    sequence_weights,
                )
                adjusted_score = float(np.clip(adjusted_score - float(guardrails.penalty), 0.0, 1.0))
                if guardrails.severe:
                    adjusted_score = min(adjusted_score, 0.18)
                step_policy = evaluate_recommendation_policy(
                    confidence=ranked.score.confidence,
                    risk_score=max(risk_score, min(guardrails.penalty * 2.0, 1.0)),
                    hard_block=(
                        bool(getattr(edge, "hard_block", False))
                        or ranked.recommendation_policy == RecommendationPolicy.suppress
                    ),
                    review_required=(
                        ranked.recommendation_policy != RecommendationPolicy.allow
                        or edge.decision_class != DecisionClass.strong_candidate
                        or bool(guardrails.flags)
                    ),
                    severe=False,
                    score_value=adjusted_score,
                    reasons=(
                        list(getattr(ranked, "policy_reasons", []))
                        + list(getattr(edge, "policy_reasons", []))
                        + (["sequence guardrails reached severe territory"] if guardrails.severe else [])
                        + list(guardrails.flags)
                    ),
                )
                if step_policy.recommendation_policy == RecommendationPolicy.suppress:
                    suppressed_transition_count += 1
                    continue
                if step_policy.recommendation_policy == RecommendationPolicy.review_only:
                    adjusted_score = float(np.clip(adjusted_score - 0.04, 0.0, 1.0))

                target_energy = target_energy_profile[min(step_index, len(target_energy_profile) - 1)]
                prev_target = target_energy_profile[min(step_index - 1, len(target_energy_profile) - 1)]
                step_explanation = (
                    f"pair {ranked.score.value:.2f}; local arc {local_arc:.2f}; "
                    f"global arc {global_arc:.2f}; lookahead {lookahead_arc:.2f}; "
                    f"terminal fit {terminal_arc:.2f}; set memory {set_memory:.2f}; "
                    f"transition quality {transition_quality:.2f}; "
                    f"risk {risk_score:.2f}; guardrail penalty {guardrails.penalty:.2f}; "
                    f"target energy {target_energy:.2f}; "
                    f"strategy {edge.recommended_transition_strategy.value}; "
                    f"{set_memory_reason}"
                )
                step = SequenceStep(
                    step_index=step_index,
                    from_track_id=branch.current.track.track_id,
                    to_track_id=ranked.track_id,
                    score=ScoredOutput(
                        value=round(adjusted_score, 4),
                        status=ModelStatus.candidate,
                        confidence=ranked.score.confidence,
                        explanation=step_explanation,
                    ),
                    recommended_transition_strategy=edge.recommended_transition_strategy,
                    decision_class=edge.decision_class,
                    pair_score=round(ranked.score.value, 4),
                    local_arc_score=round(local_arc, 4),
                    global_arc_score=round(global_arc, 4),
                    lookahead_arc_score=round(lookahead_arc, 4),
                    terminal_arc_score=round(terminal_arc, 4),
                    set_memory_score=round(set_memory, 4),
                    transition_quality_score=round(transition_quality, 4),
                    risk_score=round(risk_score, 4),
                    energy_value=round(next_energy, 4),
                    target_energy=round(target_energy, 4),
                    energy_delta=round(next_energy - branch.energies[-1], 4),
                    target_energy_delta=round(target_energy - prev_target, 4),
                    cumulative_risk_score=round(guardrails.cumulative_risk, 4),
                    effective_bpm_delta_pct=(
                        round(float(value), 3)
                        if (value := effective_bpm_delta_pct(previous_effective_bpm, next_effective_bpm)) is not None
                        else None
                    ),
                    energy_region=energy_regions[-1],
                    energy_region_streak=int(guardrails.current_streak),
                    guardrail_flags=list(guardrails.flags),
                    risk_flags=combined_risks,
                    recommendation_policy=step_policy.recommendation_policy,
                    policy_reasons=list(step_policy.reasons),
                )
                expanded.append(
                    _SequenceBranch(
                        current=next_track,
                        remaining=remaining_after_choice,
                        history=(branch.history + [branch.current])[-history_window:],
                        sequence_track_ids=branch.sequence_track_ids + [ranked.track_id],
                        energies=energies,
                        steps=branch.steps + [step],
                        step_scores=branch.step_scores + [adjusted_score],
                        local_scores=branch.local_scores + [local_arc],
                        global_scores=branch.global_scores + [global_arc],
                        lookahead_scores=branch.lookahead_scores + [lookahead_arc],
                        terminal_scores=branch.terminal_scores + [terminal_arc],
                        set_memory_scores=branch.set_memory_scores + [set_memory],
                        bpms=branch.bpms + [next_bpm],
                        effective_bpms=effective_bpms,
                        energy_regions=energy_regions,
                        cumulative_risks=cumulative_risks,
                        bpm_drift_spans=branch.bpm_drift_spans + (
                            [float(guardrails.bpm_span_pct)] if guardrails.bpm_span_pct is not None else []
                        ),
                        guardrail_flags=_dedupe(branch.guardrail_flags + list(guardrails.flags)),
                        warnings=_dedupe(
                            branch.warnings
                            + recommendation.warnings
                            + edge.warnings
                            + list(guardrails.flags)
                        ),
                    )
                )

        if not expanded:
            warnings.append("no viable continuation survived confidence floors")
            break
        beams = sorted(
            expanded,
            key=lambda branch: (
                -branch.beam_value(step_limit),
                -float(np.mean(branch.global_scores)) if branch.global_scores else 0.0,
                tuple(branch.sequence_track_ids),
            ),
        )[:beam_width]

    if not beams:
        provenance = provenance_for("sequence")
        warnings += guardrail_warnings(
            has_context=context is not None,
            source_grounding=0.25,
            conflicting=True,
            risk_score=0.95,
        )
        return SequenceDecision(
            current_track_id=current.track.track_id,
            context_id=context.context_id if context else None,
            arc_mode=arc_mode,
            horizon=max(horizon, 1),
            recent_history_track_ids=history_ids,
            sequence_track_ids=[current.track.track_id],
            observed_energy_profile=[round(track_energy(current), 4)],
            target_energy_profile=target_energy_profile[:1],
            cumulative_risk_score=0.0,
            max_energy_region_streak=1,
            suppressed_transition_count=suppressed_transition_count,
            recommendation_policy=RecommendationPolicy.suppress,
            warnings=_dedupe(warnings),
            provenance=provenance,
        )

    best = max(
        beams,
        key=lambda branch: (
            branch.beam_value(step_limit),
            float(np.mean(branch.global_scores)) if branch.global_scores else 0.0,
        ),
    )
    confidences = [step.score.confidence for step in best.steps]
    source_grounding = float(np.mean(confidences)) if confidences else 0.35
    high_risk = max((step.risk_score or (1.0 - step.score.value) for step in best.steps), default=0.8)
    warnings = _dedupe(best.warnings)
    warnings += guardrail_warnings(
        has_context=context is not None,
        source_grounding=source_grounding,
        conflicting=any(step.risk_flags for step in best.steps),
        risk_score=high_risk,
    )
    mean_score = float(np.mean(best.step_scores)) if best.step_scores else None
    mean_local = float(np.mean(best.local_scores)) if best.local_scores else None
    mean_global = float(np.mean(best.global_scores)) if best.global_scores else None
    mean_lookahead = float(np.mean(best.lookahead_scores)) if best.lookahead_scores else None
    mean_terminal = float(np.mean(best.terminal_scores)) if best.terminal_scores else None
    mean_set_memory = float(np.mean(best.set_memory_scores)) if best.set_memory_scores else None
    cumulative_risk = float(np.mean(best.cumulative_risks)) if best.cumulative_risks else 0.0
    effective_bpm_span = max(best.bpm_drift_spans) if best.bpm_drift_spans else None
    max_streak = 1
    current_streak = 1
    for previous, current_region in zip(best.energy_regions, best.energy_regions[1:]):
        if previous == current_region:
            current_streak += 1
        else:
            current_streak = 1
        max_streak = max(max_streak, current_streak)
    if any(step.recommendation_policy == RecommendationPolicy.review_only for step in best.steps):
        recommendation_policy = RecommendationPolicy.review_only
    else:
        recommendation_policy = RecommendationPolicy.allow if best.steps else RecommendationPolicy.suppress
    return SequenceDecision(
        current_track_id=current.track.track_id,
        context_id=context.context_id if context else None,
        arc_mode=arc_mode,
        horizon=max(horizon, 1),
        recent_history_track_ids=history_ids,
        sequence_track_ids=best.sequence_track_ids,
        steps=best.steps,
        mean_sequence_score=round(mean_score, 4) if mean_score is not None else None,
        local_arc_score=round(mean_local, 4) if mean_local is not None else None,
        global_arc_score=round(mean_global, 4) if mean_global is not None else None,
        lookahead_arc_score=round(mean_lookahead, 4) if mean_lookahead is not None else None,
        terminal_arc_score=round(mean_terminal, 4) if mean_terminal is not None else None,
        set_memory_score=round(mean_set_memory, 4) if mean_set_memory is not None else None,
        cumulative_risk_score=round(cumulative_risk, 4),
        effective_bpm_span_pct=round(effective_bpm_span, 3) if effective_bpm_span is not None else None,
        max_energy_region_streak=max_streak,
        observed_energy_profile=[round(value, 4) for value in best.energies],
        target_energy_profile=target_energy_profile[: len(best.energies)],
        guardrail_flags=list(best.guardrail_flags),
        suppressed_transition_count=suppressed_transition_count,
        recommendation_policy=recommendation_policy,
        model_version=MODEL_VERSION,
        warnings=_dedupe(warnings),
        provenance=provenance_for("sequence"),
    )

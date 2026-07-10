"""Next-track ranking (spec §9). Candidate implementation for Sprint 5.

U_DJ(x,t|s,c) = F(G_eff, T_eff, R, M_ix, W_transition, C_fit)

The full PDF formula family still exceeds what the repo can compute today, so
this v0.1 ranks candidates from the signals we do have:
- pairwise mixability,
- context fit,
- role fit for the requested set stage,
- energy-step suitability relative to the current track.
"""

from __future__ import annotations

import numpy as np

from dancelab.context.conditioning import track_context_score
from dancelab.core.config import DescriptorWeights, load_weights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    MixabilityInput,
    ModelStatus,
    NextTrackCandidate,
    NextTrackRecommendation,
    RecommendationPolicy,
    ScoredOutput,
    SetFunctionInput,
    TransitionWindowInput,
)
from dancelab.core.provenance import guardrail_warnings, provenance_for
from dancelab.decision._common import tempo_proximity_score
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.rules import evaluate_recommendation_policy
from dancelab.decision.set_function import classify_set_function
from dancelab.decision.transition_windows import detect_transition_windows

STATUS = "candidate"
MODEL_VERSION = "next_track_v0.1"
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


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


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
    analysis: AnalysisResult, weights: DescriptorWeights, top_k: int
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


def _energy_step_score(
    current: AnalysisResult,
    candidate: AnalysisResult,
    context: ContextProfile | None,
) -> tuple[float, str]:
    current_energy = _mean_feature(current, "rms")
    candidate_energy = _mean_feature(candidate, "rms")
    if current_energy is None or candidate_energy is None:
        return 0.5, "energy step unavailable — neutral"

    role = (context.set_role.lower() if context and context.set_role else "builder")
    target_delta = {
        "opener": -0.02,
        "builder": 0.04,
        "bridge": 0.00,
        "peak": 0.08,
        "reset": -0.08,
        "closer": -0.05,
        "tool": 0.00,
    }.get(role, 0.02)
    delta = candidate_energy - current_energy
    score = float(np.clip(1.0 - abs(delta - target_delta) / 0.18, 0.0, 1.0))
    return score, f"energy step Δ{delta:+.2f} vs target {target_delta:+.2f} ({role})"


def _groove_signature(analysis: AnalysisResult) -> float | None:
    cues = [
        _mean_feature(analysis, "pulse_clarity_proxy"),
        _mean_feature(analysis, "bass_salience"),
        _mean_feature(analysis, "microtiming_proxy"),
    ]
    available = [cue for cue in cues if cue is not None]
    return float(np.mean(available)) if available else None


def _groove_continuity_score(
    current: AnalysisResult,
    candidate: AnalysisResult,
) -> tuple[float, str]:
    current_groove = _groove_signature(current)
    candidate_groove = _groove_signature(candidate)
    if current_groove is None or candidate_groove is None:
        return 0.5, "groove continuity unavailable — neutral"
    score = float(np.clip(1.0 - abs(candidate_groove - current_groove), 0.0, 1.0))
    return score, (
        f"groove continuity {score:.2f} "
        f"(current={current_groove:.2f}, candidate={candidate_groove:.2f})"
    )


def _arc_target_delta(
    arc_mode: str,
    context: ContextProfile | None,
) -> float:
    base = {
        "build": 0.04,
        "flat": 0.00,
        "peak": 0.07,
        "closing": -0.05,
    }.get((arc_mode or "build").lower(), 0.02)
    role = (context.set_role.lower() if context and context.set_role else "")
    role_bias = {
        "opener": -0.02,
        "builder": 0.02,
        "bridge": 0.00,
        "peak": 0.03,
        "reset": -0.05,
        "closer": -0.04,
        "tool": 0.00,
    }.get(role, 0.0)
    return base + role_bias


def _tempo_continuity_score(
    bpm_a: float | None,
    bpm_b: float | None,
    tolerance_pct: float = 0.06,
) -> float:
    return tempo_proximity_score(bpm_a, bpm_b, tolerance_pct)


def _history_energy_summary(
    current: AnalysisResult,
    recent_history: list[AnalysisResult],
) -> dict[str, float] | None:
    current_energy = _mean_feature(current, "rms")
    if current_energy is None:
        return None
    values = [
        value
        for value in (_mean_feature(analysis, "rms") for analysis in recent_history[-6:])
        if value is not None
    ]
    series = values + [current_energy]
    if not series:
        return None
    return {
        "last": current_energy,
        "mean": _weighted_mean(series) or current_energy,
        "slope": _series_slope(series),
    }


def _history_tempo_summary(
    current: AnalysisResult,
    recent_history: list[AnalysisResult],
) -> dict[str, float] | None:
    if current.track.bpm_estimate is None:
        return None
    values = [
        float(analysis.track.bpm_estimate)
        for analysis in recent_history[-6:]
        if analysis.track.bpm_estimate is not None
    ]
    series = values + [float(current.track.bpm_estimate)]
    if not series:
        return None
    return {
        "last": float(current.track.bpm_estimate),
        "mean": _weighted_mean(series) or float(current.track.bpm_estimate),
        "slope": _series_slope(series),
    }


def _role_stage(role_name: str | None) -> float:
    return _ROLE_STAGE.get((role_name or "unknown").lower(), _ROLE_STAGE["unknown"])


def _history_role_summary(
    current: AnalysisResult,
    recent_history: list[AnalysisResult],
    context: ContextProfile | None,
    current_windows,
) -> dict[str, float | str] | None:
    analyses = recent_history[-5:] + [current]
    if not analyses:
        return None
    labels: list[str] = []
    stages: list[float] = []
    for analysis in analyses:
        windows = current_windows if analysis.track.track_id == current.track.track_id else []
        output = classify_set_function(
            SetFunctionInput(
                track_analysis=analysis,
                context=context,
                transition_windows=windows,
            )
        )
        label = output.primary_function.value
        labels.append(label)
        stages.append(_role_stage(label))
    return {
        "mean": _weighted_mean(stages) or stages[-1],
        "last": stages[-1],
        "last_label": labels[-1],
        "repeat_count": sum(1 for label in labels[-3:] if label == labels[-1]),
    }


def _history_energy_progression_score(
    candidate: AnalysisResult,
    energy_summary: dict[str, float] | None,
    arc_mode: str,
    context: ContextProfile | None,
) -> tuple[float, str]:
    if energy_summary is None:
        return 0.5, "sequence history energy unavailable — neutral"
    candidate_energy = _mean_feature(candidate, "rms")
    if candidate_energy is None:
        return 0.5, "candidate energy unavailable — neutral"
    target_delta = _arc_target_delta(arc_mode, context)
    predicted = energy_summary["last"] + target_delta + 0.35 * energy_summary["slope"]
    anchor = energy_summary["mean"] + 0.85 * target_delta
    delta_fit = float(np.clip(1.0 - abs(candidate_energy - predicted) / 0.20, 0.0, 1.0))
    anchor_fit = float(np.clip(1.0 - abs(candidate_energy - anchor) / 0.22, 0.0, 1.0))
    score = float(np.clip(0.65 * delta_fit + 0.35 * anchor_fit, 0.0, 1.0))
    return score, (
        f"history energy arc {arc_mode} target {predicted:.2f} / anchor {anchor:.2f} "
        f"(candidate={candidate_energy:.2f}, slope={energy_summary['slope']:+.3f})"
    )


def _history_tempo_progression_score(
    candidate: AnalysisResult,
    tempo_summary: dict[str, float] | None,
    arc_mode: str,
) -> tuple[float, str]:
    candidate_bpm = candidate.track.bpm_estimate
    if tempo_summary is None or candidate_bpm is None:
        return 0.5, "sequence history tempo unavailable — neutral"
    target_pct = {
        "build": 0.004,
        "flat": 0.000,
        "peak": 0.003,
        "closing": -0.004,
    }.get((arc_mode or "build").lower(), 0.001)
    predicted = tempo_summary["last"] * (1.0 + target_pct) + 0.25 * tempo_summary["slope"]
    continuity = _tempo_continuity_score(tempo_summary["last"], candidate_bpm, tolerance_pct=0.05)
    mean_fit = _tempo_continuity_score(tempo_summary["mean"], candidate_bpm, tolerance_pct=0.08)
    drift_fit = float(
        np.clip(1.0 - abs(candidate_bpm - predicted) / max(tempo_summary["last"] * 0.06, 1.0), 0.0, 1.0)
    )
    score = float(np.clip(0.45 * continuity + 0.30 * mean_fit + 0.25 * drift_fit, 0.0, 1.0))
    return score, (
        f"history tempo arc {arc_mode} target {predicted:.2f} "
        f"(candidate={candidate_bpm:.2f}, recent mean={tempo_summary['mean']:.2f})"
    )


def _history_role_progression_score(
    candidate_role: str,
    role_summary: dict[str, float | str] | None,
    arc_mode: str,
    context: ContextProfile | None,
) -> tuple[float, str]:
    if role_summary is None:
        return 0.5, "sequence history role unavailable — neutral"
    candidate_stage = _role_stage(candidate_role)
    target_stage = float(role_summary["last"]) + {
        "build": 0.55,
        "flat": 0.00,
        "peak": 0.95,
        "closing": -0.85,
    }.get((arc_mode or "build").lower(), 0.20)
    target_stage = 0.6 * target_stage + 0.4 * float(role_summary["mean"])
    if context and context.set_role:
        target_stage = 0.55 * target_stage + 0.45 * _role_stage(context.set_role)
    score = float(np.clip(1.0 - abs(candidate_stage - target_stage) / 2.8, 0.0, 1.0))
    if (
        role_summary["repeat_count"] >= 2
        and str(role_summary["last_label"]) == candidate_role
        and (arc_mode or "build").lower() != "flat"
    ):
        score = float(np.clip(score - 0.10, 0.0, 1.0))
    return score, (
        f"history role arc {arc_mode} target stage {target_stage:.2f} "
        f"(candidate role={candidate_role}, stage={candidate_stage:.2f})"
    )


def recommend_next(
    current: AnalysisResult,
    candidates: list[AnalysisResult],
    context: ContextProfile | None = None,
    *,
    weights: DescriptorWeights | None = None,
    top_k: int = 3,
    recent_history: list[AnalysisResult] | None = None,
    arc_mode: str = "build",
) -> NextTrackRecommendation:
    weights = weights or load_weights("configs/descriptor_weights.yaml")
    top_level_warnings: list[str] = []
    history = list(recent_history or [])
    history_ids = [analysis.track.track_id for analysis in history]

    unique_candidates: list[AnalysisResult] = []
    seen: set[str] = set()
    for candidate in candidates:
        track_id = candidate.track.track_id
        if track_id == current.track.track_id:
            _append_unique(top_level_warnings, "current track was removed from candidate pool")
            continue
        if track_id in history_ids:
            _append_unique(
                top_level_warnings,
                "recent-history tracks were removed from candidate pool",
            )
            continue
        if track_id in seen:
            continue
        unique_candidates.append(candidate)
        seen.add(track_id)

    if not unique_candidates:
        return NextTrackRecommendation(
            current_track_id=current.track.track_id,
            context_id=context.context_id if context else None,
            arc_mode=arc_mode,
            recent_history_track_ids=history_ids,
            ranking=[],
            suppressed_track_ids=[],
            recommendation_policy=RecommendationPolicy.suppress,
            model_version=MODEL_VERSION,
            warnings=_dedupe(top_level_warnings + ["no candidate tracks provided"]),
            provenance=provenance_for("next_track"),
        )

    current_windows = _transition_windows(current, weights, top_k)
    history_energy_summary = _history_energy_summary(current, history)
    history_tempo_summary = _history_tempo_summary(current, history)
    history_role_summary = _history_role_summary(current, history, context, current_windows)
    ranking: list[NextTrackCandidate] = []
    suppressed_track_ids: list[str] = []

    for candidate in unique_candidates:
        candidate_windows = _transition_windows(candidate, weights, top_k)
        mix = compute_mixability(
            MixabilityInput(
                track_a=current,
                track_b=candidate,
                context=context,
                transition_windows_a=current_windows,
                transition_windows_b=candidate_windows,
            ),
            weights.mixability,
            conflict_weights=weights.mixability_conflict,
        )
        ctx_value = 0.5
        ctx_confidence = 0.3
        ctx_warnings: list[str] = []
        if context is not None:
            ctx = track_context_score(candidate, context)
            ctx_value = ctx.value
            ctx_confidence = ctx.confidence
            ctx_warnings = ctx.warnings

        set_function = classify_set_function(
            SetFunctionInput(
                track_analysis=candidate,
                context=context,
                transition_windows=candidate_windows,
            )
        )
        role_fit = set_function.context_fit if set_function.context_fit is not None else 0.5
        energy_step, energy_reason = _energy_step_score(current, candidate, context)
        groove_step, groove_reason = _groove_continuity_score(current, candidate)
        history_energy_step, history_energy_reason = _history_energy_progression_score(
            candidate,
            history_energy_summary,
            arc_mode,
            context,
        )
        history_tempo_step, history_tempo_reason = _history_tempo_progression_score(
            candidate,
            history_tempo_summary,
            arc_mode,
        )
        history_role_step, history_role_reason = _history_role_progression_score(
            set_function.primary_function.value,
            history_role_summary,
            arc_mode,
            context,
        )
        pair_rule_flags = list(getattr(mix, "rule_flags", []))
        pair_rule_penalty = float(getattr(mix, "rule_penalty", 0.0) or 0.0)
        pair_hard_block = bool(getattr(mix, "hard_block", False))
        pair_policy = getattr(mix, "recommendation_policy", RecommendationPolicy.review_only)
        pair_policy_reasons = list(getattr(mix, "policy_reasons", []))
        score = float(
            np.clip(
                0.33 * mix.mixability_score +
                0.18 * ctx_value +
                0.12 * role_fit +
                0.10 * energy_step +
                0.07 * groove_step +
                0.08 * history_energy_step +
                0.06 * history_tempo_step +
                0.06 * history_role_step,
                0.0,
                1.0,
            )
        )
        score = float(np.clip(score - 0.18 * pair_rule_penalty, 0.0, 1.0))
        if pair_hard_block:
            score = min(score, 0.22)
        confidence = float(
            np.clip(
                0.38 * mix.confidence
                + 0.24 * ctx_confidence
                + 0.18 * set_function.confidence
                + 0.10 * (0.85 if groove_reason != "groove continuity unavailable — neutral" else 0.45)
                + 0.05 * (0.80 if history_energy_reason != "sequence history energy unavailable — neutral" else 0.45)
                + 0.03 * (0.78 if history_tempo_reason != "sequence history tempo unavailable — neutral" else 0.45)
                + 0.02 * (0.76 if history_role_reason != "sequence history role unavailable — neutral" else 0.45),
                0.0,
                1.0,
            )
        )

        risk_flags = list(mix.risks) + pair_rule_flags
        if context is not None and ctx_value < 0.45:
            risk_flags.append(f"low context fit for '{context.context_id}' ({ctx_value:.2f})")
        if context is not None and context.set_role and role_fit < 0.65:
            risk_flags.append(
                f"role mismatch: candidate reads more like '{set_function.primary_function.value}' "
                f"than requested '{context.set_role}'"
            )
        if energy_step < 0.40:
            risk_flags.append("energy step is awkward for the requested set stage")
        if groove_step < 0.40:
            risk_flags.append("groove continuity is weak across the handoff")
        if history and history_energy_step < 0.40:
            risk_flags.append(f"history energy continuity is weak for arc '{arc_mode}'")
        if history and history_tempo_step < 0.40:
            risk_flags.append(f"history tempo continuity is weak for arc '{arc_mode}'")
        if history and history_role_step < 0.40:
            risk_flags.append(f"history role progression is weak for arc '{arc_mode}'")
        if mix.harmonic_risk is not None and mix.harmonic_risk > 0.60:
            risk_flags.append(f"high harmonic risk ({mix.harmonic_risk:.2f})")
        if pair_hard_block:
            risk_flags.append("shared pair rules triggered a hard block for this handoff")

        candidate_policy = evaluate_recommendation_policy(
            confidence=confidence,
            risk_score=max(min(len(_dedupe(risk_flags)) / 6.0, 1.0), min(pair_rule_penalty * 2.0, 1.0)),
            hard_block=pair_hard_block,
            review_required=(
                pair_policy != RecommendationPolicy.allow
                or bool(risk_flags)
            ),
            score_value=score,
            reasons=pair_policy_reasons + pair_rule_flags,
        )

        explanation = (
            f"mixability {mix.mixability_score:.2f}; context fit {ctx_value:.2f}; "
            f"role fit {role_fit:.2f}; {energy_reason}; {groove_reason}; "
            f"{history_energy_reason}; {history_tempo_reason}; {history_role_reason}; "
            f"pair rule penalty {pair_rule_penalty:.2f}"
        )
        if candidate_policy.recommendation_policy == RecommendationPolicy.suppress:
            suppressed_track_ids.append(candidate.track.track_id)
            _append_unique(
                top_level_warnings,
                f"candidate '{candidate.track.track_id}' was suppressed by confidence floors",
            )
            continue
        ranking.append(
            NextTrackCandidate(
                track_id=candidate.track.track_id,
                rank=1,
                score=ScoredOutput(
                    value=round(score, 4),
                    status=ModelStatus.candidate,
                    confidence=round(confidence, 2),
                    explanation=explanation,
                ),
                risk_flags=_dedupe(risk_flags),
                rule_flags=_dedupe(pair_rule_flags),
                hard_block=pair_hard_block,
                recommendation_policy=candidate_policy.recommendation_policy,
                policy_reasons=list(candidate_policy.reasons),
            )
        )
        for warning in mix.warnings + ctx_warnings:
            _append_unique(top_level_warnings, warning)

    ranking.sort(
        key=lambda item: (
            {
                RecommendationPolicy.allow: 0,
                RecommendationPolicy.review_only: 1,
                RecommendationPolicy.suppress: 2,
            }[item.recommendation_policy],
            -item.score.value,
            item.track_id,
        )
    )
    ranking = [
        candidate.model_copy(update={"rank": idx})
        for idx, candidate in enumerate(ranking, start=1)
    ]

    if suppressed_track_ids and not ranking:
        _append_unique(top_level_warnings, "all candidate tracks were suppressed by confidence floors")
    avg_confidence = (
        float(np.mean([candidate.score.confidence for candidate in ranking]))
        if ranking else 0.25
    )
    top_risk = 1.0 - ranking[0].score.value if ranking else 1.0
    top_level_warnings += guardrail_warnings(
        has_context=context is not None,
        source_grounding=avg_confidence,
        conflicting=any(candidate.risk_flags for candidate in ranking),
        risk_score=top_risk,
    )
    if any(candidate.recommendation_policy == RecommendationPolicy.allow for candidate in ranking):
        recommendation_policy = RecommendationPolicy.allow
    elif ranking:
        recommendation_policy = RecommendationPolicy.review_only
    else:
        recommendation_policy = RecommendationPolicy.suppress

    return NextTrackRecommendation(
        current_track_id=current.track.track_id,
        context_id=context.context_id if context else None,
        arc_mode=arc_mode,
        recent_history_track_ids=history_ids,
        ranking=ranking,
        suppressed_track_ids=_dedupe(suppressed_track_ids),
        recommendation_policy=recommendation_policy,
        model_version=MODEL_VERSION,
        warnings=_dedupe(top_level_warnings),
        provenance=provenance_for("next_track"),
    )

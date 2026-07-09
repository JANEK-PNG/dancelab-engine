"""Unified pair-level edge decision layer."""

from __future__ import annotations

import numpy as np

from dancelab.context.conditioning import track_context_score
from dancelab.core.config import DescriptorWeights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    DecisionClass,
    EdgeDecision,
    GateStatus,
    MixabilityInput,
    MixabilityOutput,
    ModelStatus,
    PairWindow,
    ScoredOutput,
    TempoFeasibility,
    TransitionStrategy,
    TransitionWindow,
    TransitionWindowInput,
    WindowType,
)
from dancelab.core.provenance import guardrail_warnings, provenance_for
from dancelab.decision.blend_profile import classify_blend_profile
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.rules import evaluate_recommendation_policy
from dancelab.decision.transition_strategy import classify_transition_strategy
from dancelab.decision.transition_windows import detect_transition_windows

MODEL_VERSION = "edge_decision_v0.1"


def _find_window(
    windows: list[TransitionWindow], target: tuple[float, float] | None
) -> TransitionWindow | None:
    if target is None:
        return None
    for window in windows:
        if abs(window.start_sec - target[0]) < 0.01 and abs(window.end_sec - target[1]) < 0.01:
            return window
    return None


def _preferred_window(windows: list[TransitionWindow], kind: str) -> TransitionWindow | None:
    if not windows:
        return None
    if kind == "out":
        for window in windows:
            if window.window_type.value == "mix_out":
                return window
    if kind == "in":
        for window in windows:
            if window.window_type.value == "mix_in":
                return window
    return windows[0]


def _synthetic_window(track: AnalysisResult, kind: str) -> TransitionWindow | None:
    if not track.features:
        return None
    times = [frame.timestamp_sec for frame in track.features]
    if not times:
        return None
    duration = float(times[-1])
    center = duration * (0.75 if kind == "out" else 0.25)
    start = max(float(times[0]), center - 8.0)
    end = min(duration, center + 8.0)
    return TransitionWindow(
        transition_window_id=f"{track.track.track_id}_fallback_{kind}",
        start_sec=round(start, 2),
        end_sec=round(max(end, start + 2.0), 2),
        score=0.5,
        status=ModelStatus.candidate,
        window_type=WindowType.mix_out if kind == "out" else WindowType.mix_in,
        confidence=0.2,
        risk_score=0.45,
        reasoning=["synthetic fallback window — no strong local maxima were available"],
        warnings=["fallback window only — verify transition timing by ear"],
        recommended_strategies=[TransitionStrategy.short_blend],
        tempo_window_feasibility=TempoFeasibility.medium,
        explanation="fallback window synthesized for edge-decision completeness",
    )


def _shared_contexts(
    window_a: TransitionWindow | None,
    window_b: TransitionWindow | None,
) -> list[str]:
    contexts_a = set(window_a.compatible_contexts if window_a else [])
    contexts_b = set(window_b.compatible_contexts if window_b else [])
    if contexts_a and contexts_b:
        return sorted(contexts_a & contexts_b)
    return sorted(contexts_a | contexts_b)


def _window_support(*windows: TransitionWindow | None) -> float:
    scores = [window.score for window in windows if window is not None]
    if not scores:
        return 0.5
    return float(np.clip(np.mean(scores), 0.0, 1.0))


def _window_risk(*windows: TransitionWindow | None) -> float:
    values = [window.risk_score for window in windows if window and window.risk_score is not None]
    return float(np.mean(values)) if values else 0.35


def _context_fit_score(
    track_a: AnalysisResult,
    track_b: AnalysisResult,
    mixability: MixabilityOutput,
    context: ContextProfile | None,
) -> float | None:
    if mixability.context_fit_score is not None:
        return mixability.context_fit_score
    if context is None:
        return None
    ctx_a = track_context_score(track_a, context)
    ctx_b = track_context_score(track_b, context)
    return round((ctx_a.value + ctx_b.value) / 2.0, 4)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _decision_class(
    mixability: MixabilityOutput,
    *,
    hard_block: bool,
    strategy_standard_blend_allowed: bool,
    tempo_gate: GateStatus,
    harmonic_gate: GateStatus,
    context_fit_score: float | None,
    window_risk: float,
) -> DecisionClass:
    context_fit = context_fit_score if context_fit_score is not None else 0.5
    severe_conflict = any(
        value is not None and value >= 0.72
        for value in (
            mixability.harmonic_risk,
            mixability.vocal_clash_risk,
            mixability.bass_conflict_risk,
        )
    )
    if hard_block:
        return DecisionClass.reject_standard_blend
    if (
        mixability.mixability_score >= 0.72
        and mixability.confidence >= 0.55
        and strategy_standard_blend_allowed
        and tempo_gate == GateStatus.pass_
        and harmonic_gate == GateStatus.pass_
        and window_risk < 0.45
        and context_fit >= 0.55
        and not severe_conflict
    ):
        return DecisionClass.strong_candidate
    if mixability.mixability_score < 0.45 or (tempo_gate == GateStatus.fail and severe_conflict):
        return DecisionClass.reject_standard_blend
    if not strategy_standard_blend_allowed and mixability.mixability_score >= 0.55:
        return DecisionClass.non_standard_strategy_required
    return DecisionClass.review_required


def build_edge_decision(
    track_a: AnalysisResult,
    track_b: AnalysisResult,
    weights: DescriptorWeights,
    *,
    context: ContextProfile | None = None,
    transition_windows_a: list[TransitionWindow] | None = None,
    transition_windows_b: list[TransitionWindow] | None = None,
    mixability: MixabilityOutput | None = None,
    top_k: int = 3,
) -> EdgeDecision:
    windows_a = transition_windows_a or detect_transition_windows(
        TransitionWindowInput(
            track_id=track_a.track.track_id,
            segments=track_a.segments,
            feature_frames=track_a.features,
            beatgrid=track_a.beatgrid,
            context=context,
        ),
        weights.transition_window,
        top_k=top_k,
    ).windows
    windows_b = transition_windows_b or detect_transition_windows(
        TransitionWindowInput(
            track_id=track_b.track.track_id,
            segments=track_b.segments,
            feature_frames=track_b.features,
            beatgrid=track_b.beatgrid,
            context=context,
        ),
        weights.transition_window,
        top_k=top_k,
    ).windows

    mix = mixability or compute_mixability(
        MixabilityInput(
            track_a=track_a,
            track_b=track_b,
            context=context,
            transition_windows_a=windows_a,
            transition_windows_b=windows_b,
        ),
        weights.mixability,
        conflict_weights=weights.mixability_conflict,
    )

    best_pair = mix.best_pair_windows[0] if mix.best_pair_windows else None
    selected_window_a = _find_window(windows_a, best_pair.track_a_window if best_pair else None)
    selected_window_b = _find_window(windows_b, best_pair.track_b_window if best_pair else None)
    if best_pair is None:
        selected_window_a = _preferred_window(windows_a, "out")
        selected_window_b = _preferred_window(windows_b, "in")
        if selected_window_a is None:
            selected_window_a = _synthetic_window(track_a, "out")
        if selected_window_b is None:
            selected_window_b = _synthetic_window(track_b, "in")
        if selected_window_a is not None and selected_window_b is not None:
            best_pair = PairWindow(
                track_a_window=(selected_window_a.start_sec, selected_window_a.end_sec),
                track_b_window=(selected_window_b.start_sec, selected_window_b.end_sec),
                pair_score=round(
                    mix.mixability_score
                    + selected_window_a.score
                    + selected_window_b.score,
                    4,
                ),
                explanation=(
                    "fallback pair from top single-track windows "
                    "(best_pair_windows unavailable under current inputs)"
                ),
            )
    strategy = classify_transition_strategy(
        track_a,
        track_b,
        mix,
        selected_window_a=selected_window_a,
        selected_window_b=selected_window_b,
        context=context,
    )
    blend_profile = classify_blend_profile(
        recommended_transition_strategy=strategy.recommended_transition_strategy,
        standard_blend_allowed=strategy.standard_blend_allowed,
        bass_risk=mix.bass_conflict_risk,
        vocal_risk=mix.vocal_clash_risk,
    )
    selected_window_a = (
        selected_window_a.model_copy(
            update={
                "tempo_window_feasibility": strategy.tempo_window_feasibility,
                "standard_blend_allowed": strategy.standard_blend_allowed,
                "recommended_strategies": [strategy.recommended_transition_strategy],
                "tempo_warning": strategy.tempo_warning,
            }
        )
        if selected_window_a
        else None
    )
    selected_window_b = (
        selected_window_b.model_copy(
            update={
                "tempo_window_feasibility": strategy.tempo_window_feasibility,
                "standard_blend_allowed": strategy.standard_blend_allowed,
                "recommended_strategies": [strategy.recommended_transition_strategy],
                "tempo_warning": strategy.tempo_warning,
            }
        )
        if selected_window_b
        else None
    )

    context_fit_score = _context_fit_score(track_a, track_b, mix, context)
    window_support = _window_support(selected_window_a, selected_window_b)
    window_risk = _window_risk(selected_window_a, selected_window_b)
    strategy_support = {
        TempoFeasibility.high: 1.0,
        TempoFeasibility.medium: 0.7,
        TempoFeasibility.low: 0.35,
    }[strategy.tempo_window_feasibility]
    risk_penalty = float(
        np.mean(
            [
                mix.harmonic_risk if mix.harmonic_risk is not None else 0.5,
                mix.vocal_clash_risk if mix.vocal_clash_risk is not None else 0.35,
                mix.bass_conflict_risk if mix.bass_conflict_risk is not None else 0.35,
                window_risk,
            ]
        )
    )
    context_component = context_fit_score if context_fit_score is not None else 0.5
    score_value = float(
        np.clip(
            0.52 * mix.mixability_score
            + 0.14 * window_support
            + 0.12 * context_component
            + 0.12 * strategy_support
            + 0.10 * (1.0 - risk_penalty),
            0.0,
            1.0,
        )
    )
    confidence = float(
        np.clip(
            0.55 * mix.confidence
            + 0.15 * (1.0 if best_pair else 0.35)
            + 0.15 * (0.85 if context_fit_score is not None else 0.45)
            + 0.15 * (0.9 if strategy.tempo_gate_status != GateStatus.fail else 0.4),
            0.0,
            1.0,
        )
    )
    decision_class = _decision_class(
        mix,
        hard_block=bool(getattr(mix, "hard_block", False)),
        strategy_standard_blend_allowed=strategy.standard_blend_allowed,
        tempo_gate=strategy.tempo_gate_status,
        harmonic_gate=strategy.harmonic_gate_status,
        context_fit_score=context_fit_score,
        window_risk=window_risk,
    )

    pair_rule_flags = list(getattr(mix, "rule_flags", []))
    hard_block = bool(getattr(mix, "hard_block", False))
    rule_penalty = float(getattr(mix, "rule_penalty", 0.0) or 0.0)
    policy = evaluate_recommendation_policy(
        confidence=confidence,
        risk_score=max(risk_penalty, min(rule_penalty * 2.0, 1.0)),
        hard_block=hard_block,
        review_required=decision_class != DecisionClass.strong_candidate,
        score_value=score_value,
        reasons=pair_rule_flags,
    )
    risks = list(mix.risks) + pair_rule_flags
    if strategy.tempo_gate_status == GateStatus.fail:
        risks.append("tempo gate failed — reject standard blend")
    elif strategy.tempo_gate_status == GateStatus.strategy_dependent:
        risks.append("tempo relation requires a non-standard transition strategy")
    if strategy.harmonic_gate_status == GateStatus.fail:
        risks.append("harmonic gate failed — exposed key clash risk")
    if hard_block:
        risks.append("shared pair rules triggered a hard block for standard blending")

    warnings = list(mix.warnings)
    if strategy.tempo_warning:
        warnings.append(strategy.tempo_warning)
    warnings += guardrail_warnings(
        has_context=context is not None,
        source_grounding=confidence,
        conflicting=decision_class == DecisionClass.review_required or bool(risks),
        risk_score=1.0 - score_value,
    )
    compatible_contexts = _shared_contexts(selected_window_a, selected_window_b)
    if context is not None and context.context_id not in compatible_contexts and context_fit_score is not None:
        if context_fit_score >= 0.55:
            compatible_contexts.append(context.context_id)
    compatible_contexts = sorted(set(compatible_contexts))

    reasoning = [
        f"mixability {mix.mixability_score:.2f} with confidence {mix.confidence:.2f}",
        f"window support {window_support:.2f}, window risk {window_risk:.2f}",
        f"context fit {context_component:.2f}, strategy support {strategy_support:.2f}",
        f"tempo gate {strategy.tempo_gate_status.value}, harmonic gate {strategy.harmonic_gate_status.value}",
        strategy.explanation,
        blend_profile.explanation,
    ] + mix.reasoning

    annotation_payload: dict[str, object] = {
        "pair_id": f"{track_a.track.track_id}__{track_b.track.track_id}",
        "track_id_a": track_a.track.track_id,
        "track_id_b": track_b.track.track_id,
        "context_id": context.context_id if context else None,
        "decision_class": decision_class.value,
        "core_dj_compatibility_score": round(score_value, 4),
        "core_dj_confidence": round(confidence, 2),
        "mixability_score": round(mix.mixability_score, 4),
        "recommended_transition_strategy": strategy.recommended_transition_strategy.value,
        "blend_profile_auto": blend_profile.blend_profile_auto.value,
        "blend_profile_explanation": blend_profile.explanation,
        "standard_blend_allowed": strategy.standard_blend_allowed,
        "tempo_relation": strategy.tempo_relation,
        "harmonic_relation": mix.harmonic_relation,
        "context_fit_score": round(context_fit_score, 4) if context_fit_score is not None else None,
        "selected_window_a_id": (
            selected_window_a.transition_window_id if selected_window_a is not None else None
        ),
        "selected_window_b_id": (
            selected_window_b.transition_window_id if selected_window_b is not None else None
        ),
        "selected_pair_window": best_pair.model_dump() if isinstance(best_pair, PairWindow) else None,
        "compatible_contexts": compatible_contexts,
        "recommendation_policy": policy.recommendation_policy.value,
        "policy_reasons": list(policy.reasons),
        "rule_flags": _dedupe(pair_rule_flags),
        "hard_block": hard_block,
        "rule_penalty": round(rule_penalty, 4),
        "risks": _dedupe(risks),
        "warnings": _dedupe(warnings),
    }
    return EdgeDecision(
        track_id_a=track_a.track.track_id,
        track_id_b=track_b.track.track_id,
        decision_class=decision_class,
        core_dj_compatibility_score=ScoredOutput(
            value=round(score_value, 4),
            status=ModelStatus.candidate,
            confidence=round(confidence, 2),
            explanation=(
                f"combined candidate score from mixability, selected windows, context fit, "
                f"tempo feasibility, and explicit risk gates ({decision_class.value})"
            ),
        ),
        standard_blend_allowed=strategy.standard_blend_allowed,
        recommended_transition_strategy=strategy.recommended_transition_strategy,
        blend_profile_auto=blend_profile.blend_profile_auto,
        blend_profile_explanation=blend_profile.explanation,
        alternative_transition_strategies=strategy.alternative_transition_strategies,
        tempo_gate_status=strategy.tempo_gate_status,
        harmonic_gate_status=strategy.harmonic_gate_status,
        tempo_window_feasibility=strategy.tempo_window_feasibility,
        tempo_relation=strategy.tempo_relation,
        bpm_delta_pct=strategy.bpm_delta_pct,
        effective_bpm_delta_pct=strategy.effective_bpm_delta_pct,
        selected_pair_window=best_pair,
        selected_window_a=selected_window_a,
        selected_window_b=selected_window_b,
        harmonic_relation=mix.harmonic_relation,
        harmonic_risk=mix.harmonic_risk,
        context_fit_score=context_fit_score,
        bass_conflict_risk=mix.bass_conflict_risk,
        vocal_clash_risk=mix.vocal_clash_risk,
        compatible_contexts=compatible_contexts,
        recommendation_policy=policy.recommendation_policy,
        policy_reasons=list(policy.reasons),
        rule_flags=_dedupe(pair_rule_flags),
        hard_block=hard_block,
        rule_penalty=round(rule_penalty, 4),
        risks=_dedupe(risks),
        warnings=_dedupe(warnings),
        reasoning=_dedupe(reasoning),
        annotation_payload=annotation_payload,
        model_version=MODEL_VERSION,
        provenance=provenance_for("edge_decision"),
    )

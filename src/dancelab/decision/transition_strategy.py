"""Pair-level transition strategy classifier for DJ edges."""

from __future__ import annotations

import numpy as np

from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    GateStatus,
    MixabilityOutput,
    TempoFeasibility,
    TransitionStrategy,
    TransitionStrategyDecision,
    TransitionWindow,
    WindowType,
)
from dancelab.decision.rules import evaluate_pair_rules


def _dedupe_strategies(
    strategies: list[TransitionStrategy], primary: TransitionStrategy
) -> list[TransitionStrategy]:
    out: list[TransitionStrategy] = []
    for strategy in strategies:
        if strategy != primary and strategy not in out:
            out.append(strategy)
    return out


def _mean_window_risk(*windows: TransitionWindow | None) -> float:
    values = [window.risk_score for window in windows if window and window.risk_score is not None]
    return float(np.mean(values)) if values else 0.35


def classify_transition_strategy(
    track_a: AnalysisResult,
    track_b: AnalysisResult,
    mixability: MixabilityOutput,
    *,
    selected_window_a: TransitionWindow | None = None,
    selected_window_b: TransitionWindow | None = None,
    context: ContextProfile | None = None,
) -> TransitionStrategyDecision:
    bpm_a = track_a.track.bpm_estimate
    bpm_b = track_b.track.bpm_estimate
    window_risk = _mean_window_risk(selected_window_a, selected_window_b)
    pair_rules = evaluate_pair_rules(
        bpm_a=bpm_a,
        bpm_b=bpm_b,
        harmonic_risk=mixability.harmonic_risk,
        vocal_risk=mixability.vocal_clash_risk,
        bass_risk=mixability.bass_conflict_risk,
        phrase_fit=mixability.phrase_fit,
        tension_fit=mixability.tension_fit,
    )
    tempo_relation = pair_rules.tempo_relation
    bpm_delta_pct = pair_rules.bpm_delta_pct
    effective_delta_pct = pair_rules.effective_bpm_delta_pct
    harmonic_risk = mixability.harmonic_risk if mixability.harmonic_risk is not None else 0.5
    bridgeish = any(
        window and window.window_type == WindowType.bridge
        for window in (selected_window_a, selected_window_b)
    )

    tempo_warning = None
    if effective_delta_pct is None:
        feasibility = TempoFeasibility.medium
        standard_allowed = False
        recommended = TransitionStrategy.short_blend
        alternatives = [TransitionStrategy.echo_out, TransitionStrategy.tool_mix]
        tempo_gate = GateStatus.review
        tempo_warning = "missing BPM estimate — verify tempo relation before trusting transition strategy"
    elif tempo_relation != "direct" and effective_delta_pct <= 2.5:
        feasibility = TempoFeasibility.medium
        standard_allowed = False
        recommended = TransitionStrategy.half_time_double_time_switch
        alternatives = [TransitionStrategy.tempo_ramp, TransitionStrategy.echo_out]
        tempo_gate = GateStatus.strategy_dependent
        tempo_warning = "tempo relation is only workable through half/double-time handling"
    elif effective_delta_pct <= 2.0:
        feasibility = TempoFeasibility.high
        standard_allowed = True
        recommended = TransitionStrategy.standard_blend
        alternatives = [TransitionStrategy.phrase_aligned_blend, TransitionStrategy.short_blend]
        tempo_gate = GateStatus.pass_
    elif effective_delta_pct <= 4.0:
        feasibility = TempoFeasibility.high
        standard_allowed = True
        recommended = TransitionStrategy.short_blend
        alternatives = [TransitionStrategy.phrase_aligned_blend, TransitionStrategy.standard_blend]
        tempo_gate = GateStatus.pass_
    elif effective_delta_pct <= 6.0:
        feasibility = TempoFeasibility.medium
        standard_allowed = tempo_relation == "direct" and window_risk < 0.45
        recommended = (
            TransitionStrategy.phrase_aligned_blend
            if standard_allowed
            else TransitionStrategy.tempo_ramp
        )
        alternatives = [TransitionStrategy.short_blend, TransitionStrategy.echo_out]
        tempo_gate = GateStatus.pass_ if standard_allowed else GateStatus.strategy_dependent
        tempo_warning = "tempo gap is above easy-blend range — keep the overlap disciplined"
    elif effective_delta_pct <= 10.0:
        feasibility = TempoFeasibility.medium
        standard_allowed = False
        recommended = TransitionStrategy.tempo_ramp
        alternatives = [TransitionStrategy.echo_out, TransitionStrategy.break_transition]
        tempo_gate = GateStatus.strategy_dependent
        tempo_warning = "standard blend is risky at this BPM gap — non-standard strategy preferred"
    elif effective_delta_pct <= 18.0:
        feasibility = TempoFeasibility.low
        standard_allowed = False
        recommended = TransitionStrategy.break_transition if bridgeish else TransitionStrategy.echo_out
        alternatives = [TransitionStrategy.hard_cut, TransitionStrategy.reset]
        tempo_gate = GateStatus.strategy_dependent
        tempo_warning = "large BPM jump — treat as a transition move, not a standard blend"
    else:
        feasibility = TempoFeasibility.low
        standard_allowed = False
        recommended = TransitionStrategy.reset if bridgeish else TransitionStrategy.hard_cut
        alternatives = [TransitionStrategy.echo_out]
        tempo_gate = GateStatus.fail
        tempo_warning = "extreme BPM jump — reject standard blend"

    harmonic_gate = pair_rules.harmonic_gate_status

    if not pair_rules.standard_blend_allowed:
        standard_allowed = False
        if recommended in {
            TransitionStrategy.standard_blend,
            TransitionStrategy.short_blend,
            TransitionStrategy.phrase_aligned_blend,
        }:
            recommended = (
                TransitionStrategy.echo_out
                if (effective_delta_pct or 0.0) <= 10.0
                else TransitionStrategy.hard_cut
            )
        alternatives = _dedupe_strategies(
            alternatives + [TransitionStrategy.echo_out, TransitionStrategy.hard_cut],
            recommended,
        )
        if tempo_warning:
            tempo_warning += "; shared rules suggest a non-standard exit"
        else:
            tempo_warning = "shared rules suggest a non-standard exit instead of a standard blend"

    if context and context.set_role and context.set_role in {"opener", "reset"}:
        alternatives = _dedupe_strategies(
            alternatives + [TransitionStrategy.tool_mix, TransitionStrategy.reset],
            recommended,
        )

    explanation = (
        f"BPM relation {tempo_relation}; raw delta {bpm_delta_pct if bpm_delta_pct is not None else 'n/a'}%; "
        f"effective delta {effective_delta_pct if effective_delta_pct is not None else 'n/a'}%; "
        f"window risk {window_risk:.2f}; harmonic risk {harmonic_risk:.2f}. "
        f"Recommended strategy: {recommended.value}."
    )
    return TransitionStrategyDecision(
        bpm_a=bpm_a,
        bpm_b=bpm_b,
        bpm_delta_pct=bpm_delta_pct,
        effective_bpm_delta_pct=effective_delta_pct,
        tempo_relation=tempo_relation,
        tempo_window_feasibility=feasibility,
        standard_blend_allowed=standard_allowed,
        recommended_transition_strategy=recommended,
        alternative_transition_strategies=_dedupe_strategies(alternatives, recommended),
        tempo_gate_status=tempo_gate,
        harmonic_gate_status=harmonic_gate,
        explanation=explanation,
        tempo_warning=tempo_warning,
    )

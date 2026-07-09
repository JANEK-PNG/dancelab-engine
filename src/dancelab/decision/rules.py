"""Shared pair and sequence rule evaluators.

These rules do not replace the descriptive scores. They provide explicit
guardrails and hard blocks that can be reused across pair scoring,
recommend-next, transition strategy, and sequence planning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dancelab.core.models import GateStatus, RecommendationPolicy

_PAIR_LIMITS = {
    "tempo_review_pct": 6.0,
    "tempo_strategy_pct": 10.0,
    "tempo_hard_pct": 18.0,
    "harmonic_review": 0.50,
    "harmonic_fail": 0.75,
    "vocal_review": 0.50,
    "vocal_fail": 0.70,
    "bass_review": 0.55,
    "bass_fail": 0.72,
    "phrase_review": 0.45,
    "phrase_fail": 0.35,
    "tension_review": 0.45,
    "tension_fail": 0.35,
}
_RISK_LIMITS = {"soft": 0.48, "hard": 0.62, "consecutive_hard": 0.68}
_BPM_DRIFT_LIMITS = {"build": 0.06, "flat": 0.04, "peak": 0.08, "closing": 0.10}
_ENERGY_REGION_STREAK_LIMITS = {"build": 2, "flat": 4, "peak": 3, "closing": 3}
_POLICY_LIMITS = {
    "allow_confidence": 0.58,
    "review_confidence": 0.40,
    "suppress_confidence": 0.28,
    "review_risk": 0.58,
    "suppress_risk": 0.82,
}


@dataclass
class PairRuleAssessment:
    tempo_relation: str = "unknown"
    bpm_delta_pct: float | None = None
    effective_bpm_delta_pct: float | None = None
    tempo_gate_status: GateStatus = GateStatus.review
    harmonic_gate_status: GateStatus = GateStatus.review
    standard_blend_allowed: bool = False
    hard_block: bool = False
    review_required: bool = False
    penalty: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class SequenceRuleAssessment:
    cumulative_risk: float = 0.0
    bpm_span_pct: float | None = None
    max_streak: int = 0
    current_streak: int = 0
    dominant_region: str | None = None
    flags: list[str] = field(default_factory=list)
    penalty: float = 0.0
    severe: bool = False


@dataclass
class RecommendationPolicyAssessment:
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.review_only
    reasons: list[str] = field(default_factory=list)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def best_bpm_relation(
    bpm_a: float | None,
    bpm_b: float | None,
) -> tuple[str, float | None, float | None]:
    if not bpm_a or not bpm_b:
        return "unknown", None, None
    delta_pct = round((bpm_b - bpm_a) / bpm_a * 100.0, 2)
    candidates = [
        ("direct", bpm_b),
        ("double_time_of_b", bpm_b * 2.0),
        ("half_time_of_b", bpm_b / 2.0),
    ]
    relation, target = min(candidates, key=lambda item: abs(bpm_a - item[1]) / bpm_a)
    effective = round(abs(target - bpm_a) / bpm_a * 100.0, 2)
    return relation, delta_pct, effective


def best_effective_bpm(reference_bpm: float | None, candidate_bpm: float | None) -> float | None:
    if reference_bpm is None or candidate_bpm is None:
        return None
    variants = [candidate_bpm, candidate_bpm * 2.0, candidate_bpm / 2.0]
    return float(min(variants, key=lambda value: abs(reference_bpm - value)))


def effective_bpm_delta_pct(previous_bpm: float | None, current_bpm: float | None) -> float | None:
    if previous_bpm is None or current_bpm is None or previous_bpm == 0:
        return None
    return float(abs(current_bpm - previous_bpm) / previous_bpm * 100.0)


def energy_region(value: float, e_min: float, e_range: float) -> str:
    normalized = float(np.clip((value - e_min) / e_range, 0.0, 1.0))
    if normalized < 0.33:
        return "low"
    if normalized < 0.67:
        return "mid"
    return "high"


def pair_risk_score(
    *,
    harmonic_risk: float | None = None,
    vocal_risk: float | None = None,
    bass_risk: float | None = None,
    phrase_fit: float | None = None,
    tension_fit: float | None = None,
    rule_penalty: float = 0.0,
    hard_block: bool = False,
) -> float:
    values: list[float] = []
    for value in (harmonic_risk, vocal_risk, bass_risk):
        if value is not None:
            values.append(float(np.clip(value, 0.0, 1.0)))
    if phrase_fit is not None:
        values.append(float(np.clip(1.0 - phrase_fit, 0.0, 1.0)))
    if tension_fit is not None:
        values.append(float(np.clip(1.0 - tension_fit, 0.0, 1.0)))
    values.append(float(np.clip(rule_penalty * 2.0, 0.0, 1.0)))
    if hard_block:
        values.append(1.0)
    return float(np.clip(_mean(values), 0.0, 1.0))


def evaluate_recommendation_policy(
    *,
    confidence: float,
    risk_score: float,
    hard_block: bool = False,
    review_required: bool = False,
    severe: bool = False,
    score_value: float | None = None,
    reasons: list[str] | None = None,
) -> RecommendationPolicyAssessment:
    policy_reasons = list(reasons or [])

    if hard_block:
        policy_reasons.append("shared hard block triggered recommendation suppression")
        return RecommendationPolicyAssessment(
            recommendation_policy=RecommendationPolicy.suppress,
            reasons=_dedupe(policy_reasons),
        )
    if severe:
        policy_reasons.append("severe guardrails triggered recommendation suppression")
        return RecommendationPolicyAssessment(
            recommendation_policy=RecommendationPolicy.suppress,
            reasons=_dedupe(policy_reasons),
        )
    if confidence < _POLICY_LIMITS["suppress_confidence"]:
        policy_reasons.append(
            f"confidence {confidence:.2f} is below suppress floor {_POLICY_LIMITS['suppress_confidence']:.2f}"
        )
        return RecommendationPolicyAssessment(
            recommendation_policy=RecommendationPolicy.suppress,
            reasons=_dedupe(policy_reasons),
        )
    if (
        risk_score >= _POLICY_LIMITS["suppress_risk"]
        and confidence < _POLICY_LIMITS["allow_confidence"]
    ):
        policy_reasons.append(
            f"risk score {risk_score:.2f} exceeds suppress floor {_POLICY_LIMITS['suppress_risk']:.2f}"
        )
        return RecommendationPolicyAssessment(
            recommendation_policy=RecommendationPolicy.suppress,
            reasons=_dedupe(policy_reasons),
        )
    if score_value is not None and score_value < 0.24 and confidence < 0.45:
        policy_reasons.append("very low score under weak confidence triggered suppression")
        return RecommendationPolicyAssessment(
            recommendation_policy=RecommendationPolicy.suppress,
            reasons=_dedupe(policy_reasons),
        )

    if review_required:
        policy_reasons.append("shared rules require manual review")
    if confidence < _POLICY_LIMITS["allow_confidence"]:
        policy_reasons.append(
            f"confidence {confidence:.2f} is below allow floor {_POLICY_LIMITS['allow_confidence']:.2f}"
        )
    if risk_score >= _POLICY_LIMITS["review_risk"]:
        policy_reasons.append(
            f"risk score {risk_score:.2f} exceeds review floor {_POLICY_LIMITS['review_risk']:.2f}"
        )
    if (
        review_required
        or confidence < _POLICY_LIMITS["allow_confidence"]
        or risk_score >= _POLICY_LIMITS["review_risk"]
    ):
        return RecommendationPolicyAssessment(
            recommendation_policy=RecommendationPolicy.review_only,
            reasons=_dedupe(policy_reasons),
        )
    return RecommendationPolicyAssessment(
        recommendation_policy=RecommendationPolicy.allow,
        reasons=_dedupe(policy_reasons),
    )


def evaluate_pair_policy(
    *,
    confidence: float,
    pair_rules: PairRuleAssessment,
    harmonic_risk: float | None = None,
    vocal_risk: float | None = None,
    bass_risk: float | None = None,
    phrase_fit: float | None = None,
    tension_fit: float | None = None,
    score_value: float | None = None,
) -> RecommendationPolicyAssessment:
    return evaluate_recommendation_policy(
        confidence=confidence,
        risk_score=pair_risk_score(
            harmonic_risk=harmonic_risk,
            vocal_risk=vocal_risk,
            bass_risk=bass_risk,
            phrase_fit=phrase_fit,
            tension_fit=tension_fit,
            rule_penalty=pair_rules.penalty,
            hard_block=pair_rules.hard_block,
        ),
        hard_block=pair_rules.hard_block,
        review_required=pair_rules.review_required,
        score_value=score_value,
        reasons=list(pair_rules.flags),
    )


def evaluate_pair_rules(
    *,
    bpm_a: float | None,
    bpm_b: float | None,
    harmonic_risk: float | None = None,
    vocal_risk: float | None = None,
    bass_risk: float | None = None,
    phrase_fit: float | None = None,
    tension_fit: float | None = None,
) -> PairRuleAssessment:
    relation, bpm_delta_pct, effective_delta_pct = best_bpm_relation(bpm_a, bpm_b)
    flags: list[str] = []
    penalty = 0.0
    hard_block = False
    review_required = False
    standard_blend_allowed = True

    if effective_delta_pct is None:
        tempo_gate = GateStatus.review
        standard_blend_allowed = False
        flags.append("tempo rule unresolved because one track has no BPM estimate")
        penalty += 0.04
        review_required = True
    elif relation != "direct" and effective_delta_pct <= 2.5:
        tempo_gate = GateStatus.strategy_dependent
        standard_blend_allowed = False
        flags.append("pair needs half/double-time handling instead of a direct standard blend")
        penalty += 0.08
        review_required = True
    elif effective_delta_pct <= _PAIR_LIMITS["tempo_review_pct"]:
        tempo_gate = GateStatus.pass_
    elif effective_delta_pct <= _PAIR_LIMITS["tempo_strategy_pct"]:
        tempo_gate = GateStatus.strategy_dependent
        standard_blend_allowed = False
        flags.append(
            f"effective BPM gap {effective_delta_pct:.1f}% needs a non-standard tempo strategy"
        )
        penalty += 0.10
        review_required = True
    elif effective_delta_pct <= _PAIR_LIMITS["tempo_hard_pct"]:
        tempo_gate = GateStatus.strategy_dependent
        standard_blend_allowed = False
        flags.append(
            f"large BPM jump {effective_delta_pct:.1f}% rejects a standard blend"
        )
        penalty += 0.14
        review_required = True
    else:
        tempo_gate = GateStatus.fail
        standard_blend_allowed = False
        hard_block = True
        review_required = True
        flags.append(
            f"extreme BPM jump {effective_delta_pct:.1f}% breaches the shared hard limit"
        )
        penalty += 0.18

    if harmonic_risk is None:
        harmonic_gate = GateStatus.review
    elif harmonic_risk >= _PAIR_LIMITS["harmonic_fail"]:
        harmonic_gate = GateStatus.fail
        hard_block = True
        review_required = True
        standard_blend_allowed = False
        flags.append(
            f"harmonic clash risk {harmonic_risk:.2f} breaches the shared hard limit"
        )
        penalty += 0.16
    elif harmonic_risk >= _PAIR_LIMITS["harmonic_review"]:
        harmonic_gate = GateStatus.review
        review_required = True
        flags.append(
            f"harmonic risk {harmonic_risk:.2f} needs masking or careful transition timing"
        )
        penalty += 0.08
    else:
        harmonic_gate = GateStatus.pass_

    if vocal_risk is not None:
        if vocal_risk >= _PAIR_LIMITS["vocal_fail"]:
            hard_block = True
            review_required = True
            standard_blend_allowed = False
            flags.append(
                f"vocal clash risk {vocal_risk:.2f} breaches the shared hard limit"
            )
            penalty += 0.14
        elif vocal_risk >= _PAIR_LIMITS["vocal_review"]:
            review_required = True
            flags.append(f"vocal clash risk {vocal_risk:.2f} is elevated")
            penalty += 0.06

    if bass_risk is not None:
        if bass_risk >= _PAIR_LIMITS["bass_fail"]:
            hard_block = True
            review_required = True
            standard_blend_allowed = False
            flags.append(
                f"bass conflict risk {bass_risk:.2f} breaches the shared hard limit"
            )
            penalty += 0.14
        elif bass_risk >= _PAIR_LIMITS["bass_review"]:
            review_required = True
            flags.append(f"bass conflict risk {bass_risk:.2f} is elevated")
            penalty += 0.06

    if phrase_fit is not None:
        if phrase_fit < _PAIR_LIMITS["phrase_fail"]:
            review_required = True
            flags.append(
                f"phrase alignment {phrase_fit:.2f} is too weak for a confident blend"
            )
            penalty += 0.10
        elif phrase_fit < _PAIR_LIMITS["phrase_review"]:
            review_required = True
            flags.append(f"phrase alignment {phrase_fit:.2f} needs review")
            penalty += 0.05

    if tension_fit is not None:
        if tension_fit < _PAIR_LIMITS["tension_fail"]:
            review_required = True
            flags.append(f"tension handoff {tension_fit:.2f} looks unstable")
            penalty += 0.08
        elif tension_fit < _PAIR_LIMITS["tension_review"]:
            review_required = True
            flags.append(f"tension handoff {tension_fit:.2f} needs review")
            penalty += 0.04

    return PairRuleAssessment(
        tempo_relation=relation,
        bpm_delta_pct=bpm_delta_pct,
        effective_bpm_delta_pct=effective_delta_pct,
        tempo_gate_status=tempo_gate,
        harmonic_gate_status=harmonic_gate,
        standard_blend_allowed=standard_blend_allowed and not hard_block,
        hard_block=hard_block,
        review_required=review_required or hard_block,
        penalty=round(min(penalty, 0.45), 4),
        flags=_dedupe(flags),
    )


def _cumulative_risk_limit_state(risks: list[float]) -> tuple[float, list[str], float, bool]:
    if not risks:
        return 0.0, [], 0.0, False
    cumulative = float(np.mean(risks))
    flags: list[str] = []
    penalty = 0.0
    severe = False
    if cumulative >= _RISK_LIMITS["soft"]:
        flags.append(
            f"sequence cumulative risk {cumulative:.2f} exceeds soft limit {_RISK_LIMITS['soft']:.2f}"
        )
        penalty += 0.10
    if cumulative >= _RISK_LIMITS["hard"]:
        flags.append(
            f"sequence cumulative risk {cumulative:.2f} exceeds hard limit {_RISK_LIMITS['hard']:.2f}"
        )
        penalty += 0.12
        severe = True
    if len(risks) >= 2 and all(value >= _RISK_LIMITS["consecutive_hard"] for value in risks[-2:]):
        flags.append("two consecutive high-risk transitions breach the sequence risk limit")
        penalty += 0.14
        severe = True
    return cumulative, flags, penalty, severe


def _bpm_drift_limit_state(
    effective_bpms: list[float | None],
    arc_mode: str,
) -> tuple[float | None, list[str], float, bool]:
    values = [value for value in effective_bpms if value is not None]
    if len(values) < 2:
        return None, [], 0.0, False
    base = values[0]
    if base == 0:
        return None, [], 0.0, False
    span_pct = float((max(values) - min(values)) / base)
    limit = _BPM_DRIFT_LIMITS.get((arc_mode or "build").lower(), 0.06)
    flags: list[str] = []
    penalty = 0.0
    severe = False
    if span_pct > limit:
        flags.append(f"effective BPM drift {span_pct * 100:.1f}% exceeds limit {limit * 100:.1f}%")
        penalty += 0.10
    if span_pct > limit + 0.04:
        flags.append("effective BPM drift is severe for the requested sequence arc")
        penalty += 0.12
        severe = True
    return round(span_pct * 100.0, 3), flags, penalty, severe


def _energy_region_limit_state(
    regions: list[str],
    arc_mode: str,
) -> tuple[int, str | None, list[str], float, bool]:
    if not regions:
        return 0, None, [], 0.0, False
    max_streak = 1
    current_streak = 1
    dominant_region = regions[-1]
    for previous, current in zip(regions, regions[1:]):
        if current == previous:
            current_streak += 1
        else:
            current_streak = 1
        if current_streak > max_streak:
            max_streak = current_streak
            dominant_region = current
    limit = _ENERGY_REGION_STREAK_LIMITS.get((arc_mode or "build").lower(), 3)
    if (arc_mode or "build").lower() == "peak" and dominant_region == "high":
        limit += 1
    flags: list[str] = []
    penalty = 0.0
    severe = False
    if max_streak > limit:
        flags.append(
            f"energy region streak '{dominant_region}' reached {max_streak} steps (limit {limit})"
        )
        penalty += 0.08
    if max_streak > limit + 1:
        flags.append("sequence stayed too long in one energy region")
        penalty += 0.10
        severe = True
    return max_streak, dominant_region, flags, penalty, severe


def evaluate_sequence_guardrails(
    risks: list[float],
    effective_bpms: list[float | None],
    energy_regions: list[str],
    arc_mode: str,
) -> SequenceRuleAssessment:
    cumulative_risk, risk_flags, risk_penalty, risk_severe = _cumulative_risk_limit_state(risks)
    bpm_span_pct, bpm_flags, bpm_penalty, bpm_severe = _bpm_drift_limit_state(
        effective_bpms,
        arc_mode,
    )
    max_streak, dominant_region, energy_flags, energy_penalty, energy_severe = _energy_region_limit_state(
        energy_regions,
        arc_mode,
    )
    current_streak = 1
    if energy_regions:
        for region in reversed(energy_regions[:-1]):
            if region == energy_regions[-1]:
                current_streak += 1
            else:
                break
    return SequenceRuleAssessment(
        cumulative_risk=cumulative_risk,
        bpm_span_pct=bpm_span_pct,
        max_streak=max_streak,
        current_streak=current_streak,
        dominant_region=dominant_region,
        flags=_dedupe(risk_flags + bpm_flags + energy_flags),
        penalty=risk_penalty + bpm_penalty + energy_penalty,
        severe=risk_severe or bpm_severe or energy_severe,
    )

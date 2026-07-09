"""Shared rule engine contracts."""

from dancelab.core.models import GateStatus, RecommendationPolicy
from dancelab.decision.rules import (
    evaluate_pair_policy,
    evaluate_pair_rules,
    evaluate_sequence_guardrails,
)


def test_pair_rules_flag_hard_blocks():
    out = evaluate_pair_rules(
        bpm_a=128.0,
        bpm_b=152.0,
        harmonic_risk=0.82,
        vocal_risk=0.74,
        bass_risk=0.77,
        phrase_fit=0.32,
        tension_fit=0.34,
    )

    assert out.hard_block is True
    assert out.standard_blend_allowed is False
    assert out.harmonic_gate_status == GateStatus.fail
    assert out.flags
    assert any("shared hard limit" in flag for flag in out.flags)


def test_pair_policy_suppresses_low_grounding_or_hard_block():
    pair_rules = evaluate_pair_rules(
        bpm_a=128.0,
        bpm_b=129.0,
        harmonic_risk=0.12,
        vocal_risk=0.10,
        bass_risk=0.12,
    )
    out = evaluate_pair_policy(
        confidence=0.24,
        pair_rules=pair_rules,
        harmonic_risk=0.12,
        vocal_risk=0.10,
        bass_risk=0.12,
        score_value=0.62,
    )

    assert out.recommendation_policy == RecommendationPolicy.suppress
    assert out.reasons


def test_sequence_rules_flag_cumulative_risk_bpm_drift_and_plateau():
    out = evaluate_sequence_guardrails(
        risks=[0.70, 0.74, 0.72],
        effective_bpms=[128.0, 136.0, 140.0],
        energy_regions=["mid", "mid", "mid", "mid", "mid", "mid"],
        arc_mode="flat",
    )

    assert out.severe is True
    assert out.cumulative_risk >= 0.62
    assert out.bpm_span_pct is not None
    assert out.max_streak > 4
    assert any("cumulative risk" in flag for flag in out.flags)
    assert any("BPM drift" in flag for flag in out.flags)
    assert any("energy region streak" in flag for flag in out.flags)

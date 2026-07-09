"""Sprint 3 source-grounding / no-overclaiming layer.

Every decision output must carry a provenance block traceable to a model card,
must be to_validate (nothing is validated yet), must list cannot_claim, and must
be graded no higher than E4 (Evidence Grading Standard cap)."""

import pytest

from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    EvidenceGrade,
    FeatureFrame,
    MixabilityInput,
    ScientificStatus,
    SetFunctionInput,
    Track,
    TransitionWindowInput,
    ValidationStatus,
)
from dancelab.core.provenance import (
    get_model_card,
    guardrail_warnings,
    load_model_cards,
)
from dancelab.context.conditioning import evaluate_context
from dancelab.decision.edge_decision import build_edge_decision
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.next_track import recommend_next
from dancelab.decision.sequence import recommend_sequence
from dancelab.decision.set_function import classify_set_function
from dancelab.decision.transition_windows import detect_transition_windows

ENGINE_KEYS = [
    "transition_windows",
    "transition_strategy",
    "mixability",
    "edge_decision",
    "set_function",
    "context_evaluation",
    "next_track",
    "sequence",
    "stem_aware_layer",
    "set_builder",
    "harmonic",
]


@pytest.fixture
def weights():
    return load_weights("configs/descriptor_weights.yaml")


def make_analysis(tid, n=40, bpm=128):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=tid, bpm_estimate=bpm),
        features=[FeatureFrame(track_id=tid, timestamp_sec=float(t), rms=0.3,
                               spectral_flux=10.0, bass_energy=50.0,
                               low_freq_energy_ratio=0.5) for t in range(n)],
    )


# --------------------------------------------------------------- model cards


def test_all_engines_have_a_card():
    cards = load_model_cards("configs/model_cards.yaml")
    assert set(cards) == set(ENGINE_KEYS)


def test_cards_capped_at_e4_and_to_validate():
    for key in ENGINE_KEYS:
        c = get_model_card(key)
        assert c.evidence_grade == EvidenceGrade.E4  # Sprint 3 honesty cap
        assert c.validation_status == ValidationStatus.to_validate
        assert c.cannot_claim, "every card must list prohibited claims"
        assert c.required_validation and c.source_basis


def test_e5_e6_card_is_rejected(tmp_path):
    from dancelab.core.errors import ConfigError
    bad = tmp_path / "cards.yaml"
    bad.write_text(
        "version: '0.1.0'\ncards:\n  x:\n    model_card_id: x\n    model_version: v\n"
        "    intended_use: u\n    scientific_status: candidate\n    evidence_grade: E6\n"
        "    validation_status: to_validate\n"
    )
    load_model_cards.cache_clear()
    with pytest.raises(ConfigError, match="without a pilot"):
        load_model_cards(str(bad))
    load_model_cards.cache_clear()


# --------------------------------------------------------- provenance on outputs


def test_transition_windows_carry_provenance(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_analysis("t1").features),
        weights.transition_window,
    )
    p = out.provenance
    assert p is not None
    assert p.model_card_id == "transition_window_model_card_v0.1"
    assert p.validation_status == ValidationStatus.to_validate
    assert p.scientific_status == ScientificStatus.candidate
    assert "best transition point" in p.cannot_claim
    assert p.required_validation


def test_mixability_carries_provenance(weights):
    out = compute_mixability(
        MixabilityInput(track_a=make_analysis("a"), track_b=make_analysis("b")),
        weights.mixability, weights.mixability_conflict,
    )
    assert out.provenance.model_card_id == "mixability_model_card_v0.1"
    assert "this transition will work" in out.provenance.cannot_claim


def test_set_function_carries_provenance():
    out = classify_set_function(SetFunctionInput(track_analysis=make_analysis("t1", n=300)))
    assert out.provenance.model_card_id == "set_function_model_card_v0.1"
    assert out.provenance.evidence_grade == EvidenceGrade.E4


def test_context_evaluation_carries_provenance():
    out = evaluate_context(
        make_analysis("ctx", n=120),
        ContextProfile(context_id="club_peak", set_role="peak", venue_type="club"),
    )
    assert out.provenance.model_card_id == "context_evaluation_model_card_v0.1"
    assert "crowd reaction" in " ".join(out.provenance.cannot_claim)


def test_next_track_carries_provenance(weights):
    out = recommend_next(
        current=make_analysis("current", n=120, bpm=128),
        candidates=[make_analysis("cand", n=120, bpm=129)],
        context=ContextProfile(context_id="club_peak", set_role="peak", venue_type="club"),
        weights=weights,
    )
    assert out.provenance.model_card_id == "next_track_model_card_v0.1"
    assert out.ranking


def test_sequence_carries_provenance(weights):
    out = recommend_sequence(
        current=make_analysis("current", n=120, bpm=128),
        candidates=[
            make_analysis("cand1", n=120, bpm=129),
            make_analysis("cand2", n=120, bpm=130),
        ],
        context=ContextProfile(context_id="club_peak", set_role="peak", venue_type="club"),
        weights=weights,
        horizon=2,
    )
    assert out.provenance.model_card_id == "sequence_model_card_v0.1"
    assert out.sequence_track_ids


def test_edge_decision_carries_provenance(weights):
    out = build_edge_decision(
        make_analysis("a", n=120, bpm=128),
        make_analysis("b", n=120, bpm=129),
        weights,
        context=ContextProfile(context_id="club_peak", set_role="peak", venue_type="club"),
    )
    assert out.provenance.model_card_id == "edge_decision_model_card_v0.1"
    assert out.recommended_transition_strategy.value


def test_short_track_output_still_carries_provenance(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=[]), weights.transition_window
    )
    assert out.windows == [] and out.provenance is not None


# ------------------------------------------------------------- guardrail warnings


def test_guardrail_warnings_missing_inputs():
    w = guardrail_warnings(has_beatgrid=False, has_context=False, dj_validated=False)
    assert any("no beatgrid" in x for x in w)
    assert any("no context" in x for x in w)
    assert any("not DJ-validated" in x for x in w)


def test_guardrail_high_risk_and_low_grounding():
    w = guardrail_warnings(source_grounding=0.2, risk_score=0.9)
    assert any("low source grounding" in x for x in w)
    assert any("high risk" in x for x in w)


def test_no_beatgrid_triggers_warning_in_transition_windows(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_analysis("t1").features,
                              beatgrid=None),
        weights.transition_window,
    )
    assert any("no beatgrid" in w for w in out.warnings)
    assert any("not DJ-validated" in w for w in out.warnings)


# ------------------------------------------------------------------ API endpoint


def test_model_cards_endpoint():
    from fastapi.testclient import TestClient
    from dancelab.api.main import app

    body = TestClient(app).get("/model-cards").json()
    assert set(body) == set(ENGINE_KEYS)
    assert body["mixability"]["evidence_grade"] == "E4"
    assert body["mixability"]["cannot_claim"]

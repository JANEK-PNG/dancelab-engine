"""Unified edge decision contracts."""

from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    BlendProfile,
    ContextProfile,
    DecisionClass,
    FeatureFrame,
    Track,
)
from dancelab.decision.edge_decision import MODEL_VERSION, build_edge_decision
from dancelab.storage.repositories import FileAnalysisRepository


def make_analysis(track_id, bpm, camelot, rms=0.42, vocal=0.1, lfer=0.48, style="techno", n=90):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=track_id,
            bpm_estimate=bpm,
            key_estimate=camelot,
            key_confidence=0.9,
            style_label=style,
        ),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=rms,
                low_freq_energy_ratio=lfer,
                vocal_density_proxy=vocal,
                spectral_flux=10.0,
                bass_energy=45.0,
            )
            for t in range(n)
        ],
    )


def test_build_edge_decision_returns_unified_payload():
    weights = load_weights("configs/descriptor_weights.yaml")
    a = make_analysis("a", 128, "8A", rms=0.42)
    b = make_analysis("b", 129, "9A", rms=0.47)
    context = ContextProfile(context_id="festival_daytime", venue_type="festival", set_role="builder", style_focus=["techno"])
    out = build_edge_decision(a, b, weights, context=context)

    assert out.model_version == MODEL_VERSION
    assert out.provenance.model_card_id == "edge_decision_model_card_v0.1"
    assert out.selected_pair_window is not None
    assert out.recommended_transition_strategy.value
    assert out.blend_profile_auto == BlendProfile.bass_swap
    assert out.blend_profile_explanation
    assert out.core_dj_compatibility_score.value >= 0
    assert out.annotation_payload["pair_id"] == "a__b"
    assert out.annotation_payload["track_id_a"] == "a"
    assert out.annotation_payload["track_id_b"] == "b"
    assert out.annotation_payload["blend_profile_auto"] == BlendProfile.bass_swap.value


def test_edge_decision_surfaces_shared_rule_hard_block():
    weights = load_weights("configs/descriptor_weights.yaml")
    a = make_analysis("a", 128, "8A", rms=0.42, vocal=0.45, lfer=0.78, style="techno")
    b = make_analysis("b", 150, "3B", rms=0.82, vocal=0.78, lfer=0.81, style="trance")
    out = build_edge_decision(a, b, weights)

    assert out.hard_block is True
    assert out.decision_class == DecisionClass.reject_standard_blend
    assert out.rule_flags


def test_api_edge_decision_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(make_analysis("a", 128, "8A"))
    repo.save(make_analysis("b", 129, "9A"))

    client = TestClient(app)
    r = client.post(
        "/pairs/edge-decision",
        json={
            "track_id_a": "a",
            "track_id_b": "b",
            "context_profile": {
                "context_id": "festival_daytime",
                "venue_type": "festival",
                "set_role": "builder",
                "style_focus": ["techno"],
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == MODEL_VERSION
    assert body["recommended_transition_strategy"]
    assert body["blend_profile_auto"]
    assert body["blend_profile_explanation"]
    assert body["provenance"]["model_card_id"] == "edge_decision_model_card_v0.1"

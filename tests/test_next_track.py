"""Next-track ranking contracts."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    FeatureFrame,
    SetFunction,
    Track,
)
from dancelab.decision.next_track import MODEL_VERSION, recommend_next
from dancelab.storage.repositories import FileAnalysisRepository


def make_analysis(track_id, camelot, bpm, rms, lfer=0.55, vocal=0.12, style="techno", n=90):
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
                bass_energy=50.0,
            )
            for t in range(n)
        ],
    )


def test_recommend_next_prefers_harmonic_gentle_builder_step():
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.42, lfer=0.55, style="techno")
    candidate_good = make_analysis("good", "9A", 129, 0.48, lfer=0.58, style="techno")
    candidate_bad = make_analysis("bad", "3B", 138, 0.86, lfer=0.72, vocal=0.6, style="trance")
    context = ContextProfile(context_id="festival_daytime", venue_type="festival", set_role="builder", style_focus=["techno"])

    out = recommend_next(current, [candidate_bad, candidate_good], context=context, weights=weights)

    assert out.model_version == MODEL_VERSION
    assert out.provenance.model_card_id == "next_track_model_card_v0.1"
    assert out.ranking[0].track_id == "good"
    assert out.recommendation_policy.value in {"allow", "review_only"}
    bad_visible = next((candidate for candidate in out.ranking if candidate.track_id == "bad"), None)
    if bad_visible is not None:
        assert bad_visible.recommendation_policy.value == "review_only"
    else:
        assert "bad" in out.suppressed_track_ids


def test_api_recommend_next_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(make_analysis("current", "8A", 128, 0.42))
    repo.save(make_analysis("good", "9A", 129, 0.48))
    repo.save(make_analysis("bad", "3B", 138, 0.86, vocal=0.6, style="trance"))

    client = TestClient(app)
    r = client.post(
        "/sets/recommend-next",
        json={
            "current_track_id": "current",
            "candidate_track_ids": ["good", "bad"],
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
    assert body["ranking"][0]["track_id"] == "good"
    bad_visible = next((candidate for candidate in body["ranking"] if candidate["track_id"] == "bad"), None)
    if bad_visible is not None:
        assert bad_visible["recommendation_policy"] == "review_only"
    else:
        assert "bad" in body["suppressed_track_ids"]
    assert body["provenance"]["model_card_id"] == "next_track_model_card_v0.1"


def test_recommend_next_removes_recent_history_from_pool():
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.42)
    recent = make_analysis("recent", "9A", 129, 0.46)
    fresh = make_analysis("fresh", "9A", 129, 0.47)

    out = recommend_next(
        current,
        [recent, fresh],
        weights=weights,
        recent_history=[recent],
        arc_mode="build",
    )

    assert out.arc_mode == "build"
    assert out.recent_history_track_ids == ["recent"]
    assert [candidate.track_id for candidate in out.ranking] == ["fresh"]
    assert any("recent-history tracks were removed" in warning for warning in out.warnings)


def test_recommend_next_uses_history_signals_beyond_pair_score(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    history_a = make_analysis("history_a", "7A", 126, 0.30)
    history_b = make_analysis("history_b", "8A", 127, 0.35)
    current = make_analysis("current", "8A", 128, 0.40)
    smooth = make_analysis("smooth", "9A", 129, 0.46)
    jumpy = make_analysis("jumpy", "3B", 138, 0.82, vocal=0.5, style="trance")

    monkeypatch.setattr(
        "dancelab.decision.next_track.detect_transition_windows",
        lambda *args, **kwargs: SimpleNamespace(windows=[]),
    )
    monkeypatch.setattr(
        "dancelab.decision.next_track.track_context_score",
        lambda *args, **kwargs: SimpleNamespace(value=0.5, confidence=0.5, warnings=[]),
    )

    def fake_mixability(input_obj, *args, **kwargs):
        score = 0.81 if input_obj.track_b.track.track_id == "jumpy" else 0.76
        return SimpleNamespace(
            mixability_score=score,
            confidence=0.8,
            risks=[],
            warnings=[],
            harmonic_risk=0.15,
            vocal_clash_risk=0.15,
            bass_conflict_risk=0.15,
        )

    def fake_set_function(input_obj):
        role = SetFunction.peak if input_obj.track_analysis.track.track_id == "jumpy" else SetFunction.builder
        return SimpleNamespace(
            primary_function=role,
            context_fit=0.7 if role == SetFunction.builder else 0.45,
            confidence=0.85,
        )

    monkeypatch.setattr("dancelab.decision.next_track.compute_mixability", fake_mixability)
    monkeypatch.setattr("dancelab.decision.next_track.classify_set_function", fake_set_function)

    out = recommend_next(
        current=current,
        candidates=[jumpy, smooth],
        context=ContextProfile(context_id="festival_daytime", venue_type="festival", set_role="builder"),
        weights=weights,
        recent_history=[history_a, history_b],
        arc_mode="build",
    )

    assert out.ranking[0].track_id == "smooth"
    assert out.ranking[0].score.value >= out.ranking[1].score.value
    assert "history energy arc" in out.ranking[0].score.explanation


def test_recommend_next_downranks_shared_rule_hard_block(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.40)
    safe = make_analysis("safe", "9A", 129, 0.47)
    blocked = make_analysis("blocked", "3B", 138, 0.48, vocal=0.55, style="trance")

    monkeypatch.setattr(
        "dancelab.decision.next_track.detect_transition_windows",
        lambda *args, **kwargs: SimpleNamespace(windows=[]),
    )
    monkeypatch.setattr(
        "dancelab.decision.next_track.track_context_score",
        lambda *args, **kwargs: SimpleNamespace(value=0.5, confidence=0.5, warnings=[]),
    )
    monkeypatch.setattr(
        "dancelab.decision.next_track.classify_set_function",
        lambda input_obj: SimpleNamespace(
            primary_function=SetFunction.builder,
            context_fit=0.75,
            confidence=0.85,
        ),
    )

    def fake_mixability(input_obj, *args, **kwargs):
        if input_obj.track_b.track.track_id == "blocked":
            return SimpleNamespace(
                mixability_score=0.89,
                confidence=0.82,
                risks=[],
                warnings=[],
                harmonic_risk=0.82,
                vocal_clash_risk=0.72,
                bass_conflict_risk=0.74,
                rule_flags=["harmonic clash risk 0.82 breaches the shared hard limit"],
                rule_penalty=0.36,
                hard_block=True,
            )
        return SimpleNamespace(
            mixability_score=0.74,
            confidence=0.82,
            risks=[],
            warnings=[],
            harmonic_risk=0.12,
            vocal_clash_risk=0.15,
            bass_conflict_risk=0.20,
            rule_flags=[],
            rule_penalty=0.0,
            hard_block=False,
        )

    monkeypatch.setattr("dancelab.decision.next_track.compute_mixability", fake_mixability)

    out = recommend_next(
        current=current,
        candidates=[blocked, safe],
        context=ContextProfile(context_id="festival_daytime", venue_type="festival", set_role="builder"),
        weights=weights,
    )

    assert out.ranking[0].track_id == "safe"
    assert out.suppressed_track_ids == ["blocked"]
    assert all(candidate.track_id != "blocked" for candidate in out.ranking)

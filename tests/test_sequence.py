"""Phase 3 sequence planner contracts."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    DecisionClass,
    FeatureFrame,
    ModelStatus,
    NextTrackCandidate,
    NextTrackRecommendation,
    RecommendationPolicy,
    ScoredOutput,
    Track,
    TransitionStrategy,
)
from dancelab.decision.sequence import (
    MODEL_VERSION,
    _lookahead_arc_score,
    _set_memory_score,
    recommend_sequence,
)
from dancelab.storage.repositories import FileAnalysisRepository


def make_analysis(
    track_id,
    camelot,
    bpm,
    rms,
    lfer=0.55,
    vocal=0.12,
    style="techno",
    n=90,
    tension=0.42,
    release=0.18,
):
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
                tension_proxy=tension,
                release_proxy=release,
            )
            for t in range(n)
        ],
    )


def test_recommend_sequence_returns_short_chain():
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.42)
    history = [
        make_analysis("prev1", "7A", 127, 0.34),
        make_analysis("prev2", "8A", 128, 0.38),
    ]
    candidates = [
        make_analysis("next1", "9A", 129, 0.48),
        make_analysis("next2", "10A", 130, 0.53),
        make_analysis("bad", "3B", 138, 0.82, vocal=0.6, style="trance"),
    ]
    context = ContextProfile(
        context_id="festival_daytime",
        venue_type="festival",
        set_role="builder",
        style_focus=["techno"],
    )

    out = recommend_sequence(
        current=current,
        candidates=candidates,
        context=context,
        weights=weights,
        recent_history=history,
        arc_mode="build",
        horizon=2,
    )

    assert out.model_version == MODEL_VERSION
    assert out.provenance.model_card_id == "sequence_model_card_v0.1"
    assert out.sequence_track_ids[0] == "current"
    assert len(out.steps) == 2
    assert out.steps[0].to_track_id == "next1"
    assert out.steps[1].to_track_id == "next2"
    assert out.lookahead_arc_score is not None
    assert out.terminal_arc_score is not None
    assert out.set_memory_score is not None
    assert out.steps[0].lookahead_arc_score is not None
    assert out.steps[0].terminal_arc_score is not None
    assert out.steps[0].set_memory_score is not None


def test_api_recommend_sequence_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(make_analysis("prev1", "7A", 127, 0.34))
    repo.save(make_analysis("current", "8A", 128, 0.42))
    repo.save(make_analysis("next1", "9A", 129, 0.48))
    repo.save(make_analysis("next2", "10A", 130, 0.53))
    repo.save(make_analysis("bad", "3B", 138, 0.82, vocal=0.6, style="trance"))

    client = TestClient(app)
    r = client.post(
        "/sets/recommend-sequence",
        json={
            "current_track_id": "current",
            "candidate_track_ids": ["next1", "next2", "bad"],
            "recent_track_ids": ["prev1"],
            "arc_mode": "build",
            "horizon": 2,
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
    assert body["sequence_track_ids"][:2] == ["current", "next1"]
    assert body["provenance"]["model_card_id"] == "sequence_model_card_v0.1"


def test_api_recommend_sequence_accepts_longer_horizon(monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(make_analysis("prev1", "7A", 127, 0.34))
    repo.save(make_analysis("current", "8A", 128, 0.42))
    for index in range(1, 7):
        repo.save(make_analysis(f"next{index}", f"{8 + index}A", 128 + index, 0.42 + 0.04 * index))

    client = TestClient(app)
    r = client.post(
        "/sets/recommend-sequence",
        json={
            "current_track_id": "current",
            "candidate_track_ids": [f"next{index}" for index in range(1, 7)],
            "recent_track_ids": ["prev1"],
            "arc_mode": "build",
            "horizon": 6,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["horizon"] == 6
    assert len(body["sequence_track_ids"]) == 7


def test_recommend_sequence_prefers_global_arc_over_greedy_top1(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.40)
    candidate_a = make_analysis("A", "9A", 129, 0.52)
    candidate_b = make_analysis("B", "8A", 128, 0.46)
    candidate_c = make_analysis("C", "10A", 130, 0.78)

    def fake_recommend_next(current, candidates, **kwargs):
        mapping = {
            "current": [("C", 0.84), ("A", 0.80), ("B", 0.55)],
            "A": [("C", 0.88), ("B", 0.52)],
            "C": [("A", 0.60), ("B", 0.58)],
            "B": [("A", 0.58), ("C", 0.56)],
        }
        ranking = [
            NextTrackCandidate(
                track_id=track_id,
                rank=index,
                score=ScoredOutput(
                    value=score,
                    status=ModelStatus.candidate,
                    confidence=0.82,
                    explanation=f"fake {current.track.track_id}->{track_id}",
                ),
                risk_flags=[],
            )
            for index, (track_id, score) in enumerate(mapping[current.track.track_id], start=1)
            if track_id in {candidate.track.track_id for candidate in candidates}
        ]
        return NextTrackRecommendation(
            current_track_id=current.track.track_id,
            arc_mode=kwargs.get("arc_mode", "build"),
            recent_history_track_ids=[track.track.track_id for track in kwargs.get("recent_history", [])],
            ranking=ranking,
            warnings=[],
            provenance=None,
        )

    def fake_build_edge_decision(track_a, track_b, weights, **kwargs):
        return SimpleNamespace(
            decision_class=DecisionClass.strong_candidate,
            recommended_transition_strategy=TransitionStrategy.standard_blend,
            risks=[],
            warnings=[],
            core_dj_compatibility_score=SimpleNamespace(value=0.9),
            harmonic_risk=0.1,
            bass_conflict_risk=0.1,
            vocal_clash_risk=0.1,
        )

    monkeypatch.setattr("dancelab.decision.sequence.recommend_next", fake_recommend_next)
    monkeypatch.setattr("dancelab.decision.sequence.build_edge_decision", fake_build_edge_decision)

    out = recommend_sequence(
        current=current,
        candidates=[candidate_a, candidate_b, candidate_c],
        context=ContextProfile(context_id="festival_daytime", set_role="builder", venue_type="festival"),
        weights=weights,
        horizon=2,
        arc_mode="build",
    )

    assert out.sequence_track_ids == ["current", "A", "C"]
    assert out.local_arc_score is not None and out.global_arc_score is not None
    assert out.steps[0].pair_score == 0.8
    assert out.steps[0].global_arc_score > 0.8
    assert "global arc" in out.steps[0].score.explanation


def test_recommend_sequence_guardrails_flag_cumulative_risk_and_bpm_drift(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.40)
    candidate_a = make_analysis("A", "9A", 136, 0.52)
    candidate_b = make_analysis("B", "10A", 144, 0.60)

    def fake_recommend_next(current, candidates, **kwargs):
        ranking = [
            NextTrackCandidate(
                track_id=candidate.track.track_id,
                rank=index,
                score=ScoredOutput(
                    value=0.82 - 0.01 * index,
                    status=ModelStatus.candidate,
                    confidence=0.8,
                    explanation=f"fake {current.track.track_id}->{candidate.track.track_id}",
                ),
                risk_flags=["pair risk"],
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        return NextTrackRecommendation(
            current_track_id=current.track.track_id,
            arc_mode=kwargs.get("arc_mode", "build"),
            recent_history_track_ids=[track.track.track_id for track in kwargs.get("recent_history", [])],
            ranking=ranking,
            warnings=[],
            provenance=None,
        )

    def fake_build_edge_decision(track_a, track_b, weights, **kwargs):
        return SimpleNamespace(
            decision_class=DecisionClass.reject_standard_blend,
            recommended_transition_strategy=TransitionStrategy.hard_cut,
            risks=["high overlap", "timing risk"],
            warnings=[],
            core_dj_compatibility_score=SimpleNamespace(value=0.42),
            harmonic_risk=0.82,
            bass_conflict_risk=0.78,
            vocal_clash_risk=0.74,
        )

    monkeypatch.setattr("dancelab.decision.sequence.recommend_next", fake_recommend_next)
    monkeypatch.setattr("dancelab.decision.sequence.build_edge_decision", fake_build_edge_decision)

    out = recommend_sequence(
        current=current,
        candidates=[candidate_a, candidate_b],
        weights=weights,
        horizon=2,
        arc_mode="build",
    )

    assert out.cumulative_risk_score is not None and out.cumulative_risk_score >= 0.6
    assert out.effective_bpm_span_pct is not None and out.effective_bpm_span_pct > 6.0
    assert any("cumulative risk" in flag for flag in out.guardrail_flags)
    assert any("BPM drift" in flag for flag in out.guardrail_flags)
    assert any(step.guardrail_flags for step in out.steps)


def test_recommend_sequence_guardrails_flag_energy_plateau(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.42)
    candidate_a = make_analysis("A", "9A", 129, 0.44)
    candidate_b = make_analysis("B", "10A", 130, 0.45)
    candidate_c = make_analysis("C", "11A", 131, 0.46)
    candidate_d = make_analysis("D", "12A", 132, 0.90)

    def fake_recommend_next(current, candidates, **kwargs):
        ranking = [
            NextTrackCandidate(
                track_id=candidate.track.track_id,
                rank=index,
                score=ScoredOutput(
                    value=0.78 - 0.01 * index,
                    status=ModelStatus.candidate,
                    confidence=0.82,
                    explanation=f"fake {current.track.track_id}->{candidate.track.track_id}",
                ),
                risk_flags=[],
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        return NextTrackRecommendation(
            current_track_id=current.track.track_id,
            arc_mode=kwargs.get("arc_mode", "build"),
            recent_history_track_ids=[track.track.track_id for track in kwargs.get("recent_history", [])],
            ranking=ranking,
            warnings=[],
            provenance=None,
        )

    def fake_build_edge_decision(track_a, track_b, weights, **kwargs):
        return SimpleNamespace(
            decision_class=DecisionClass.strong_candidate,
            recommended_transition_strategy=TransitionStrategy.standard_blend,
            risks=[],
            warnings=[],
            core_dj_compatibility_score=SimpleNamespace(value=0.9),
            harmonic_risk=0.10,
            bass_conflict_risk=0.10,
            vocal_clash_risk=0.10,
        )

    monkeypatch.setattr("dancelab.decision.sequence.recommend_next", fake_recommend_next)
    monkeypatch.setattr("dancelab.decision.sequence.build_edge_decision", fake_build_edge_decision)

    out = recommend_sequence(
        current=current,
        candidates=[candidate_a, candidate_b, candidate_c, candidate_d],
        weights=weights,
        horizon=3,
        arc_mode="build",
    )

    assert out.max_energy_region_streak is not None and out.max_energy_region_streak >= 3
    assert any("energy region streak" in flag for flag in out.guardrail_flags)
    assert any(step.energy_region_streak and step.energy_region_streak >= 3 for step in out.steps)


def test_recommend_sequence_skips_suppressed_transitions(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    current = make_analysis("current", "8A", 128, 0.40)
    safe = make_analysis("safe", "9A", 129, 0.48)
    blocked = make_analysis("blocked", "3B", 142, 0.70)

    def fake_recommend_next(current, candidates, **kwargs):
        ranking = []
        for index, candidate in enumerate(candidates, start=1):
            if candidate.track.track_id == "blocked":
                ranking.append(
                    NextTrackCandidate(
                        track_id="blocked",
                        rank=index,
                        score=ScoredOutput(
                            value=0.92,
                            status=ModelStatus.candidate,
                            confidence=0.84,
                            explanation="blocked candidate",
                        ),
                        hard_block=True,
                        recommendation_policy=RecommendationPolicy.suppress,
                        policy_reasons=["shared hard block"],
                    )
                )
            else:
                ranking.append(
                    NextTrackCandidate(
                        track_id="safe",
                        rank=index,
                        score=ScoredOutput(
                            value=0.78,
                            status=ModelStatus.candidate,
                            confidence=0.84,
                            explanation="safe candidate",
                        ),
                        recommendation_policy=RecommendationPolicy.allow,
                    )
                )
        return NextTrackRecommendation(
            current_track_id=current.track.track_id,
            arc_mode=kwargs.get("arc_mode", "build"),
            recent_history_track_ids=[track.track.track_id for track in kwargs.get("recent_history", [])],
            ranking=ranking,
            warnings=[],
            provenance=None,
        )

    def fake_build_edge_decision(track_a, track_b, weights, **kwargs):
        return SimpleNamespace(
            decision_class=DecisionClass.strong_candidate,
            recommended_transition_strategy=TransitionStrategy.standard_blend,
            risks=[],
            warnings=[],
            core_dj_compatibility_score=SimpleNamespace(value=0.88),
            harmonic_risk=0.10,
            bass_conflict_risk=0.10,
            vocal_clash_risk=0.10,
            hard_block=False,
            policy_reasons=[],
        )

    monkeypatch.setattr("dancelab.decision.sequence.recommend_next", fake_recommend_next)
    monkeypatch.setattr("dancelab.decision.sequence.build_edge_decision", fake_build_edge_decision)

    out = recommend_sequence(
        current=current,
        candidates=[blocked, safe],
        weights=weights,
        horizon=1,
        arc_mode="build",
    )

    assert out.sequence_track_ids == ["current", "safe"]
    assert out.suppressed_transition_count >= 1


def test_lookahead_arc_score_prefers_preserving_future_headroom():
    greedy_high = make_analysis("greedy_high", "9A", 129, 0.62)
    future_low = make_analysis("future_low", "10A", 130, 0.48)
    future_mid = make_analysis("future_mid", "11A", 131, 0.60)
    future_high = make_analysis("future_high", "12A", 132, 0.86)

    target_profile_norm = [0.0, 0.18, 0.48, 0.92]
    e_min = 0.40
    e_range = 0.46

    greedy_score, greedy_terminal = _lookahead_arc_score(
        [0.40, 0.62],
        [future_low, future_mid],
        target_profile_norm,
        e_min,
        e_range,
        "peak",
    )
    preserved_score, preserved_terminal = _lookahead_arc_score(
        [0.40, 0.48],
        [greedy_high, future_high],
        target_profile_norm,
        e_min,
        e_range,
        "peak",
    )

    assert preserved_score > greedy_score
    assert preserved_terminal > greedy_terminal


def test_set_memory_score_prefers_role_and_tension_progression(monkeypatch):
    weights = load_weights("configs/descriptor_weights.yaml")
    context = ContextProfile(
        context_id="festival_daytime",
        venue_type="festival",
        set_role="builder",
        style_focus=["techno"],
    )
    history = [
        make_analysis("prev1", "7A", 126, 0.32, tension=0.24, release=0.10),
        make_analysis("prev2", "8A", 127, 0.36, tension=0.33, release=0.12),
    ]
    current = make_analysis("current", "8A", 128, 0.42, tension=0.43, release=0.14)
    build_fit = make_analysis("build_fit", "9A", 129, 0.48, tension=0.56, release=0.12)
    reset_like = make_analysis("reset_like", "9A", 129, 0.48, tension=0.21, release=0.48)
    role_map = {
        "prev1": "opener",
        "prev2": "builder",
        "current": "builder",
        "build_fit": "bridge",
        "reset_like": "reset",
    }

    monkeypatch.setattr(
        "dancelab.decision.sequence._classify_set_function_label",
        lambda analysis, context, weights, role_cache, top_k=3: role_map[analysis.track.track_id],
    )

    build_score, _ = _set_memory_score(
        current,
        build_fit,
        history,
        context,
        "build",
        weights,
        {},
    )
    reset_score, _ = _set_memory_score(
        current,
        reset_like,
        history,
        context,
        "build",
        weights,
        {},
    )

    assert build_score > reset_score

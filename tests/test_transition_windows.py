"""Transition Windows Engine v0.1 — tests per Engineering Ticket:
scoring unit, TopK localmax, JSON schema, API endpoint, edge cases
(no beatgrid, very short track, continuous vocal)."""

import json
from pathlib import Path

import numpy as np
import pytest

from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    ContextProfile,
    FeatureFrame,
    Segment,
    Track,
    TransitionWindowInput,
    TransitionWindowOutput,
    WindowType,
)
from dancelab.decision.transition_windows import (
    MODEL_VERSION,
    detect_transition_windows,
    local_maxima,
    score_transition,
    top_k_windows,
)


@pytest.fixture
def weights():
    return load_weights("configs/descriptor_weights.yaml").transition_window


def make_frames(n=60, vocal=None, tension=None):
    """Synthetic frames: bass dips around t=40..44 → expected best window there."""
    frames = []
    for t in range(n):
        bass = 100.0 if not (40 <= t <= 44) else 5.0
        frames.append(
            FeatureFrame(
                track_id="t1",
                timestamp_sec=float(t),
                rms=0.3,
                spectral_flux=10.0,
                bass_energy=bass,
                vocal_density_proxy=vocal,
                tension_proxy=tension,
            )
        )
    return frames


# ------------------------------------------------------------------ scoring unit


def test_score_transition_weighted_sum(weights):
    n = 5
    comps = {name: np.full(n, 1.0) for name in
             ("structural", "rhythm", "energy", "phrase", "bass", "vocal_risk", "tension_conflict")}
    w = weights.weights
    expected = (w["structural"] + w["rhythm"] + w["energy"] + w["phrase"] + w["bass"]
                - w["vocal_risk"] - w["tension_conflict"])
    assert np.allclose(score_transition(comps, weights), expected)


def test_penalties_reduce_score(weights):
    n = 5
    base = {name: np.full(n, 0.5) for name in
            ("structural", "rhythm", "energy", "phrase", "bass")}
    clean = dict(base, vocal_risk=np.zeros(n), tension_conflict=np.zeros(n))
    vocal = dict(base, vocal_risk=np.ones(n), tension_conflict=np.zeros(n))
    assert score_transition(vocal, weights).mean() < score_transition(clean, weights).mean()


# ------------------------------------------------------------- TopK local maxima


def test_local_maxima_simple():
    s = np.array([0.0, 1.0, 0.0, 2.0, 0.0, 3.0, 0.0])
    assert list(local_maxima(s)) == [1, 3, 5]


def test_local_maxima_excludes_endpoints_and_short_input():
    assert len(local_maxima(np.array([3.0, 1.0]))) == 0
    assert list(local_maxima(np.array([5.0, 1.0, 0.5]))) == []  # peak at endpoint ignored


def test_top_k_orders_by_score():
    s = np.array([0.0, 1.0, 0.0, 3.0, 0.0, 2.0, 0.0])
    t = np.arange(7, dtype=float)
    wins = top_k_windows(s, t, k=2, half_width_sec=1.0)
    assert [w[0] for w in wins] == [3, 5]  # best first
    assert wins[0][1] == 2.0 and wins[0][2] == 4.0  # ±1 s around peak


# ------------------------------------------------------------------- end-to-end


def test_detect_finds_bass_dip_window(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames()), weights
    )
    assert out.model_version == MODEL_VERSION
    assert out.windows, "expected at least one window"
    best = out.windows[0]
    assert best.start_sec <= 42 <= best.end_sec  # window contains the bass dip center
    assert best.risk_score is not None and best.confidence is not None
    assert best.reasoning, "reasoning is mandatory (ticket DoD)"
    assert best.recommended_strategies


def test_window_type_position_heuristic(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames()), weights
    )
    best = out.windows[0]  # peak at ~42s of 59s → last third → mix_out
    assert best.window_type == WindowType.mix_out


def test_segments_boost_boundary_scores(weights):
    frames = make_frames()
    seg = [Segment(segment_id="s1", track_id="t1", start_sec=0, end_sec=42.0,
                   segment_type="build"),
           Segment(segment_id="s2", track_id="t1", start_sec=42.0, end_sec=59.0,
                   segment_type="outro")]
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=frames, segments=seg), weights
    )
    assert not any("structural component unavailable" in w for w in out.warnings)


# -------------------------------------------------------------------- edge cases


def test_edge_no_beatgrid_warns_but_works(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames()), weights
    )
    assert any("no beatgrid" in w for w in out.warnings)
    assert out.windows


def test_edge_beatgrid_enables_phrase_component(weights):
    bg = BeatGrid(bpm=120.0, beat_times_sec=[i * 0.5 for i in range(120)])
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames(), beatgrid=bg),
        weights,
    )
    assert not any("phrase component unavailable" in w for w in out.warnings)


def test_segments_enable_phrase_fallback_without_beatgrid(weights):
    out = detect_transition_windows(
        TransitionWindowInput(
            track_id="t1",
            feature_frames=make_frames(),
            segments=[
                Segment(segment_id="s1", track_id="t1", start_sec=0.0, end_sec=16.0, segment_type="build"),
                Segment(segment_id="s2", track_id="t1", start_sec=16.0, end_sec=32.0, segment_type="groove"),
                Segment(segment_id="s3", track_id="t1", start_sec=32.0, end_sec=59.0, segment_type="outro"),
            ],
        ),
        weights,
    )
    assert any("segment-boundary fallback" in warning for warning in out.warnings)
    assert not any("phrase component unavailable" in warning for warning in out.warnings)


def test_edge_very_short_track(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames(n=2)), weights
    )
    assert out.windows == []
    assert any("too short" in w for w in out.warnings)


def test_edge_continuous_vocal_raises_risk(weights):
    quiet = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames(vocal=0.0)), weights
    )
    vocal = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames(vocal=0.9)), weights
    )
    assert vocal.windows[0].risk_score > quiet.windows[0].risk_score
    assert any("high vocal density" in w for w in vocal.windows[0].warnings)
    assert "echo_out" in [s.value for s in vocal.windows[0].recommended_strategies]


def test_compatible_contexts_are_inferred_from_window_profile(weights):
    out = detect_transition_windows(
        TransitionWindowInput(
            track_id="t1",
            feature_frames=make_frames(),
            available_contexts=[
                ContextProfile(context_id="club_peak", set_role="peak"),
                ContextProfile(context_id="club_opening", set_role="opener"),
                ContextProfile(context_id="festival_daytime", set_role="builder"),
            ],
        ),
        weights,
    )
    assert out.windows[0].compatible_contexts
    assert "club_peak" in out.windows[0].compatible_contexts


# ------------------------------------------------------------------ JSON schema


def test_output_json_roundtrip(weights):
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=make_frames()), weights
    )
    again = TransitionWindowOutput.model_validate_json(out.model_dump_json())
    assert again == out


def test_example_transition_windows_json_validates():
    p = Path("data/examples/example_transition_windows.json")
    out = TransitionWindowOutput.model_validate(json.loads(p.read_text()))
    assert out.model_version == MODEL_VERSION
    assert out.windows and out.windows[0].reasoning


# ------------------------------------------------------------------ API endpoint


def test_api_transition_windows_endpoint(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from dancelab.api.main import app
    from dancelab.storage.repositories import FileAnalysisRepository

    analysis = AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id="apitest1"),
        features=make_frames(),
    )
    # route reads DANCELAB_PROCESSED_DIR → isolated storage for this test
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    FileAnalysisRepository(tmp_path).save(analysis)

    client = TestClient(app)
    r = client.post("/tracks/apitest1/transition-windows",
                    json={"context_id": "club_peak", "previous_track_id": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == MODEL_VERSION
    assert body["windows"]
    assert "club_peak" in body["windows"][0]["compatible_contexts"]
    assert any("unused by model v0.1" in w for w in body["warnings"])

    assert client.post("/tracks/nope/transition-windows", json={}).status_code == 404


def test_top_k_suppresses_adjacent_peaks():
    # two near-identical adjacent maxima → only one selected, next pick is distant
    s = np.array([0.0, 3.0, 0.1, 2.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0])
    t = np.arange(12, dtype=float)
    wins = top_k_windows(s, t, k=3, half_width_sec=2.0)  # min_sep = 4 s
    idxs = [w[0] for w in wins]
    assert idxs[0] == 1
    assert 3 not in idxs  # suppressed: 2 s from peak 1
    assert 10 in idxs

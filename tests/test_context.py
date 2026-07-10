"""Context conditioning and context-evaluation contracts."""

import numpy as np
from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.context.conditioning import (
    _infer_role,
    condition,
    evaluate_context,
    track_context_score,
)
from dancelab.core.models import AnalysisResult, ContextProfile, FeatureFrame, Track
from dancelab.storage.repositories import FileAnalysisRepository


def test_infer_role_late_night_boundaries():
    # AUD-L7: 00:00–03:59 is peak (03:xx no longer falls through to builder),
    # 04:00–08:59 is closer, 22:00+ opener.
    def role_at(hour):
        return _infer_role(ContextProfile(context_id="c", time_of_night=f"{hour:02d}:00"))

    assert role_at(0) == "peak"
    assert role_at(3) == "peak"   # was the dead-branch gap → builder
    assert role_at(4) == "closer"
    assert role_at(23) == "opener"


def make_analysis(track_id, rms_curve, lfer=0.5, vocal=0.2, style="techno", bpm=128):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=track_id, bpm_estimate=bpm, style_label=style),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(i),
                rms=float(rms),
                low_freq_energy_ratio=lfer,
                vocal_density_proxy=vocal,
            )
            for i, rms in enumerate(rms_curve)
        ],
    )


def test_peak_track_scores_higher_for_peak_context():
    peakish = make_analysis("peakish", np.linspace(0.55, 0.9, 120), lfer=0.72, vocal=0.12)
    peak = ContextProfile(context_id="club_peak", venue_type="club", set_role="peak", style_focus=["techno"])
    opener = ContextProfile(
        context_id="club_opening", venue_type="club", set_role="opener", style_focus=["deep-house"]
    )

    peak_score = track_context_score(peakish, peak)
    opener_score = track_context_score(peakish, opener)

    assert peak_score.value > opener_score.value
    assert peak_score.role_fits["peak"] > peak_score.role_fits["opener"]


def test_evaluate_context_returns_candidate_scores_and_provenance():
    track = make_analysis("ctx", np.linspace(0.15, 0.45, 100), lfer=0.35, vocal=0.35, style="minimal")
    ctx = ContextProfile(context_id="club_opening", venue_type="club", set_role="opener")
    out = evaluate_context(track, ctx)

    assert out.context_fit.status == "candidate"
    assert out.opening_fit is not None and out.peak_time_fit is not None
    assert out.provenance.model_card_id == "context_evaluation_model_card_v0.1"
    assert out.model_version == "context_evaluation_v0.1"


def test_condition_multiplies_curve_by_context_fit():
    curve = np.array([0.2, 0.4, 0.8])
    c_fit = np.array([0.5, 0.25, 1.0])
    assert np.allclose(condition(curve, c_fit), [0.1, 0.1, 0.8])


def test_api_context_evaluate_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(make_analysis("ctx_api", np.linspace(0.2, 0.8, 90), lfer=0.6, style="techno"))

    client = TestClient(app)
    r = client.post(
        "/contexts/evaluate",
        json={
            "track_id": "ctx_api",
            "context_profile": {
                "context_id": "club_peak",
                "venue_type": "club",
                "set_role": "peak",
                "style_focus": ["techno"],
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["context_fit"]["value"] >= 0
    assert body["provenance"]["model_card_id"] == "context_evaluation_model_card_v0.1"

"""Set Function Engine v0.1 — tests per ticket: role scores, context
sensitivity, JSON schema, API, edge cases (no context, multi-role track)."""

import numpy as np

from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    FeatureFrame,
    SetFunction,
    SetFunctionInput,
    SetFunctionOutput,
    Track,
)
from dancelab.decision.set_function import (
    MODEL_VERSION,
    classify_set_function,
    role_scores,
)


def make_analysis(track_id, rms_curve, lfer=0.5):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=track_id),
        features=[FeatureFrame(track_id=track_id, timestamp_sec=float(t),
                               rms=float(r), low_freq_energy_ratio=lfer)
                  for t, r in enumerate(rms_curve)],
    )


def peak_track():
    """Sustained high energy, bass-heavy → peak-ish."""
    return make_analysis("peaky", [0.28 + 0.02 * np.sin(t / 9) for t in range(300)], lfer=0.7)


def opener_track():
    """Low floor, gentle rise, never slams."""
    return make_analysis("opener", [0.05 + 0.0003 * t for t in range(300)], lfer=0.3)


# ------------------------------------------------------------------ role scores


def test_role_scores_prefer_peak_for_sustained_energy():
    out = classify_set_function(SetFunctionInput(track_analysis=peak_track()))
    assert out.role_scores[SetFunction.peak.value] > out.role_scores[SetFunction.opener.value]


def test_role_scores_prefer_opener_for_low_floor():
    out = classify_set_function(SetFunctionInput(track_analysis=opener_track()))
    assert out.primary_function in (SetFunction.opener, SetFunction.builder)
    assert out.role_scores[SetFunction.opener.value] > out.role_scores[SetFunction.peak.value]


def test_role_scores_pure_function():
    phi = {"e_start": 0.1, "e_end": 0.9, "e_mean": 0.5, "slope": 0.9,
           "sustain": 0.2, "dip": 0.3, "bass": 0.5, "windows": 0.5, "short": 0.2}
    scores = role_scores(phi)
    assert scores[SetFunction.builder] > scores[SetFunction.closer]  # rising energy


# ---------------------------------------------------------- context sensitivity


def test_context_shifts_scores_c010():
    track = peak_track()
    free = classify_set_function(SetFunctionInput(track_analysis=track))
    peak_ctx = classify_set_function(SetFunctionInput(
        track_analysis=track,
        context=ContextProfile(context_id="club_peak", set_role="peak")))
    assert peak_ctx.role_scores[SetFunction.peak.value] > free.role_scores[SetFunction.peak.value]
    assert peak_ctx.context_fit == 0.8


def test_edge_no_context_warns():
    out = classify_set_function(SetFunctionInput(track_analysis=peak_track()))
    assert out.context_fit is None
    assert any("no context profile" in w for w in out.warnings)


# ------------------------------------------------------------------- multi-role


def test_edge_multi_role_track_has_secondaries_and_risk():
    # flat mid-energy track → ambiguous roles, small margin → high risk
    flat = make_analysis("flat", [0.15] * 300, lfer=0.5)
    out = classify_set_function(SetFunctionInput(track_analysis=flat))
    assert out.risk_score >= 0.3
    assert isinstance(out.secondary_functions, list)
    assert 0 <= out.confidence <= 1


# ----------------------------------------------------------------- JSON schema


def test_output_json_roundtrip():
    out = classify_set_function(SetFunctionInput(track_analysis=peak_track()))
    assert out.model_version == MODEL_VERSION
    assert SetFunctionOutput.model_validate_json(out.model_dump_json()) == out
    assert out.reasoning  # ticket DoD


def test_example_set_function_json_validates():
    import json
    from pathlib import Path
    out = SetFunctionOutput.model_validate(
        json.loads(Path("data/examples/example_set_function.json").read_text())
    )
    assert out.model_version == MODEL_VERSION and out.reasoning


# ------------------------------------------------------------------------- API


def test_api_set_function_endpoint(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from dancelab.api.main import app
    from dancelab.storage.repositories import FileAnalysisRepository

    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    FileAnalysisRepository(tmp_path).save(peak_track())

    client = TestClient(app)
    r = client.post("/tracks/peaky/set-function", json={"context_id": "club_peak"})
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == MODEL_VERSION
    assert body["primary_function"] in [r.value for r in SetFunction]
    assert body["reasoning"] and "risk_score" in body

    assert client.post("/tracks/nope/set-function", json={}).status_code == 404

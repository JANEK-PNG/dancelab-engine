"""API contract tests for the public surface."""

import pytest
from fastapi.testclient import TestClient

from dancelab.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["engine_version"]
    assert body["weights_version"]


def test_openapi_lists_contracted_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for endpoint in (
        "/contracts/node-host",
        "/tracks/analyze",
        "/tracks/{track_id}",
        "/pairs/mixability",
        "/pairs/edge-decision",
        "/contexts/evaluate",
        "/sets/recommend-next",
        "/sets/recommend-sequence",
    ):
        assert endpoint in paths, f"missing contracted endpoint: {endpoint}"


def test_context_profiles_endpoint(client):
    r = client.get("/contexts/profiles")
    assert r.status_code == 200
    assert "club_peak" in r.json()


def test_analyze_missing_file_is_422(client):
    r = client.post("/tracks/analyze", json={"source_path": "data/raw/nope.wav"})
    assert r.status_code == 422
    assert r.json()["error"] == "ingestion"


def test_analyze_rejects_invalid_body(client):
    r = client.post("/tracks/analyze", json={"bpm_hint": -5})
    assert r.status_code == 422  # FastAPI validation: missing source_path, bad bpm


def test_mixability_unknown_tracks_return_404(client, monkeypatch, tmp_path):
    # implemented in Sprint 2 Final — unknown track ids → 404, never fake scores
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    r = client.post("/pairs/mixability", json={"track_id_a": "a", "track_id_b": "b"})
    assert r.status_code == 404


def test_edge_decision_unknown_tracks_return_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    r = client.post("/pairs/edge-decision", json={"track_id_a": "a", "track_id_b": "b"})
    assert r.status_code == 404


def test_recommend_next_unknown_tracks_return_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    r = client.post(
        "/sets/recommend-next",
        json={"current_track_id": "a", "candidate_track_ids": ["b", "c"]},
    )
    assert r.status_code == 404


def test_recommend_sequence_unknown_tracks_return_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    r = client.post(
        "/sets/recommend-sequence",
        json={"current_track_id": "a", "candidate_track_ids": ["b", "c"], "horizon": 2},
    )
    assert r.status_code == 404


def test_context_evaluate_unknown_track_returns_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    r = client.post(
        "/contexts/evaluate",
        json={
            "track_id": "a",
            "context_profile": {"context_id": "club_peak", "set_role": "peak"},
        },
    )
    assert r.status_code == 404


def test_get_unknown_track_returns_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    r = client.get("/tracks/some-id")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"

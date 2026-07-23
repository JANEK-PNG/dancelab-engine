"""API contract tests for the public surface."""

import pytest
from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.core.models import (
    DANCELAB_SCHEMA_VERSION,
    AnalysisResult,
    BeatGrid,
    FeatureFrame,
    SetPlan,
    Track,
)
from dancelab.stems.workflow import StemExportArtifact
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.workflows.smart_playlist import SmartPlaylistResult


@pytest.fixture
def client():
    return TestClient(app)


def _stored_analysis(track_id: str, key: str, bpm: float, source_path: str) -> AnalysisResult:
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=track_id,
            title=track_id.replace("_", " ").title(),
            artist="DanceLab",
            key_estimate=key,
            bpm_estimate=bpm,
            source_path=source_path,
            duration_sec=300.0,
            sample_rate=44100,
        ),
        beatgrid=BeatGrid(bpm=bpm, beat_times_sec=[0.0, 0.5, 1.0], downbeats_sec=[0.0]),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=0.2 + 0.01 * t,
                low_freq_energy_ratio=0.5,
                bass_energy=40.0,
            )
            for t in range(30)
        ],
    )


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
        "/tracks/analyze",
        "/tracks/{track_id}",
        "/pairs/mixability",
        "/pairs/edge-decision",
        "/contexts/evaluate",
        "/sets/recommend-next",
        "/sets/recommend-sequence",
        "/sets/build",
        "/sets/export-rekordbox",
        "/sets/smart-playlist",
        "/stems/export",
    ):
        assert endpoint in paths, f"missing contracted endpoint: {endpoint}"


def test_context_profiles_endpoint(client):
    r = client.get("/contexts/profiles")
    assert r.status_code == 200
    assert "club_peak" in r.json()


def test_analyze_missing_file_is_422(client):
    r = client.post("/tracks/analyze", json={"source_path": "data/raw/nope.wav"})
    assert r.status_code == 422
    assert r.json()["detail"] == "input file does not exist"


def test_analyze_rejects_invalid_body(client):
    r = client.post("/tracks/analyze", json={"bpm_hint": -5})
    assert r.status_code == 422  # FastAPI validation: missing source_path, bad bpm


def test_request_limit_counts_streamed_body_without_content_length(
    client, monkeypatch
):
    monkeypatch.setenv("DANCELAB_API_MAX_REQUEST_BYTES", "32")
    chunks = iter([b'{"source_path":"', b"x" * 64, b'"}'])

    r = client.post(
        "/tracks/analyze",
        content=chunks,
        headers={"content-type": "application/json"},
    )

    assert r.status_code == 413
    assert r.json()["error"] == "request_too_large"


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


def test_build_set_endpoint_uses_stored_analyses(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(_stored_analysis("track_alpha", "8A", 128.0, "/tmp/Track Alpha.mp3"))
    repo.save(_stored_analysis("track_beta", "9A", 128.0, "/tmp/Track Beta.mp3"))

    r = client.post(
        "/sets/build",
        json={
            "track_ids": ["track_beta", "track_alpha"],
            "start_track_id": "track_alpha",
            "target_track_count": 2,
            "locked_positions": {"1": "track_alpha"},
            "pinned_track_ids": ["track_beta"],
            "arc": "build",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == DANCELAB_SCHEMA_VERSION
    assert body["model_version"] == "set_builder_v0.2"
    assert body["track_order"][0] == "track_alpha"
    assert set(body["track_order"]) == {"track_alpha", "track_beta"}
    assert body["locked_positions"] == {"1": "track_alpha"}
    assert body["pinned_track_ids"] == ["track_beta"]


def test_build_set_endpoint_rejects_conflicting_constraints(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(_stored_analysis("track_alpha", "8A", 128.0, "/tmp/Track Alpha.mp3"))
    repo.save(_stored_analysis("track_beta", "9A", 128.0, "/tmp/Track Beta.mp3"))

    r = client.post(
        "/sets/build",
        json={
            "track_ids": ["track_alpha", "track_beta"],
            "target_track_count": 1,
            "pinned_track_ids": ["track_alpha", "track_beta"],
        },
    )

    assert r.status_code == 422
    assert "exceed target_track_count" in r.json()["detail"]


def test_export_rekordbox_endpoint_returns_and_writes_xml(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("DANCELAB_API_OUTPUT_ROOTS", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path / "processed")
    repo.save(_stored_analysis("track_alpha", "8A", 128.0, "/tmp/Track Alpha.mp3"))
    repo.save(_stored_analysis("track_beta", "9A", 128.0, "/tmp/Track Beta.mp3"))
    output_path = tmp_path / "exports" / "api_set.xml"

    r = client.post(
        "/sets/export-rekordbox",
        json={
            "track_ids": ["track_alpha", "track_beta"],
            "start_track_id": "track_alpha",
            "locked_positions": {"1": "track_alpha"},
            "playlist_name": "API Test Set",
            "output_path": str(output_path),
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == DANCELAB_SCHEMA_VERSION
    assert body["set_plan"]["schema_version"] == DANCELAB_SCHEMA_VERSION
    assert body["playlist_name"] == "API Test Set"
    assert body["track_count"] == 2
    assert body["output_path"] == str(output_path)
    assert "DJ_PLAYLISTS" in body["xml"]
    assert "API Test Set" in output_path.read_text(encoding="utf-8")


def test_stem_export_endpoint_returns_artifacts(client, monkeypatch, tmp_path):
    output_root = tmp_path / "stem_exports"
    source_path = tmp_path / "Track Alpha.mp3"
    source_path.write_bytes(b"test audio placeholder")
    monkeypatch.setenv("DANCELAB_API_INPUT_ROOTS", str(tmp_path))
    monkeypatch.setenv("DANCELAB_API_OUTPUT_ROOTS", str(tmp_path))

    def export_stub(source_paths, config, output_root_arg, *, stem_method, vocal_method):
        assert source_paths == [str(source_path)]
        assert output_root_arg == str(output_root)
        assert stem_method == "none"
        assert vocal_method == "hpss"
        return [
            StemExportArtifact(
                track_id="track_alpha",
                title="Track Alpha",
                artifact_path=str(output_root / "Track Alpha [track_alpha]"),
                stems_written=["vocals.wav"],
                stem_source_status="source_backed",
                warnings=[],
            )
        ]

    monkeypatch.setattr("dancelab.api.routes_stems.export_stems_for_paths", export_stub)
    r = client.post(
        "/stems/export",
        json={
            "source_paths": [str(source_path)],
            "output_root": str(output_root),
            "stem_method": "none",
            "vocal_method": "hpss",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == DANCELAB_SCHEMA_VERSION
    assert body["track_count"] == 1
    assert body["output_root"] == str(output_root)
    assert body["artifacts"][0]["track_id"] == "track_alpha"
    assert body["artifacts"][0]["stems_written"] == ["vocals.wav"]


def test_smart_playlist_endpoint_builds_from_folder(client, monkeypatch, tmp_path):
    output_path = tmp_path / "exports" / "api_smart.xml"
    music_folder = tmp_path / "music"
    music_folder.mkdir()
    monkeypatch.setenv("DANCELAB_API_INPUT_ROOTS", str(tmp_path))
    monkeypatch.setenv("DANCELAB_API_OUTPUT_ROOTS", str(tmp_path))

    def workflow_stub(folder_path, config, **kwargs):
        assert folder_path == music_folder
        assert kwargs["target_track_count"] == 10
        assert kwargs["playlist_name"] == "API Smart Set"
        assert kwargs["output_path"] == str(output_path)
        assert kwargs["planner_mode"] == "bpm"
        assert kwargs["analysis_depth"] == "deep"
        plan = SetPlan(track_order=["track_a", "track_b"], target_track_count=10)
        return SmartPlaylistResult(
            playlist_name="API Smart Set",
            source_folder=str(music_folder),
            source_track_count=12,
            analyzed_track_count=12,
            target_track_count=10,
            processed_dir=str(tmp_path / "processed"),
            output_path=str(output_path),
            set_plan=plan,
            xml="<DJ_PLAYLISTS />",
            analyzed_track_ids=["track_a", "track_b"],
            failed_tracks=[],
        )

    monkeypatch.setattr(
        "dancelab.api.routes_sets.build_smart_playlist_from_folder",
        workflow_stub,
    )
    r = client.post(
        "/sets/smart-playlist",
        json={
            "folder_path": str(music_folder),
            "target_track_count": 10,
            "playlist_name": "API Smart Set",
            "output_path": str(output_path),
            "planner_mode": "bpm",
            "analysis_depth": "deep",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == DANCELAB_SCHEMA_VERSION
    assert body["source_track_count"] == 12
    assert body["target_track_count"] == 10
    assert body["output_path"] == str(output_path)
    assert body["set_plan"]["track_order"] == ["track_a", "track_b"]


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


def test_track_id_traversal_is_rejected_before_repository_access(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    response = client.get("/tracks/bad%24id")
    assert response.status_code == 422


def test_api_rejects_untrusted_host(client):
    response = client.get("/health", headers={"host": "public.example"})
    assert response.status_code == 400

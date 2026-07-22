from __future__ import annotations

import json
from pathlib import Path

from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track
from dancelab.ingestion.metadata import make_track_id
from dancelab.validation.djmix.model_gate import (
    build_ordering_model_gate,
    write_ordering_analysis_queue,
    write_ordering_model_gate,
)
from dancelab.validation.djmix.ordering import (
    CorpusOrderingDataset,
    OrderingObservation,
)


def _dataset(track_ids: tuple[str, ...] = ("a", "b", "c")) -> CorpusOrderingDataset:
    observations = tuple(
        OrderingObservation(
            mix_id=mix_id,
            run_id=f"{mix_id}:run-1",
            position=1,
            history_track_ids=(track_ids[0],),
            candidate_track_ids=tuple(sorted(track_ids[1:])),
            selected_track_id=track_ids[1],
        )
        for mix_id in ("mix-1", "mix-2", "mix-3")
    )
    return CorpusOrderingDataset(
        observations=observations,
        audit={"source": {"dataset_sha256": "a" * 64}},
        fingerprint="d" * 64,
    )


def _analysis(audio_path: Path) -> AnalysisResult:
    track_id = make_track_id(str(audio_path.resolve()))
    return AnalysisResult(
        engine_version="fixture",
        track=Track(
            track_id=track_id,
            source_path=str(audio_path.resolve()),
            duration_sec=240.0,
            bpm_estimate=130.0,
            key_estimate="8A",
            key_confidence=0.8,
        ),
        beatgrid=BeatGrid(
            bpm=130.0,
            beat_times_sec=[0.0, 0.46, 0.92],
            reliable=True,
        ),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=0.0,
                rms=0.2,
                spectral_flux=100.0,
                low_freq_energy_ratio=0.4,
                onset_density=3.0,
                bass_energy=2000.0,
            ),
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=1.0,
                rms=0.3,
                spectral_flux=120.0,
                low_freq_energy_ratio=0.5,
                onset_density=4.0,
                bass_energy=2500.0,
            ),
        ],
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _complete_evidence(tmp_path: Path, corpus: Path, track_ids: tuple[str, ...]):
    analysis_root = tmp_path / "analyses"
    analysis_root.mkdir()
    index_tracks: dict[str, str] = {}
    embedding_tracks: dict[str, list[float]] = {}
    for index, catalog_track_id in enumerate(track_ids):
        audio_path = corpus / "tracks" / f"{catalog_track_id}.wav"
        audio_path.write_bytes(b"fixture")
        analysis = _analysis(audio_path)
        analysis_path = analysis_root / f"{analysis.track.track_id}.json"
        analysis_path.write_text(analysis.model_dump_json(), encoding="utf-8")
        index_tracks[catalog_track_id] = analysis_path.name
        embedding_tracks[catalog_track_id] = [float(index + 1), 0.5]

    analysis_index = tmp_path / "analysis-index.json"
    _write_json(
        analysis_index,
        {
            "schema_version": "ordering-analysis-index-v1",
            "tracks": index_tracks,
        },
    )
    embeddings = tmp_path / "embeddings.json"
    _write_json(
        embeddings,
        {
            "schema_version": "ordering-embeddings-v1",
            "embedding_name": "fixture-encoder-v1",
            "model": {
                "name": "fixture encoder",
                "version": "1",
                "sha256": "e" * 64,
                "source": "unit-test fixture",
                "license": "test-only",
                "frozen": True,
            },
            "tracks": embedding_tracks,
            "provenance": {"source": "fixture"},
        },
    )
    dj_map = tmp_path / "dj-map.json"
    _write_json(
        dj_map,
        {
            "schema_version": "ordering-dj-map-v1",
            "dj_by_mix": {
                "mix-1": "dj-a",
                "mix-2": "dj-a",
                "mix-3": "dj-b",
            },
            "provenance": {"source": "fixture"},
        },
    )
    return analysis_root, analysis_index, embeddings, dj_map


def test_gate_is_ready_only_with_complete_source_backed_h_e_and_dj(tmp_path: Path):
    dataset = _dataset()
    corpus = tmp_path / "corpus"
    (corpus / "tracks").mkdir(parents=True)
    evidence = _complete_evidence(tmp_path, corpus, ("a", "b", "c"))

    first, first_queue = build_ordering_model_gate(
        dataset,
        corpus,
        analysis_root=evidence[0],
        analysis_index_path=evidence[1],
        embedding_catalog_path=evidence[2],
        dj_mapping_path=evidence[3],
        expected_dataset_fingerprint=dataset.fingerprint,
    )
    second, second_queue = build_ordering_model_gate(
        dataset,
        corpus,
        analysis_root=evidence[0],
        analysis_index_path=evidence[1],
        embedding_catalog_path=evidence[2],
        dj_mapping_path=evidence[3],
        expected_dataset_fingerprint=dataset.fingerprint,
    )

    assert first.ready_for_five_models
    assert first.readiness["feature_catalog_ready"] is True
    assert first.blockers == ()
    assert first_queue.complete
    assert first_queue.status == "complete"
    assert first.fingerprint == second.fingerprint
    assert first_queue.fingerprint == second_queue.fingerprint


def test_gate_reports_every_audio_and_evidence_blocker_without_partial_queue(
    tmp_path: Path,
):
    dataset = _dataset(("a", "b", "c", "d"))
    corpus = tmp_path / "corpus"
    tracks = corpus / "tracks"
    tracks.mkdir(parents=True)
    (tracks / "a.wav").write_bytes(b"a")
    (tracks / "._a.wav").write_bytes(b"appledouble")
    (tracks / "b.webm").write_bytes(b"b")
    (tracks / "c.wav").write_bytes(b"c-wav")
    (tracks / "c.mp3").write_bytes(b"c-mp3")

    report, queue = build_ordering_model_gate(dataset, corpus)

    assert report.ready_for_five_models is False
    assert report.source_audio.ignored_appledouble_count == 1
    assert report.source_audio.missing_ids == ("d",)
    assert set(report.source_audio.ambiguous_paths) == {"c"}
    assert report.source_audio.unsupported_for_engine_ids == ("b",)
    assert queue.safe_to_run is False
    assert [job.catalog_track_id for job in queue.jobs] == ["a"]
    assert queue.blocked_missing_ids == ("d",)
    assert queue.blocked_ambiguous_ids == ("c",)
    assert queue.blocked_unsupported_ids == ("b",)
    assert report.handcrafted.missing_ids == ("a", "b", "c", "d")
    assert report.embeddings.missing_ids == ("a", "b", "c", "d")
    assert report.dj_identity.missing_ids == ("mix-1", "mix-2", "mix-3")
    assert any("H queue blocked" in blocker for blocker in report.blockers)


def test_gate_rejects_analysis_index_path_traversal_and_queues_reanalysis(
    tmp_path: Path,
):
    dataset = _dataset()
    corpus = tmp_path / "corpus"
    tracks = corpus / "tracks"
    tracks.mkdir(parents=True)
    for track_id in ("a", "b", "c"):
        (tracks / f"{track_id}.wav").write_bytes(track_id.encode("ascii"))

    analysis_root = tmp_path / "analyses"
    analysis_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(_analysis(tracks / "a.wav").model_dump_json(), encoding="utf-8")
    analysis_index = tmp_path / "analysis-index.json"
    _write_json(
        analysis_index,
        {
            "schema_version": "ordering-analysis-index-v1",
            "tracks": {
                "a": "../outside.json",
            },
        },
    )

    report, queue = build_ordering_model_gate(
        dataset,
        corpus,
        analysis_root=analysis_root,
        analysis_index_path=analysis_index,
    )

    assert "a" in report.handcrafted.invalid_items
    assert report.handcrafted.missing_ids == ("b", "c")
    assert [job.catalog_track_id for job in queue.jobs] == ["a", "b", "c"]
    assert queue.safe_to_run
    assert report.ready_for_five_models is False


def test_gate_and_queue_writes_are_complete_json_artifacts(tmp_path: Path):
    dataset = _dataset()
    corpus = tmp_path / "corpus"
    (corpus / "tracks").mkdir(parents=True)
    evidence = _complete_evidence(tmp_path, corpus, ("a", "b", "c"))
    report, queue = build_ordering_model_gate(
        dataset,
        corpus,
        analysis_root=evidence[0],
        analysis_index_path=evidence[1],
        embedding_catalog_path=evidence[2],
        dj_mapping_path=evidence[3],
    )

    gate_path = write_ordering_model_gate(report, tmp_path / "out" / "gate.json")
    queue_path = write_ordering_analysis_queue(queue, tmp_path / "out" / "queue.json")
    gate_payload = json.loads(gate_path.read_text(encoding="utf-8"))
    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))

    assert gate_payload["schema_version"] == "ordering-model-gate-v1"
    assert gate_payload["fingerprint"] == report.fingerprint
    assert gate_payload["readiness"]["five_model_evaluation_ready"] is True
    assert queue_payload["schema_version"] == "ordering-analysis-queue-v1"
    assert queue_payload["fingerprint"] == queue.fingerprint

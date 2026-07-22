from __future__ import annotations

import json
from datetime import datetime, timezone

from dancelab.validation.djmix.checkpoint import create_checkpoint, verify_checkpoint


def _fixture_roots(tmp_path):
    project = tmp_path / "project"
    corpus = tmp_path / "corpus"
    checkpoints = project / "data" / "checkpoints" / "corpus"
    (project / "src").mkdir(parents=True)
    (project / "scripts").mkdir()
    (project / "tests").mkdir()
    (project / "src" / "engine.py").write_text("MODE = 'legacy'\n")
    (project / "scripts" / "align.py").write_text("print('align')\n")
    (project / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (corpus / "mixes").mkdir(parents=True)
    (corpus / "tracks").mkdir()
    (corpus / "alignments").mkdir()
    (corpus / "mixes" / "mix0001.m4a").write_bytes(b"mix")
    (corpus / "tracks" / "track0001.webm").write_bytes(b"track")
    (corpus / "djmix-dataset.json").write_text("[]")
    (corpus / "manifest.csv").write_text("key,kind,status,path,error,ts\n")
    return project, corpus, checkpoints


def test_checkpoint_records_only_atomic_completed_reports(tmp_path):
    project, corpus, checkpoints = _fixture_roots(tmp_path)
    (corpus / "alignments" / "mix0001.json").write_text(json.dumps({"mix_id": "mix0001"}))
    (corpus / "alignments" / "mix0002.json.tmp").write_text("partial")

    slot = create_checkpoint(
        project_root=project,
        corpus_root=corpus,
        checkpoint_root=checkpoints,
        label="baseline",
        engine_mode="legacy",
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )

    manifest = json.loads((slot / "checkpoint.json").read_text())
    progress = manifest["corpus_progress"]
    assert progress["completed_report_ids"] == ["mix0001"]
    assert progress["in_flight_report_files"] == ["mix0002.json.tmp"]
    assert manifest["safety"]["source_audio_copied"] is False
    assert verify_checkpoint(slot)["valid"] is True


def test_checkpoint_verification_detects_tampering(tmp_path):
    project, corpus, checkpoints = _fixture_roots(tmp_path)
    slot = create_checkpoint(
        project_root=project,
        corpus_root=corpus,
        checkpoint_root=checkpoints,
        now=datetime(2026, 7, 16, 12, 1, tzinfo=timezone.utc),
    )
    (slot / "completed_reports.txt").write_text("tampered\n")

    result = verify_checkpoint(slot)

    assert result["valid"] is False
    assert "sha256 mismatch: completed_reports.txt" in result["errors"]

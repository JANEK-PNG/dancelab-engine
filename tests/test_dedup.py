"""Byte-identical audio de-duplication (decision/dedup.py)."""

from __future__ import annotations

from dancelab.core.models import AnalysisResult, Track
from dancelab.decision.dedup import dedupe_by_audio


def _analysis(track_id: str, path: str) -> AnalysisResult:
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, source_path=path, duration_sec=180.0, bpm_estimate=128.0),
    )


def test_dedupe_collapses_byte_identical_files(tmp_path):
    # same bytes, two names — Janek's real case (03 Movement.aif == 03-Daniel_Avery...)
    a = tmp_path / "03 Movement.aif"
    b = tmp_path / "03-Daniel_Avery_-_Movement.aif"
    c = tmp_path / "other.aif"
    a.write_bytes(b"AUDIOCONTENT-MOVEMENT")
    b.write_bytes(b"AUDIOCONTENT-MOVEMENT")  # identical bytes
    c.write_bytes(b"DIFFERENT-TRACK")

    analyses = [_analysis("id_a", str(a)), _analysis("id_b", str(b)), _analysis("id_c", str(c))]
    unique, warnings = dedupe_by_audio(analyses)

    kept_ids = [x.track.track_id for x in unique]
    assert kept_ids == ["id_a", "id_c"]           # first duplicate kept, second dropped
    assert len(warnings) == 1
    assert "id_b" in warnings[0] and "id_a" in warnings[0]


def test_dedupe_keeps_missing_files_never_merges_on_uncertainty(tmp_path):
    real = tmp_path / "real.aif"
    real.write_bytes(b"REAL")
    analyses = [
        _analysis("gone1", str(tmp_path / "missing1.aif")),
        _analysis("gone2", str(tmp_path / "missing2.aif")),
        _analysis("real", str(real)),
    ]
    unique, warnings = dedupe_by_audio(analyses)
    assert [x.track.track_id for x in unique] == ["gone1", "gone2", "real"]  # nothing merged
    assert warnings == []

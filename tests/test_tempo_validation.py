from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dancelab.preprocessing.tempo_precision import refine_bpm_from_beat_times
from dancelab.validation.tempo.benchmark import (
    run_tempo_benchmark,
    write_tempo_benchmark,
)


def test_long_span_refinement_removes_frame_quantization_without_metric_change():
    # 43/44-frame intervals at 44.1 kHz average to the true half-second beat.
    intervals = np.resize(np.array([0.4992] * 15 + [0.5108]), 160)
    beats = np.concatenate([[0.0], np.cumsum(intervals)])

    result = refine_bpm_from_beat_times(beats, 120.19)

    assert result["accepted"] is True
    assert result["bpm"] == pytest.approx(120.0, abs=0.03)
    assert result["robust_cv"] < 0.01


def test_long_span_refinement_refuses_unstable_grid():
    intervals = np.concatenate([np.full(80, 0.42), np.full(80, 0.58)])
    beats = np.concatenate([[0.0], np.cumsum(intervals)])

    result = refine_bpm_from_beat_times(beats, 120.0)

    assert result["accepted"] is False
    assert result["reason"] == "unstable_long_span_tempo"
    assert result["bpm"] == 120.0


def _write_analysis(path: Path, source: Path, *, first_beat: float) -> None:
    beats = [first_beat + index * 0.5 for index in range(96)]
    payload = {
        "track": {
            "track_id": path.stem,
            "title": source.stem,
            "source_path": str(source),
        },
        "beatgrid": {
            "bpm": 120.19,
            "beat_times_sec": beats,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_benchmark_uses_exact_paths_and_exposes_downbeat_proxy_error(tmp_path):
    analyses = tmp_path / "analyses"
    analyses.mkdir()
    track_a = tmp_path / "Track A.mp3"
    track_b = tmp_path / "Track B.mp3"
    _write_analysis(analyses / "a.json", track_a, first_beat=0.0)
    _write_analysis(analyses / "b.json", track_b, first_beat=0.5)

    xml = tmp_path / "library.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0"><PRODUCT Name="rekordbox" Version="7.2.14"/>
<COLLECTION Entries="2">
<TRACK TrackID="1" Name="Track A" Artist="A" AverageBpm="120.00"
 Location="file://localhost{path_a}"><TEMPO Inizio="0.000" Bpm="120.00" Battito="1"/></TRACK>
<TRACK TrackID="2" Name="Track B" Artist="B" AverageBpm="120.00"
 Location="file://localhost{path_b}"><TEMPO Inizio="0.000" Bpm="120.00" Battito="1"/></TRACK>
</COLLECTION></DJ_PLAYLISTS>
""".format(path_a=track_a.as_posix(), path_b=track_b.as_posix()),
        encoding="utf-8",
    )

    report = run_tempo_benchmark(analyses, [xml])
    primary = report["metrics"]["primary_exact_path"]

    assert primary["count"] == 2
    assert primary["refined_bpm"]["median_pct"] == 0.0
    assert primary["phase"]["proxy_downbeat_correct"] == 1
    assert primary["phase"]["proxy_reference_beat_counts"] == {"1": 1, "2": 1}
    assert report["gates"]["proxy_downbeats_safe_for_phrase_quantization"] is False
    assert report["gates"]["engine_mutation_authorized_by_report"] is False

    output = tmp_path / "report"
    write_tempo_benchmark(report, output)
    assert (output / "benchmark.json").exists()
    assert (output / "tracks.csv").exists()
    assert "operational reference" in (output / "summary.md").read_text()

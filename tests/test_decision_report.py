"""Decision report builder contracts."""

from __future__ import annotations

import csv
import json

from dancelab.core.models import AnalysisResult, FeatureFrame, Track
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.validation.decision_report import build_decision_report


def make_analysis(track_id, source_path, bpm, camelot, title):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=track_id,
            source_path=str(source_path),
            bpm_estimate=bpm,
            key_estimate=camelot,
            key_confidence=0.9,
            title=title,
            style_label="techno",
        ),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=0.4 + 0.001 * t,
                low_freq_energy_ratio=0.45,
                vocal_density_proxy=0.1,
                spectral_flux=10.0,
                bass_energy=50.0,
            )
            for t in range(80)
        ],
    )


def test_build_decision_report_writes_core_artifacts(tmp_path):
    processed = tmp_path / "processed"
    report = tmp_path / "report"
    processed.mkdir()
    source_a = tmp_path / "a.wav"
    source_b = tmp_path / "b.wav"
    source_a.write_bytes(b"fake")
    source_b.write_bytes(b"fake")

    repo = FileAnalysisRepository(processed)
    repo.save(make_analysis("a", source_a, 128, "8A", "Track A"))
    repo.save(make_analysis("b", source_b, 129, "9A", "Track B"))

    paths = build_decision_report(processed, report)

    summary = json.loads(paths["decision_summary"].read_text())
    pairs = json.loads(paths["mixability_pairs"].read_text())
    edges = json.loads(paths["edge_decisions"].read_text())
    payloads = [
        json.loads(line)
        for line in paths["edge_decision_payloads"].read_text().splitlines()
        if line.strip()
    ]
    with paths["edge_decision_review"].open(newline="", encoding="utf-8") as f:
        review_rows = list(csv.DictReader(f))
    analysis_summary = json.loads(paths["analysis_summary"].read_text())

    assert summary["ordered_pair_count"] == 2
    assert len(pairs) == 2
    assert len(edges) == 2
    assert len(payloads) == 2
    assert len(review_rows) == 2
    assert pairs[0]["pair_id"]
    assert pairs[0]["edge_decision"]["recommended_transition_strategy"]
    assert pairs[0]["edge_decision"]["blend_profile_auto"]
    assert payloads[0]["annotation_payload"]["pair_id"] == payloads[0]["pair_id"]
    assert payloads[0]["annotation_payload"]["blend_profile_auto"]
    assert review_rows[0]["engine_strategy"]
    assert review_rows[0]["engine_blend_profile_auto"]
    assert summary["artifacts"]["edge_decision_review"].endswith("edge_decision_review.csv")
    assert analysis_summary["track_count"] == 2

"""Decision report builder contracts."""

from __future__ import annotations

import csv
import json

from dancelab.core.models import AnalysisResult, FeatureFrame, Track
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.visualization.decision_report import build_decision_report


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


def test_build_decision_report_writes_core_artifacts(monkeypatch, tmp_path):
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

    def fake_waveforms(report_root, *, top_n=10, bins=1000):
        waveforms_dir = report_root / "waveforms"
        waveforms_dir.mkdir(parents=True, exist_ok=True)
        overview = waveforms_dir / "top_mixability_overview.svg"
        index = waveforms_dir / "index.html"
        overview.write_text("<svg/>")
        index.write_text("<html/>")
        return {"overview": overview, "index": index}

    monkeypatch.setattr("dancelab.visualization.decision_report.render_mixability_waveform_gallery", fake_waveforms)

    paths = build_decision_report(processed, report, top_n_waveforms=5)

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

    assert paths["waveform_index"].exists()
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


def test_waveform_gallery_uses_local_analysis_summary(monkeypatch, tmp_path):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    source_a = tmp_path / "a.wav"
    source_b = tmp_path / "b.wav"
    source_a.write_bytes(b"fake")
    source_b.write_bytes(b"fake")

    analysis_a = make_analysis("a", source_a, 128, "8A", "Track A")
    analysis_b = make_analysis("b", source_b, 129, "9A", "Track B")
    (report_dir / "analysis_summary.json").write_text(
        json.dumps(
            {
                "analysis_root": str(tmp_path),
                "track_count": 2,
                "tracks": [
                    {"track_id": "a", "json_path": str(tmp_path / "a.json")},
                    {"track_id": "b", "json_path": str(tmp_path / "b.json")},
                ],
            }
        )
    )
    (tmp_path / "a.json").write_text(analysis_a.model_dump_json())
    (tmp_path / "b.json").write_text(analysis_b.model_dump_json())
    (report_dir / "decision_summary.json").write_text(
        json.dumps({"analysis_root": str(tmp_path)})
    )
    (report_dir / "mixability_pairs.json").write_text(
        json.dumps(
            [
                {
                    "track_a_id": "a",
                    "track_b_id": "b",
                    "track_a_title": "Track A",
                    "track_b_title": "Track B",
                    "mixability": {
                        "mixability_score": 0.7,
                        "confidence": 0.4,
                        "risks": [],
                        "best_pair_windows": [
                            {
                                "track_a_window": [10.0, 26.0],
                                "track_b_window": [4.0, 20.0],
                                "pair_score": 1.9,
                            }
                        ],
                    },
                    "edge_decision": {
                        "decision_class": "review_required",
                        "recommended_transition_strategy": "echo_out",
                    },
                }
            ]
        )
    )

    monkeypatch.setattr(
        "dancelab.visualization.mixability_waveforms._load_peaks",
        lambda *args, **kwargs: [(-0.2, 0.2), (-0.4, 0.5), (-0.1, 0.1)],
    )

    from dancelab.visualization.mixability_waveforms import render_mixability_waveform_gallery

    paths = render_mixability_waveform_gallery(report_dir, top_n=1)
    assert paths["index"].exists()
    assert "echo out" in paths["index"].read_text()

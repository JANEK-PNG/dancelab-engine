"""Validation pack builder contracts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from dancelab.core.models import AnalysisResult, FeatureFrame, Track
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.validation.pilot_pack import build_validation_pack
from dancelab.validation.preview_timing import quantized_cue_and_start


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def make_analysis(track_id: str, title: str, bpm: float, rms: float) -> AnalysisResult:
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=track_id,
            title=title,
            bpm_estimate=bpm,
            key_estimate="8A",
            key_confidence=0.9,
            style_label="techno",
        ),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=rms,
                low_freq_energy_ratio=0.45,
                vocal_density_proxy=0.1,
                bass_energy=50.0,
                tension_proxy=0.4,
                release_proxy=0.2,
            )
            for t in range(90)
        ],
    )


def seed_annotations(root: Path) -> None:
    write_csv(
        root / "track_metadata.csv",
        ["track_id", "title", "artist", "duration_sec", "bpm", "style", "key", "source"],
        [
            ["t1", "Track 1", "", "300", "128", "techno", "", ""],
            ["t2", "Track 2", "", "320", "129", "techno", "", ""],
            ["ghost", "Ghost", "", "200", "120", "house", "", ""],
        ],
    )
    write_csv(
        root / "segment_annotations.csv",
        ["segment_id", "track_id", "start_sec", "end_sec", "segment_type", "phrase_length_bars", "energy_level", "tension_level", "vocal_presence", "bass_intensity", "comment"],
        [],
    )
    write_csv(
        root / "transition_window_annotations.csv",
        ["window_id", "track_id", "window_type", "start_sec", "end_sec", "dj_rating", "engine_candidate", "reason_good", "risk_notes"],
        [
            ["t1_tw1", "t1", "mix_out", "100", "116", "", "true", "", ""],
            ["t2_tw1", "t2", "mix_in", "12", "28", "", "true", "", ""],
            ["ghost_tw1", "ghost", "bridge", "50", "66", "", "true", "", ""],
        ],
    )
    write_csv(
        root / "mixability_pair_annotations.csv",
        ["pair_id", "track_id_a", "track_id_b", "window_a_id", "window_b_id", "dj_mixability_rating", "tempo_fit_rating", "phrase_fit_rating", "bass_conflict_rating", "vocal_conflict_rating", "tension_fit_rating", "comment"],
        [],
    )
    write_csv(
        root / "set_function_labels.csv",
        ["track_id", "context_profile_id", "primary_function", "secondary_functions", "dj_confidence", "reasoning", "risk_notes"],
        [],
    )
    write_csv(
        root / "context_profiles.csv",
        ["context_profile_id", "venue_type", "set_role", "time_of_night", "crowd_energy", "style_focus"],
        [["festival_daytime", "festival", "builder", "14:00-18:00", "medium", "tech-house"]],
    )
    write_csv(
        root / "exp009_dj_window_review.csv",
        ["title", "track_id", "window_id", "engine_window_type", "engine_window(mm:ss)", "engine_score", "engine_risk", "dj_verdict(good/bad)", "dj_own_window(mm:ss-mm:ss)", "dj_comment"],
        [
            ["Track 1", "t1", "t1_tw1", "mix_out", "1:40-1:56", "0.83", "0.2", "good", "1:42-1:58", ""],
            ["Track 1", "t1", "t1_tw2", "bridge", "0:40-0:56", "0.70", "0.2", "", "", ""],
            ["Track 2", "t2", "t2_tw1", "mix_in", "0:12-0:28", "0.81", "0.2", "", "", ""],
            ["Ghost", "ghost", "ghost_tw1", "bridge", "0:50-1:06", "0.75", "0.2", "bad", "", ""],
        ],
    )
    write_csv(
        root / "exp011_set_function_review.csv",
        ["title", "track_id", "engine_primary", "engine_secondary", "engine_conf", "engine_risk", "dj_primary", "dj_comment"],
        [
            ["Track 1", "t1", "builder", "bridge", "0.3", "0.4", "builder", ""],
            ["Track 2", "t2", "bridge", "", "0.2", "0.6", "peak", ""],
            ["Ghost", "ghost", "opener", "", "0.2", "0.5", "", ""],
        ],
    )
    write_csv(
        root / "annotation_sheet.csv",
        ["track_id", "title", "duration_sec", "style", "bpm", "set_function(opener/builder/peak/closer)", "groove_rating_1_5", "tension_rating_1_5", "release_rating_1_5", "best_transition_window_1(mm:ss-mm:ss)", "best_transition_window_2", "notes"],
        [
            ["t1", "Track 1", "300", "techno", "128", "", "", "", "", "", "", ""],
            ["t2", "Track 2", "320", "techno", "129", "", "", "", "", "", "", ""],
            ["ghost", "Ghost", "200", "house", "120", "", "", "", "", "", "", ""],
        ],
    )


def test_build_validation_pack_filters_to_active_corpus(tmp_path):
    processed = tmp_path / "processed"
    annotations = tmp_path / "annotations"
    report = tmp_path / "validation_pack"
    repo = FileAnalysisRepository(processed)
    repo.save(make_analysis("t1", "Track 1", 128, 0.42))
    repo.save(make_analysis("t2", "Track 2", 129, 0.48))
    seed_annotations(annotations)

    paths = build_validation_pack(processed, report, annotations_dir=annotations)

    summary = json.loads(paths["summary_json"].read_text())
    subset_track_rows = list(csv.DictReader((report / "track_metadata_subset.csv").open(encoding="utf-8")))
    subset_exp009_rows = list(csv.DictReader((report / "exp009_dj_window_review_subset.csv").open(encoding="utf-8")))

    assert summary["analyzed_track_count"] == 2
    assert summary["annotation_valid"] is True
    assert summary["overlap"]["annotated_track_overlap_count"] == 2
    assert summary["subset_counts"]["track_metadata"] == 2
    assert summary["metrics"]["transition_windows"]["review_track_count"] == 1
    assert summary["metrics"]["set_function"]["labeled_track_count"] == 2
    assert subset_track_rows[0]["track_id"] in {"t1", "t2"}
    assert {row["track_id"] for row in subset_exp009_rows} == {"t1", "t2"}


def test_build_validation_pack_uses_pair_review_when_available(tmp_path):
    processed = tmp_path / "processed"
    annotations = tmp_path / "annotations"
    output = tmp_path / "validation_pack"
    report_dir = tmp_path / "decision_report"
    repo = FileAnalysisRepository(processed)
    repo.save(make_analysis("t1", "Track 1", 128, 0.42))
    repo.save(make_analysis("t2", "Track 2", 129, 0.48))
    repo.save(make_analysis("t3", "Track 3", 130, 0.54))
    seed_annotations(annotations)
    write_csv(
        report_dir / "edge_decision_review.csv",
        [
            "pair_id",
            "track_id_a",
            "track_id_b",
            "title_a",
            "title_b",
            "engine_score",
            "engine_blend_profile_auto",
            "engine_blend_profile_explanation",
            "dj_mixability_rating",
        ],
        [
            ["p1", "t1", "t2", "Track 1", "Track 2", "0.20", "plain_blend", "Auto mode selects plain blend.", "1"],
            ["p2", "t2", "t3", "Track 2", "Track 3", "0.55", "bass_swap", "Auto mode selects bass swap because bass conflict risk is elevated.", "3"],
            ["p3", "t3", "t1", "Track 3", "Track 1", "0.91", "tops_swap", "Auto mode selects tops swap because short blend prefers a tighter upper-band handoff.", "5"],
        ],
    )

    paths = build_validation_pack(
        processed,
        output,
        annotations_dir=annotations,
        report_dir=report_dir,
    )

    summary = json.loads(paths["summary_json"].read_text())
    pair_metrics = summary["metrics"]["mixability_pairs"]

    assert pair_metrics["rated_pair_count"] == 3
    assert pair_metrics["pearson_r"] == pytest.approx(1.0, abs=1e-4)
    assert pair_metrics["spearman_rho"] == pytest.approx(1.0)
    assert pair_metrics["kendall_tau"] == pytest.approx(1.0)


def test_preview_timing_quantizes_to_eight_beat_grid():
    beat_times = [index * 0.5 for index in range(81)]
    downbeats = [index * 2.0 for index in range(21)]

    cue_a, start_a, lead_a = quantized_cue_and_start(
        20.0,
        beat_times,
        downbeats,
    )
    cue_b, start_b, lead_b = quantized_cue_and_start(
        9.0,
        beat_times,
        downbeats,
    )

    assert cue_a == pytest.approx(20.0)
    assert start_a == pytest.approx(12.0)
    assert lead_a == 16
    assert cue_b == pytest.approx(8.0)
    assert start_b == pytest.approx(0.0)
    assert lead_b == 16

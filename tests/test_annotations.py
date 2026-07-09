"""Dataset & Annotation Pipeline — tests per ticket DoD:
schema validators, dataset loading, error report, works without audio."""

import csv
from pathlib import Path

import pytest

from dancelab.data.annotation_loader import (
    AnnotationFileError,
    load_set_function_labels,
    load_track_metadata,
    load_transition_windows,
)
from dancelab.data.annotation_validator import validate_annotation_dataset
from dancelab.validation.dj_decision_metrics import (
    false_positive_rate,
    mean_overlap,
    rating_correlation,
    top_k_hit,
    window_overlap_sec,
)


def write_csv(path: Path, header: list[str], rows: list[list]):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def dataset(tmp_path):
    """Minimal valid dataset."""
    write_csv(tmp_path / "track_metadata.csv",
              ["track_id", "title", "duration_sec", "bpm", "style"],
              [["t1", "Track One", "300", "128", "techno"],
               ["t2", "Track Two", "240", "", ""]])
    write_csv(tmp_path / "transition_window_annotations.csv",
              ["window_id", "track_id", "window_type", "start_sec", "end_sec",
               "dj_rating", "engine_candidate", "reason_good", "risk_notes"],
              [["t1_tw1", "t1", "mix_out", "250", "280", "4", "true", "phrase ok", ""]])
    write_csv(tmp_path / "mixability_pair_annotations.csv",
              ["pair_id", "track_id_a", "track_id_b", "dj_mixability_rating", "comment"],
              [["p1", "t1", "t2", "4", ""]])
    write_csv(tmp_path / "set_function_labels.csv",
              ["track_id", "context_profile_id", "primary_function",
               "secondary_functions", "dj_confidence"],
              [["t1", "club_peak", "peak", "builder;tension_builder", "4"]])
    write_csv(tmp_path / "context_profiles.csv",
              ["context_profile_id", "venue_type", "set_role"],
              [["club_peak", "club", "peak"]])
    return tmp_path


def test_loaders_parse_types(dataset):
    tracks = load_track_metadata(dataset / "track_metadata.csv")
    assert tracks[0].bpm == 128.0
    assert tracks[1].bpm is None  # empty stays None — never fabricated
    windows = load_transition_windows(dataset / "transition_window_annotations.csv")
    assert windows[0].engine_candidate is True and windows[0].dj_rating == 4
    labels = load_set_function_labels(dataset / "set_function_labels.csv")
    assert labels[0].secondary_functions == ["builder", "tension_builder"]


def test_missing_column_fails_loud(tmp_path):
    write_csv(tmp_path / "track_metadata.csv", ["title"], [["no id"]])
    with pytest.raises(AnnotationFileError, match="missing columns"):
        load_track_metadata(tmp_path / "track_metadata.csv")


def test_valid_dataset_passes(dataset):
    report = validate_annotation_dataset(dataset)
    assert report.valid, report.errors
    assert report.counts["track_metadata"] == 2
    # segments file absent → warning, not error (ticket: report, don't crash)
    assert any("segment_annotations.csv missing" in w for w in report.warnings)


def test_validator_catches_cross_reference_errors(dataset):
    write_csv(dataset / "mixability_pair_annotations.csv",
              ["pair_id", "track_id_a", "track_id_b", "dj_mixability_rating", "comment"],
              [["p1", "t1", "GHOST", "5", ""]])
    report = validate_annotation_dataset(dataset)
    assert not report.valid
    assert any("unknown track_id_b 'GHOST'" in e for e in report.errors)
    assert any("rating 5 without comment" in w for w in report.warnings)


def test_validator_catches_bad_spans_and_roles(dataset):
    write_csv(dataset / "transition_window_annotations.csv",
              ["window_id", "track_id", "window_type", "start_sec", "end_sec",
               "dj_rating", "engine_candidate", "reason_good", "risk_notes"],
              [["w_bad", "t1", "mix_out", "290", "250", "", "false", "", ""],
               ["w_long", "t2", "mix_in", "100", "500", "", "false", "", ""]])
    write_csv(dataset / "set_function_labels.csv",
              ["track_id", "context_profile_id", "primary_function",
               "secondary_functions", "dj_confidence"],
              [["t1", "club_peak", "banger", "", ""]])
    report = validate_annotation_dataset(dataset)
    msgs = " | ".join(report.errors)
    assert "start_sec 290.0 >= end_sec 250.0" in msgs
    assert "beyond track duration" in msgs
    assert "unknown role 'banger'" in msgs


def test_depends_is_a_legal_label(dataset):
    write_csv(dataset / "set_function_labels.csv",
              ["track_id", "context_profile_id", "primary_function",
               "secondary_functions", "dj_confidence"],
              [["t1", "club_peak", "depends", "", "2"]])
    assert validate_annotation_dataset(dataset).valid


def test_real_repo_annotation_dir_is_valid():
    """The shipped contract files (prefilled from engine outputs) must validate."""
    report = validate_annotation_dataset("data/annotations")
    assert report.valid, report.errors
    assert report.counts["track_metadata"] > 0
    assert report.counts["transition_windows"] > 0


# ------------------------------------------------------------- EXP009 metrics


def test_window_overlap_and_topk():
    engine = [(100.0, 116.0), (200.0, 216.0)]
    dj = [(110.0, 130.0)]
    assert window_overlap_sec(engine[0], dj[0]) == 6.0
    assert top_k_hit(engine, dj, k=1, min_overlap_sec=4.0) is True
    assert top_k_hit(engine, dj, k=1, min_overlap_sec=10.0) is False
    assert false_positive_rate(engine, dj) == 0.5
    assert 0 < mean_overlap(engine, dj) < 1


def test_rating_correlation_honest_none():
    assert rating_correlation([0.5, 0.6], [3, 4]) is None          # too few
    assert rating_correlation([0.5, 0.5, 0.5], [1, 3, 5]) is None  # zero variance
    r = rating_correlation([0.1, 0.5, 0.9], [1, 3, 5])
    assert r == pytest.approx(1.0)

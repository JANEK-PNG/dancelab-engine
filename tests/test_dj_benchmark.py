"""DJ transition rating benchmark tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from dancelab.validation.dj_benchmark import (
    build_benchmark_summary,
    load_rating_rows,
    write_benchmark_report,
)


def write_ratings(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "pair_id",
            "track_id_a",
            "track_id_b",
            "engine_score",
            "dj_mixability_rating",
            "comment",
            "blind",
        ])
        writer.writerows(rows)


def complete_session_rows(offset: int = 0) -> list[list[object]]:
    rows: list[list[object]] = []
    for index in range(30):
        rating = 1 + (index % 5)
        engine_score = 0.2 + (rating * 0.13)
        rows.append([
            f"p{offset}_{index}",
            f"t{offset}_{index}",
            f"u{offset}_{index}",
            f"{engine_score:.4f}",
            rating,
            "beatgrid bpm style" if index == 0 else "",
            1 if index % 2 == 0 else 0,
        ])
    return rows


def test_benchmark_requires_five_complete_sessions(tmp_path):
    write_ratings(
        tmp_path / "Janek_transition_ratings.csv",
        [
            ["dup", "a", "b", "0.9000", "1", "rozjechany beatgrid bpm", 0],
            ["dup", "a", "b", "0.8500", "2", "duplikat albo ta sama plyta", 0],
            ["ok", "b", "c", "0.7000", "5", "styl i energia super", 0],
        ],
    )

    summary = build_benchmark_summary([tmp_path], min_sessions=5, min_rated_transitions_per_session=3)

    assert summary.session_count == 1
    assert summary.complete_session_count == 1
    assert summary.required_additional_sessions == 4
    assert summary.is_ready_for_tuning is False
    assert summary.false_positive_count == 2
    assert summary.sessions[0].duplicate_pair_count == 1
    assert summary.topic_counts["bpm_grid_sync"] == 1
    assert summary.topic_counts["duplicates_same_album"] == 1
    assert summary.top_false_positives[0].pair_id == "dup"


def test_benchmark_is_ready_after_five_complete_sessions(tmp_path):
    for session_index in range(5):
        write_ratings(
            tmp_path / f"DJ_{session_index}_transition_ratings.csv",
            complete_session_rows(session_index),
        )

    summary = build_benchmark_summary([tmp_path])

    assert summary.session_count == 5
    assert summary.complete_session_count == 5
    assert summary.required_additional_sessions == 0
    assert summary.is_ready_for_tuning is True
    assert summary.total_rated_count == 150
    assert summary.overall_pearson_r == pytest.approx(1.0, abs=1e-9)
    assert summary.topic_counts["bpm_grid_sync"] == 5


def test_write_benchmark_report_outputs_json_and_markdown(tmp_path):
    ratings = tmp_path / "ratings"
    write_ratings(ratings / "Janek_transition_ratings.csv", complete_session_rows())
    summary = build_benchmark_summary([ratings])

    outputs = write_benchmark_report(summary, tmp_path / "report")

    assert outputs["summary_json"].exists()
    assert outputs["summary_md"].exists()
    payload = json.loads(outputs["summary_json"].read_text())
    assert payload["session_count"] == 1
    markdown = outputs["summary_md"].read_text()
    assert "DJ Validation Benchmark" in markdown
    assert "NOT READY FOR TUNING" in markdown


def test_load_rating_rows_skips_unrated_rows(tmp_path):
    path = tmp_path / "Anon_transition_ratings.csv"
    write_ratings(
        path,
        [
            ["rated", "a", "b", "0.5000", "4", "", 1],
            ["missing_rating", "b", "c", "0.6000", "", "", 0],
        ],
    )

    rows = load_rating_rows(path)

    assert len(rows) == 1
    assert rows[0].pair_id == "rated"
    assert rows[0].blind is True

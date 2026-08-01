"""Regression tests for untrusted metadata crossing output boundaries."""

from __future__ import annotations

import csv

from dancelab.security import spreadsheet_safe_value
from dancelab.validation.transition_edits import (
    TransitionEditEvent,
    append_transition_edit,
)

def test_csv_formula_prefixes_are_neutralized():
    for value in ("=2+2", " +SUM(A1:A2)", "-1+2", "@cmd", "\t=1", "\r=1"):
        assert spreadsheet_safe_value(value).startswith("'")
    assert spreadsheet_safe_value("Track Title") == "Track Title"


def test_transition_edit_csv_neutralizes_formula_metadata(tmp_path):
    path = tmp_path / "transition_edits.csv"
    append_transition_edit(
        path,
        TransitionEditEvent(
            pair_id="track-a__track-b",
            track_id_a="track-a",
            track_id_b="track-b",
            deck="B",
            track_id="track-b",
            action="hot_cue_set",
            marker_type="mix_in",
            marker_name="=HYPERLINK(\"https://example.invalid\")",
            user_start_sec=16.0,
            annotator="@untrusted",
        ),
    )

    with path.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["marker_name"].startswith("'=")
    assert row["annotator"].startswith("'@")

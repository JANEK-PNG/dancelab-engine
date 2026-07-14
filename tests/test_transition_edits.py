from __future__ import annotations

import csv

import pytest

from dancelab.validation.transition_edits import (
    TransitionEditEvent,
    append_transition_edit,
    latest_transition_edits,
    transition_edits_path,
)


def _event(**updates) -> TransitionEditEvent:
    values = {
        "pair_id": "track_a__track_b",
        "track_id_a": "track_a",
        "track_id_b": "track_b",
        "deck": "B",
        "track_id": "track_b",
        "action": "transition_region_set",
        "marker_type": "mix_in",
        "reference_source": "engine_transition_window",
        "reference_start_sec": 16.0,
        "reference_end_sec": 32.0,
        "user_start_sec": 24.0,
        "user_end_sec": 40.0,
        "quantize_grid_beats": 8,
        "beatgrid_reliable": True,
        "annotator": "Jan Tester",
    }
    values.update(updates)
    return TransitionEditEvent(**values)


def test_transition_edits_are_append_only_and_restore_latest(tmp_path):
    path = transition_edits_path(tmp_path, "Jan Tester")
    first = append_transition_edit(path, _event())
    second = append_transition_edit(
        path,
        _event(user_start_sec=32.0, user_end_sec=48.0),
    )

    assert first.event_id and first.recorded_at_utc
    assert second.event_id != first.event_id
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["reference_start_sec"] == "16.000000"
    assert rows[1]["user_start_sec"] == "32.000000"
    assert rows[1]["quantize_grid_beats"] == "8"

    latest = latest_transition_edits(path, "track_a__track_b")
    restored = latest[("B", "transition_region_set", "")]
    assert restored["user_start_sec"] == "32.000000"
    assert restored["user_end_sec"] == "48.000000"


def test_transition_edit_rejects_reversed_region():
    with pytest.raises(ValueError, match="cannot precede"):
        _event(user_start_sec=40.0, user_end_sec=20.0)

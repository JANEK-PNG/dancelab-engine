"""Regression tests for untrusted metadata crossing output boundaries."""

from __future__ import annotations

import csv

from dancelab.security import json_for_inline_script, spreadsheet_safe_value
from dancelab.validation.review_ui.swipe_review import (
    _download_script,
    _render_pair_page,
)
from dancelab.validation.transition_edits import (
    TransitionEditEvent,
    append_transition_edit,
)


def test_inline_json_cannot_close_script_element():
    payload = json_for_inline_script(
        {"title": "</script><script id=pwned>&window.pwned=true</script>"}
    )

    assert "</script>" not in payload
    assert "\\u003c/script\\u003e" in payload
    assert "\\u0026" in payload


def test_review_page_escapes_metadata_at_script_and_dom_boundaries(tmp_path):
    attack = "</script><script id=pwned>window.pwned=true</script>"
    output = _render_pair_page(
        [
            {
                "id": "pair-1",
                "title": attack,
                "image_path": "javascript:alert(1)",
                "row": {"title_a": attack},
            }
        ],
        ["title_a"],
        tmp_path / "pairs.html",
    )
    html = output.read_text(encoding="utf-8")

    assert attack not in html
    assert "\\u003c/script\\u003e" in html
    assert "function displayItem(item)" in html
    assert "function safeLocalUrl(value)" in html
    assert "renderCard(displayItem(item))" in html


def test_csv_formula_prefixes_are_neutralized():
    for value in ("=2+2", " +SUM(A1:A2)", "-1+2", "@cmd", "\t=1", "\r=1"):
        assert spreadsheet_safe_value(value).startswith("'")
    assert spreadsheet_safe_value("Track Title") == "Track Title"
    assert "/^[=+\\-@\\t\\r]/" in _download_script()


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

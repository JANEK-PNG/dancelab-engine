"""Write-safety rules, tested WITHOUT a Rekordbox database.

These are the rules that protect the DJ's library. They must be verifiable on
any machine — CI, a fresh clone, or while Rekordbox is open — which is exactly
what the database-backed writer tests cannot do.
"""

import pytest

from dancelab.decision.cue_export_models import CuePlan, TrackCuePlan, PlannedCue
from dancelab.decision.cue_write_ops import (
    ExistingPadCue,
    resolve_write_operations,
)


def _plan(kind=5, pad="D", replace=False, content_id="t1"):
    return CuePlan(tracks=[TrackCuePlan(content_id=content_id, cues=[
        PlannedCue(content_id=content_id, position_ms=61000, kind=kind,
                   pad_label=pad, comment="MIX IN", cue_type="mix_in",
                   replace_existing=replace),
    ])])


def test_free_pad_inserts_without_deleting():
    ops = resolve_write_operations(
        _plan(), known_content_ids={"t1"}, existing_pad_cues=[]
    )
    assert ops.written == 1
    assert ops.deleted == 0


def test_occupied_pad_without_permission_is_refused():
    with pytest.raises(ValueError, match="no replace permission"):
        resolve_write_operations(
            _plan(replace=False), known_content_ids={"t1"},
            existing_pad_cues=[ExistingPadCue(content_id="t1", kind=5, comment="DJ OWN")],
        )


def test_occupied_pad_with_permission_deletes_then_inserts():
    ops = resolve_write_operations(
        _plan(replace=True), known_content_ids={"t1"},
        existing_pad_cues=[ExistingPadCue(content_id="t1", kind=5, comment="DJ OWN")],
    )
    assert ops.deleted == 1 and ops.written == 1
    assert ops.deletes[0].comment == "DJ OWN"


def test_unknown_track_is_refused():
    with pytest.raises(ValueError, match="not in this Rekordbox database"):
        resolve_write_operations(
            _plan(content_id="ghost"), known_content_ids={"t1"}, existing_pad_cues=[]
        )


def test_a_cue_on_another_pad_does_not_block_us():
    """Only the same (track, pad) blocks — a cue elsewhere is irrelevant."""
    ops = resolve_write_operations(
        _plan(kind=5), known_content_ids={"t1"},
        existing_pad_cues=[ExistingPadCue(content_id="t1", kind=1, comment="INTRO")],
    )
    assert ops.written == 1 and ops.deleted == 0


def test_a_cue_on_the_same_pad_of_another_track_does_not_block_us():
    ops = resolve_write_operations(
        _plan(content_id="t1"), known_content_ids={"t1"},
        existing_pad_cues=[ExistingPadCue(content_id="t2", kind=5, comment="OTHER")],
    )
    assert ops.written == 1 and ops.deleted == 0


def test_track_with_no_cues_needs_no_database_entry():
    """An empty track is skipped before the existence check — nothing to write."""
    plan = CuePlan(tracks=[TrackCuePlan(content_id="ghost", cues=[])])
    ops = resolve_write_operations(plan, known_content_ids=set(), existing_pad_cues=[])
    assert ops.written == 0 and ops.deleted == 0

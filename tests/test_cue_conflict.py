"""Conflict resolution: skip / replace / merge + dedup + review."""

from dancelab.decision.cue_conflict import resolve_conflicts, ExistingCue
from dancelab.decision.cue_export_models import (
    CuePlan, TrackCuePlan, PlannedCue, ConflictAction,
)


def _plan_one(pad_label="A", kind=1, pos=30000):
    return CuePlan(tracks=[TrackCuePlan(content_id="B", cues=[
        PlannedCue(content_id="B", position_ms=pos, kind=kind,
                   pad_label=pad_label, cue_type="mix_in")
    ])])


def test_merge_relocates_to_free_pad_on_pad_conflict():
    existing = {"B": [ExistingCue(pad_index=1, position_ms=15000, comment="INTRO")]}
    plan2, report = resolve_conflicts(_plan_one(), existing,
                                      action=ConflictAction.merge, review=False)
    cue = plan2.tracks[0].cues[0]
    assert cue.pad_label != "A" and cue.kind != 1  # moved off pad A
    assert report.conflict_count == 1


def test_merge_dedups_same_position():
    existing = {"B": [ExistingCue(pad_index=2, position_ms=30200, comment="mine")]}
    plan2, report = resolve_conflicts(_plan_one(pos=30000), existing,
                                      action=ConflictAction.merge, review=False)
    assert plan2.tracks[0].cues == []  # ours dropped as duplicate


def test_skip_drops_our_cue_on_pad_conflict():
    existing = {"B": [ExistingCue(pad_index=1, position_ms=15000, comment="INTRO")]}
    plan2, report = resolve_conflicts(_plan_one(), existing,
                                      action=ConflictAction.skip, review=False)
    assert plan2.tracks[0].cues == []
    assert report.conflict_count == 1


def test_replace_keeps_our_cue_and_counts_overwrite():
    existing = {"B": [ExistingCue(pad_index=1, position_ms=15000, comment="INTRO")]}
    plan2, report = resolve_conflicts(_plan_one(), existing,
                                      action=ConflictAction.replace, review=False)
    assert len(plan2.tracks[0].cues) == 1
    assert plan2.tracks[0].cues[0].pad_label == "A"  # stays on the pad
    assert report.overwrite_count == 1


def test_no_conflict_passes_through():
    plan2, report = resolve_conflicts(_plan_one(), {"B": []},
                                      action=ConflictAction.merge, review=False)
    assert len(plan2.tracks[0].cues) == 1
    assert report.conflict_count == 0
    assert report.cues_to_write == 1


def test_merge_no_free_pad_drops_and_reports():
    existing = {"B": [ExistingCue(pad_index=i, position_ms=1000 * i, comment=f"c{i}")
                      for i in range(1, 9)]}  # all 8 pads full
    plan2, report = resolve_conflicts(_plan_one(), existing,
                                      action=ConflictAction.merge, review=False)
    assert plan2.tracks[0].cues == []
    assert any(it.resolution == "no_free_pad" for it in report.items)


def test_review_marks_clean_cue_needs_decision():
    plan2, report = resolve_conflicts(_plan_one(), {"B": []},
                                      action=ConflictAction.merge, review=True)
    assert len(report.items) == 1
    assert report.items[0].needs_decision is True
    assert report.items[0].resolution == "placed"

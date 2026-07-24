"""Cue-export models + pad/kind mapping."""

from dancelab.decision.cue_export_models import (
    pad_index_to_kind,
    kind_to_pad_index,
    PlannedCue,
)


def test_pad_kind_mapping_reserves_kind4():
    assert [pad_index_to_kind(i) for i in range(1, 9)] == [1, 2, 3, 5, 6, 7, 8, 9]
    assert kind_to_pad_index(5) == 4
    assert kind_to_pad_index(4) is None  # reserved
    assert kind_to_pad_index(0) is None  # memory cue


def test_planned_cue_defaults_confident_true():
    c = PlannedCue(
        content_id="1", position_ms=1000, kind=1, pad_label="A",
        color=-1, comment="MIX IN", cue_type="mix_in",
    )
    assert c.confident is True

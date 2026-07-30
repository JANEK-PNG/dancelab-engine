"""Cue-export domain models — the pure planner's vocabulary (SPEC: cue export).

No I/O here. These types describe *what* cues to write; the writer layer
(`ingestion/rekordbox_cue_writer.py`) turns a CuePlan into master.db rows.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

PAD_NAMES = "ABCDEFGH"


class CueContentMode(str, Enum):
    """What the engine puts on the pads."""

    none = "none"
    in_out = "in_out"
    structural = "structural"


class ConflictAction(str, Enum):
    """OS file-copy metaphor for pad/position collisions with the DJ's cues."""

    skip = "skip"
    replace = "replace"
    merge = "merge"


def pad_index_to_kind(pad_index: int) -> int:
    """pad_index 1..8 (A..H) -> Rekordbox DjmdCue.Kind.

    Rekordbox reserves Kind=4, so pads A/B/C map to 1/2/3 and pad D..H map to
    pad_index+1 (5..9). Kind=0 is a memory cue (not a pad).
    """
    if not 1 <= pad_index <= 8:
        raise ValueError(f"pad_index out of range (1..8): {pad_index}")
    return pad_index if pad_index <= 3 else pad_index + 1


def kind_to_pad_index(kind: int) -> int | None:
    """Inverse of pad_index_to_kind. None for non-pad kinds (0 memory, 4 reserved)."""
    if kind in (0, 4):
        return None
    if 1 <= kind <= 3:
        return kind
    if 5 <= kind <= 9:
        return kind - 1
    return None


class PlannedCue(BaseModel):
    """One cue the engine intends to write to one track."""

    content_id: str
    position_ms: int = Field(ge=0)
    kind: int
    pad_label: str
    color: int = -1
    comment: str = ""
    cue_type: str = "mix_in"  # mix_in|mix_out|drop|breakdown|phrase|unverified
    confident: bool = True
    # Permission to destroy whatever already occupies this pad. Only conflict
    # resolution may grant it; a writer must never infer it. Default False keeps
    # the DJ's cues safe even when a plan reaches a writer unresolved.
    replace_existing: bool = False
    reasoning: list[str] = Field(default_factory=list)


class TrackCuePlan(BaseModel):
    """All planned cues for a single track."""

    content_id: str
    track_title: str = ""
    cues: list[PlannedCue] = Field(default_factory=list)


class CuePlan(BaseModel):
    """The full set-level plan, ready for conflict resolution + writing."""

    mode: CueContentMode = CueContentMode.in_out
    tracks: list[TrackCuePlan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

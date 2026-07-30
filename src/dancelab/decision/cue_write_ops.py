"""What a cue write would do, decided without touching a database.

The rules that protect the DJ's library — never clear a pad without explicit
permission, never write to a track that is not there — used to live inside the
Rekordbox writer, where they could only be tested on a machine that happens to
have a real Rekordbox library. That made the most dangerous logic in the project
the least tested: those tests silently skip on CI, on a fresh clone, and while
Rekordbox is open.

The decision now lives here as a pure function over plain data, so it is tested
everywhere. The writer stays a thin executor of the operations returned.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from dancelab.decision.cue_export_models import CuePlan, PlannedCue


class ExistingPadCue(BaseModel):
    """A cue already occupying a pad, as seen by the writer."""

    content_id: str
    kind: int
    comment: str = ""


class WriteOperations(BaseModel):
    """Deletes to perform before inserts, and the cues to insert."""

    deletes: list[ExistingPadCue] = Field(default_factory=list)
    inserts: list[PlannedCue] = Field(default_factory=list)

    @property
    def written(self) -> int:
        return len(self.inserts)

    @property
    def deleted(self) -> int:
        return len(self.deletes)


def resolve_write_operations(
    plan: CuePlan,
    *,
    known_content_ids: set[str],
    existing_pad_cues: list[ExistingPadCue],
) -> WriteOperations:
    """Turn a resolved CuePlan into the exact deletes and inserts to perform.

    Raises ValueError when the plan asks for something unsafe: a track this
    database does not have, or a pad that is occupied by a cue the plan has no
    permission to replace (which means conflict resolution was skipped).
    """
    occupied: dict[tuple[str, int], ExistingPadCue] = {
        (c.content_id, c.kind): c for c in existing_pad_cues
    }
    ops = WriteOperations()

    for track in plan.tracks:
        if not track.cues:
            continue
        if str(track.content_id) not in known_content_ids:
            raise ValueError(
                f"track {track.content_id} is not in this Rekordbox database"
            )
        for cue in track.cues:
            blocker = occupied.get((str(track.content_id), cue.kind))
            if blocker is not None:
                if not cue.replace_existing:
                    raise ValueError(
                        f"pad {cue.pad_label} on track {track.content_id} already holds a "
                        f"cue ({blocker.comment!r}) and this cue has no replace permission "
                        "— resolve conflicts before writing"
                    )
                ops.deletes.append(blocker)
            ops.inserts.append(cue)

    return ops

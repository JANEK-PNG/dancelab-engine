"""Conflict resolution between a CuePlan and the DJ's existing cues.

OS file-copy metaphor: on a collision (target pad occupied, or our cue at ~the
same position as an existing one) the caller picks skip / replace / merge.
`merge` keeps the DJ's cue and relocates ours to a free pad, and dedups (drops
ours) when a cue already sits at ~the same spot — never a duplicate. This layer
is pure: it decides *what* to write and reports collisions; the writer performs
any deletions (`replace`).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from dancelab.decision.cue_export_models import (
    CuePlan,
    TrackCuePlan,
    ConflictAction,
    pad_index_to_kind,
    kind_to_pad_index,
    PAD_NAMES,
)

DEFAULT_POS_TOLERANCE_MS = 750


class ExistingCue(BaseModel):
    """A cue already present on a track (adapted from a Rekordbox DjmdCue row)."""

    pad_index: int | None = None  # None = memory cue (not on a pad)
    position_ms: int
    comment: str = ""


class ConflictItem(BaseModel):
    content_id: str
    track_title: str = ""
    cue_type: str
    wanted_pad: str
    wanted_position_ms: int
    existing_pad: str | None = None
    existing_comment: str = ""
    resolution: str  # placed|skipped|relocated|replaced|deduped|no_free_pad
    new_pad: str | None = None
    needs_decision: bool = False


class ConflictReport(BaseModel):
    items: list[ConflictItem] = Field(default_factory=list)
    cues_to_write: int = 0
    conflict_count: int = 0
    overwrite_count: int = 0


def _pad_name(index: int) -> str:
    return PAD_NAMES[index - 1]


def _resolve_track(
    track: TrackCuePlan,
    existing: list[ExistingCue],
    *,
    action: ConflictAction,
    review: bool,
    pos_tol: int,
    report: ConflictReport,
) -> TrackCuePlan:
    taken = {e.pad_index for e in existing if e.pad_index is not None}
    survivors = []

    for cue in track.cues:
        our_pad = kind_to_pad_index(cue.kind)
        wanted_pad_name = cue.pad_label
        dup = next((e for e in existing if abs(e.position_ms - cue.position_ms) <= pos_tol), None)
        pad_taken = our_pad in taken

        item = ConflictItem(
            content_id=track.content_id, track_title=track.track_title,
            cue_type=cue.cue_type, wanted_pad=wanted_pad_name,
            wanted_position_ms=cue.position_ms, resolution="placed",
        )

        if dup is not None:
            report.conflict_count += 1
            item.existing_comment = dup.comment
            item.existing_pad = _pad_name(dup.pad_index) if dup.pad_index else None
            if action == ConflictAction.replace:
                report.overwrite_count += 1
                item.resolution = "replaced"
                survivors.append(cue.model_copy(update={"replace_existing": True}))
                if our_pad is not None:
                    taken.add(our_pad)
            else:  # skip or merge -> drop ours (already there)
                item.resolution = "deduped"
            report.items.append(item)
            continue

        if pad_taken:
            report.conflict_count += 1
            on_pad = next((e for e in existing if e.pad_index == our_pad), None)
            item.existing_pad = wanted_pad_name
            item.existing_comment = on_pad.comment if on_pad else ""
            if action == ConflictAction.skip:
                item.resolution = "skipped"
            elif action == ConflictAction.replace:
                report.overwrite_count += 1
                item.resolution = "replaced"
                survivors.append(cue.model_copy(update={"replace_existing": True}))
                taken.add(our_pad)
            else:  # merge -> relocate to next free pad
                free = next((p for p in range(1, 9) if p not in taken), None)
                if free is None:
                    item.resolution = "no_free_pad"
                else:
                    relocated = cue.model_copy(update={
                        "kind": pad_index_to_kind(free),
                        "pad_label": _pad_name(free),
                    })
                    survivors.append(relocated)
                    taken.add(free)
                    item.resolution = "relocated"
                    item.new_pad = _pad_name(free)
            report.items.append(item)
            continue

        # no conflict
        survivors.append(cue)
        if our_pad is not None:
            taken.add(our_pad)
        if review:
            item.needs_decision = True
            report.items.append(item)

    return track.model_copy(update={"cues": survivors})


_ACTIONS_BY_RESOLUTION = {
    "relocated": "[skip]  [replace]  [merge → {new}]",
    "skipped": "[skip]  [replace]  [merge → free pad]",
    "replaced": "[skip]  [replace ✓]  [merge]",
    "deduped": "already present — kept yours",
    "no_free_pad": "all pads full → [skip]  [replace]",
    "placed": "clean",
}


def render_report(report: ConflictReport) -> str:
    """OS-style, human-readable conflict report for --dry-run / --review."""
    lines: list[str] = []
    shown = [it for it in report.items if it.resolution != "placed" or it.needs_decision]
    if shown:
        lines.append(f"⚠ CONFLICTS ({report.conflict_count} of {len(report.items)} cues flagged):\n")
        for it in shown:
            title = it.track_title or it.content_id
            mins, secs = divmod(it.wanted_position_ms // 1000, 60)
            lines.append(f'  "{title}"')
            lines.append(f"     pad {it.wanted_pad}  ← want: {it.cue_type} @ {mins}:{secs:02d}")
            if it.existing_comment or it.existing_pad:
                where = f"pad {it.existing_pad}  " if it.existing_pad else ""
                lines.append(f'     {where}already: "{it.existing_comment}"')
            opt = _ACTIONS_BY_RESOLUTION.get(it.resolution, it.resolution)
            lines.append(f"     → {opt.replace('{new}', it.new_pad or '?')}")
            lines.append("")
    lines.append(
        f"Summary: {report.cues_to_write} cues to write · "
        f"{report.conflict_count} conflicts · {report.overwrite_count} overwrites"
    )
    return "\n".join(lines)


def resolve_conflicts(
    plan: CuePlan,
    existing_by_track: dict[str, list[ExistingCue]],
    *,
    action: ConflictAction = ConflictAction.merge,
    review: bool = False,
    pos_tolerance_ms: int = DEFAULT_POS_TOLERANCE_MS,
) -> tuple[CuePlan, ConflictReport]:
    report = ConflictReport()
    new_tracks = []
    for track in plan.tracks:
        existing = existing_by_track.get(track.content_id, [])
        new_tracks.append(
            _resolve_track(track, existing, action=action, review=review,
                           pos_tol=pos_tolerance_ms, report=report)
        )
    report.cues_to_write = sum(len(t.cues) for t in new_tracks)
    return plan.model_copy(update={"tracks": new_tracks}), report

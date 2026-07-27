"""Bridge: match a DanceLab set's tracks to Rekordbox ContentIDs.

The engine identifies a track by its own id / file path / title; Rekordbox
identifies it by DjmdContent.ID. To read the DJ's existing cues and write ours to
the RIGHT track, we resolve one to the other. Match order: exact file path
(strongest), then title+artist, then title alone. Anything unmatched is reported,
never guessed.
"""

from __future__ import annotations

import os

from pydantic import BaseModel


class TrackRef(BaseModel):
    """What we know about a track we want to place cues on."""

    track_id: str
    source_path: str | None = None
    title: str | None = None
    artist: str | None = None


def _norm_path(p: str | None) -> str | None:
    if not p:
        return None
    return os.path.normcase(os.path.normpath(p))


def _norm_text(s: str | None) -> str | None:
    if not s:
        return None
    return s.strip().casefold()


def build_track_refs(analyses: dict) -> list[TrackRef]:
    """Adapt {track_id: AnalysisResult} into TrackRefs for matching."""
    refs = []
    for tid, an in analyses.items():
        tr = getattr(an, "track", None)
        refs.append(TrackRef(
            track_id=str(tid),
            source_path=getattr(tr, "source_path", None) if tr else None,
            title=getattr(tr, "title", None) if tr else None,
            artist=getattr(tr, "artist", None) if tr else None,
        ))
    return refs


def match_tracks(refs: list[TrackRef], db, tables) -> tuple[dict[str, str], list[str]]:
    """Return (mapping track_id -> ContentID str, list of unmatched track_ids).

    Safety rule: a track is matched ONLY when the evidence is unambiguous.
    An exact file path is unique by construction. Title(+artist) lookups keep
    every candidate; if a key resolves to more than one ContentID the track is
    reported as unmatched rather than guessed — writing a cue onto the wrong
    track is worse than writing none.
    """
    by_path: dict[str, str] = {}
    by_title_artist: dict[tuple, set[str]] = {}
    by_title: dict[str, set[str]] = {}

    for row in db.session.query(tables.DjmdContent).all():
        cid = str(row.ID)
        np = _norm_path(row.FolderPath)
        if np and np not in by_path:
            by_path[np] = cid
        title = _norm_text(row.Title)
        artist = _norm_text(row.Artist.Name if row.Artist else None)
        if title:
            by_title_artist.setdefault((title, artist), set()).add(cid)
            by_title.setdefault(title, set()).add(cid)

    def _unique(candidates: set[str] | None) -> str | None:
        """Accept a candidate set only when it names exactly one track."""
        if candidates and len(candidates) == 1:
            return next(iter(candidates))
        return None

    mapping: dict[str, str] = {}
    unmatched: list[str] = []
    for ref in refs:
        np = _norm_path(ref.source_path)
        title = _norm_text(ref.title)
        artist = _norm_text(ref.artist)
        cid = (
            (np and by_path.get(np))
            or _unique(by_title_artist.get((title, artist)) if title else None)
            or _unique(by_title.get(title) if title else None)
        )
        if cid:
            mapping[ref.track_id] = cid
        else:
            unmatched.append(ref.track_id)
    return mapping, unmatched


def remap_plan_content_ids(plan, mapping: dict[str, str]):
    """Return a copy of the CuePlan with track/cue content_ids swapped to RB
    ContentIDs; tracks with no mapping are dropped (and their track_ids returned).
    """
    new_tracks = []
    dropped: list[str] = []
    for track in plan.tracks:
        cid = mapping.get(track.content_id)
        if cid is None:
            if track.cues:
                dropped.append(track.content_id)
            continue
        new_cues = [c.model_copy(update={"content_id": cid}) for c in track.cues]
        new_tracks.append(track.model_copy(update={"content_id": cid, "cues": new_cues}))
    return plan.model_copy(update={"tracks": new_tracks}), dropped

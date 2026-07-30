"""Apply a CuePlan to a Rekordbox master.db — the only layer that touches the
library. Owns all safety: refuse if Rekordbox is running, back up first, write
atomically, verify, and auto-restore on failure.

Proven recipe (memory: dancelab-cue-write-proven): pyrekordbox auto-extracts the
SQLCipher key; a hot cue is a DjmdCue row with InFrame=round(InMsec*0.15),
OutMsec=-1 for a point; db.autoincrement_usn(set_row_usn=True) stamps the USN
bookkeeping; commit + WAL checkpoint folds it into a single file that Rekordbox
opens and trusts.

HARD INVARIANT: this module writes ONLY DjmdCue rows. It never touches BPM or
beatgrid data (DjmdContent tempo fields, DjmdBeatGrid).
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from pydantic import BaseModel

from dancelab.decision.cue_export_models import CuePlan, kind_to_pad_index
from dancelab.decision.cue_conflict import ExistingCue
from dancelab.decision.cue_write_ops import ExistingPadCue, resolve_write_operations
from dancelab.ingestion.rb_backup import (
    backup_master,
    copy_database_bundle,
    remove_database_bundle,
    restore_backup,
)


class WriteResult(BaseModel):
    written: int = 0
    deleted: int = 0
    backup_path: str | None = None
    verified: bool = False
    restored: bool = False
    target: str | None = None
    problems: list[str] = []


def is_rekordbox_running() -> bool:
    """True if a Rekordbox process is running (writing then would corrupt WAL)."""
    try:
        import psutil
    except ImportError:  # fail CLOSED: without a way to check, assume it runs
        return True
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if "rekordbox" in name:
            return True
    return False


def read_existing_cues(db, tables) -> dict[str, list[ExistingCue]]:
    """Adapt the DJ's current hot cues into ExistingCue, keyed by ContentID (str)."""
    out: dict[str, list[ExistingCue]] = {}
    for row in db.session.query(tables.DjmdCue).all():
        if row.Kind == 0:  # memory cue, not a pad
            continue
        cid = str(row.ContentID)
        out.setdefault(cid, []).append(
            ExistingCue(
                pad_index=kind_to_pad_index(row.Kind),
                position_ms=int(row.InMsec),
                comment=row.Comment or "",
            )
        )
    return out


def insert_hot_cue(db, tables, *, content_id, content_uuid, position_ms, kind, color, comment) -> int:
    """Insert one hot cue via the proven recipe. Returns the new cue ID."""
    proto = db.session.query(tables.DjmdCue).filter(tables.DjmdCue.Kind != 0).first()
    cols = [c.name for c in tables.DjmdCue.__table__.columns]
    if proto is not None:
        vals = {c: getattr(proto, c) for c in cols}
    else:  # empty library — build minimal row
        vals = {c: None for c in cols}
        vals.update(InMpegFrame=0, InMpegAbs=0, OutFrame=0, ActiveLoop=0,
                    rb_local_deleted=0, rb_local_synced=0)
    new_id = db.generate_unused_id(tables.DjmdCue, is_28_bit=False)
    # Rekordbox hot-cue colors: palette index in ColorTableIndex (Color=255 flags
    # "use palette"); a negative index means the Rekordbox default (Color=-1,
    # ColorTableIndex=None). Mirrors how the DJ's own cues store color.
    if color is not None and color >= 0:
        color_field, color_index = 255, int(color)
    else:
        color_field, color_index = -1, None
    vals.update(
        ID=new_id, ContentID=content_id, ContentUUID=content_uuid,
        UUID=str(uuid.uuid4()), Kind=kind, InMsec=int(position_ms),
        InFrame=round(int(position_ms) * 0.15), OutMsec=-1, OutFrame=0,
        Color=color_field, ColorTableIndex=color_index, Comment=comment,
        rb_local_usn=None, created_at=None, updated_at=None,
    )
    db.session.add(tables.DjmdCue(**vals))
    return new_id


def _apply(plan: CuePlan, db, tables) -> tuple[int, int]:
    """Execute the plan. The safety rules themselves live in cue_write_ops.

    This function reads the database state, asks the pure resolver what to do,
    and performs it. Keeping the decision out of here is what lets the rules be
    tested on machines with no Rekordbox library.
    """
    wanted_ids = {str(t.content_id) for t in plan.tracks if t.cues}
    if not wanted_ids:
        return 0, 0

    contents = db.session.query(tables.DjmdContent).filter(
        tables.DjmdContent.ID.in_(wanted_ids)
    ).all()
    content_by_id = {str(c.ID): c for c in contents}

    rows = db.session.query(tables.DjmdCue).filter(
        tables.DjmdCue.ContentID.in_(wanted_ids)
    ).all()
    row_by_pad = {(str(r.ContentID), r.Kind): r for r in rows}
    existing = [
        ExistingPadCue(content_id=str(r.ContentID), kind=r.Kind, comment=r.Comment or "")
        for r in rows
    ]

    ops = resolve_write_operations(
        plan, known_content_ids=set(content_by_id), existing_pad_cues=existing
    )

    for doomed in ops.deletes:
        row = row_by_pad.get((doomed.content_id, doomed.kind))
        if row is not None:
            db.session.delete(row)
    for cue in ops.inserts:
        content = content_by_id[str(cue.content_id)]
        insert_hot_cue(
            db, tables, content_id=cue.content_id, content_uuid=content.UUID,
            position_ms=cue.position_ms, kind=cue.kind, color=cue.color,
            comment=cue.comment,
        )
    return ops.written, ops.deleted


def _verify_plan_written(plan: CuePlan, db, tables) -> tuple[bool, list[str]]:
    """Confirm every planned cue exists on the RIGHT track, pad and position.

    A row count alone cannot catch a cue written to the wrong track, so each
    planned cue is looked up by (ContentID, Kind, InMsec) and its comment
    compared. Returns (all_ok, problems).
    """
    problems: list[str] = []
    for track in plan.tracks:
        for cue in track.cues:
            row = db.session.query(tables.DjmdCue).filter(
                tables.DjmdCue.ContentID == track.content_id,
                tables.DjmdCue.Kind == cue.kind,
                tables.DjmdCue.InMsec == cue.position_ms,
            ).first()
            if row is None:
                problems.append(
                    f"missing cue: content={track.content_id} pad={cue.pad_label} "
                    f"@{cue.position_ms}ms ({cue.cue_type})"
                )
            elif (row.Comment or "") != cue.comment:
                problems.append(
                    f"comment mismatch on content={track.content_id} "
                    f"pad={cue.pad_label}: {row.Comment!r} != {cue.comment!r}"
                )
    return (not problems), problems


def _open(db_path: Path):
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    return Rekordbox6Database(path=str(db_path)), tables


def _execute_write(
    target: Path,
    plan: CuePlan,
    result: WriteResult,
    *,
    playlist_name: str | None,
    playlist_content_ids: list[str] | None,
    playlist_folder: str,
) -> None:
    """Apply the plan inside one database and record what happened.

    Everything here is about the database: apply, commit, fold the WAL back, and
    check that what landed matches what was planned. Deciding whether the result
    may be kept — and cleaning up if not — is the caller's job.
    """
    from sqlalchemy import text

    db, tables = _open(target)
    try:
        before = db.session.query(tables.DjmdCue).count()
        result.written, result.deleted = _apply(plan, db, tables)
        if playlist_name and playlist_content_ids:
            from dancelab.ingestion.rekordbox_playlist import create_set_playlist
            create_set_playlist(db, tables, name=playlist_name,
                                content_ids=playlist_content_ids,
                                folder_name=playlist_folder)
        db.autoincrement_usn(set_row_usn=True)
        db.commit()
        db.session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        db.session.commit()

        expected = before + result.written - result.deleted
        after = db.session.query(tables.DjmdCue).count()
        content_ok, problems = _verify_plan_written(plan, db, tables)
        if after != expected:
            problems.insert(0, f"cue count {after} != expected {expected}")
        result.problems = problems
        result.verified = content_ok and after == expected
    except Exception:
        db.session.rollback()
        raise
    finally:
        db.close()


def write_plan(
    plan: CuePlan,
    *,
    db_path: Path,
    backup_dir: Path,
    timestamp: str,
    meta: dict | None = None,
    safe_swap: bool = False,
    playlist_name: str | None = None,
    playlist_content_ids: list[str] | None = None,
    playlist_folder: str = "DanceLab",
) -> WriteResult:
    """Safely apply `plan` to the master.db at db_path.

    Aborts while Rekordbox is running, takes a dedicated rollback backup, then
    hands the database work to _execute_write. A write that cannot be verified is
    never kept: in place it is rolled back to the backup, and under safe_swap the
    live database was never touched at all.
    """
    db_path = Path(db_path)
    result = WriteResult()

    if is_rekordbox_running():
        raise RuntimeError("Rekordbox is running — close it before writing cues.")

    # deduplicate=False: this backup is a dedicated rollback point. A dedup skip
    # would leave us with nothing to restore to if the write goes wrong.
    backup = backup_master(db_path, backup_dir, timestamp=timestamp,
                           meta=meta or {}, deduplicate=False)
    if backup is None:
        raise RuntimeError("no rollback backup was created — refusing to write")
    result.backup_path = str(backup)

    target = db_path
    if safe_swap:
        target = db_path.with_suffix(".dancelab_tmp.db")
        copy_database_bundle(db_path, target)  # includes WAL/SHM sidecars
    result.target = str(target)

    try:
        _execute_write(
            target, plan, result,
            playlist_name=playlist_name,
            playlist_content_ids=playlist_content_ids,
            playlist_folder=playlist_folder,
        )
    except Exception:
        # A safe-swap failure leaves the live database untouched; an in-place
        # failure must be rolled back to the backup taken above.
        if safe_swap:
            remove_database_bundle(target)
        else:
            restore_backup(backup_dir, db_path, timestamp=timestamp)
            result.restored = True
        raise

    if safe_swap:
        if not result.verified:
            remove_database_bundle(target)
            raise RuntimeError(
                "verification failed on safe-swap copy; live db untouched: "
                + "; ".join(result.problems[:5])
            )
        copy_database_bundle(target, db_path)
        remove_database_bundle(target)
        result.target = str(db_path)
        return result

    # In-place write: a failed verification must NOT be left in the database.
    if not result.verified:
        restore_backup(backup_dir, db_path, timestamp=timestamp)
        result.restored = True
        raise RuntimeError(
            "verification failed; database restored from backup: "
            + "; ".join(result.problems[:5])
        )

    return result

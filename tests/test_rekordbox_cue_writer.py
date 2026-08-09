"""Safe writer against a THROWAWAY copy of master.db. Never touches live.

Skips cleanly when pyrekordbox or a real master.db is unavailable (CI).
"""

import shutil
import inspect
from pathlib import Path

import pytest

pytest.importorskip("pyrekordbox")

from dancelab.decision.cue_export_models import CuePlan, TrackCuePlan, PlannedCue
from dancelab.ingestion import rekordbox_cue_writer as W

LIVE = Path.home() / "Library/Pioneer/rekordbox/master.db"


def test_safe_swap_is_the_library_default():
    assert inspect.signature(W.write_plan).parameters["safe_swap"].default is True


@pytest.fixture()
def copy_db(tmp_path):
    if not LIVE.exists():
        pytest.skip("no local master.db to copy")
    dst = tmp_path / "master.db"
    shutil.copy2(LIVE, dst)
    return dst


def _first_track_id(db_path):
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(db_path))
    tid = db.session.query(tables.DjmdContent).filter(
        tables.DjmdContent.FolderPath != None  # noqa: E711
    ).first().ID
    db.close()
    return str(tid)


def _plan_for(tid, color=22):
    return CuePlan(tracks=[TrackCuePlan(content_id=tid, cues=[
        PlannedCue(content_id=tid, position_ms=61000, kind=5, pad_label="D",
                   color=color, comment="TEST IN", cue_type="mix_in"),
    ])])


def test_write_plan_adds_cue_and_verifies(copy_db, tmp_path, monkeypatch):
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)
    res = W.write_plan(_plan_for(tid), db_path=copy_db,
                       backup_dir=tmp_path / "bk", timestamp="20260724_1300", meta={})
    assert res.written == 1
    assert res.verified is True
    assert res.backup_path  # a backup was taken

    # reopen fresh and confirm the cue is on disk
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(copy_db))
    found = db.session.query(tables.DjmdCue).filter(
        tables.DjmdCue.ContentID == tid, tables.DjmdCue.Kind == 5
    ).all()
    db.close()
    # cue written with correct position AND palette color (Color=255, index=22)
    assert any(
        c.Comment == "TEST IN" and c.InMsec == 61000
        and c.ColorTableIndex == 22 and c.Color == 255
        for c in found
    )


def test_aborts_when_rekordbox_running(copy_db, tmp_path, monkeypatch):
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: True)
    tid = _first_track_id(copy_db)
    with pytest.raises(RuntimeError, match="Rekordbox is running"):
        W.write_plan(_plan_for(tid), db_path=copy_db,
                     backup_dir=tmp_path / "bk", timestamp="20260724_1300", meta={})


def test_rollback_and_restore_on_failure(copy_db, tmp_path, monkeypatch):
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(copy_db))
    before = db.session.query(tables.DjmdCue).count()
    db.close()

    def boom(*a, **k):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(W, "insert_hot_cue", boom)
    with pytest.raises(RuntimeError, match="forced failure"):
        W.write_plan(_plan_for(tid), db_path=copy_db,
                     backup_dir=tmp_path / "bk", timestamp="20260724_1300", meta={})

    db = Rekordbox6Database(path=str(copy_db))
    after = db.session.query(tables.DjmdCue).count()
    db.close()
    assert after == before  # atomic rollback + restore left cue count unchanged


def test_writer_does_not_delete_the_djs_cue_unless_told_to(copy_db, tmp_path, monkeypatch):
    """A plan alone must never destroy an existing cue.

    Conflict resolution lives in another layer; the writer cannot assume it ran.
    Only a cue explicitly marked replace_existing may overwrite a pad.
    """
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    # give the track a cue of the DJ's own on pad D (Kind=5)
    db = Rekordbox6Database(path=str(copy_db))
    content = db.session.query(tables.DjmdContent).filter(
        tables.DjmdContent.ID == tid
    ).first()
    W.insert_hot_cue(db, tables, content_id=tid, content_uuid=content.UUID,
                     position_ms=12345, kind=5, color=-1, comment="DJ OWN CUE")
    db.autoincrement_usn(set_row_usn=True)
    db.commit()
    db.close()

    # writing our own pad-D cue must refuse, not silently destroy theirs
    with pytest.raises(ValueError, match="no replace permission"):
        W.write_plan(_plan_for(tid), db_path=copy_db, backup_dir=tmp_path / "bk",
                     timestamp="20260724_1800", meta={}, safe_swap=False)

    db = Rekordbox6Database(path=str(copy_db))
    survivors = db.session.query(tables.DjmdCue).filter(
        tables.DjmdCue.ContentID == tid, tables.DjmdCue.Kind == 5
    ).all()
    comments = {c.Comment for c in survivors}
    db.close()
    assert "DJ OWN CUE" in comments, "the writer destroyed a cue it was never told to replace"


def test_replace_permission_lets_the_writer_clear_the_pad(copy_db, tmp_path, monkeypatch):
    """With permission granted by conflict resolution, the pad is cleared."""
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database(path=str(copy_db))
    content = db.session.query(tables.DjmdContent).filter(
        tables.DjmdContent.ID == tid
    ).first()
    W.insert_hot_cue(db, tables, content_id=tid, content_uuid=content.UUID,
                     position_ms=12345, kind=5, color=-1, comment="OLD CUE")
    db.autoincrement_usn(set_row_usn=True)
    db.commit()
    db.close()

    plan = _plan_for(tid)
    plan.tracks[0].cues[0].replace_existing = True
    res = W.write_plan(plan, db_path=copy_db, backup_dir=tmp_path / "bk",
                       timestamp="20260724_1801", meta={}, safe_swap=False)
    assert res.deleted == 1 and res.verified is True

    db = Rekordbox6Database(path=str(copy_db))
    comments = {c.Comment for c in db.session.query(tables.DjmdCue).filter(
        tables.DjmdCue.ContentID == tid, tables.DjmdCue.Kind == 5).all()}
    db.close()
    assert comments == {"TEST IN"}  # old cue replaced, exactly one cue on the pad


def test_failed_verification_restores_database(copy_db, tmp_path, monkeypatch):
    """A cue written to the wrong place must not survive: restore + raise."""
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(copy_db))
    before = db.session.query(tables.DjmdCue).count()
    db.close()

    # simulate a write that lands somewhere other than planned
    monkeypatch.setattr(W, "_verify_plan_written",
                        lambda plan, db, tables: (False, ["forced mismatch"]))
    with pytest.raises(RuntimeError, match="verification failed"):
        W.write_plan(_plan_for(tid), db_path=copy_db, backup_dir=tmp_path / "bk",
                     timestamp="20260724_1700", meta={}, safe_swap=False)

    db = Rekordbox6Database(path=str(copy_db))
    after = db.session.query(tables.DjmdCue).count()
    db.close()
    assert after == before  # rolled back, nothing left behind


def test_safe_swap_leaves_live_untouched_on_failed_verification(copy_db, tmp_path, monkeypatch):
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)
    original = copy_db.read_bytes()
    monkeypatch.setattr(W, "_verify_plan_written",
                        lambda plan, db, tables: (False, ["forced mismatch"]))
    with pytest.raises(RuntimeError, match="live db untouched"):
        W.write_plan(_plan_for(tid), db_path=copy_db, backup_dir=tmp_path / "bk",
                     timestamp="20260724_1701", meta={}, safe_swap=True)
    assert copy_db.read_bytes() == original
    assert not copy_db.with_suffix(".dancelab_tmp.db").exists()  # temp cleaned up


def test_verification_detects_missing_cue(copy_db, tmp_path, monkeypatch):
    """Real verifier: a plan whose cue was never written must fail verification."""
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)
    monkeypatch.setattr(W, "_apply", lambda plan, db, tables: (1, 0, []))  # writes nothing
    with pytest.raises(RuntimeError, match="verification failed"):
        W.write_plan(_plan_for(tid), db_path=copy_db, backup_dir=tmp_path / "bk",
                     timestamp="20260724_1702", meta={}, safe_swap=True)


def test_missing_psutil_fails_closed(monkeypatch):
    """No psutil -> assume Rekordbox is running rather than risk a live write."""
    import builtins
    real_import = builtins.__import__

    def no_psutil(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_psutil)
    assert W.is_rekordbox_running() is True


def test_never_writes_bpm_or_beatgrid(copy_db, tmp_path, monkeypatch):
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    tid = _first_track_id(copy_db)

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    def content_snapshot(path):
        db = Rekordbox6Database(path=str(path))
        row = db.session.query(tables.DjmdContent).filter(
            tables.DjmdContent.ID == tid
        ).first()
        snap = {c.name: getattr(row, c.name) for c in tables.DjmdContent.__table__.columns}
        db.close()
        return snap

    before = content_snapshot(copy_db)
    W.write_plan(_plan_for(tid), db_path=copy_db,
                 backup_dir=tmp_path / "bk", timestamp="20260724_1300", meta={})
    after = content_snapshot(copy_db)

    # BPM / tempo / beatgrid-bearing fields on the track are untouched
    for key in ("BPM", "BitRate", "SampleRate", "Length"):
        if key in before:
            assert before[key] == after[key], f"{key} changed!"
    # the whole content row is unchanged except possibly a sync bookkeeping column
    changed = {k for k in before if before[k] != after.get(k)}
    assert changed <= {"rb_local_usn", "usn", "updated_at"}, f"unexpected content changes: {changed}"

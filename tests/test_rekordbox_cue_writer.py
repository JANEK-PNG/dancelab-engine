"""Safe writer against a THROWAWAY copy of master.db. Never touches live.

Skips cleanly when pyrekordbox or a real master.db is unavailable (CI).
"""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pyrekordbox")

from dancelab.decision.cue_export_models import CuePlan, TrackCuePlan, PlannedCue
from dancelab.ingestion import rekordbox_cue_writer as W

LIVE = Path.home() / "Library/Pioneer/rekordbox/master.db"


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

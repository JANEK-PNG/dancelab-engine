"""Native playlist creation in a DanceLab folder. Runs on a copy; skips if none."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pyrekordbox")

from dancelab.ingestion.rekordbox_playlist import create_set_playlist, ensure_folder

LIVE = Path.home() / "Library/Pioneer/rekordbox/master.db"


@pytest.fixture()
def copy_db(tmp_path):
    if not LIVE.exists():
        pytest.skip("no local master.db")
    dst = tmp_path / "master.db"
    shutil.copy2(LIVE, dst)
    return dst


def _open(path):
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    return Rekordbox6Database(path=str(path)), tables


def _two_track_ids(db, tables):
    rows = db.session.query(tables.DjmdContent).filter(
        tables.DjmdContent.FolderPath != None  # noqa: E711
    ).limit(2).all()
    return [str(r.ID) for r in rows]


def test_creates_folder_and_playlist_with_tracks(copy_db):
    if __import__("pyrekordbox.utils", fromlist=["get_rekordbox_pid"]).get_rekordbox_pid():
        pytest.skip("Rekordbox running")
    db, tables = _open(copy_db)
    ids = _two_track_ids(db, tables)
    create_set_playlist(db, tables, name="E2E Test Set", content_ids=ids)
    db.commit()
    db.close()

    db, tables = _open(copy_db)
    folder = db.session.query(tables.DjmdPlaylist).filter(
        tables.DjmdPlaylist.Name == "DanceLab", tables.DjmdPlaylist.Attribute == 1
    ).first()
    assert folder is not None
    pl = db.session.query(tables.DjmdPlaylist).filter(
        tables.DjmdPlaylist.Name == "E2E Test Set"
    ).first()
    assert pl is not None and str(pl.ParentID) == str(folder.ID)
    songs = db.session.query(tables.DjmdSongPlaylist).filter(
        tables.DjmdSongPlaylist.PlaylistID == pl.ID
    ).all()
    assert {str(s.ContentID) for s in songs} == set(ids)
    db.close()


def test_folder_reused_not_duplicated(copy_db):
    if __import__("pyrekordbox.utils", fromlist=["get_rekordbox_pid"]).get_rekordbox_pid():
        pytest.skip("Rekordbox running")
    db, tables = _open(copy_db)
    ensure_folder(db, tables)
    db.commit()
    ensure_folder(db, tables)  # second call must not create a duplicate
    db.commit()
    n = db.session.query(tables.DjmdPlaylist).filter(
        tables.DjmdPlaylist.Name == "DanceLab", tables.DjmdPlaylist.Attribute == 1
    ).count()
    db.close()
    assert n == 1

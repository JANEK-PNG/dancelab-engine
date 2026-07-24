"""Rolling, capped, deduplicated master.db backups + manifest + restore."""

from dancelab.ingestion.rb_backup import (
    backup_master,
    list_backups,
    restore_backup,
)


def _db(tmp_path, content=b"AAAA"):
    p = tmp_path / "master.db"
    p.write_bytes(content)
    return p


def test_first_backup_creates_file_and_manifest(tmp_path):
    db = _db(tmp_path)
    bdir = tmp_path / "bk"
    out = backup_master(db, bdir, timestamp="20260724_1200", meta={"set": "x"})
    assert out is not None and out.exists()
    entries = list_backups(bdir)
    assert len(entries) == 1
    assert entries[0]["timestamp"] == "20260724_1200"
    assert entries[0]["meta"]["set"] == "x"


def test_dedup_skips_identical(tmp_path):
    db = _db(tmp_path)
    bdir = tmp_path / "bk"
    assert backup_master(db, bdir, timestamp="20260724_1200", meta={}) is not None
    # unchanged db -> no new backup
    assert backup_master(db, bdir, timestamp="20260724_1201", meta={}) is None
    assert len(list_backups(bdir)) == 1


def test_change_makes_new_backup(tmp_path):
    db = _db(tmp_path)
    bdir = tmp_path / "bk"
    backup_master(db, bdir, timestamp="20260724_1200", meta={})
    db.write_bytes(b"BBBB")  # changed
    assert backup_master(db, bdir, timestamp="20260724_1201", meta={}) is not None
    assert len(list_backups(bdir)) == 2


def test_cap_prunes_oldest(tmp_path):
    db = _db(tmp_path)
    bdir = tmp_path / "bk"
    for i in range(5):
        db.write_bytes(bytes([i]) * 8)  # distinct each time
        backup_master(db, bdir, timestamp=f"20260724_120{i}", meta={}, cap=3)
    entries = list_backups(bdir)
    assert len(entries) == 3
    kept = {e["timestamp"] for e in entries}
    assert kept == {"20260724_1202", "20260724_1203", "20260724_1204"}  # oldest pruned
    # pruned files are gone from disk
    assert not (bdir / "master_20260724_1200.db").exists()


def test_restore_copies_backup_over_db(tmp_path):
    db = _db(tmp_path, b"ORIGINAL")
    bdir = tmp_path / "bk"
    backup_master(db, bdir, timestamp="20260724_1200", meta={})
    db.write_bytes(b"MODIFIED")
    restore_backup(bdir, db, timestamp="20260724_1200")
    assert db.read_bytes() == b"ORIGINAL"

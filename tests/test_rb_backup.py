"""Rolling, capped, deduplicated master.db backups + manifest + restore."""

import json
from pathlib import Path

import pytest

from dancelab.ingestion.rb_backup import (
    backup_master,
    copy_database_bundle,
    list_backups,
    restore_backup,
)


def _db(tmp_path, content=b"AAAA"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "master.db"
    p.write_bytes(content)
    return p


def test_first_backup_creates_file_and_manifest(tmp_path):
    db = _db(tmp_path)
    Path(f"{db}-wal").write_bytes(b"WAL")
    Path(f"{db}-shm").write_bytes(b"SHM")
    bdir = tmp_path / "bk"
    out = backup_master(db, bdir, timestamp="20260724_1200", meta={"set": "x"})
    assert out is not None and out.exists()
    entries = list_backups(bdir)
    assert len(entries) == 1
    assert entries[0]["timestamp"] == "20260724_1200"
    assert entries[0]["meta"]["set"] == "x"
    assert {item["role"] for item in entries[0]["files"]} == {"db", "wal", "shm"}
    assert (bdir / f"{out.name}-wal").read_bytes() == b"WAL"
    assert (bdir / f"{out.name}-shm").read_bytes() == b"SHM"


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


def test_sidecar_change_makes_new_backup(tmp_path):
    db = _db(tmp_path)
    wal = Path(f"{db}-wal")
    wal.write_bytes(b"WAL-1")
    bdir = tmp_path / "bk"
    backup_master(db, bdir, timestamp="20260724_1200", meta={})
    wal.write_bytes(b"WAL-2")
    assert backup_master(db, bdir, timestamp="20260724_1201", meta={}) is not None
    assert len(list_backups(bdir)) == 2


def test_dedup_can_be_disabled_for_dedicated_rollback_point(tmp_path):
    db = _db(tmp_path)
    bdir = tmp_path / "bk"
    backup_master(db, bdir, timestamp="20260724_1200", meta={})
    assert backup_master(
        db,
        bdir,
        timestamp="20260724_1201",
        meta={},
        deduplicate=False,
    ) is not None
    assert len(list_backups(bdir)) == 2


def test_cap_prunes_oldest(tmp_path):
    db = _db(tmp_path)
    wal = Path(f"{db}-wal")
    bdir = tmp_path / "bk"
    for i in range(5):
        db.write_bytes(bytes([i]) * 8)  # distinct each time
        wal.write_bytes(bytes([i + 10]) * 8)
        backup_master(db, bdir, timestamp=f"20260724_120{i}", meta={}, cap=3)
    entries = list_backups(bdir)
    assert len(entries) == 3
    kept = {e["timestamp"] for e in entries}
    assert kept == {"20260724_1202", "20260724_1203", "20260724_1204"}  # oldest pruned
    # pruned files are gone from disk
    assert not (bdir / "master_20260724_1200.db").exists()
    assert not (bdir / "master_20260724_1200.db-wal").exists()


def test_restore_copies_backup_over_db(tmp_path):
    db = _db(tmp_path, b"ORIGINAL")
    wal = Path(f"{db}-wal")
    shm = Path(f"{db}-shm")
    wal.write_bytes(b"ORIGINAL-WAL")
    shm.write_bytes(b"ORIGINAL-SHM")
    bdir = tmp_path / "bk"
    backup_master(db, bdir, timestamp="20260724_1200", meta={})
    db.write_bytes(b"MODIFIED")
    wal.write_bytes(b"MODIFIED-WAL")
    shm.unlink()
    restore_backup(bdir, db, timestamp="20260724_1200")
    assert db.read_bytes() == b"ORIGINAL"
    assert wal.read_bytes() == b"ORIGINAL-WAL"
    assert shm.read_bytes() == b"ORIGINAL-SHM"


def test_restore_refuses_corrupt_backup_without_touching_target(tmp_path):
    db = _db(tmp_path, b"ORIGINAL")
    bdir = tmp_path / "bk"
    backup = backup_master(db, bdir, timestamp="20260724_1200", meta={})
    assert backup is not None
    backup.write_bytes(b"CORRUPT")
    db.write_bytes(b"CURRENT")

    with pytest.raises(OSError, match="checksum mismatch"):
        restore_backup(bdir, db, timestamp="20260724_1200")

    assert db.read_bytes() == b"CURRENT"


def test_restore_rejects_manifest_path_traversal(tmp_path):
    db = _db(tmp_path, b"CURRENT")
    bdir = tmp_path / "bk"
    bdir.mkdir()
    (bdir / "manifest.json").write_text(json.dumps([{
        "timestamp": "bad",
        "file": "../outside.db",
        "sha256": "0" * 64,
        "meta": {},
    }]))

    with pytest.raises(ValueError, match="unsafe backup filename"):
        restore_backup(bdir, db, timestamp="bad")

    assert db.read_bytes() == b"CURRENT"


def test_copy_database_bundle_removes_stale_target_sidecars(tmp_path):
    source = _db(tmp_path / "source", b"DB")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target = target_dir / "master.db"
    target.write_bytes(b"OLD")
    Path(f"{target}-wal").write_bytes(b"STALE")

    copy_database_bundle(source, target)

    assert target.read_bytes() == b"DB"
    assert not Path(f"{target}-wal").exists()


def test_rejects_unsafe_or_duplicate_timestamp(tmp_path):
    db = _db(tmp_path)
    bdir = tmp_path / "bk"
    with pytest.raises(ValueError, match="unsafe backup timestamp"):
        backup_master(db, bdir, timestamp="../escape", meta={})

    backup_master(db, bdir, timestamp="same", meta={})
    with pytest.raises(ValueError, match="already exists"):
        backup_master(db, bdir, timestamp="same", meta={}, deduplicate=False)

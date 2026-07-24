"""Rolling, capped, deduplicated backups of the Rekordbox master.db.

Lives in a dedicated folder (never touches Rekordbox's own master.backup*.db
rotation). Timestamped, not numbered — natural time sort, no rename chains. A
manifest.json records every backup (timestamp, file, sha256, meta) so restore is
"the one before the Four-Tet set at 12:30", not a guess. Checksum dedup skips a
backup when the db is byte-identical to the newest one.

`timestamp` is always passed in by the caller (never generated here) so the
behavior is deterministic and testable.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

MANIFEST_NAME = "manifest.json"
DEFAULT_CAP = 10


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_path(backup_dir: Path) -> Path:
    return Path(backup_dir) / MANIFEST_NAME


def _read_manifest(backup_dir: Path) -> list[dict]:
    mp = _manifest_path(backup_dir)
    if not mp.exists():
        return []
    return json.loads(mp.read_text())


def _write_manifest(backup_dir: Path, entries: list[dict]) -> None:
    _manifest_path(backup_dir).write_text(json.dumps(entries, indent=2))


def list_backups(backup_dir: Path) -> list[dict]:
    """Return manifest entries, oldest first."""
    return _read_manifest(Path(backup_dir))


def backup_master(
    db_path: Path,
    backup_dir: Path,
    *,
    timestamp: str,
    meta: dict,
    cap: int = DEFAULT_CAP,
) -> Path | None:
    """Copy db_path into backup_dir as master_<timestamp>.db.

    Returns the backup path, or None if the db is byte-identical to the newest
    existing backup (dedup). Prunes oldest backups beyond `cap`.
    """
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    digest = _sha256(db_path)
    entries = _read_manifest(backup_dir)
    if entries and entries[-1]["sha256"] == digest:
        return None  # unchanged since last backup

    dest = backup_dir / f"master_{timestamp}.db"
    shutil.copy2(db_path, dest)
    entries.append({
        "timestamp": timestamp,
        "file": dest.name,
        "sha256": digest,
        "meta": meta,
    })

    # prune oldest beyond cap
    while len(entries) > cap:
        old = entries.pop(0)
        old_file = backup_dir / old["file"]
        if old_file.exists():
            old_file.unlink()

    _write_manifest(backup_dir, entries)
    return dest


def restore_backup(backup_dir: Path, db_path: Path, *, timestamp: str) -> Path:
    """Copy the backup with the given timestamp over db_path. Returns db_path."""
    backup_dir = Path(backup_dir)
    entries = _read_manifest(backup_dir)
    match = next((e for e in entries if e["timestamp"] == timestamp), None)
    if match is None:
        raise ValueError(f"no backup with timestamp {timestamp} in {backup_dir}")
    src = backup_dir / match["file"]
    if not src.exists():
        raise FileNotFoundError(f"backup file missing: {src}")
    shutil.copy2(src, db_path)
    return Path(db_path)

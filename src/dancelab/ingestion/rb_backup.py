"""Verified backups of a Rekordbox database bundle.

SQLite WAL mode stores committed data across ``master.db``, ``master.db-wal``
and ``master.db-shm``. Treating only the main file as a backup can therefore
produce an incomplete or internally inconsistent restore. This module always
handles the files as one bundle and validates every copy before publishing it.

``timestamp`` is supplied by the caller so behavior remains deterministic and
testable. Backups live outside Rekordbox's own rotation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

MANIFEST_NAME = "manifest.json"
DEFAULT_CAP = 10
SIDECAR_SUFFIXES = ("-wal", "-shm")
_COPY_CHUNK_SIZE = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(_COPY_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(backup_dir: Path) -> Path:
    return Path(backup_dir) / MANIFEST_NAME


def _read_manifest(backup_dir: Path) -> list[dict[str, Any]]:
    manifest = _manifest_path(backup_dir)
    if not manifest.exists():
        return []
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"invalid Rekordbox backup manifest: {manifest}")
    return payload


def _write_manifest(backup_dir: Path, entries: list[dict[str, Any]]) -> None:
    """Publish the manifest atomically after all bundle files are verified."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{MANIFEST_NAME}.",
        suffix=".tmp",
        dir=backup_dir,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(entries, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _manifest_path(backup_dir))
    finally:
        temporary.unlink(missing_ok=True)


def _bundle_paths(db_path: Path) -> dict[str, Path]:
    db_path = Path(db_path)
    paths = {"db": db_path}
    for suffix in SIDECAR_SUFFIXES:
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists():
            paths[suffix.removeprefix("-")] = sidecar
    return paths


def _target_for_role(db_path: Path, role: str) -> Path:
    if role == "db":
        return Path(db_path)
    if role in {"wal", "shm"}:
        return Path(f"{db_path}-{role}")
    raise ValueError(f"unsupported database bundle role: {role!r}")


def _safe_manifest_file(backup_dir: Path, filename: str) -> Path:
    candidate = Path(filename)
    if candidate.is_absolute() or candidate.name != filename:
        raise ValueError(f"unsafe backup filename in manifest: {filename!r}")
    resolved = (Path(backup_dir) / candidate).resolve()
    if resolved.parent != Path(backup_dir).resolve():
        raise ValueError(f"backup file escapes backup directory: {filename!r}")
    return resolved


def _entry_files(entry: dict[str, Any]) -> list[dict[str, Any]]:
    files = entry.get("files")
    if files is not None:
        if not isinstance(files, list) or not files:
            raise ValueError("backup manifest entry has invalid files list")
        return files

    # Backward compatibility with manifests created before bundle backups.
    return [{
        "role": "db",
        "file": entry["file"],
        "sha256": entry["sha256"],
    }]


def _bundle_signature(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in sorted(files, key=lambda value: str(value["role"])):
        digest.update(str(item["role"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item["sha256"]).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _copy_verified(source: Path, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    actual = _sha256(destination)
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise OSError(
            f"backup copy checksum mismatch for {destination}: "
            f"expected {expected_sha256}, got {actual}"
        )


def _validate_timestamp(timestamp: str) -> None:
    if not timestamp or Path(timestamp).name != timestamp:
        raise ValueError(f"unsafe backup timestamp: {timestamp!r}")


def copy_database_bundle(source_db: Path, target_db: Path) -> Path:
    """Copy and verify the main database and every present WAL/SHM sidecar."""
    source_db = Path(source_db)
    target_db = Path(target_db)
    if not source_db.is_file():
        raise FileNotFoundError(f"database file missing: {source_db}")

    source_paths = _bundle_paths(source_db)
    copied_roles: set[str] = set()
    try:
        for role, source in source_paths.items():
            target = _target_for_role(target_db, role)
            _copy_verified(source, target, _sha256(source))
            copied_roles.add(role)
    except Exception:
        remove_database_bundle(target_db)
        raise

    for role in {"wal", "shm"} - copied_roles:
        _target_for_role(target_db, role).unlink(missing_ok=True)
    return target_db


def remove_database_bundle(db_path: Path) -> None:
    """Remove a temporary database and its SQLite sidecars."""
    db_path = Path(db_path)
    for path in _bundle_paths(db_path).values():
        path.unlink(missing_ok=True)
    for role in ("wal", "shm"):
        _target_for_role(db_path, role).unlink(missing_ok=True)


def list_backups(backup_dir: Path) -> list[dict[str, Any]]:
    """Return manifest metadata, oldest first."""
    return _read_manifest(Path(backup_dir))


def backup_master(
    db_path: Path,
    backup_dir: Path,
    *,
    timestamp: str,
    meta: dict[str, Any],
    cap: int = DEFAULT_CAP,
    deduplicate: bool = True,
) -> Path | None:
    """Back up ``master.db`` with all present WAL/SHM files.

    Returns the main backup path. When ``deduplicate`` is true, returns ``None``
    if the complete bundle is identical to the newest entry. Writers should use
    ``deduplicate=False`` when they need a dedicated rollback point.
    """
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    _validate_timestamp(timestamp)
    if cap < 1:
        raise ValueError("backup cap must be at least 1")
    if not db_path.is_file():
        raise FileNotFoundError(f"database file missing: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    entries = _read_manifest(backup_dir)
    if any(entry.get("timestamp") == timestamp for entry in entries):
        raise ValueError(f"backup timestamp already exists: {timestamp}")

    source_files: list[dict[str, Any]] = []
    for role, source in _bundle_paths(db_path).items():
        source_files.append({
            "role": role,
            "source": source,
            "sha256": _sha256(source),
            "size": source.stat().st_size,
        })
    signature = _bundle_signature(source_files)
    if deduplicate and entries:
        latest = entries[-1]
        latest_signature = latest.get("bundle_sha256")
        if latest_signature is None:
            latest_signature = _bundle_signature(_entry_files(latest))
        if latest_signature == signature:
            return None

    main_destination = backup_dir / f"master_{timestamp}.db"
    published_files: list[dict[str, Any]] = []
    try:
        for item in source_files:
            destination = _target_for_role(main_destination, item["role"])
            _copy_verified(item["source"], destination, item["sha256"])
            published_files.append({
                "role": item["role"],
                "file": destination.name,
                "sha256": item["sha256"],
                "size": item["size"],
            })
    except Exception:
        remove_database_bundle(main_destination)
        raise

    main_file = next(item for item in published_files if item["role"] == "db")
    entries.append({
        "timestamp": timestamp,
        "file": main_file["file"],
        "sha256": main_file["sha256"],
        "bundle_sha256": signature,
        "files": published_files,
        "meta": meta,
    })

    while len(entries) > cap:
        old = entries.pop(0)
        for item in _entry_files(old):
            _safe_manifest_file(backup_dir, str(item["file"])).unlink(missing_ok=True)

    _write_manifest(backup_dir, entries)
    return main_destination


def restore_backup(backup_dir: Path, db_path: Path, *, timestamp: str) -> Path:
    """Validate and atomically restore one complete database bundle."""
    backup_dir = Path(backup_dir)
    db_path = Path(db_path)
    entries = _read_manifest(backup_dir)
    match = next((entry for entry in entries if entry.get("timestamp") == timestamp), None)
    if match is None:
        raise ValueError(f"no backup with timestamp {timestamp} in {backup_dir}")

    files = _entry_files(match)
    roles = {str(item.get("role")) for item in files}
    if "db" not in roles or not roles <= {"db", "wal", "shm"}:
        raise ValueError(f"invalid database bundle roles in backup {timestamp}: {roles}")

    sources: dict[str, tuple[Path, str]] = {}
    for item in files:
        role = str(item["role"])
        source = _safe_manifest_file(backup_dir, str(item["file"]))
        expected = str(item["sha256"])
        if not source.is_file():
            raise FileNotFoundError(f"backup file missing: {source}")
        actual = _sha256(source)
        if actual != expected:
            raise OSError(
                f"backup checksum mismatch for {source}: "
                f"expected {expected}, got {actual}"
            )
        sources[role] = (source, expected)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".dancelab-restore-",
        dir=db_path.parent,
    ) as temporary_dir:
        staged_db = Path(temporary_dir) / db_path.name
        for role, (source, expected) in sources.items():
            _copy_verified(source, _target_for_role(staged_db, role), expected)

        # Rekordbox must be closed by the caller. Publish sidecars first and the
        # main database last so the visible main file is always a complete copy.
        for role in ("wal", "shm"):
            target = _target_for_role(db_path, role)
            staged = _target_for_role(staged_db, role)
            if role in sources:
                os.replace(staged, target)
            else:
                target.unlink(missing_ok=True)
        os.replace(staged_db, db_path)

    for role, (_, expected) in sources.items():
        target = _target_for_role(db_path, role)
        if _sha256(target) != expected:
            raise OSError(f"restored database checksum mismatch: {target}")
    return db_path

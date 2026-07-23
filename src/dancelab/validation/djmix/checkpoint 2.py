"""Durable, non-destructive save slots for the corpus research pipeline.

A slot captures code, repository state, the exact corpus progress boundary, and
the command contract without copying source audio. Final alignment reports are
already atomic, so only completed ``*.json`` files enter the saved boundary;
``*.json.tmp`` files are recorded separately as in-flight work.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKPOINT_SCHEMA_VERSION = "1.0.0"
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".webm", ".wav", ".flac", ".ogg", ".aac"}
SOURCE_SNAPSHOT_PATHS = (
    "src",
    "scripts",
    "tests",
    "configs",
    "pyproject.toml",
    "pysidedeploy.spec",
    "README.md",
)
_ARCHIVE_EXCLUDES = {
    ".DS_Store",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return slug[:48] or "save"


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _write_text(path: Path, payload: str) -> None:
    _write_bytes(path, payload.encode("utf-8"))


def _real_audio_stems(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        {
            path.stem
            for path in directory.iterdir()
            if path.is_file()
            and not path.name.startswith("._")
            and path.suffix.lower() in AUDIO_EXTENSIONS
        }
    )


def collect_corpus_progress(corpus_root: Path) -> dict[str, Any]:
    alignments = corpus_root / "alignments"
    completed = sorted(
        path.stem
        for path in alignments.glob("*.json")
        if path.is_file() and not path.name.startswith("._")
    )
    in_flight = sorted(
        path.name
        for path in alignments.glob("*.json.tmp")
        if path.is_file() and not path.name.startswith("._")
    )
    errors = sorted(
        path.name
        for path in alignments.glob("*.error.txt")
        if path.is_file() and not path.name.startswith("._")
    )
    dataset = corpus_root / "djmix-dataset.json"
    manifest = corpus_root / "manifest.csv"
    return {
        "mix_audio_count": len(_real_audio_stems(corpus_root / "mixes")),
        "track_audio_count": len(_real_audio_stems(corpus_root / "tracks")),
        "completed_report_count": len(completed),
        "completed_report_ids": completed,
        "in_flight_report_count": len(in_flight),
        "in_flight_report_files": in_flight,
        "error_report_count": len(errors),
        "error_report_files": errors,
        "dataset_sha256": sha256_file(dataset) if dataset.is_file() else None,
        "manifest_sha256": sha256_file(manifest) if manifest.is_file() else None,
        "safe_completed_boundary": True,
    }


def _archive_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = Path(info.name).parts
    if any(part in _ARCHIVE_EXCLUDES for part in parts):
        return None
    if info.name.endswith((".pyc", ".pyo")):
        return None
    return info


def _write_source_archive(project_root: Path, destination: Path) -> list[str]:
    included: list[str] = []
    with tarfile.open(destination, "w:gz") as archive:
        for relative in SOURCE_SNAPSHOT_PATHS:
            source = project_root / relative
            if not source.exists():
                continue
            archive.add(source, arcname=relative, recursive=True, filter=_archive_filter)
            included.append(relative)
    return included


def _git_snapshot(project_root: Path, destination: Path) -> dict[str, Any]:
    commit = _run_git(project_root, "rev-parse", "HEAD")
    branch = _run_git(project_root, "branch", "--show-current")
    status = _run_git(project_root, "status", "--short", "--branch")
    unstaged = _run_git(project_root, "diff", "--binary", "--no-ext-diff")
    staged = _run_git(project_root, "diff", "--cached", "--binary", "--no-ext-diff")
    untracked = _run_git(project_root, "ls-files", "--others", "--exclude-standard")

    _write_bytes(destination / "working_tree.patch", unstaged.stdout)
    _write_bytes(destination / "staged.patch", staged.stdout)
    _write_bytes(destination / "git_status.txt", status.stdout + status.stderr)
    _write_bytes(destination / "untracked_files.txt", untracked.stdout)

    return {
        "available": commit.returncode == 0,
        "commit": commit.stdout.decode("utf-8", errors="replace").strip() or None,
        "branch": branch.stdout.decode("utf-8", errors="replace").strip() or None,
        "dirty": bool(status.stdout.decode("utf-8", errors="replace").splitlines()[1:]),
    }


def _artifact_hashes(directory: Path) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "checkpoint.json":
            artifacts[path.name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    return artifacts


def create_checkpoint(
    *,
    project_root: Path,
    corpus_root: Path,
    checkpoint_root: Path,
    label: str = "manual-save",
    engine_mode: str = "legacy",
    pipeline_command: str = "",
    now: datetime | None = None,
) -> Path:
    """Create an immutable-by-convention save slot and return its directory."""

    project_root = project_root.resolve()
    corpus_root = corpus_root.resolve()
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    created = now or datetime.now(timezone.utc)
    slot_id = f"{created.strftime('%Y%m%dT%H%M%SZ')}_{_safe_slug(label)}"
    destination = checkpoint_root / slot_id
    temporary = checkpoint_root / f".{slot_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"checkpoint slot already exists: {slot_id}")
    temporary.mkdir()

    try:
        progress = collect_corpus_progress(corpus_root)
        _write_text(
            temporary / "completed_reports.txt",
            "".join(f"{item}\n" for item in progress["completed_report_ids"]),
        )
        _write_text(
            temporary / "in_flight_reports.txt",
            "".join(f"{item}\n" for item in progress["in_flight_report_files"]),
        )
        _write_text(
            temporary / "error_reports.txt",
            "".join(f"{item}\n" for item in progress["error_report_files"]),
        )
        git = _git_snapshot(project_root, temporary)
        included_paths = _write_source_archive(project_root, temporary / "source_snapshot.tar.gz")

        manifest = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "slot_id": slot_id,
            "label": label,
            "created_at_utc": created.isoformat(),
            "project_root": str(project_root),
            "corpus_root": str(corpus_root),
            "engine_mode": engine_mode,
            "pipeline_command": pipeline_command,
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
            },
            "git": git,
            "source_snapshot_paths": included_paths,
            "corpus_progress": progress,
            "safety": {
                "completed_reports_only": True,
                "in_flight_reports_excluded": True,
                "source_audio_copied": False,
                "restore_requires_manual_review": True,
                "legacy_mode_is_canonical": engine_mode == "legacy",
            },
            "artifacts": _artifact_hashes(temporary),
        }
        _write_text(temporary / "checkpoint.json", json.dumps(manifest, indent=2) + "\n")
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink(missing_ok=True)
            temporary.rmdir()
        raise
    return destination


def verify_checkpoint(slot: Path) -> dict[str, Any]:
    slot = slot.resolve()
    manifest_path = slot / "checkpoint.json"
    if not manifest_path.is_file():
        return {"valid": False, "errors": ["checkpoint.json is missing"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"valid": False, "errors": [f"checkpoint.json is unreadable: {exc}"]}

    errors: list[str] = []
    if manifest.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        errors.append("unsupported checkpoint schema")
    for name, expected in manifest.get("artifacts", {}).items():
        path = slot / name
        if not path.is_file():
            errors.append(f"missing artifact: {name}")
            continue
        if path.stat().st_size != expected.get("bytes"):
            errors.append(f"size mismatch: {name}")
        if sha256_file(path) != expected.get("sha256"):
            errors.append(f"sha256 mismatch: {name}")
    return {
        "valid": not errors,
        "slot_id": manifest.get("slot_id"),
        "errors": errors,
        "completed_report_count": manifest.get("corpus_progress", {}).get(
            "completed_report_count"
        ),
    }

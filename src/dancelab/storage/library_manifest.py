"""Analyzed-library manifest (PRODUCT_SPEC §7) — incremental reuse.

A track is never reprocessed while its stored analysis is valid. Validity is
decided here, from recorded facts — file checksum, engine/schema versions,
weights (formula) hash, analysis tier — never from filename alone.

Sidecar JSON next to the processed-analysis JSONs; headless and testable.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from dancelab import __version__ as ENGINE_VERSION
from dancelab.core.models import DANCELAB_SCHEMA_VERSION

MANIFEST_NAME = "library_manifest.json"

TIER_RANK = {"quick": 1, "deep": 2}


def file_checksum(path: str | Path) -> str:
    """blake2b of file bytes — identity survives renames and moved paths."""
    digest = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def formula_hash(weights_file: str | Path) -> str:
    """Hash of the weights/formula file — scoring changes invalidate reuse."""
    p = Path(weights_file)
    if not p.exists():
        return "missing"
    return hashlib.blake2b(p.read_bytes(), digest_size=8).hexdigest()


@dataclass
class TrackRecord:
    track_id: str
    source_path: str
    source_checksum: str
    analysis_tier: str            # "quick" | "deep"
    engine_version: str
    schema_version: str
    formula_version: str
    analyzed_at: float
    failed: bool = False
    failure: str | None = None


class LibraryManifest:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.path = self.directory / MANIFEST_NAME
        self._records: dict[str, TrackRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = {
                key: TrackRecord(**value) for key, value in data.get("tracks", {}).items()
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            self._records = {}  # corrupt manifest → rebuild by re-analysis, no crash

    def _save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {"tracks": {key: asdict(rec) for key, rec in self._records.items()}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, track_id: str) -> TrackRecord | None:
        return self._records.get(track_id)

    def mark_analyzed(
        self,
        track_id: str,
        *,
        source_path: str,
        source_checksum: str,
        analysis_tier: str,
        formula_version: str,
    ) -> None:
        self._records[track_id] = TrackRecord(
            track_id=track_id,
            source_path=str(source_path),
            source_checksum=source_checksum,
            analysis_tier=analysis_tier,
            engine_version=ENGINE_VERSION,
            schema_version=DANCELAB_SCHEMA_VERSION,
            formula_version=formula_version,
            analyzed_at=time.time(),
        )
        self._save()

    def mark_failed(self, track_id: str, *, source_path: str, error: str) -> None:
        self._records[track_id] = TrackRecord(
            track_id=track_id,
            source_path=str(source_path),
            source_checksum="",
            analysis_tier="quick",
            engine_version=ENGINE_VERSION,
            schema_version=DANCELAB_SCHEMA_VERSION,
            formula_version="",
            analyzed_at=time.time(),
            failed=True,
            failure=error,
        )
        self._save()

    def reuse_reason_or_none(
        self,
        track_id: str,
        *,
        source_checksum: str,
        requested_tier: str,
        formula_version: str,
        analysis_file_exists: bool,
    ) -> str | None:
        """None → stored analysis is valid, reuse it.
        Otherwise the specific re-analysis reason (§7 trigger list)."""
        record = self._records.get(track_id)
        if record is None:
            return "not analyzed yet"
        if record.failed:
            return "previous run failed"
        if not analysis_file_exists:
            return "cache missing"
        if record.source_checksum != source_checksum:
            return "source file changed"
        if record.engine_version != ENGINE_VERSION:
            return f"engine version changed ({record.engine_version} → {ENGINE_VERSION})"
        if record.schema_version != DANCELAB_SCHEMA_VERSION:
            return "schema version changed"
        if record.formula_version != formula_version:
            return "formula/weights changed"
        if TIER_RANK.get(requested_tier, 1) > TIER_RANK.get(record.analysis_tier, 1):
            return f"tier upgrade ({record.analysis_tier} → {requested_tier})"
        return None

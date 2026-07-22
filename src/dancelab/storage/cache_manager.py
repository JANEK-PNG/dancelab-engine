"""Cache manager — visible, bounded, relocatable storage (PRODUCT_SPEC §8).

One cache root, named cache classes, one manifest. Rules enforced here:
- no silent writes outside the root (all cache dirs resolve through this
  module);
- `exports` are user data: never auto-evicted, never bulk-cleared by
  enforce_limit;
- estimates are shown BEFORE jobs run (analysis ≈ 0.25 MB/track, measured;
  stems ≈ duration × sample_rate × 2 bytes × stem count);
- missing cache is a state ("needs reprocess"), never a crash;
- startup scan removes temp orphans and marks manifest entries whose files
  vanished.

Headless (no Qt) so persistence is testable without a display.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dancelab.core.errors import DanceLabError

CACHE_CLASSES = ("analysis", "waveforms", "stems", "features", "temp", "exports")
EVICTABLE_CLASSES = ("analysis", "waveforms", "stems", "features")
MANIFEST_NAME = "cache_manifest.json"
MANIFEST_VERSION = 1

DEFAULT_MAX_BYTES = 10 * 1024**3          # 10 GB
DEFAULT_LOW_DISK_FLOOR = 2 * 1024**3      # block heavy jobs under 2 GB free

ANALYSIS_BYTES_PER_TRACK = 256 * 1024     # ~0.25 MB, measured on this repo


class CacheError(DanceLabError):
    """Cache root unusable or manifest corrupt beyond recovery."""


def default_cache_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "DanceLab" / "cache"
    return Path.home() / ".cache" / "dancelab"


@dataclass
class CacheEntry:
    cache_class: str
    key: str
    path: str                 # relative to root
    bytes: int
    created_at: float
    last_used_at: float
    source_hash: str | None = None
    engine_version: str | None = None
    missing: bool = False     # file vanished — needs reprocess, not a crash


@dataclass
class CacheEstimate:
    analysis_bytes: int = 0
    stems_bytes: int = 0

    @property
    def total_bytes(self) -> int:
        return self.analysis_bytes + self.stems_bytes


@dataclass
class _Manifest:
    version: int = MANIFEST_VERSION
    entries: list[CacheEntry] = field(default_factory=list)


class CacheManager:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        low_disk_floor_bytes: int = DEFAULT_LOW_DISK_FLOOR,
    ):
        configured_root = Path(root).expanduser() if root else default_cache_root()
        self.root = configured_root.resolve(strict=False)
        self.max_bytes = max_bytes
        self.low_disk_floor_bytes = low_disk_floor_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        for cache_class in CACHE_CLASSES:
            (self.root / cache_class).mkdir(exist_ok=True)
        self._manifest = self._load_manifest()

    # ------------------------------------------------------------ manifest

    def _manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    def _load_manifest(self) -> _Manifest:
        path = self._manifest_path()
        if not path.exists():
            return _Manifest()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries: list[CacheEntry] = []
            for raw_entry in data.get("entries", []):
                entry = CacheEntry(**raw_entry)
                try:
                    self._entry_path(entry)
                except CacheError:
                    continue
                entries.append(entry)
            return _Manifest(
                version=int(data.get("version", MANIFEST_VERSION)),
                entries=entries,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            # corrupt manifest: rebuild empty and rescan — never crash the app
            return _Manifest()

    def _save_manifest(self) -> None:
        payload = {
            "version": self._manifest.version,
            "entries": [asdict(entry) for entry in self._manifest.entries],
        }
        tmp = self._manifest_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._manifest_path())

    # ------------------------------------------------------------ core API

    def class_dir(self, cache_class: str) -> Path:
        if cache_class not in CACHE_CLASSES:
            raise CacheError(f"unknown cache class '{cache_class}'")
        path = self.root / cache_class
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _entry_path(self, entry: CacheEntry, *, root: Path | None = None) -> Path:
        """Resolve a manifest entry strictly inside its declared cache class."""
        if entry.cache_class not in CACHE_CLASSES:
            raise CacheError(f"unknown cache class '{entry.cache_class}'")
        relative = Path(entry.path)
        if relative.is_absolute():
            raise CacheError("cache manifest entry must use a relative path")
        base = (root or self.root).resolve(strict=False)
        class_root = (base / entry.cache_class).resolve(strict=False)
        candidate = (base / relative).resolve(strict=False)
        try:
            candidate.relative_to(class_root)
        except ValueError as exc:
            raise CacheError("cache manifest entry escapes its cache class") from exc
        if candidate == class_root:
            raise CacheError("cache manifest entry must identify a file")
        return candidate

    def register(
        self,
        cache_class: str,
        key: str,
        path: str | Path,
        *,
        source_hash: str | None = None,
        engine_version: str | None = None,
    ) -> CacheEntry:
        """Record a file the caller just wrote under the cache root."""
        if cache_class not in CACHE_CLASSES:
            raise CacheError(f"unknown cache class '{cache_class}'")
        file_path = Path(path).expanduser()
        if file_path.is_symlink():
            raise CacheError("refusing to register a symbolic link")
        resolved = file_path.resolve(strict=False)
        class_root = self.class_dir(cache_class).resolve(strict=False)
        try:
            resolved.relative_to(class_root)
            relative = resolved.relative_to(self.root)
        except ValueError as exc:
            raise CacheError(
                f"refusing to register file outside cache root: {file_path}"
            ) from exc
        now = time.time()
        size = resolved.stat().st_size if resolved.exists() else 0
        entry = CacheEntry(
            cache_class=cache_class,
            key=key,
            path=str(relative),
            bytes=size,
            created_at=now,
            last_used_at=now,
            source_hash=source_hash,
            engine_version=engine_version,
        )
        self._manifest.entries = [
            existing
            for existing in self._manifest.entries
            if not (existing.cache_class == cache_class and existing.key == key)
        ]
        self._manifest.entries.append(entry)
        self._save_manifest()
        return entry

    def touch(self, cache_class: str, key: str) -> None:
        for entry in self._manifest.entries:
            if entry.cache_class == cache_class and entry.key == key:
                entry.last_used_at = time.time()
        self._save_manifest()

    def entries(self, cache_class: str | None = None) -> list[CacheEntry]:
        if cache_class is None:
            return list(self._manifest.entries)
        return [e for e in self._manifest.entries if e.cache_class == cache_class]

    # ------------------------------------------------------------- reporting

    def usage(self) -> dict[str, int]:
        """Actual on-disk bytes per class (walk, not manifest — honest)."""
        report: dict[str, int] = {}
        for cache_class in CACHE_CLASSES:
            total = 0
            class_root = self.root / cache_class
            if class_root.exists():
                for path in class_root.rglob("*"):
                    if path.is_symlink():
                        continue
                    if path.is_file():
                        total += path.stat().st_size
            report[cache_class] = total
        return report

    def free_disk_bytes(self) -> int:
        return shutil.disk_usage(self.root).free

    def low_disk(self) -> bool:
        return self.free_disk_bytes() < self.low_disk_floor_bytes

    @staticmethod
    def estimate(
        *,
        new_track_count: int = 0,
        stem_track_durations_sec: list[float] | None = None,
        sample_rate: int = 44100,
        stems_per_track: int = 4,
    ) -> CacheEstimate:
        stems_bytes = 0
        for duration in stem_track_durations_sec or []:
            stems_bytes += int(duration * sample_rate * 2) * stems_per_track
        return CacheEstimate(
            analysis_bytes=new_track_count * ANALYSIS_BYTES_PER_TRACK,
            stems_bytes=stems_bytes,
        )

    # ------------------------------------------------------------- lifecycle

    def startup_scan(self) -> dict[str, int]:
        """Delete temp orphans; mark manifest entries whose files vanished."""
        temp_dir = self.root / "temp"
        removed = 0
        if temp_dir.exists():
            for path in temp_dir.iterdir():
                if path.is_symlink() or path.is_file():
                    path.unlink(missing_ok=True)
                    removed += 1
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
        missing = 0
        for entry in self._manifest.entries:
            exists = self._entry_path(entry).exists()
            if not exists and not entry.missing:
                entry.missing = True
                missing += 1
            elif exists and entry.missing:
                entry.missing = False
        self._save_manifest()
        return {"temp_removed": removed, "missing_marked": missing}

    def clear(self, cache_class: str) -> int:
        """Delete a cache class's files; returns bytes freed. Never exports."""
        if cache_class == "exports":
            raise CacheError("exports are user data — clear them manually, never in bulk")
        class_root = self.class_dir(cache_class)
        freed = 0
        for path in sorted(class_root.rglob("*"), reverse=True):
            if path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_file():
                freed += path.stat().st_size
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self._manifest.entries = [
            e for e in self._manifest.entries if e.cache_class != cache_class
        ]
        self._save_manifest()
        return freed

    def enforce_limit(self) -> int:
        """LRU-evict evictable classes until under max_bytes; returns freed."""
        usage = self.usage()
        total = sum(usage[c] for c in CACHE_CLASSES if c != "exports")
        if total <= self.max_bytes:
            return 0
        freed = 0
        candidates = sorted(
            (e for e in self._manifest.entries if e.cache_class in EVICTABLE_CLASSES),
            key=lambda e: e.last_used_at,
        )
        for entry in candidates:
            if total - freed <= self.max_bytes:
                break
            file_path = self._entry_path(entry)
            if file_path.exists():
                freed += file_path.stat().st_size
                file_path.unlink(missing_ok=True)
            entry.missing = True
        self._save_manifest()
        return freed

    def move_root(self, new_root: str | Path) -> Path:
        """Relocate the cache: copy → verify → swap. Never delete-first."""
        destination = Path(new_root).expanduser()
        if destination.resolve() == self.root.resolve():
            return self.root
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            raise CacheError(f"destination not empty: {destination}")
        for source in self.root.rglob("*"):
            if source.is_symlink():
                raise CacheError(f"refusing to relocate cache containing symlink: {source}")
        shutil.copytree(self.root, destination, dirs_exist_ok=True)
        # verify: every manifest-tracked file made it across
        for entry in self._manifest.entries:
            if not entry.missing and not self._entry_path(entry, root=destination).exists():
                shutil.rmtree(destination, ignore_errors=True)
                raise CacheError(f"copy verification failed for {entry.path}; move aborted")
        old_root = self.root
        self.root = destination
        self._save_manifest()
        shutil.rmtree(old_root, ignore_errors=True)
        return self.root


def cache_manager_for(config) -> CacheManager:
    """CacheManager from EngineConfig.cache ('' root → platform default)."""
    cache = getattr(config, "cache", None)
    return CacheManager(
        (cache.root or None) if cache else None,
        max_bytes=cache.max_bytes if cache else DEFAULT_MAX_BYTES,
        low_disk_floor_bytes=cache.low_disk_floor_bytes if cache else DEFAULT_LOW_DISK_FLOOR,
    )


def format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"

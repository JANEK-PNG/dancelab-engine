"""Audio-content de-duplication for set building.

A DJ library often holds the same track twice under different filenames — a
track bought in two packs, or renamed on disk. Track ids are derived from the
path, so the engine sees two distinct tracks and can place both in one set
("dwa te same utwory"). This module collapses byte-identical audio to one entry
using the library's blake2b file checksum (identity survives renames).

Scope: exact byte duplicates only — zero false positives. Re-encoded copies of
the same music have different bytes and need audio fingerprinting (deferred).
"""

from __future__ import annotations

from pathlib import Path

from dancelab.core.models import AnalysisResult
from dancelab.storage.library_manifest import file_checksum

_checksum_cache: dict[tuple[str, int, int], str] = {}


def _cached_checksum(source_path: str | None) -> str | None:
    """blake2b of file bytes, cached on (path, size, mtime). None if unreadable."""
    if not source_path:
        return None
    path = Path(source_path)
    try:
        stat = path.stat()
    except OSError:
        return None  # missing file → cannot hash; treat as unique, never merge
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    cached = _checksum_cache.get(key)
    if cached is None:
        try:
            cached = file_checksum(path)
        except OSError:
            # stat() may succeed where open() is denied (macOS TCC on ~/Music):
            # an unreadable file is kept as-is, it must never kill the build
            return None
        _checksum_cache[key] = cached
    return cached


def dedupe_by_audio(
    analyses: list[AnalysisResult],
) -> tuple[list[AnalysisResult], list[str]]:
    """Keep one analysis per byte-identical audio file, first occurrence wins.

    Returns (unique_analyses, warnings). A track whose file is missing or
    unreadable is kept as-is — we never merge on uncertainty.
    """
    seen: dict[str, str] = {}  # checksum -> kept track_id
    unique: list[AnalysisResult] = []
    dropped: list[tuple[str, str]] = []  # (dropped_id, kept_id)
    for analysis in analyses:
        checksum = _cached_checksum(analysis.track.source_path)
        if checksum is None:
            unique.append(analysis)
            continue
        kept = seen.get(checksum)
        if kept is not None:
            dropped.append((analysis.track.track_id, kept))
            continue
        seen[checksum] = analysis.track.track_id
        unique.append(analysis)

    warnings: list[str] = []
    if dropped:
        pairs = ", ".join(f"{dup}→{kept}" for dup, kept in dropped)
        warnings.append(
            f"removed {len(dropped)} duplicate audio file(s) (same bytes): {pairs}"
        )
    return unique, warnings

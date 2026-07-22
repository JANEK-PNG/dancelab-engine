"""Repositories for engine entities.

v0: file-based over data/processed/<track_id>.json — exactly what the batch
CLI writes, so batch results are immediately queryable by the API.
Database-backed implementation replaces this behind the same interface later.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

from dancelab.core.errors import DanceLabError
from dancelab.core.models import DANCELAB_SCHEMA_VERSION, AnalysisResult
from dancelab.storage.artifact_store import load_json, save_json
from dancelab.storage.library_manifest import MANIFEST_NAME


_NON_ANALYSIS_STEMS = {"manifest", Path(MANIFEST_NAME).stem}
_TRACK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class TrackNotFoundError(DanceLabError):
    """No stored analysis for the requested track_id."""


class SchemaVersionWarning(UserWarning):
    """A stored analysis was written by a different engine schema version."""


class InvalidTrackIdError(DanceLabError):
    """A repository key is not a canonical, path-safe track identifier."""


class FileAnalysisRepository:
    """Save/load AnalysisResult as JSON files keyed by track_id."""

    def __init__(self, directory: str | Path = "data/processed"):
        self.directory = Path(directory)

    def _path(self, track_id: str) -> Path:
        if not _TRACK_ID_PATTERN.fullmatch(track_id):
            raise InvalidTrackIdError("track_id contains unsupported characters")
        root = self.directory.expanduser().resolve(strict=False)
        candidate = (root / f"{track_id}.json").resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:  # defensive if the identifier policy changes later
            raise InvalidTrackIdError("track_id resolves outside the analysis repository") from exc
        return candidate

    def save(self, result: AnalysisResult) -> Path:
        return save_json(result, self._path(result.track.track_id))

    def get(self, track_id: str) -> AnalysisResult:
        p = self._path(track_id)
        if not p.exists():
            raise TrackNotFoundError(
                f"No stored analysis for track '{track_id}'. Run analyze/batch first."
            )
        # AUD-H6: warn on schema drift so a growing AnalysisResult schema does
        # not silently mis-load previously-analyzed tracks (the whole point of
        # "no re-analysis" is that old stores stay valid — or say so loudly).
        stored_version = json.loads(p.read_text(encoding="utf-8")).get("schema_version")
        if stored_version is not None and stored_version != DANCELAB_SCHEMA_VERSION:
            warnings.warn(
                f"'{track_id}' was written by schema {stored_version}, engine is "
                f"{DANCELAB_SCHEMA_VERSION}; re-analyze if fields look stale.",
                SchemaVersionWarning,
                stacklevel=2,
            )
        return load_json(AnalysisResult, p)

    def list_track_ids(self) -> list[str]:
        return sorted(
            path.stem
            for path in self.directory.glob("*.json")
            if path.stem not in _NON_ANALYSIS_STEMS
            and _TRACK_ID_PATTERN.fullmatch(path.stem)
        )

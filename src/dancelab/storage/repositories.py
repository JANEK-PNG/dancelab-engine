"""Repositories for engine entities.

v0: file-based over data/processed/<track_id>.json — exactly what the batch
CLI writes, so batch results are immediately queryable by the API.
Database-backed implementation replaces this behind the same interface later.
"""

from __future__ import annotations

from pathlib import Path

from dancelab.core.errors import DanceLabError
from dancelab.core.models import AnalysisResult
from dancelab.storage.artifact_store import load_json, save_json


class TrackNotFoundError(DanceLabError):
    """No stored analysis for the requested track_id."""


class FileAnalysisRepository:
    """Save/load AnalysisResult as JSON files keyed by track_id."""

    def __init__(self, directory: str | Path = "data/processed"):
        self.directory = Path(directory)

    def _path(self, track_id: str) -> Path:
        return self.directory / f"{track_id}.json"

    def save(self, result: AnalysisResult) -> Path:
        return save_json(result, self._path(result.track.track_id))

    def get(self, track_id: str) -> AnalysisResult:
        p = self._path(track_id)
        if not p.exists():
            raise TrackNotFoundError(
                f"No stored analysis for track '{track_id}'. Run analyze/batch first."
            )
        return load_json(AnalysisResult, p)

    def list_track_ids(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json") if p.stem != "manifest")

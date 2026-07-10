"""Dataset manifest: one JSON snapshot tying analyses + annotations together."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from dancelab.core.models import DANCELAB_SCHEMA_VERSION
from dancelab.data.annotation_validator import DatasetValidationReport, validate_annotation_dataset
from dancelab.storage.repositories import FileAnalysisRepository


class DatasetManifest(BaseModel):
    schema_version: str = DANCELAB_SCHEMA_VERSION
    engine_version: str
    n_analyzed_tracks: int
    annotation_counts: dict[str, int] = Field(default_factory=dict)
    annotation_valid: bool
    analyzed_track_ids: list[str] = Field(default_factory=list)


def build_dataset_manifest(
    processed_dir: str | Path = "data/processed",
    annotations_dir: str | Path = "data/annotations",
    engine_version: str = "0.1.0",
) -> tuple[DatasetManifest, DatasetValidationReport]:
    repo = FileAnalysisRepository(processed_dir)
    ids = repo.list_track_ids()
    report = validate_annotation_dataset(annotations_dir)
    manifest = DatasetManifest(
        engine_version=engine_version,
        n_analyzed_tracks=len(ids),
        annotation_counts=report.counts,
        annotation_valid=report.valid,
        analyzed_track_ids=ids,
    )
    return manifest, report


def write_dataset_manifest(manifest: DatasetManifest, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    return p

"""Stem export endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from dancelab.api.schemas import (
    StemExportArtifactResponse,
    StemExportRequest,
    StemExportResponse,
)
from dancelab.api.security import ApiPathPolicy, heavy_job_slot
from dancelab.core.config import load_config
from dancelab.stems.workflow import export_stems_for_paths

router = APIRouter(prefix="/stems", tags=["stems"])


def _config():
    return load_config(os.environ.get("DANCELAB_CONFIG", "configs/default.yaml"))


@router.post("/export", response_model=StemExportResponse)
async def export_stems(
    request: StemExportRequest,
    _slot: None = Depends(heavy_job_slot),
) -> StemExportResponse:
    config = _config()
    policy = ApiPathPolicy.from_config(config)
    if len(request.source_paths) > policy.limits.max_stem_tracks:
        raise HTTPException(status_code=413, detail="stem batch exceeds API track-count limit")
    source_paths = [str(policy.input_file(path)) for path in request.source_paths]
    output_root = str(policy.output_path(request.output_root))
    try:
        artifacts = export_stems_for_paths(
            source_paths,
            config,
            output_root,
            stem_method=request.stem_method,
            vocal_method=request.vocal_method,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return StemExportResponse(
        output_root=output_root,
        track_count=len(artifacts),
        artifacts=[
            StemExportArtifactResponse(
                track_id=artifact.track_id,
                title=artifact.title,
                artifact_path=artifact.artifact_path,
                stems_written=artifact.stems_written,
                stem_source_status=artifact.stem_source_status,
                warnings=artifact.warnings,
            )
            for artifact in artifacts
        ],
    )

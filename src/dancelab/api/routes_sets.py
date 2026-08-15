"""Set endpoints (API Contract Draft):

POST /sets/recommend-next — ranked candidates + explanations + risk flags
POST /sets/recommend-sequence — draft short-horizon sequence planner

Note: contract draft groups this under sets; blueprint listed only three route
files — this fourth router is a deliberate, documented addition.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from dancelab.api.schemas import (
    BuildSetRequest,
    NextTrackRecommendation,
    RecommendNextRequest,
    RecommendSequenceRequest,
    SequenceDecision,
    SmartPlaylistFailureResponse,
    SmartPlaylistRequest,
    SmartPlaylistResponse,
)
from dancelab.api.security import ApiPathPolicy, heavy_job_slot
from dancelab.core.config import load_config, load_weights
from dancelab.core.models import SetPlan
from dancelab.decision.next_track import recommend_next as recommend_next_engine
from dancelab.decision.sequence import recommend_sequence as recommend_sequence_engine
from dancelab.decision.set_builder import build_set as build_set_engine
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.workflows.smart_playlist import build_smart_playlist_from_folder

router = APIRouter(prefix="/sets", tags=["sets"])


def _config():
    return load_config(os.environ.get("DANCELAB_CONFIG", "configs/default.yaml"))


def _repository(config) -> FileAnalysisRepository:
    return FileAnalysisRepository(
        os.environ.get("DANCELAB_PROCESSED_DIR", config.paths.processed_dir)
    )


def _requested_analyses(repo: FileAnalysisRepository, track_ids: list[str]):
    ids = track_ids or repo.list_track_ids()
    return [repo.get(track_id) for track_id in ids]


@router.post("/recommend-next", response_model=NextTrackRecommendation)
async def recommend_next(request: RecommendNextRequest) -> NextTrackRecommendation:
    config = _config()
    repo = _repository(config)
    current = repo.get(request.current_track_id)
    candidates = [repo.get(track_id) for track_id in request.candidate_track_ids]
    recent_history = [repo.get(track_id) for track_id in request.recent_track_ids]

    weights = load_weights(config.weights_file)
    return recommend_next_engine(
        current=current,
        candidates=candidates,
        context=request.context_profile,
        weights=weights,
        top_k=config.analysis.transition_top_n,
        recent_history=recent_history,
        arc_mode=request.arc_mode,
    )


@router.post("/recommend-sequence", response_model=SequenceDecision)
async def recommend_sequence(request: RecommendSequenceRequest) -> SequenceDecision:
    config = _config()
    repo = _repository(config)
    current = repo.get(request.current_track_id)
    candidates = [repo.get(track_id) for track_id in request.candidate_track_ids]
    recent_history = [repo.get(track_id) for track_id in request.recent_track_ids]

    weights = load_weights(config.weights_file)
    return recommend_sequence_engine(
        current=current,
        candidates=candidates,
        context=request.context_profile,
        weights=weights,
        top_k=config.analysis.transition_top_n,
        recent_history=recent_history,
        arc_mode=request.arc_mode,
        horizon=request.horizon,
    )


@router.post("/build", response_model=SetPlan)
async def build_set(request: BuildSetRequest) -> SetPlan:
    """Build a set via the same engine path used by CLI workflows."""
    config = _config()
    repo = _repository(config)
    weights = load_weights(config.weights_file)
    analyses = _requested_analyses(repo, request.track_ids)
    try:
        return build_set_engine(
            analyses,
            weights,
            arc=request.arc,
            planner_mode=request.planner_mode,
            start_track_id=request.start_track_id,
            target_track_count=request.target_track_count,
            locked_positions=request.locked_positions,
            pinned_track_ids=request.pinned_track_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/smart-playlist", response_model=SmartPlaylistResponse)
async def smart_playlist(
    request: SmartPlaylistRequest,
    _slot: None = Depends(heavy_job_slot),
) -> SmartPlaylistResponse:
    """One-shot DJ-set preset: folder -> analysis -> set plan -> Rekordbox XML."""
    config = _config()
    policy = ApiPathPolicy.from_config(config)
    folder_path = policy.input_directory(request.folder_path)
    policy.validate_audio_tree(folder_path, recursive=request.recursive)
    output_path = (
        str(policy.output_path(request.output_path)) if request.output_path else None
    )
    processed_dir = (
        str(policy.output_path(request.processed_dir)) if request.processed_dir else None
    )
    try:
        result = build_smart_playlist_from_folder(
            folder_path,
            config,
            target_track_count=request.target_track_count,
            playlist_name=request.playlist_name,
            output_path=output_path,
            processed_dir=processed_dir,
            arc=request.arc,
            planner_mode=request.planner_mode,
            analysis_depth=request.analysis_depth,
            recursive=request.recursive,
            recompute=request.recompute,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SmartPlaylistResponse(
        playlist_name=result.playlist_name,
        source_folder=result.source_folder,
        source_track_count=result.source_track_count,
        analyzed_track_count=result.analyzed_track_count,
        target_track_count=result.target_track_count,
        output_path=result.output_path,
        processed_dir=result.processed_dir,
        analyzed_track_ids=result.analyzed_track_ids,
        failed_tracks=[
            SmartPlaylistFailureResponse(
                source_path=failure.source_path,
                error=failure.error,
            )
            for failure in result.failed_tracks
        ],
        set_plan=result.set_plan,
        bundle_path=result.bundle_path,
    )

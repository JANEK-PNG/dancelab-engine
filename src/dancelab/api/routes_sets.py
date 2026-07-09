"""Set endpoints (API Contract Draft):

POST /sets/recommend-next — ranked candidates + explanations + risk flags
POST /sets/recommend-sequence — draft short-horizon sequence planner

Note: contract draft groups this under sets; blueprint listed only three route
files — this fourth router is a deliberate, documented addition.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from dancelab.api.schemas import (
    NextTrackRecommendation,
    RecommendNextRequest,
    RecommendSequenceRequest,
    SequenceDecision,
)
from dancelab.core.config import load_config, load_weights
from dancelab.decision.next_track import recommend_next as recommend_next_engine
from dancelab.decision.sequence import recommend_sequence as recommend_sequence_engine
from dancelab.storage.repositories import FileAnalysisRepository

router = APIRouter(prefix="/sets", tags=["sets"])


def _config():
    return load_config(os.environ.get("DANCELAB_CONFIG", "configs/default.yaml"))


def _repository(config) -> FileAnalysisRepository:
    return FileAnalysisRepository(
        os.environ.get("DANCELAB_PROCESSED_DIR", config.paths.processed_dir)
    )


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

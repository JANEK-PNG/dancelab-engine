"""Context endpoints (API Contract Draft):

POST /contexts/evaluate — context fit, peak/opening/closing fit, risk score
GET  /contexts/profiles — available example context profiles
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from dancelab.api.schemas import ContextEvaluateRequest, ContextEvaluation
from dancelab.core.config import load_config, load_context_profiles
from dancelab.context.conditioning import evaluate_context
from dancelab.storage.repositories import FileAnalysisRepository

router = APIRouter(prefix="/contexts", tags=["contexts"])


def _config():
    return load_config(os.environ.get("DANCELAB_CONFIG", "configs/default.yaml"))


def _repository(config) -> FileAnalysisRepository:
    return FileAnalysisRepository(
        os.environ.get("DANCELAB_PROCESSED_DIR", config.paths.processed_dir)
    )


@router.get("/profiles")
async def profiles() -> dict:
    config = _config()
    return load_context_profiles(config.context_profiles_file)


@router.post("/evaluate", response_model=ContextEvaluation)
async def evaluate(request: ContextEvaluateRequest) -> ContextEvaluation:
    config = _config()
    analysis = _repository(config).get(request.track_id)
    return evaluate_context(analysis, request.context_profile)

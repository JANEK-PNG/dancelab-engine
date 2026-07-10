"""Track endpoints (API Contract Draft + Sprint 2 Engineering Ticket):

POST /tracks/analyze — audio + metadata → analysis (stored + returned)
GET  /tracks/{track_id} — stored track profile
POST /tracks/{track_id}/transition-windows — Transition Windows Engine v0.1
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from dancelab.api.schemas import (
    AnalysisResult,
    AnalyzeTrackRequest,
    SetFunctionRequest,
    TransitionWindowOutput,
    TransitionWindowsRequest,
)
from dancelab.context.context_profile import get_context_profile
from dancelab.core.config import load_config, load_context_profiles, load_weights
from dancelab.core.models import (
    ContextProfile,
    SetFunctionInput,
    SetFunctionOutput,
    TransitionWindowInput,
)
from dancelab.core.pipeline import analyze_track
from dancelab.decision.set_function import classify_set_function
from dancelab.decision.transition_windows import detect_transition_windows
from dancelab.storage.repositories import FileAnalysisRepository

router = APIRouter(prefix="/tracks", tags=["tracks"])


def _config():
    return load_config(os.environ.get("DANCELAB_CONFIG", "configs/default.yaml"))


def _repository(config) -> FileAnalysisRepository:
    return FileAnalysisRepository(
        os.environ.get("DANCELAB_PROCESSED_DIR", config.paths.processed_dir)
    )


def _available_contexts(config) -> list[ContextProfile]:
    return [
        ContextProfile(context_id=context_id, **payload)
        for context_id, payload in load_context_profiles(config.context_profiles_file).items()
    ]


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(request: AnalyzeTrackRequest) -> AnalysisResult:
    # AUD-H3: forward EVERY accepted field — bpm_hint was validated then
    # silently dropped, making API-analyze diverge from CLI-analyze.
    config = _config()
    result = analyze_track(
        request.source_path,
        config,
        style_label=request.style_label,
        bpm_hint=request.bpm_hint,
        title=request.title,
        artist=request.artist,
    )
    _repository(config).save(result)  # analyzed → immediately queryable
    return result


@router.get("/{track_id}", response_model=AnalysisResult)
async def get_track(track_id: str) -> AnalysisResult:
    return _repository(_config()).get(track_id)


@router.post("/{track_id}/transition-windows", response_model=TransitionWindowOutput)
async def transition_windows(
    track_id: str, request: TransitionWindowsRequest
) -> TransitionWindowOutput:
    config = _config()
    analysis = _repository(config).get(track_id)

    context = request.context_profile
    if context is None and request.context_id:
        context = get_context_profile(request.context_id, config.context_profiles_file)

    weights = load_weights(config.weights_file)
    output = detect_transition_windows(
        TransitionWindowInput(
            track_id=track_id,
            segments=analysis.segments,
            feature_frames=analysis.features,
            beatgrid=analysis.beatgrid,
            context=context,
            available_contexts=_available_contexts(config),
        ),
        weights.transition_window,
        top_k=config.analysis.transition_top_n,
    )
    if request.previous_track_id or request.candidate_next_track_id:
        output.warnings.append(
            "previous/next track context accepted but unused by model v0.1 "
            "(pair scoring W_pair is a later model version)"
        )
    return output


@router.post("/{track_id}/set-function", response_model=SetFunctionOutput)
async def set_function(track_id: str, request: SetFunctionRequest) -> SetFunctionOutput:
    config = _config()
    analysis = _repository(config).get(track_id)

    context = request.context_profile
    if context is None and request.context_id:
        context = get_context_profile(request.context_id, config.context_profiles_file)

    weights = load_weights(config.weights_file)
    windows = detect_transition_windows(
        TransitionWindowInput(
            track_id=track_id,
            segments=analysis.segments,
            feature_frames=analysis.features,
            beatgrid=analysis.beatgrid,
            available_contexts=_available_contexts(config),
        ),
        weights.transition_window,
        top_k=config.analysis.transition_top_n,
    ).windows
    return classify_set_function(
        SetFunctionInput(track_analysis=analysis, context=context, transition_windows=windows)
    )

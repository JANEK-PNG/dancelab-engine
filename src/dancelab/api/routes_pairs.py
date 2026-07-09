"""Pair endpoints (API Contract Draft + Sprint 2 Final):

POST /pairs/mixability — Mixability Engine v0.1 (candidate)
POST /pairs/edge-decision — unified pair decision payload
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from dancelab.api.schemas import MixabilityRequest
from dancelab.context.context_profile import get_context_profile
from dancelab.core.config import load_config, load_context_profiles, load_weights
from dancelab.core.models import (
    ContextProfile,
    EdgeDecision,
    MixabilityInput,
    MixabilityOutput,
    TransitionWindowInput,
)
from dancelab.decision.edge_decision import build_edge_decision
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.transition_windows import detect_transition_windows
from dancelab.storage.repositories import FileAnalysisRepository

router = APIRouter(prefix="/pairs", tags=["pairs"])


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


def _resolve_context(request: MixabilityRequest, config) -> ContextProfile | None:
    if request.context_profile is not None:
        return request.context_profile
    if request.context_id:
        return get_context_profile(request.context_id, config.context_profiles_file)
    return None


def _pair_windows(config, weights, analysis_a, analysis_b, context: ContextProfile | None):
    available_contexts = _available_contexts(config)
    return {
        tid: detect_transition_windows(
            TransitionWindowInput(
                track_id=tid,
                segments=analysis.segments,
                feature_frames=analysis.features,
                beatgrid=analysis.beatgrid,
                context=context,
                available_contexts=available_contexts,
            ),
            weights.transition_window,
            top_k=config.analysis.transition_top_n,
        ).windows
        for tid, analysis in (
            (analysis_a.track.track_id, analysis_a),
            (analysis_b.track.track_id, analysis_b),
        )
    }


@router.post("/mixability", response_model=MixabilityOutput)
async def mixability(request: MixabilityRequest) -> MixabilityOutput:
    config = _config()
    repo = _repository(config)
    analysis_a = repo.get(request.track_id_a)
    analysis_b = repo.get(request.track_id_b)

    weights = load_weights(config.weights_file)
    context = _resolve_context(request, config)
    windows = _pair_windows(config, weights, analysis_a, analysis_b, context)

    return compute_mixability(
        MixabilityInput(
            track_a=analysis_a,
            track_b=analysis_b,
            context=context,
            transition_windows_a=windows[request.track_id_a],
            transition_windows_b=windows[request.track_id_b],
        ),
        weights.mixability,
        conflict_weights=weights.mixability_conflict,
    )


@router.post("/edge-decision", response_model=EdgeDecision)
async def edge_decision(request: MixabilityRequest) -> EdgeDecision:
    config = _config()
    repo = _repository(config)
    analysis_a = repo.get(request.track_id_a)
    analysis_b = repo.get(request.track_id_b)
    weights = load_weights(config.weights_file)
    context = _resolve_context(request, config)
    windows = _pair_windows(config, weights, analysis_a, analysis_b, context)
    mix = compute_mixability(
        MixabilityInput(
            track_a=analysis_a,
            track_b=analysis_b,
            context=context,
            transition_windows_a=windows[analysis_a.track.track_id],
            transition_windows_b=windows[analysis_b.track.track_id],
        ),
        weights.mixability,
        conflict_weights=weights.mixability_conflict,
    )
    return build_edge_decision(
        analysis_a,
        analysis_b,
        weights,
        context=context,
        transition_windows_a=windows[analysis_a.track.track_id],
        transition_windows_b=windows[analysis_b.track.track_id],
        mixability=mix,
        top_k=config.analysis.transition_top_n,
    )

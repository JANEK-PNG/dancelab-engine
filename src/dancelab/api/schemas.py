"""API request/response schemas (API Contract Draft).

Response bodies reuse core domain models directly — the API is a thin gateway
(ADR-006); it must not fork the data model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from dancelab.core.models import (  # noqa: F401  (re-exported as API responses)
    AnalysisResult,
    ContextEvaluation,
    ContextProfile,
    MixabilityResult,
    NextTrackRecommendation,
    SequenceDecision,
    Track,
    TransitionWindowOutput,
)


class AnalyzeTrackRequest(BaseModel):
    """POST /tracks/analyze — v0 accepts a server-visible path; file upload later."""

    source_path: str
    title: str | None = None
    artist: str | None = None
    style_label: str | None = None
    bpm_hint: float | None = Field(default=None, gt=0)
    context_id: str | None = None


class MixabilityRequest(BaseModel):
    track_id_a: str
    track_id_b: str
    context_id: str | None = None
    context_profile: ContextProfile | None = None


class SetFunctionRequest(BaseModel):
    """POST /tracks/{track_id}/set-function (Sprint 2 Final contract)."""

    context_id: str | None = None
    context_profile: ContextProfile | None = None


class ContextEvaluateRequest(BaseModel):
    track_id: str
    context_profile: ContextProfile


class RecommendNextRequest(BaseModel):
    current_track_id: str
    candidate_track_ids: list[str]
    recent_track_ids: list[str] = Field(default_factory=list)
    context_profile: ContextProfile | None = None
    arc_mode: str = "build"


class RecommendSequenceRequest(BaseModel):
    current_track_id: str
    candidate_track_ids: list[str]
    recent_track_ids: list[str] = Field(default_factory=list)
    context_profile: ContextProfile | None = None
    arc_mode: str = "build"
    horizon: int = Field(default=3, ge=1, le=12)


class TransitionWindowsRequest(BaseModel):
    """POST /tracks/{track_id}/transition-windows (Sprint 2 contract).

    previous_track_id / candidate_next_track_id are accepted per contract but
    unused by model v0.1 (pair scoring W_pair is a later version) — the
    response warns about this instead of silently ignoring it.
    """

    context_id: str | None = None
    context_profile: ContextProfile | None = None
    previous_track_id: str | None = None
    candidate_next_track_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    engine_version: str
    weights_version: str


class NotImplementedResponse(BaseModel):
    """Honest 501 body for specified-but-unimplemented computations (ADR-005)."""

    error: str = "not_implemented"
    feature: str
    formula_status: str
    detail: str

"""API request/response schemas (API Contract Draft).

Response bodies reuse core domain models directly — the API is a thin gateway
(ADR-006); it must not fork the data model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from dancelab.core.models import (  # noqa: F401  (re-exported as API responses)
    AnalysisResult,
    ContextEvaluation,
    ContextProfile,
    DANCELAB_SCHEMA_VERSION,
    MixabilityResult,
    NextTrackRecommendation,
    SetPlan,
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
    # AUD-M9: context_id removed — it was accepted and silently ignored
    # (conditioning is decision-time, not analyze-time).


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


class BuildSetRequest(BaseModel):
    """POST /sets/build — builds a SetPlan from stored analysis results."""

    track_ids: list[str] = Field(default_factory=list)
    start_track_id: str | None = None
    target_track_count: int | None = Field(default=None, ge=1)
    locked_positions: dict[int, str] = Field(default_factory=dict)
    pinned_track_ids: list[str] = Field(default_factory=list)
    arc: str = "build"


class RekordboxExportRequest(BaseModel):
    """POST /sets/export-rekordbox — returns XML and optionally writes it to disk."""

    track_ids: list[str] = Field(default_factory=list)
    set_plan: SetPlan | None = None
    start_track_id: str | None = None
    target_track_count: int | None = Field(default=None, ge=1)
    locked_positions: dict[int, str] = Field(default_factory=dict)
    pinned_track_ids: list[str] = Field(default_factory=list)
    arc: str = "build"
    playlist_name: str = "DanceLab Set"
    output_path: str | None = None


class RekordboxExportResponse(BaseModel):
    schema_version: str = DANCELAB_SCHEMA_VERSION
    playlist_name: str
    track_count: int
    output_path: str | None = None
    set_plan: SetPlan
    xml: str


class StemExportRequest(BaseModel):
    """POST /stems/export — analyze with stems enabled and write artifact folders."""

    source_paths: list[str] = Field(min_length=1)
    output_root: str = "data/exports/stems"
    stem_method: Literal["auto", "demucs", "none"] = "auto"
    vocal_method: Literal["hpss", "auto", "demucs"] | None = None


class StemExportArtifactResponse(BaseModel):
    track_id: str
    title: str | None = None
    artifact_path: str
    stems_written: list[str] = Field(default_factory=list)
    stem_source_status: str | None = None
    warnings: list[str] = Field(default_factory=list)


class StemExportResponse(BaseModel):
    schema_version: str = DANCELAB_SCHEMA_VERSION
    output_root: str
    track_count: int
    artifacts: list[StemExportArtifactResponse] = Field(default_factory=list)


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

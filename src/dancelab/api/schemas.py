"""API request/response schemas (API Contract Draft).

Response bodies reuse core domain models directly — the API is a thin gateway
(ADR-006); it must not fork the data model.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

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

TrackId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    ),
]
FilesystemPath = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
]


class AnalyzeTrackRequest(BaseModel):
    """POST /tracks/analyze — v0 accepts a server-visible path; file upload later."""

    source_path: FilesystemPath
    title: str | None = Field(default=None, max_length=512)
    artist: str | None = Field(default=None, max_length=512)
    style_label: str | None = Field(default=None, max_length=256)
    bpm_hint: float | None = Field(default=None, gt=0)
    # AUD-M9: context_id removed — it was accepted and silently ignored
    # (conditioning is decision-time, not analyze-time).


class MixabilityRequest(BaseModel):
    track_id_a: TrackId
    track_id_b: TrackId
    context_id: str | None = None
    context_profile: ContextProfile | None = None


class SetFunctionRequest(BaseModel):
    """POST /tracks/{track_id}/set-function (Sprint 2 Final contract)."""

    context_id: str | None = None
    context_profile: ContextProfile | None = None


class ContextEvaluateRequest(BaseModel):
    track_id: TrackId
    context_profile: ContextProfile


class RecommendNextRequest(BaseModel):
    current_track_id: TrackId
    candidate_track_ids: list[TrackId] = Field(min_length=1, max_length=2_000)
    recent_track_ids: list[TrackId] = Field(default_factory=list, max_length=200)
    context_profile: ContextProfile | None = None
    arc_mode: str = "build"


class RecommendSequenceRequest(BaseModel):
    current_track_id: TrackId
    candidate_track_ids: list[TrackId] = Field(min_length=1, max_length=2_000)
    recent_track_ids: list[TrackId] = Field(default_factory=list, max_length=200)
    context_profile: ContextProfile | None = None
    arc_mode: str = "build"
    horizon: int = Field(default=3, ge=1, le=12)


class BuildSetRequest(BaseModel):
    """POST /sets/build — builds a SetPlan from stored analysis results."""

    track_ids: list[TrackId] = Field(default_factory=list, max_length=2_000)
    start_track_id: TrackId | None = None
    target_track_count: int | None = Field(default=None, ge=1)
    locked_positions: dict[int, TrackId] = Field(default_factory=dict)
    pinned_track_ids: list[TrackId] = Field(default_factory=list, max_length=2_000)
    arc: str = "build"
    planner_mode: str = "smart"


class RekordboxExportRequest(BaseModel):
    """POST /sets/export-rekordbox — returns XML and optionally writes it to disk."""

    track_ids: list[TrackId] = Field(default_factory=list, max_length=2_000)
    set_plan: SetPlan | None = None
    start_track_id: TrackId | None = None
    target_track_count: int | None = Field(default=None, ge=1)
    locked_positions: dict[int, TrackId] = Field(default_factory=dict)
    pinned_track_ids: list[TrackId] = Field(default_factory=list, max_length=2_000)
    arc: str = "build"
    planner_mode: str = "smart"
    playlist_name: str = Field(default="DanceLab Set", min_length=1, max_length=200)
    output_path: FilesystemPath | None = None


class RekordboxExportResponse(BaseModel):
    schema_version: str = DANCELAB_SCHEMA_VERSION
    playlist_name: str
    track_count: int
    output_path: str | None = None
    set_plan: SetPlan
    xml: str


class SmartPlaylistRequest(BaseModel):
    """POST /sets/smart-playlist — folder in, analyzed Rekordbox playlist out."""

    folder_path: FilesystemPath
    target_track_count: Literal[5, 10, 15, 20] = 10
    playlist_name: str = Field(default="DanceLab Smart Set", min_length=1, max_length=200)
    output_path: FilesystemPath | None = None
    processed_dir: FilesystemPath | None = None
    arc: str = "build"
    planner_mode: str = "smart"
    analysis_depth: str = "normal"
    recursive: bool = True
    recompute: bool = False


class SmartPlaylistFailureResponse(BaseModel):
    source_path: str
    error: str


class SmartPlaylistResponse(BaseModel):
    schema_version: str = DANCELAB_SCHEMA_VERSION
    playlist_name: str
    source_folder: str
    source_track_count: int
    analyzed_track_count: int
    target_track_count: int
    output_path: str
    processed_dir: str
    analyzed_track_ids: list[str] = Field(default_factory=list)
    failed_tracks: list[SmartPlaylistFailureResponse] = Field(default_factory=list)
    set_plan: SetPlan
    xml: str


class StemExportRequest(BaseModel):
    """POST /stems/export — analyze with stems enabled and write artifact folders."""

    source_paths: list[FilesystemPath] = Field(min_length=1, max_length=32)
    output_root: FilesystemPath = "data/exports/stems"
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
    previous_track_id: TrackId | None = None
    candidate_next_track_id: TrackId | None = None


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

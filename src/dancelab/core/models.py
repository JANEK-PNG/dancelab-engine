"""Domain models for DanceLab Engine (Data Model and Schemas + Output Taxonomy).

All engine outputs are Pydantic models → JSON-serializable by construction (ADR-004).
Every decision output carries `status`, `explanation` and `confidence` (Master Prompt).
Core depends on Pydantic only — never on FastAPI (ADR-003).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


DANCELAB_SCHEMA_VERSION = "1.0.0"


class SchemaVersionedOutput(BaseModel):
    """Marker for top-level public JSON/API output contracts.

    This versions the serialized schema shape, separate from `model_version`
    (which versions a scoring/model formula) and `engine_version` (which
    versions the software package).
    """

    schema_version: str = DANCELAB_SCHEMA_VERSION


class ModelStatus(str, Enum):
    """Scientific status of a formula/output (ADR-005)."""

    stable = "stable"
    candidate = "candidate"
    planned = "planned"
    draft = "draft"


class ScientificStatus(str, Enum):
    """Sprint 3 source-grounding status (Scientific Status Encoding Model v0.1)."""

    source = "source"            # source-backed component
    inferred = "inferred"        # inferred from source-backed components
    hypothesis = "hypothesis"    # dancelab hypothesis
    candidate = "candidate"      # candidate computation model
    assumption = "assumption"    # domain assumption
    to_validate = "to_validate"  # awaiting empirical validation


class EvidenceGrade(str, Enum):
    """Evidence Grading Standard — Sprint 3. E5/E6 forbidden without a real pilot."""

    E0 = "E0"  # no evidence — idea only
    E1 = "E1"  # source mentioned
    E2 = "E2"  # source mapped to computation
    E3 = "E3"  # candidate formula (with cannot_claim)
    E4 = "E4"  # annotation protocol / validation-ready
    E5 = "E5"  # pilot tested
    E6 = "E6"  # replicated / robust


class ValidationStatus(str, Enum):
    to_validate = "to_validate"
    validation_ready = "validation_ready"
    pilot_supported = "pilot_supported"
    empirically_supported = "empirically_supported"


class ModelCard(BaseModel):
    """Semantic contract for an engine module (R&D Model Card Handoff Requirements).

    Every decision output must be traceable to one of these (traceability rule).
    """

    model_config = ConfigDict(protected_namespaces=())

    model_card_id: str
    model_version: str
    intended_use: str
    scientific_status: ScientificStatus
    evidence_grade: EvidenceGrade
    validation_status: ValidationStatus
    source_basis: list[str] = Field(default_factory=list)
    dance_lab_inference: str = ""
    limitations: list[str] = Field(default_factory=list)
    cannot_claim: list[str] = Field(default_factory=list)
    required_validation: list[str] = Field(default_factory=list)
    allowed_ui_wording: str = ""


class ComponentMetadata(BaseModel):
    """Metadata for one formula term (Formula Term Specification - Sprint 3).

    Enforces 'no anonymous variables': every weighted component in a decision
    score resolves to one of these, with its scientific status and cannot_claim.
    """

    component_key: str
    formula_symbol: str
    name: str
    scientific_status: ScientificStatus
    source_basis: list[str] = Field(default_factory=list)
    normalization_method: str = ""
    missing_data_policy: str = ""
    validation_required: str = ""
    cannot_claim: str = ""


class OutputProvenance(BaseModel):
    """Provenance block attached to every decision output (No-Overclaiming Contract).

    Carries the fields the Sprint 3 handoff mandates so no output can be shown
    as validated truth: scientific_status, evidence_grade, validation_status,
    source_basis, dance_lab_inference, cannot_claim, required_validation,
    limitations, allowed_ui_wording — all traceable to a model_card_id.
    """

    model_config = ConfigDict(protected_namespaces=())

    model_card_id: str
    scientific_status: ScientificStatus
    evidence_grade: EvidenceGrade
    validation_status: ValidationStatus
    source_basis: list[str] = Field(default_factory=list)
    dance_lab_inference: str = ""
    cannot_claim: list[str] = Field(default_factory=list)
    required_validation: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    allowed_ui_wording: str = ""


class SegmentType(str, Enum):
    intro = "intro"
    build = "build"
    drop = "drop"
    breakdown = "breakdown"
    groove = "groove"
    outro = "outro"
    unknown = "unknown"


class SetFunction(str, Enum):
    """Role of a track in a DJ set (Validation Plan labels + Set Function note)."""

    opener = "opener"
    builder = "builder"
    bridge = "bridge"
    peak = "peak"
    closer = "closer"
    reset = "reset"
    tool = "tool"
    unknown = "unknown"


class WindowType(str, Enum):
    """Transition window types (Transition Windows Engine, Sprint 2)."""

    mix_in = "mix_in"
    mix_out = "mix_out"
    bridge = "bridge"
    reset = "reset"
    peak_handoff = "peak_handoff"
    unknown = "unknown"


class TempoFeasibility(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class TransitionStrategy(str, Enum):
    standard_blend = "standard_blend"
    short_blend = "short_blend"
    phrase_aligned_blend = "phrase_aligned_blend"
    tempo_ramp = "tempo_ramp"
    break_transition = "break_transition"
    echo_out = "echo_out"
    hard_cut = "hard_cut"
    reset = "reset"
    half_time_double_time_switch = "half_time_double_time_switch"
    tool_mix = "tool_mix"


class BlendProfile(str, Enum):
    plain_blend = "plain_blend"
    bass_swap = "bass_swap"
    tops_swap = "tops_swap"
    contour_blend = "contour_blend"


class GateStatus(str, Enum):
    pass_ = "pass"
    review = "review"
    fail = "fail"
    strategy_dependent = "strategy_dependent"


class DecisionClass(str, Enum):
    strong_candidate = "strong_candidate"
    review_required = "review_required"
    non_standard_strategy_required = "non_standard_strategy_required"
    reject_standard_blend = "reject_standard_blend"


class RecommendationPolicy(str, Enum):
    allow = "allow"
    review_only = "review_only"
    suppress = "suppress"


class StemType(str, Enum):
    vocals = "vocals"
    bass = "bass"
    drums = "drums"
    other = "other"


class StemExtractionStatus(str, Enum):
    success = "success"
    partial = "partial"
    fallback = "fallback"
    failed = "failed"
    unavailable = "unavailable"


class ArtifactFlag(str, Enum):
    none = "none"
    mild = "mild"
    clear = "clear"
    severe = "severe"


class WarningLevel(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class SourceStatus(str, Enum):
    source_backed = "source_backed"
    fallback_full_mix = "fallback_full_mix"
    unavailable = "unavailable"


class DurationMatchStatus(str, Enum):
    match = "match"
    resampled = "resampled"
    mismatch = "mismatch"


class BeatGrid(BaseModel):
    """Beat grid: user-provided or estimated (preprocessing/beatgrid.py)."""

    bpm: float = Field(gt=0)
    beat_times_sec: list[float] = Field(default_factory=list)
    downbeats_sec: list[float] = Field(default_factory=list)
    quality_score: float | None = Field(default=None, ge=0, le=1)
    interval_cv: float | None = Field(default=None, ge=0)
    mean_grid_error_sec: float | None = Field(default=None, ge=0)
    max_grid_error_sec: float | None = Field(default=None, ge=0)
    bpm_mismatch_pct: float | None = Field(default=None, ge=0)
    coverage_sec: float | None = Field(default=None, ge=0)
    diagnostic_flags: list[str] = Field(default_factory=list)
    # True only when beat 1 of the bar comes from a verified source. The
    # baseline tracker finds beats, not bar phase; beat_times[::4] is a visual
    # proxy and must not authorize phrase-grid export or hot-cue claims.
    downbeat_phase_verified: bool = False
    # AUD-M2: False when no beats were detected (silence/untrackable) and the
    # bpm is a placeholder, not a measurement — downstream must not trust it.
    reliable: bool = True


# --------------------------------------------------------------------------- entities


class Track(BaseModel):
    track_id: str
    title: str | None = None
    artist: str | None = None
    duration_sec: float | None = Field(default=None, ge=0)
    sample_rate: int | None = Field(default=None, gt=0)
    channels: int | None = Field(default=None, ge=1, le=2)
    source_path: str | None = None
    style_label: str | None = None
    bpm_estimate: float | None = Field(default=None, gt=0)
    # Camelot / harmonic fields (Sprint 5.1 R&D handoff)
    key_estimate: str | None = None            # camelot_key, e.g. "8A" (Rekordbox Tonality)
    key_name: str | None = None                # musical_key, e.g. "A minor"
    key_confidence: float | None = Field(default=None, ge=0, le=1)
    camelot_number: int | None = Field(default=None, ge=1, le=12)
    camelot_mode: str | None = None            # "A" (minor) | "B" (major)
    key_detection_source: str | None = None    # detector | file_tag | rekordbox | manual
    key_verified_by: str | None = None         # manual override / DJ verifier
    # Odcisk brzmienia (CLAP). Opcjonalny: biblioteka bez osadzeń działa dalej,
    # składnik brzmienia jest wtedy pomijany, a nie zerowany — patrz
    # decision/sound_affinity.py.
    sound_embedding: list[float] | None = None

    def with_manual_key(self, camelot: str, verified_by: str = "manual") -> "Track":
        """Return a copy with a DJ-supplied key override (R&D: support manual override)."""
        from dancelab.decision.harmonic import parse_camelot
        parsed = parse_camelot(camelot)
        num, mode = (parsed if parsed else (None, None))
        return self.model_copy(update={
            "key_estimate": camelot, "camelot_number": num, "camelot_mode": mode,
            "key_confidence": 1.0, "key_detection_source": "manual",
            "key_verified_by": verified_by,
        })


class Segment(BaseModel):
    segment_id: str
    track_id: str
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    segment_type: SegmentType = SegmentType.unknown
    phrase_length_bars: int | None = Field(default=None, gt=0)


class FeatureFrame(BaseModel):
    """One time-frame of low-level features (Data Model and Schemas)."""

    track_id: str
    timestamp_sec: float = Field(ge=0)
    rms: float | None = None
    spectral_flux: float | None = None
    low_freq_energy_ratio: float | None = None
    onset_density: float | None = None
    pulse_clarity_proxy: float | None = None
    syncopation_proxy: float | None = None
    bass_energy: float | None = None
    bass_salience: float | None = None
    microtiming_proxy: float | None = None
    tension_proxy: float | None = None
    release_proxy: float | None = None
    vocal_density_proxy: float | None = None


class StemProvenance(BaseModel):
    """Provenance block for one stem-extraction run (Sprint 4 handoff)."""

    provenance_id: str
    model_name: str
    model_variant: str | None = None
    model_signature: str | None = None
    processing_command: str | None = None
    config_hash: str | None = None
    input_audio_id: str
    output_stem_ids: dict[StemType, str] = Field(default_factory=dict)
    output_sample_rate: int | None = Field(default=None, gt=0)
    duration_match_status: DurationMatchStatus = DurationMatchStatus.match
    extraction_status: StemExtractionStatus
    artifact_flag: ArtifactFlag = ArtifactFlag.none
    fallback_used: bool = False


class StemChannelSummary(BaseModel):
    """JSON-safe summary of one extracted stem."""

    stem_type: StemType
    stem_id: str | None = None
    available: bool = False
    source_status: SourceStatus = SourceStatus.unavailable
    warning_level: WarningLevel = WarningLevel.info
    activity_mean: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)


class StemAwareScore(BaseModel):
    """Guardrailed score container for Sprint 4 stem-aware outputs."""

    score: float | None = Field(default=None, ge=0, le=1)
    warning_level: WarningLevel = WarningLevel.info
    source_status: SourceStatus = SourceStatus.unavailable
    validation_status: ValidationStatus = ValidationStatus.to_validate
    cannot_claim: str = ""
    provenance_pointer: str | None = None
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StemExtractionResult(BaseModel):
    """Track-level summary of the optional stem-aware preprocessing layer."""

    status: ModelStatus = ModelStatus.candidate
    source_status: SourceStatus = SourceStatus.unavailable
    warning_level: WarningLevel = WarningLevel.info
    validation_status: ValidationStatus = ValidationStatus.to_validate
    cannot_claim: str = ""
    provenance: StemProvenance
    channels: list[StemChannelSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StemWindowFeature(BaseModel):
    """Stem-aware per-window candidate feature for pilots and future decisions."""

    track_id: str
    window_id: str
    stem_type: StemType
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    activity_score: float | None = Field(default=None, ge=0, le=1)
    density_score: float | None = Field(default=None, ge=0, le=1)
    continuity_score: float | None = Field(default=None, ge=0, le=1)
    confidence_score: float = Field(ge=0, le=1)
    warning_level: WarningLevel = WarningLevel.info
    source_status: SourceStatus = SourceStatus.unavailable
    validation_status: ValidationStatus = ValidationStatus.to_validate
    cannot_claim: str = ""
    provenance_pointer: str | None = None


class ContextProfile(BaseModel):
    context_id: str
    venue_type: str | None = None
    set_role: str | None = None
    time_of_night: str | None = None
    crowd_energy: str | None = None
    style_focus: list[str] = Field(default_factory=list)
    bpm_min: float | None = Field(default=None, gt=0)
    bpm_max: float | None = Field(default=None, gt=0)


class LibraryProfile(SchemaVersionedOutput):
    """Library-level summary extracted from analyzed tracks."""

    track_count: int = Field(ge=0)
    bpm_min: float | None = None
    bpm_max: float | None = None
    bpm_mean: float | None = None
    style_counts: dict[str, int] = Field(default_factory=dict)
    dominant_style: str | None = None
    missing_style_count: int = Field(default=0, ge=0)
    preferred_styles: list[str] = Field(default_factory=list)
    preferred_style_track_count: int = Field(default=0, ge=0)
    bpm_preference_min: float | None = None
    bpm_preference_max: float | None = None
    bpm_preference_track_count: int = Field(default=0, ge=0)
    context_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------- curves & windows


class DescriptorCurve(BaseModel):
    """Time series of one descriptor, with explicit scientific status."""

    name: str
    status: ModelStatus
    times_sec: list[float] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    unit: str | None = None


class TransitionWindow(BaseModel):
    """One candidate transition window (Transition Windows Engine output table)."""

    transition_window_id: str | None = None
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    score: float
    status: ModelStatus = ModelStatus.candidate
    window_type: WindowType = WindowType.unknown
    confidence: float | None = Field(default=None, ge=0, le=1)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    compatible_contexts: list[str] = Field(default_factory=list)
    tempo_window_feasibility: TempoFeasibility | None = None
    standard_blend_allowed: bool | None = None
    recommended_strategies: list[TransitionStrategy] = Field(default_factory=list)
    tempo_warning: str | None = None
    explanation: str = ""


class TransitionWindowInput(BaseModel):
    """Input contract for detect_transition_windows (Engineering Ticket)."""

    track_id: str
    segments: list[Segment] = Field(default_factory=list)
    feature_frames: list[FeatureFrame] = Field(default_factory=list)
    beatgrid: BeatGrid | None = None
    context: ContextProfile | None = None
    available_contexts: list[ContextProfile] = Field(default_factory=list)


class TransitionWindowOutput(SchemaVersionedOutput):
    """Output contract for detect_transition_windows (Engineering Ticket)."""

    model_config = ConfigDict(protected_namespaces=())

    track_id: str
    windows: list[TransitionWindow] = Field(default_factory=list)
    model_version: str
    warnings: list[str] = Field(default_factory=list)
    provenance: OutputProvenance | None = None


# ------------------------------------------------------------------- decision outputs


class ScoredOutput(BaseModel):
    """A single decision-layer score. Explanation + confidence are mandatory
    (Master Prompt: 'Every decision output must include explanation and
    confidence/risk fields')."""

    value: float
    status: ModelStatus
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str


class DecisionOutput(BaseModel):
    track_id: str
    context_id: str | None = None
    groove_score: ScoredOutput | None = None
    tension_score: ScoredOutput | None = None
    release_score: ScoredOutput | None = None
    set_function: SetFunction = SetFunction.unknown
    set_function_confidence: float | None = Field(default=None, ge=0, le=1)
    peak_time_fit: ScoredOutput | None = None
    opening_fit: ScoredOutput | None = None
    closing_fit: ScoredOutput | None = None
    risk_score: ScoredOutput | None = None
    best_transition_windows: list[TransitionWindow] = Field(default_factory=list)
    candidate_next_track_ids: list[str] = Field(default_factory=list)


class AnalysisResult(SchemaVersionedOutput):
    """Full per-track analysis (POST /tracks/analyze response body)."""

    engine_version: str
    weights_version: str | None = None
    # Odcisk PLIKU wag, którym policzono tę analizę — nie numer wersji, tylko
    # skrót zawartości. `weights_version` mówi „0.1.0" i nie zmienia się, gdy
    # ktoś podkręci wagę w środku; skrót zmienia się zawsze. Dzięki temu analiza
    # sama o sobie mówi, czym powstała, i da się ją ponownie użyć w innym
    # katalogu niż ten, w którym powstała — bez tego pola trzeba ją przeliczyć,
    # bo „nie wiem, czym to policzono" nie jest podstawą do użycia (ADR-005).
    formula_version: str | None = None
    track: Track
    beatgrid: BeatGrid | None = None
    segments: list[Segment] = Field(default_factory=list)
    features: list[FeatureFrame] = Field(default_factory=list)
    stem_extraction: StemExtractionResult | None = None
    stem_window_features: list[StemWindowFeature] = Field(default_factory=list)
    descriptor_curves: list[DescriptorCurve] = Field(default_factory=list)
    decision_outputs: DecisionOutput | None = None
    notes: list[str] = Field(default_factory=list)
    """Honest coverage notes: what this analysis did and did not compute."""


class MixabilityResult(SchemaVersionedOutput):
    """POST /pairs/mixability response body (API Contract Draft)."""

    track_id_a: str
    track_id_b: str
    mixability_score: ScoredOutput
    tempo_fit: float | None = None
    energy_fit: float | None = None
    bass_fit: float | None = None
    style_fit: float | None = None
    recommended_transition_points: list[TransitionWindow] = Field(default_factory=list)


class ContextEvaluation(SchemaVersionedOutput):
    """POST /contexts/evaluate response body."""

    track_id: str
    context_id: str
    context_fit: ScoredOutput
    peak_time_fit: ScoredOutput | None = None
    opening_fit: ScoredOutput | None = None
    closing_fit: ScoredOutput | None = None
    risk_score: ScoredOutput | None = None
    model_version: str = "context_evaluation_v0.1"
    warnings: list[str] = Field(default_factory=list)
    provenance: OutputProvenance | None = None


class PairWindow(BaseModel):
    """A matched (mix-out of A, mix-in of B) window pair with its M_pair score."""

    track_a_window: tuple[float, float]
    track_b_window: tuple[float, float]
    pair_score: float
    explanation: str = ""


class MixabilityInput(BaseModel):
    """Input contract for compute_mixability (Sprint 2 Final ticket)."""

    track_a: AnalysisResult
    track_b: AnalysisResult
    context: ContextProfile | None = None
    transition_windows_a: list[TransitionWindow] = Field(default_factory=list)
    transition_windows_b: list[TransitionWindow] = Field(default_factory=list)


class MixabilityOutput(SchemaVersionedOutput):
    """Output contract for compute_mixability (Sprint 2 Final ticket)."""

    model_config = ConfigDict(protected_namespaces=())

    track_id_a: str
    track_id_b: str
    mixability_score: float
    status: ModelStatus = ModelStatus.candidate
    confidence: float = Field(ge=0, le=1)
    best_pair_windows: list[PairWindow] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_version: str
    provenance: OutputProvenance | None = None
    tempo_fit: float | None = Field(default=None, ge=0, le=1)
    phrase_fit: float | None = Field(default=None, ge=0, le=1)
    energy_fit: float | None = Field(default=None, ge=0, le=1)
    tension_fit: float | None = Field(default=None, ge=0, le=1)
    style_fit: float | None = Field(default=None, ge=0, le=1)
    context_fit_score: float | None = Field(default=None, ge=0, le=1)
    bass_conflict_risk: float | None = Field(default=None, ge=0, le=1)
    vocal_clash_risk: float | None = Field(default=None, ge=0, le=1)
    # Harmonic Compatibility (Sprint 5.1 acceptance criteria)
    harmonic_relation: str | None = None
    harmonic_risk: float | None = Field(default=None, ge=0, le=1)
    key_a: str | None = None
    key_b: str | None = None
    key_confidence_min: float | None = Field(default=None, ge=0, le=1)
    tempo_relation: str = "unknown"
    bpm_delta_pct: float | None = None
    effective_bpm_delta_pct: float | None = None
    tempo_gate_status: GateStatus = GateStatus.review
    harmonic_gate_status: GateStatus = GateStatus.review
    standard_blend_allowed: bool = False
    rule_flags: list[str] = Field(default_factory=list)
    hard_block: bool = False
    rule_penalty: float = Field(default=0.0, ge=0, le=1)
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.review_only
    policy_reasons: list[str] = Field(default_factory=list)


class TransitionStrategyDecision(BaseModel):
    bpm_a: float | None = Field(default=None, gt=0)
    bpm_b: float | None = Field(default=None, gt=0)
    bpm_delta_pct: float | None = None
    effective_bpm_delta_pct: float | None = None
    tempo_relation: str = "unknown"
    tempo_window_feasibility: TempoFeasibility
    standard_blend_allowed: bool
    recommended_transition_strategy: TransitionStrategy
    alternative_transition_strategies: list[TransitionStrategy] = Field(default_factory=list)
    tempo_gate_status: GateStatus
    harmonic_gate_status: GateStatus
    explanation: str
    tempo_warning: str | None = None


class BlendProfileDecision(BaseModel):
    blend_profile_auto: BlendProfile
    explanation: str


class EdgeDecision(SchemaVersionedOutput):
    """Unified pair-level DJ decision payload."""

    model_config = ConfigDict(protected_namespaces=())

    track_id_a: str
    track_id_b: str
    decision_class: DecisionClass
    core_dj_compatibility_score: ScoredOutput
    standard_blend_allowed: bool
    recommended_transition_strategy: TransitionStrategy
    blend_profile_auto: BlendProfile = BlendProfile.plain_blend
    blend_profile_explanation: str = ""
    alternative_transition_strategies: list[TransitionStrategy] = Field(default_factory=list)
    tempo_gate_status: GateStatus
    harmonic_gate_status: GateStatus
    tempo_window_feasibility: TempoFeasibility
    tempo_relation: str = "unknown"
    bpm_delta_pct: float | None = None
    effective_bpm_delta_pct: float | None = None
    selected_pair_window: PairWindow | None = None
    selected_window_a: TransitionWindow | None = None
    selected_window_b: TransitionWindow | None = None
    harmonic_relation: str | None = None
    harmonic_risk: float | None = Field(default=None, ge=0, le=1)
    context_fit_score: float | None = Field(default=None, ge=0, le=1)
    bass_conflict_risk: float | None = Field(default=None, ge=0, le=1)
    vocal_clash_risk: float | None = Field(default=None, ge=0, le=1)
    compatible_contexts: list[str] = Field(default_factory=list)
    rule_flags: list[str] = Field(default_factory=list)
    hard_block: bool = False
    rule_penalty: float = Field(default=0.0, ge=0, le=1)
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.review_only
    policy_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    annotation_payload: dict[str, object] = Field(default_factory=dict)
    model_version: str = "edge_decision_v0.1"
    provenance: OutputProvenance | None = None


class SetFunctionInput(BaseModel):
    """Input contract for classify_set_function (Sprint 2 Final ticket)."""

    track_analysis: AnalysisResult
    context: ContextProfile | None = None
    transition_windows: list[TransitionWindow] = Field(default_factory=list)


class SetFunctionOutput(SchemaVersionedOutput):
    """Output contract for classify_set_function (Sprint 2 Final ticket)."""

    model_config = ConfigDict(protected_namespaces=())

    track_id: str
    primary_function: SetFunction
    secondary_functions: list[SetFunction] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    context_fit: float | None = Field(default=None, ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    role_scores: dict[str, float] = Field(default_factory=dict)
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_version: str
    provenance: OutputProvenance | None = None


class SetTransition(BaseModel):
    """One step in an ordered set: from track A to track B, with rationale."""

    from_track_id: str
    to_track_id: str
    transition_score: float
    # Vocabulary comes from decision/harmonic.py harmonic_relation() and matches
    # the corpus priors measurement exactly: "exact" | "relative_major_minor" |
    # "adjacent_same_mode" | "cautious" | "risky" | "unknown".
    harmonic_relation: str
    key_from: str | None = None     # Camelot
    key_to: str | None = None
    bpm_from: float | None = None
    bpm_to: float | None = None
    bpm_delta_pct: float | None = None
    energy_delta: float | None = None
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransitionCue(SchemaVersionedOutput):
    """Edge-level transition cue (SPEC §13): where A hands off to B.

    Rekordbox cues are track-level; recommendations are edge-level — this
    bridges them. HARD RULE (ADR-005): no edge may claim "start Track B
    here" unless b_cue_source is a verified cue with a real timestamp;
    window_only edges always require a manual listen. mix_duration_beats is
    None (never fabricated) when either beatgrid is unreliable.
    """

    from_track_id: str
    to_track_id: str
    transition_type: str = "unknown"
    a_out_start_sec: float | None = None
    a_window_source: str = "dancelab_transition_window"
    b_in_start_sec: float | None = None
    b_cue_source: str = "window_only"   # "rekordbox_hotcue" | "dancelab_written_hotcue" | "window_only"
    b_cue_slot: int | None = None        # hot cue slot 1-8 (A-H) when rekordbox_hotcue
    mix_duration_beats: int | None = None
    # Blend length from the stability craft rule (decision/transition_length):
    # a named rule over the RMS envelopes, NOT a measurement — kept in its own
    # field so it can never be mistaken for the measured window length above.
    suggested_blend_beats: int | None = None
    blend_beats_basis: str = "stability_craft_rule"
    confidence: float | None = Field(default=None, ge=0, le=1)
    requires_manual_listen: bool = True
    reasoning: list[str] = Field(default_factory=list)


class SetCoherence(BaseModel):
    """Whole-set shape as one measured number, decomposed and honest.

    A report, not a ranking input: it measures whether the finished set holds
    together as a whole (the DJ's "does this belong together"), separate from
    the pairwise transition scores. None of these are crowd-response claims.
    """

    overall: float = Field(ge=0.0, le=1.0)
    # None when arc="off": adherence to a target that does not exist is not a
    # measurement, and reporting a number there would invent one (ADR-005).
    arc_adherence: float | None = Field(default=None, ge=0.0, le=1.0)
    tempo_continuity: float = Field(ge=0.0, le=1.0)  # smoothness of BPM progression
    note: str = ""


class SetPlan(SchemaVersionedOutput):
    """An ordered DJ set proposed by the set-builder (candidate)."""

    model_config = ConfigDict(protected_namespaces=())

    track_order: list[str] = Field(default_factory=list)
    transitions: list[SetTransition] = Field(default_factory=list)
    arc: str = "build"
    planner_mode: str = "smart"
    target_track_count: int | None = Field(default=None, ge=1)
    locked_positions: dict[int, str] = Field(default_factory=dict)
    pinned_track_ids: list[str] = Field(default_factory=list)
    dropped_track_ids: list[str] = Field(default_factory=list)
    mean_transition_score: float | None = None
    set_coherence: SetCoherence | None = None
    model_version: str = "set_builder_v0.2"
    warnings: list[str] = Field(default_factory=list)
    provenance: OutputProvenance | None = None


class NextTrackCandidate(BaseModel):
    track_id: str
    rank: int = Field(ge=1)
    score: ScoredOutput
    risk_flags: list[str] = Field(default_factory=list)
    rule_flags: list[str] = Field(default_factory=list)
    hard_block: bool = False
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.allow
    policy_reasons: list[str] = Field(default_factory=list)


class NextTrackRecommendation(SchemaVersionedOutput):
    """POST /sets/recommend-next response body."""

    current_track_id: str
    context_id: str | None = None
    arc_mode: str = "build"
    recent_history_track_ids: list[str] = Field(default_factory=list)
    ranking: list[NextTrackCandidate] = Field(default_factory=list)
    suppressed_track_ids: list[str] = Field(default_factory=list)
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.review_only
    model_version: str = "next_track_v0.1"
    warnings: list[str] = Field(default_factory=list)
    provenance: OutputProvenance | None = None


class SequenceStep(BaseModel):
    step_index: int = Field(ge=1)
    from_track_id: str
    to_track_id: str
    score: ScoredOutput
    recommended_transition_strategy: TransitionStrategy | None = None
    decision_class: DecisionClass | None = None
    pair_score: float | None = Field(default=None, ge=0, le=1)
    local_arc_score: float | None = Field(default=None, ge=0, le=1)
    global_arc_score: float | None = Field(default=None, ge=0, le=1)
    lookahead_arc_score: float | None = Field(default=None, ge=0, le=1)
    terminal_arc_score: float | None = Field(default=None, ge=0, le=1)
    set_memory_score: float | None = Field(default=None, ge=0, le=1)
    transition_quality_score: float | None = Field(default=None, ge=0, le=1)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    energy_value: float | None = None
    target_energy: float | None = None
    energy_delta: float | None = None
    target_energy_delta: float | None = None
    cumulative_risk_score: float | None = Field(default=None, ge=0, le=1)
    effective_bpm_delta_pct: float | None = None
    energy_region: str | None = None
    energy_region_streak: int | None = Field(default=None, ge=1)
    guardrail_flags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.review_only
    policy_reasons: list[str] = Field(default_factory=list)


class SequenceDecision(SchemaVersionedOutput):
    """Draft sequence planner output for Phase 3."""

    current_track_id: str
    context_id: str | None = None
    arc_mode: str = "build"
    horizon: int = Field(default=3, ge=1)
    recent_history_track_ids: list[str] = Field(default_factory=list)
    sequence_track_ids: list[str] = Field(default_factory=list)
    steps: list[SequenceStep] = Field(default_factory=list)
    mean_sequence_score: float | None = None
    local_arc_score: float | None = Field(default=None, ge=0, le=1)
    global_arc_score: float | None = Field(default=None, ge=0, le=1)
    lookahead_arc_score: float | None = Field(default=None, ge=0, le=1)
    terminal_arc_score: float | None = Field(default=None, ge=0, le=1)
    set_memory_score: float | None = Field(default=None, ge=0, le=1)
    cumulative_risk_score: float | None = Field(default=None, ge=0, le=1)
    effective_bpm_span_pct: float | None = None
    max_energy_region_streak: int | None = Field(default=None, ge=1)
    observed_energy_profile: list[float] = Field(default_factory=list)
    target_energy_profile: list[float] = Field(default_factory=list)
    guardrail_flags: list[str] = Field(default_factory=list)
    suppressed_transition_count: int = Field(default=0, ge=0)
    recommendation_policy: RecommendationPolicy = RecommendationPolicy.review_only
    model_version: str = "sequence_v0.1"
    warnings: list[str] = Field(default_factory=list)
    provenance: OutputProvenance | None = None

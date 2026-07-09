"""Schema contracts: JSON round-trips (ADR-004) and example output validity."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dancelab.core.models import (
    AnalysisResult,
    ArtifactFlag,
    ContextProfile,
    DecisionOutput,
    DurationMatchStatus,
    ScoredOutput,
    SetFunction,
    SourceStatus,
    StemChannelSummary,
    StemExtractionResult,
    StemExtractionStatus,
    StemProvenance,
    StemType,
    StemWindowFeature,
    Track,
    ValidationStatus,
    WarningLevel,
)


def test_example_json_validates_against_schema():
    """The committed example (real analyze output) MUST match the schema.

    A stored analysis carries features + beatgrid + segments but NOT
    decision_outputs — decisions are produced on demand by the decision
    endpoints, never persisted as fabricated fields (ADR-005)."""
    raw = json.loads(Path("data/examples/example_track_analysis.json").read_text())
    result = AnalysisResult.model_validate(raw)
    assert result.decision_outputs is None
    assert result.beatgrid is not None and result.beatgrid.bpm > 0
    assert result.segments and result.features
    assert all(f.onset_density is not None for f in result.features)


def test_analysis_result_json_roundtrip():
    raw = json.loads(Path("data/examples/example_track_analysis.json").read_text())
    result = AnalysisResult.model_validate(raw)
    again = AnalysisResult.model_validate_json(result.model_dump_json())
    assert again == result


def test_analysis_result_with_stem_fields_json_roundtrip():
    result = AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id="stem-track"),
        stem_extraction=StemExtractionResult(
            source_status=SourceStatus.source_backed,
            warning_level=WarningLevel.info,
            validation_status=ValidationStatus.to_validate,
            cannot_claim="candidate only",
            provenance=StemProvenance(
                provenance_id="prov-1",
                model_name="htdemucs",
                model_variant="demucs",
                input_audio_id="stem-track",
                output_stem_ids={StemType.vocals: "stem-track:vocals"},
                output_sample_rate=44100,
                duration_match_status=DurationMatchStatus.match,
                extraction_status=StemExtractionStatus.success,
                artifact_flag=ArtifactFlag.none,
            ),
            channels=[
                StemChannelSummary(
                    stem_type=StemType.vocals,
                    stem_id="stem-track:vocals",
                    available=True,
                    source_status=SourceStatus.source_backed,
                    warning_level=WarningLevel.info,
                    activity_mean=0.4,
                    confidence=0.8,
                )
            ],
            warnings=[],
        ),
        stem_window_features=[
            StemWindowFeature(
                track_id="stem-track",
                window_id="stem-track_vocals_000001",
                stem_type=StemType.vocals,
                start_sec=1.0,
                end_sec=2.0,
                activity_score=0.4,
                density_score=0.4,
                continuity_score=0.9,
                confidence_score=0.8,
                warning_level=WarningLevel.info,
                source_status=SourceStatus.source_backed,
                validation_status=ValidationStatus.to_validate,
                cannot_claim="candidate only",
                provenance_pointer="prov-1",
            )
        ],
    )

    again = AnalysisResult.model_validate_json(result.model_dump_json())
    assert again == result


def test_scored_output_requires_explanation_and_confidence():
    with pytest.raises(ValidationError):
        ScoredOutput(value=0.5, status="candidate")  # missing confidence + explanation
    with pytest.raises(ValidationError):
        ScoredOutput(value=0.5, status="candidate", confidence=1.5, explanation="x")


def test_track_field_constraints():
    with pytest.raises(ValidationError):
        Track(track_id="t", bpm_estimate=-10)
    with pytest.raises(ValidationError):
        Track(track_id="t", channels=3)


def test_decision_output_defaults_to_unknown_set_function():
    d = DecisionOutput(track_id="t")
    assert d.set_function == SetFunction.unknown
    assert d.best_transition_windows == []


def test_context_profile_serializes():
    c = ContextProfile(context_id="club_peak", venue_type="club", style_focus=["techno"])
    assert json.loads(c.model_dump_json())["context_id"] == "club_peak"

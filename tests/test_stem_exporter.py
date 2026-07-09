"""Artifact export tests for separated stems."""

from __future__ import annotations

import json

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.models import (
    AnalysisResult,
    ArtifactFlag,
    DurationMatchStatus,
    SourceStatus,
    StemChannelSummary,
    StemExtractionResult,
    StemExtractionStatus,
    StemProvenance,
    StemType,
    Track,
    ValidationStatus,
    WarningLevel,
)
from dancelab.stems import StemBundle, export_stem_artifacts


def test_export_stem_artifacts_writes_expected_files(tmp_path):
    source = tmp_path / "track.mp3"
    source.write_bytes(b"fake mp3")

    result = AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id="track-1",
            title="Track One",
            source_path=str(source),
        ),
        stem_extraction=StemExtractionResult(
            source_status=SourceStatus.source_backed,
            warning_level=WarningLevel.info,
            validation_status=ValidationStatus.to_validate,
            cannot_claim="candidate only",
            provenance=StemProvenance(
                provenance_id="prov-1",
                model_name="htdemucs",
                model_variant="demucs",
                input_audio_id="track-1",
                output_stem_ids={StemType.vocals: "track-1:vocals"},
                output_sample_rate=44100,
                duration_match_status=DurationMatchStatus.match,
                extraction_status=StemExtractionStatus.success,
                artifact_flag=ArtifactFlag.none,
            ),
            channels=[
                StemChannelSummary(
                    stem_type=StemType.vocals,
                    stem_id="track-1:vocals",
                    available=True,
                    source_status=SourceStatus.source_backed,
                    warning_level=WarningLevel.info,
                    activity_mean=0.5,
                    confidence=0.9,
                )
            ],
            warnings=[],
        ),
    )
    bundle = StemBundle(
        channels={
            StemType.vocals: AudioSignal(
                samples=np.ones(2048, dtype=np.float32),
                sample_rate=44100,
                source_path=str(source),
            )
        },
        result=result.stem_extraction,
    )

    out_dir = export_stem_artifacts(result, bundle, tmp_path / "exports")

    assert out_dir.is_dir()
    assert (out_dir / "track.mp3").exists()
    assert (out_dir / "analysis.json").exists()
    assert (out_dir / "vocals.wav").exists()
    manifest = json.loads((out_dir / "stem_manifest.json").read_text())
    assert manifest["stem_source_status"] == "source_backed"
    assert manifest["stems_written"] == ["vocals.wav"]

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig
from dancelab.core.models import (
    AnalysisResult,
    ModelStatus,
    SourceStatus,
    StemChannelSummary,
    StemExtractionResult,
    StemExtractionStatus,
    StemProvenance,
    StemType,
    Track,
    WarningLevel,
)
from dancelab.stems.extractor import StemBundle
from dancelab.stems.workflow import export_stems_for_paths


def _stem_result(track_id: str) -> StemExtractionResult:
    return StemExtractionResult(
        status=ModelStatus.candidate,
        source_status=SourceStatus.source_backed,
        warning_level=WarningLevel.info,
        provenance=StemProvenance(
            provenance_id=f"{track_id}:test",
            model_name="test_stem_backend",
            input_audio_id=track_id,
            output_stem_ids={StemType.vocals: f"{track_id}:vocals"},
            output_sample_rate=44100,
            extraction_status=StemExtractionStatus.success,
        ),
        channels=[
            StemChannelSummary(
                stem_type=StemType.vocals,
                stem_id=f"{track_id}:vocals",
                available=True,
                source_status=SourceStatus.source_backed,
                confidence=0.9,
            )
        ],
    )


def test_export_stems_for_paths_enables_stem_config_and_writes_artifacts(tmp_path):
    pytest.importorskip("soundfile")
    source_path = tmp_path / "Track One.mp3"
    source_path.write_bytes(b"fake mp3 payload")
    output_root = tmp_path / "stem_exports"
    seen_configs: list[EngineConfig] = []

    def analyze_stub(path: str, config: EngineConfig):
        seen_configs.append(config)
        track_id = Path(path).stem.lower().replace(" ", "_")
        result = AnalysisResult(
            engine_version="test-stems",
            track=Track(
                track_id=track_id,
                title=Path(path).stem,
                source_path=path,
            ),
            stem_extraction=_stem_result(track_id),
        )
        bundle = StemBundle(
            channels={
                StemType.vocals: AudioSignal(
                    samples=np.ones(1024, dtype=np.float32),
                    sample_rate=44100,
                    source_path=path,
                )
            },
            result=result.stem_extraction,
        )
        return result, bundle

    artifacts = export_stems_for_paths(
        [str(source_path)],
        EngineConfig(),
        output_root,
        stem_method="demucs",
        vocal_method="auto",
        analyze_fn=analyze_stub,
    )

    assert seen_configs[0].stems.enabled is True
    assert seen_configs[0].stems.method == "demucs"
    assert seen_configs[0].stems.export_stems is True
    assert seen_configs[0].analysis.vocal_method == "auto"
    assert artifacts[0].track_id == "track_one"
    assert artifacts[0].stems_written == ["vocals.wav"]
    assert artifacts[0].stem_source_status == "source_backed"
    assert Path(artifacts[0].artifact_path, "analysis.json").exists()
    assert Path(artifacts[0].artifact_path, "stem_manifest.json").exists()
    assert Path(artifacts[0].artifact_path, "vocals.wav").exists()

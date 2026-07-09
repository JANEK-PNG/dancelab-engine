"""Stem-aware helper tests."""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig
from dancelab.core.models import (
    ArtifactFlag,
    DurationMatchStatus,
    SourceStatus,
    StemChannelSummary,
    StemExtractionResult,
    StemExtractionStatus,
    StemProvenance,
    StemType,
    ValidationStatus,
    WarningLevel,
)
from dancelab.stems.extractor import extract_stems
from dancelab.stems.window_features import build_stem_window_features, stem_energy_ratio_per_frame


def make_summary(source_status: SourceStatus) -> StemExtractionResult:
    return StemExtractionResult(
        source_status=source_status,
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
                source_status=source_status,
                warning_level=WarningLevel.info,
                activity_mean=0.5,
                confidence=0.8,
            )
        ],
        warnings=[],
    )


def test_extract_stems_full_mix_fallback_when_backend_unavailable(monkeypatch):
    config = EngineConfig.model_validate({"stems": {"enabled": True, "method": "auto"}})
    signal = AudioSignal(samples=np.ones(4096, dtype=np.float32), sample_rate=44100)

    monkeypatch.setattr("dancelab.stems.extractor._demucs_available", lambda: False)

    bundle = extract_stems(signal, "track-1", config)

    assert bundle is not None
    assert bundle.channels == {}
    assert bundle.result.source_status == SourceStatus.fallback_full_mix
    assert bundle.result.provenance.model_name == "stem_fallback"
    assert bundle.result.provenance.processing_command is None
    assert bundle.result.provenance.extraction_status == StemExtractionStatus.unavailable


def test_stem_energy_ratio_per_frame_gates_near_silence():
    n = 44100 * 3
    mix = np.ones(n, dtype=np.float32)
    mix[: n // 3] *= 1e-4
    stem = mix.copy()

    ratio = stem_energy_ratio_per_frame(stem, mix, 2048, 512)

    assert ratio[: len(ratio) // 4].max() == 0.0
    assert ratio[len(ratio) // 2 :].mean() > 0.9


def test_build_stem_window_features_skips_fallback_summaries():
    signal = AudioSignal(samples=np.ones(44100 * 2, dtype=np.float32), sample_rate=44100)
    channels = {
        StemType.vocals: AudioSignal(samples=np.ones(44100 * 2, dtype=np.float32), sample_rate=44100)
    }
    summary = make_summary(SourceStatus.fallback_full_mix)

    out = build_stem_window_features(
        track_id="track-1",
        mix_signal=signal,
        channels=channels,
        summary=summary,
        frame_size=2048,
        hop_size=512,
    )

    assert out == []

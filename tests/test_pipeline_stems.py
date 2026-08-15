"""Stem-aware integration tests for analyze_track."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig
from dancelab.core.models import (
    ArtifactFlag,
    BeatGrid,
    DurationMatchStatus,
    FeatureFrame,
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
from dancelab.core.pipeline import analyze_track
from dancelab.stems.extractor import StemBundle


def make_stem_result(
    *,
    track_id: str,
    source_status: SourceStatus,
    extraction_status: StemExtractionStatus,
    warning_level: WarningLevel,
    warnings: list[str] | None = None,
    available_vocals: bool = False,
    fallback_used: bool = False,
) -> StemExtractionResult:
    return StemExtractionResult(
        source_status=source_status,
        warning_level=warning_level,
        validation_status=ValidationStatus.to_validate,
        cannot_claim="candidate only",
        provenance=StemProvenance(
            provenance_id=f"{track_id}-prov",
            model_name="htdemucs" if available_vocals else "stem_fallback",
            model_variant="demucs" if available_vocals else "none",
            input_audio_id=track_id,
            output_stem_ids={StemType.vocals: f"{track_id}:vocals"} if available_vocals else {},
            output_sample_rate=44100,
            duration_match_status=DurationMatchStatus.match,
            extraction_status=extraction_status,
            artifact_flag=ArtifactFlag.none,
            fallback_used=fallback_used,
        ),
        channels=[
            StemChannelSummary(
                stem_type=StemType.vocals,
                stem_id=f"{track_id}:vocals",
                available=available_vocals,
                source_status=source_status if available_vocals else SourceStatus.unavailable,
                warning_level=warning_level if available_vocals else WarningLevel.warning,
                activity_mean=0.25 if available_vocals else None,
                confidence=0.9 if available_vocals else 0.0,
            )
        ],
        warnings=warnings or [],
    )


def test_analyze_track_prefers_source_backed_vocal_stem(monkeypatch):
    config = EngineConfig()
    signal = AudioSignal(
        samples=np.ones(44100 * 2, dtype=np.float32),
        sample_rate=44100,
        source_path="dummy.wav",
    )
    vocal_signal = AudioSignal(
        samples=np.full(44100 * 2, 0.5, dtype=np.float32),
        sample_rate=44100,
        source_path="dummy.wav",
    )
    captured: dict[str, np.ndarray] = {}

    monkeypatch.setattr("dancelab.core.pipeline.load_weights", lambda _: SimpleNamespace(version="w1"))
    monkeypatch.setattr("dancelab.core.pipeline.load_audio", lambda path, cfg: signal)
    monkeypatch.setattr(
        "dancelab.core.pipeline.build_track",
        lambda sig, title=None, artist=None, style_label=None, bpm_estimate=None: Track(track_id="track-1"),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.extract_stems",
        lambda sig, track_id, cfg: StemBundle(
            channels={StemType.vocals: vocal_signal},
            result=make_stem_result(
                track_id=track_id,
                source_status=SourceStatus.source_backed,
                extraction_status=StemExtractionStatus.success,
                warning_level=WarningLevel.info,
                available_vocals=True,
            ),
        ),
    )
    # 14.08: te trzy testy podmieniały `estimate_beatgrid` — nazwę, której
    # pipeline przestał wołać, gdy weszła sztywna siatka. Atrapa nigdy się
    # nie odpalała i liczyła się PRAWDZIWA siatka; testy przechodziły
    # przypadkiem. Podmieniamy to, co kod naprawdę woła.
    monkeypatch.setattr(
        "dancelab.core.pipeline.estimate_beatgrid_best",
        lambda *args, **kwargs: BeatGrid(bpm=128.0, beat_times_sec=[0.0, 0.5, 1.0]),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.estimate_key",
        lambda *args, **kwargs: ("A minor", "8A", 0.8),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.detect_onsets",
        lambda *args, **kwargs: np.array([0.1, 0.4], dtype=np.float64),
    )
    monkeypatch.setattr("dancelab.core.pipeline.segment_track", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "dancelab.core.pipeline.build_stem_window_features",
        lambda **kwargs: [],
    )

    def fake_extract_features(*args, **kwargs):
        captured["vocal_proxy"] = kwargs["vocal_proxy"]
        return [FeatureFrame(track_id="track-1", timestamp_sec=0.0, rms=0.1)]

    def fail_vocal_activity(*args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("vocal_activity fallback should not run when vocals stem exists")

    monkeypatch.setattr("dancelab.core.pipeline.extract_features", fake_extract_features)
    monkeypatch.setattr("dancelab.core.pipeline.vocal_activity", fail_vocal_activity)

    result = analyze_track("dummy.wav", config)

    assert np.allclose(captured["vocal_proxy"], 0.25)
    assert result.stem_extraction is not None
    assert result.stem_extraction.source_status == SourceStatus.source_backed
    assert any("source-separated vocal-energy ratio" in note for note in result.notes)


def test_analyze_track_falls_back_to_hpss_when_stems_unavailable(monkeypatch):
    config = EngineConfig()
    signal = AudioSignal(
        samples=np.ones(44100 * 2, dtype=np.float32),
        sample_rate=44100,
        source_path="dummy.wav",
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr("dancelab.core.pipeline.load_weights", lambda _: SimpleNamespace(version="w1"))
    monkeypatch.setattr("dancelab.core.pipeline.load_audio", lambda path, cfg: signal)
    monkeypatch.setattr(
        "dancelab.core.pipeline.build_track",
        lambda sig, title=None, artist=None, style_label=None, bpm_estimate=None: Track(track_id="track-2"),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.extract_stems",
        lambda sig, track_id, cfg: StemBundle(
            channels={},
            result=make_stem_result(
                track_id=track_id,
                source_status=SourceStatus.fallback_full_mix,
                extraction_status=StemExtractionStatus.unavailable,
                warning_level=WarningLevel.warning,
                warnings=["stem-aware layer unavailable"],
                fallback_used=True,
            ),
        ),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.estimate_beatgrid_best",
        lambda *args, **kwargs: BeatGrid(bpm=128.0, beat_times_sec=[0.0, 0.5, 1.0]),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.estimate_key",
        lambda *args, **kwargs: ("A minor", "8A", 0.8),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.detect_onsets",
        lambda *args, **kwargs: np.array([0.1, 0.4], dtype=np.float64),
    )
    monkeypatch.setattr("dancelab.core.pipeline.segment_track", lambda *args, **kwargs: [])

    def fake_vocal_activity(*args, **kwargs):
        captured["method"] = kwargs["method"]
        return np.array([0.2, 0.3, 0.4], dtype=np.float64)

    def fake_extract_features(*args, **kwargs):
        captured["vocal_proxy"] = kwargs["vocal_proxy"]
        return [FeatureFrame(track_id="track-2", timestamp_sec=0.0, rms=0.1)]

    def fail_build_stem_windows(**kwargs):  # pragma: no cover - defensive
        raise AssertionError("stem windows should not be built without source-backed channels")

    monkeypatch.setattr("dancelab.core.pipeline.vocal_activity", fake_vocal_activity)
    monkeypatch.setattr("dancelab.core.pipeline.extract_features", fake_extract_features)
    monkeypatch.setattr("dancelab.core.pipeline.build_stem_window_features", fail_build_stem_windows)

    result = analyze_track("dummy.wav", config)

    assert captured["method"] == "hpss"
    assert np.allclose(captured["vocal_proxy"], [0.2, 0.3, 0.4])
    assert result.stem_extraction is not None
    assert result.stem_extraction.source_status == SourceStatus.fallback_full_mix
    assert any("HPSS mid-band VAD proxy" in note for note in result.notes)
    assert any("stem-aware layer unavailable" in note for note in result.notes)

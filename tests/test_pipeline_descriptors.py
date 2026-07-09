"""Descriptor enrichment inside analyze_track."""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig, load_weights
from dancelab.core.models import BeatGrid, FeatureFrame, Track
from dancelab.core.pipeline import analyze_track


def test_analyze_track_populates_descriptor_proxies(monkeypatch):
    config = EngineConfig()
    signal = AudioSignal(
        samples=np.ones(44100 * 2, dtype=np.float32),
        sample_rate=44100,
        source_path="dummy.wav",
    )
    weights = load_weights("configs/descriptor_weights.yaml")

    monkeypatch.setattr("dancelab.core.pipeline.load_weights", lambda _: weights)
    monkeypatch.setattr("dancelab.core.pipeline.load_audio", lambda path, cfg: signal)
    monkeypatch.setattr(
        "dancelab.core.pipeline.build_track",
        lambda sig, style_label=None, bpm_estimate=None: Track(track_id="track-descriptors"),
    )
    monkeypatch.setattr("dancelab.core.pipeline.extract_stems", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "dancelab.core.pipeline.estimate_key",
        lambda *args, **kwargs: ("A minor", "8A", 0.9),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.estimate_beatgrid",
        lambda *args, **kwargs: BeatGrid(
            bpm=128.0,
            beat_times_sec=[i * 0.5 for i in range(40)],
            downbeats_sec=[i * 2.0 for i in range(10)],
        ),
    )
    monkeypatch.setattr(
        "dancelab.core.pipeline.detect_onsets",
        lambda *args, **kwargs: np.array([0.02, 0.24, 0.51, 0.77, 1.02, 1.28], dtype=np.float64),
    )
    monkeypatch.setattr("dancelab.core.pipeline.segment_track", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "dancelab.core.pipeline.vocal_activity",
        lambda *args, **kwargs: np.array([0.1, 0.2, 0.1, 0.2], dtype=np.float64),
    )

    def fake_extract_features(*args, **kwargs):
        return [
            FeatureFrame(
                track_id="track-descriptors",
                timestamp_sec=float(t),
                rms=0.3 + 0.03 * t,
                spectral_flux=5.0 + t,
                low_freq_energy_ratio=0.4,
                onset_density=0.4 + 0.05 * (t % 2),
                pulse_clarity_proxy=0.65,
                bass_energy=30.0 + 2.0 * t,
                vocal_density_proxy=0.1 + 0.05 * (t % 2),
            )
            for t in range(4)
        ]

    monkeypatch.setattr("dancelab.core.pipeline.extract_features", fake_extract_features)

    result = analyze_track("dummy.wav", config)

    curve_names = {curve.name for curve in result.descriptor_curves}
    assert {
        "bass_salience",
        "tension",
        "release",
        "groove_density",
        "breakdown_likelihood",
        "drop_likelihood",
    } <= curve_names
    assert all(frame.bass_salience is not None for frame in result.features)
    assert all(frame.syncopation_proxy is not None for frame in result.features)
    assert all(frame.microtiming_proxy is not None for frame in result.features)
    assert all(frame.tension_proxy is not None for frame in result.features)
    assert all(frame.release_proxy is not None for frame in result.features)
    assert any("descriptor proxies computed" in note for note in result.notes)

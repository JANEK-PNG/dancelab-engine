from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dancelab.host.waveform_cache import (
    build_waveform_data,
    load_or_build_waveform,
)


def _write_test_wave(path: Path) -> None:
    sf = pytest.importorskip("soundfile")
    sample_rate = 12_000
    time = np.arange(sample_rate * 2, dtype=np.float64) / sample_rate
    signal = 0.55 * np.sin(2 * np.pi * 90 * time) + 0.2 * np.sin(2 * np.pi * 3200 * time)
    sf.write(path, signal.astype(np.float32), sample_rate)


def test_waveform_cache_builds_truthful_peaks_and_reuses_file(tmp_path):
    source = tmp_path / "tone.wav"
    _write_test_wave(source)

    data = build_waveform_data(source, target_bins=256)
    assert data.duration_sec == pytest.approx(2.0, abs=0.01)
    assert data.bin_count >= 90
    assert data.minimum.shape == data.maximum.shape
    assert data.low.shape == data.minimum.shape
    assert data.mid.shape == data.minimum.shape
    assert data.high.shape == data.minimum.shape
    assert np.min(data.minimum) < -0.5
    assert np.max(data.maximum) > 0.5
    assert np.allclose(data.low + data.mid + data.high, 1.0, atol=1e-5)

    first, cache_path, built_now = load_or_build_waveform(
        source,
        "tone",
        tmp_path / "cache",
        target_bins=256,
    )
    second, same_path, rebuilt = load_or_build_waveform(
        source,
        "tone",
        tmp_path / "cache",
        target_bins=256,
    )
    assert built_now is True
    assert rebuilt is False
    assert same_path == cache_path
    assert second.bin_count == first.bin_count

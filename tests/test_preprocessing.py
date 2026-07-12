"""Beatgrid, onset density and segmentation.

Pure-counting parts (onset_density_at, segment labels) tested without audio;
the librosa-backed detectors are tested on a synthetic click track when the
[audio] extra is installed, else skipped."""

import numpy as np
import pytest

from dancelab.core.audio_types import AudioSignal
from dancelab.core.models import SegmentType
from dancelab.features.onset_density import onset_density_at

librosa = pytest.importorskip("librosa")  # skip file if [audio] not installed
SR = 22050


def click_track(bpm=120.0, duration=20.0, sr=SR):
    """Deterministic click train at a fixed BPM."""
    period = 60.0 / bpm
    times = np.arange(0, duration, period)
    return librosa.clicks(times=times, sr=sr, click_duration=0.05, length=int(duration * sr)), times


# ---------------------------------------------------------------- onset density


def test_onset_density_counts_per_second():
    onsets = np.array([0.0, 0.5, 1.0, 1.5, 2.0])  # 2 onsets/sec
    q = np.array([1.0])
    d = onset_density_at(onsets, q, window_sec=2.0)
    assert d[0] == pytest.approx(2.5)  # 5 onsets in [0,2] window / 2s


def test_onset_density_empty():
    assert onset_density_at(np.array([]), np.array([5.0]), 4.0)[0] == 0.0


def test_onset_density_edges():
    onsets = np.arange(0, 10, 1.0)  # 1/sec
    d = onset_density_at(onsets, np.array([0.0, 5.0, 9.0]), window_sec=4.0)
    assert d[1] == pytest.approx(1.25)  # 5 onsets in [3,7] / 4s


# ------------------------------------------------------------------- beatgrid


def test_beatgrid_recovers_bpm():
    from dancelab.preprocessing.beatgrid import estimate_beatgrid

    y, _ = click_track(bpm=128.0)
    bg = estimate_beatgrid(AudioSignal(samples=y, sample_rate=SR), bpm_hint=128.0)
    assert bg.bpm == pytest.approx(128.0, abs=3.0)
    assert len(bg.beat_times_sec) > 10
    assert len(bg.downbeats_sec) == pytest.approx(len(bg.beat_times_sec) / 4, abs=2)
    assert bg.reliable is True  # real beats tracked


def test_beatgrid_on_silence_is_flagged_unreliable():
    # AUD-M2: silence yields no trackable beats. The bpm stays a positive
    # placeholder (schema requires >0) but reliable=False so downstream never
    # treats the fabricated tempo as a measurement.
    from dancelab.preprocessing.beatgrid import estimate_beatgrid

    y = np.zeros(SR * 5, dtype=np.float32)
    bg = estimate_beatgrid(AudioSignal(samples=y, sample_rate=SR))
    assert bg.reliable is False
    assert bg.bpm > 0


def test_beatgrid_diagnostics_flag_fixed_grid_drift():
    from dancelab.preprocessing.beatgrid import _fixed_grid_diagnostics

    regular = np.arange(0.0, 32.0, 0.5)
    ok = _fixed_grid_diagnostics(regular, 120.0)
    assert ok["reliable"] is True
    assert ok["quality_score"] == pytest.approx(1.0)
    assert "grid_drift" not in ok["diagnostic_flags"]

    drifting = regular + np.linspace(0.0, 0.35, len(regular))
    bad = _fixed_grid_diagnostics(drifting, 120.0)
    assert bad["reliable"] is False
    assert "grid_drift" in bad["diagnostic_flags"]
    assert bad["bpm_mismatch_pct"] > 0.8


def test_beatgrid_deterministic():
    from dancelab.preprocessing.beatgrid import estimate_beatgrid

    y, _ = click_track(bpm=120.0)
    sig = AudioSignal(samples=y, sample_rate=SR)
    assert estimate_beatgrid(sig) == estimate_beatgrid(sig)


# -------------------------------------------------------------------- onsets


def test_detect_onsets_finds_clicks():
    from dancelab.features.onset_density import detect_onsets

    y, true_times = click_track(bpm=120.0, duration=10.0)
    onsets = detect_onsets(y, SR)
    # roughly one onset per click (allow detector slack)
    assert len(true_times) * 0.6 <= len(onsets) <= len(true_times) * 1.5


# ------------------------------------------------------------- segmentation


def test_segment_track_covers_full_duration():
    from dancelab.preprocessing.segmentation import segment_track

    # two-half track: quiet then loud → at least one boundary
    sr = SR
    quiet = 0.02 * np.random.default_rng(0).standard_normal(sr * 15)
    loud = 0.5 * np.random.default_rng(1).standard_normal(sr * 15)
    y = np.concatenate([quiet, loud]).astype(np.float32)
    segs = segment_track(AudioSignal(samples=y, sample_rate=sr), "t1")
    assert segs[0].start_sec == 0.0
    assert segs[-1].end_sec == pytest.approx(len(y) / sr, abs=0.1)
    # contiguous, non-overlapping
    for a, b in zip(segs, segs[1:]):
        assert a.end_sec == pytest.approx(b.start_sec)
    assert segs[0].segment_type == SegmentType.intro
    assert segs[-1].segment_type == SegmentType.outro


def test_segment_short_track_single_segment():
    from dancelab.preprocessing.segmentation import segment_track

    y = (0.1 * np.random.default_rng(2).standard_normal(SR * 5)).astype(np.float32)
    segs = segment_track(AudioSignal(samples=y, sample_rate=SR), "t1")
    assert len(segs) == 1

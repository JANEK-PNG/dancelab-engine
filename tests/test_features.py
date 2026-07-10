"""Implemented low-level and rhythmic features on synthetic ground truth."""

import numpy as np

from dancelab.features.bass import bass_energy
from dancelab.features.microtiming import microtiming_deviations
from dancelab.features.pulse import pulse_clarity
from dancelab.features.rms import frame_signal, rms_energy
from dancelab.features.spectral_flux import (
    low_freq_energy_ratio,
    magnitude_spectrogram,
    spectral_flux,
)

SR = 44100


def sine(freq_hz: float, duration_sec: float = 1.0, amp: float = 1.0) -> np.ndarray:
    t = np.arange(int(SR * duration_sec)) / SR
    return amp * np.sin(2 * np.pi * freq_hz * t)


def test_frame_signal_shape():
    frames = frame_signal(np.zeros(SR), 2048, 512)
    assert frames.shape[1] == 2048
    assert frames.shape[0] == 1 + (SR - 2048) // 512


def test_rms_of_constant_signal():
    x = np.full(SR, 0.5)
    assert np.allclose(rms_energy(x), 0.5)


def test_rms_of_sine_is_amp_over_sqrt2():
    x = sine(440.0, amp=0.8)
    assert np.allclose(rms_energy(x), 0.8 / np.sqrt(2), atol=1e-3)


def test_spectral_flux_zero_for_stationary_signal():
    mag = magnitude_spectrogram(sine(440.0))
    flux = spectral_flux(mag)
    assert flux[0] == 0.0
    # stationary sine -> interior flux ~ 0 relative to spectrum energy
    assert np.median(flux[1:]) < 0.01 * mag.sum(axis=1).mean()


def test_lfer_high_for_bass_low_for_hihat_range():
    bass_mag = magnitude_spectrogram(sine(60.0))
    hi_mag = magnitude_spectrogram(sine(8000.0))
    lfer_bass = low_freq_energy_ratio(bass_mag, SR, 2048)
    lfer_hi = low_freq_energy_ratio(hi_mag, SR, 2048)
    assert lfer_bass.mean() > 0.9
    assert lfer_hi.mean() < 0.1


def test_bass_energy_orders_signals_correctly():
    loud_bass = magnitude_spectrogram(sine(60.0, amp=1.0))
    quiet_bass = magnitude_spectrogram(sine(60.0, amp=0.1))
    assert bass_energy(loud_bass, SR, 2048).mean() > bass_energy(quiet_bass, SR, 2048).mean()


def test_microtiming_deviations_match_nearest_beats():
    deviations = microtiming_deviations(
        np.array([0.02, 0.49, 1.02, 1.51]),
        np.array([0.0, 0.5, 1.0, 1.5]),
    )
    assert deviations.size == 4
    assert np.all(np.abs(deviations) <= 0.02 + 1e-9)


def test_pulse_clarity_is_high_for_beat_locked_novelty():
    rate = 100.0
    novelty = np.zeros(600)
    beat_times = np.arange(0.5, 5.6, 0.5)
    for beat in beat_times:
        novelty[int(round(beat * rate))] = 1.0

    values = pulse_clarity(
        novelty,
        beat_times,
        rate,
        query_times_sec=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    assert np.all(values > 0.2)


def test_pulse_clarity_is_low_for_irregular_novelty():
    rate = 100.0
    novelty = np.zeros(600)
    beat_times = np.arange(0.5, 5.6, 0.5)
    irregular_hits = np.array([0.37, 0.91, 1.66, 2.41, 3.08, 4.27, 5.11])
    for hit in irregular_hits:
        novelty[int(round(hit * rate))] = 1.0

    values = pulse_clarity(
        novelty,
        beat_times,
        rate,
        query_times_sec=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    assert np.all(values < 0.2)


def test_extract_features_on_synthetic_signal(config):
    """60 Hz sine -> high LFER; per-second aggregation; deterministic."""
    from dancelab.core.audio_types import AudioSignal
    from dancelab.features.extract import extract_features

    signal = AudioSignal(samples=sine(60.0, duration_sec=3.0, amp=0.5), sample_rate=SR)
    frames = extract_features(signal, config, "t1")
    assert 2 <= len(frames) <= 3  # ~1 frame per second
    assert all(f.low_freq_energy_ratio > 0.9 for f in frames)
    assert all(abs(f.rms - 0.5 / np.sqrt(2)) < 1e-2 for f in frames)
    # deterministic: second run identical
    assert frames == extract_features(signal, config, "t1")


def test_extract_features_fills_pulse_proxy_when_beatgrid_is_known(config):
    from dancelab.core.audio_types import AudioSignal
    from dancelab.features.extract import extract_features

    duration = 3.0
    samples = np.zeros(int(SR * duration), dtype=np.float64)
    beat_times = np.arange(0.5, duration, 0.5)
    pulse_len = int(0.01 * SR)
    pulse = np.hanning(pulse_len)
    for beat in beat_times:
        start = int(round(beat * SR))
        end = min(len(samples), start + pulse_len)
        samples[start:end] += pulse[: end - start]

    signal = AudioSignal(samples=samples, sample_rate=SR)
    frames = extract_features(signal, config, "t1", beat_times_sec=beat_times)
    assert frames
    assert all(f.pulse_clarity_proxy is not None for f in frames)
    assert max(f.pulse_clarity_proxy for f in frames) > 0.2


def test_extract_features_block_boundary_consistency(config):
    """Flux must be continuous across processing blocks (no boundary spikes)."""
    import dancelab.features.extract as ex
    from dancelab.core.audio_types import AudioSignal

    signal = AudioSignal(samples=sine(440.0, duration_sec=2.0), sample_rate=SR)
    normal = ex.extract_features(signal, config, "t1")
    old = ex.BLOCK_FRAMES
    try:
        ex.BLOCK_FRAMES = 16  # force many tiny blocks
        chunked = ex.extract_features(signal, config, "t1")
    finally:
        ex.BLOCK_FRAMES = old
    assert normal == chunked


def test_microtiming_excludes_offbeat_onsets():
    """AUD-H2: exact off-beat hits are syncopation, not microtiming — they
    must be filtered, not saturate the deviation stats."""
    from dancelab.features.microtiming import microtiming_deviations, microtiming_profile

    beats = np.arange(0.0, 8.0, 0.5)            # 120 BPM grid
    offbeats = beats[:-1] + 0.25                # exact off-beats
    assert microtiming_deviations(offbeats, beats).size == 0

    # off-beat-only material must NOT report maximal microtiming
    prof = microtiming_profile(offbeats, beats, np.array([1.0, 3.0, 5.0]))
    assert float(prof.max()) == 0.0

    # genuine push/drag around the beat (±30 ms) IS kept
    rng = np.random.default_rng(1)
    near = beats + rng.uniform(-0.03, 0.03, size=beats.size)
    devs = microtiming_deviations(near, beats)
    assert devs.size == beats.size
    assert np.all(np.abs(devs) <= 0.075 + 1e-9)

"""Spectral flux + low-frequency energy ratio (Engine Computation Spec §1.2, §1.3).

SF(t)   = sum_k max(0, X_t(k) - X_{t-1}(k))          — half-wave rectified flux
LFER(t) = sum_{f in B_low} P(f,t) / sum_{f in B_all} P(f,t)

Status: stable (standard MIR definitions), pure numpy, deterministic.
"""

from __future__ import annotations

import numpy as np

from dancelab.features.rms import frame_signal


def magnitude_spectrogram(
    x: np.ndarray, frame_size: int = 2048, hop_size: int = 512
) -> np.ndarray:
    """Hann-windowed magnitude spectrogram, shape (n_frames, frame_size//2 + 1)."""
    frames = frame_signal(x, frame_size, hop_size)
    window = np.hanning(frame_size)
    return np.abs(np.fft.rfft(frames * window, axis=1))


def spectral_flux(mag: np.ndarray) -> np.ndarray:
    """Half-wave rectified spectral flux, shape (n_frames,). First frame = 0."""
    if mag.shape[0] == 0:
        return np.zeros(0)
    diff = np.diff(mag, axis=0)
    flux = np.sum(np.maximum(diff, 0.0), axis=1)
    return np.concatenate([[0.0], flux])


def low_freq_energy_ratio(
    mag: np.ndarray,
    sample_rate: int,
    frame_size: int,
    band_hz: tuple[float, float] = (20.0, 150.0),
    eps: float = 1e-12,
) -> np.ndarray:
    """LFER per frame using power spectrum P = |X|^2."""
    power = mag.astype(np.float64) ** 2
    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    low = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    return power[:, low].sum(axis=1) / (power.sum(axis=1) + eps)

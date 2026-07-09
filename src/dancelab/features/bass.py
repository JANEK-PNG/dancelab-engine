"""Bass energy + kick alignment inputs for bass salience (spec §3).

B_energy(t) = sum_{f in B_bass} P(f,t)   — implementable now via spectrogram.
Kick-bass alignment / masking penalty need beatgrid + HPSS → Sprint 1.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.errors import NotImplementedFeature


def bass_energy(
    mag: np.ndarray, sample_rate: int, frame_size: int, band_hz: tuple[float, float] = (20.0, 150.0)
) -> np.ndarray:
    """Absolute bass-band power per frame (spec §3.1). Status: stable."""
    power = mag.astype(np.float64) ** 2
    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    low = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    return power[:, low].sum(axis=1)


def kick_alignment(onset_times_sec: np.ndarray, beat_times_sec: np.ndarray) -> np.ndarray:
    """A_kick_align — kick/bass agreement with beatgrid. Status: planned."""
    raise NotImplementedFeature("kick alignment", status="planned")


def masking_penalty(mag: np.ndarray) -> np.ndarray:
    """C_mask — penalty for spectral masking of the bass region. Status: planned."""
    raise NotImplementedFeature("masking penalty", status="planned")

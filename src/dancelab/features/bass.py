"""Bass-band energy input for bass salience (spec §3).

B_energy(t) = sum_{f in B_bass} P(f,t).
"""

from __future__ import annotations

import numpy as np


def bass_energy(
    mag: np.ndarray, sample_rate: int, frame_size: int, band_hz: tuple[float, float] = (20.0, 150.0)
) -> np.ndarray:
    """Absolute bass-band power per frame (spec §3.1). Status: stable."""
    power = mag.astype(np.float64) ** 2
    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    low = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    return power[:, low].sum(axis=1)

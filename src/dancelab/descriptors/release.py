"""Release (spec §5.2). STATUS: candidate — experimental, ADR-005.

R(t) = max(0, T_eff(t−) − T_eff(t+))  around local tension maxima,
plus event detection: drop / harmonic resolution / rhythmic payoff.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.normalization import robust_01

STATUS = "candidate"


def release_map(tension_eff: np.ndarray, times_sec: np.ndarray) -> np.ndarray:
    tension = np.asarray(tension_eff, dtype=np.float64)
    times = np.asarray(times_sec, dtype=np.float64)
    if tension.ndim != 1 or times.ndim != 1:
        raise ValueError("release_map expects 1-D arrays")
    if len(tension) != len(times):
        raise ValueError("tension and times must have the same length")
    if len(tension) == 0:
        return np.array([], dtype=np.float64)
    if len(tension) == 1:
        return np.zeros(1, dtype=np.float64)

    # AUD-L9: duplicate/non-monotonic timestamps make np.gradient(tension, times)
    # divide by a zero/negative dt → inf/NaN. Callers pass monotonic times, but
    # fall back to unit-spacing gradient rather than silently emitting NaNs.
    if np.all(np.diff(times) > 0):
        gradient = np.gradient(tension, times)
    else:
        gradient = np.gradient(tension)
    drop = np.clip(-gradient, 0.0, None)

    lookahead = np.empty_like(tension)
    lookahead[:-2] = (tension[1:-1] + tension[2:]) / 2.0
    lookahead[-2] = tension[-1]
    lookahead[-1] = tension[-1]
    fall = np.clip(tension - lookahead, 0.0, None)

    peaks = np.zeros_like(tension)
    peaks[1:-1] = (
        (tension[1:-1] >= tension[:-2])
        & (tension[1:-1] > tension[2:])
    ).astype(np.float64)

    raw = (0.55 * fall + 0.45 * drop) * (0.7 + 0.3 * peaks)
    if np.allclose(raw, raw[0]):
        return np.clip(raw, 0.0, 1.0)
    return np.clip(robust_01(raw), 0.0, 1.0)

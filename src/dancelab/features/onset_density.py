"""Onset detection + onset density (Engine Computation Spec §2.1). STATUS: stable baseline.

D_onset(t) = N_onset(t, Δ) / Δ   — onsets per second in a window of length Δ.

Baseline onset detection: librosa.onset.onset_detect on the spectral-flux
novelty curve. Density is a centered sliding-window count → onsets/sec.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.errors import MissingDependencyError


def detect_onsets(x: np.ndarray, sample_rate: int, hop_size: int = 512) -> np.ndarray:
    """Onset times in seconds (deterministic for a fixed signal)."""
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "librosa is required for onset detection. Install: pip install 'dancelab-engine[audio]'"
        ) from exc

    x = np.asarray(x, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0)
    return librosa.onset.onset_detect(
        y=x, sr=sample_rate, hop_length=hop_size, units="time", backtrack=False
    )


def onset_density_at(
    onset_times_sec: np.ndarray, query_times_sec: np.ndarray, window_sec: float
) -> np.ndarray:
    """Onsets/sec in a centered window of length window_sec around each query time.

    Pure counting — no audio needed, so it is unit-testable in isolation.
    """
    onsets = np.sort(np.asarray(onset_times_sec, dtype=np.float64))
    half = window_sec / 2.0
    lo = np.searchsorted(onsets, query_times_sec - half, side="left")
    hi = np.searchsorted(onsets, query_times_sec + half, side="right")
    return (hi - lo) / window_sec

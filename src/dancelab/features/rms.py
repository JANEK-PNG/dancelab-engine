"""RMS energy (Engine Computation Specification §1.1). Status: stable.

RMS(t) = sqrt( (1/N) * sum_n x_n^2 )  per short window.
"""

from __future__ import annotations

import numpy as np


def frame_signal(x: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    """Slice a mono signal into overlapping frames, shape (n_frames, frame_size)."""
    if x.ndim != 1:
        raise ValueError("frame_signal expects a mono signal, shape (n,)")
    if len(x) < frame_size:
        return np.empty((0, frame_size), dtype=x.dtype)
    n_frames = 1 + (len(x) - frame_size) // hop_size
    idx = np.arange(frame_size)[None, :] + hop_size * np.arange(n_frames)[:, None]
    return x[idx]


def rms_energy(x: np.ndarray, frame_size: int = 2048, hop_size: int = 512) -> np.ndarray:
    """Frame-level RMS, shape (n_frames,)."""
    frames = frame_signal(x, frame_size, hop_size)
    return np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))


def frame_times(n_frames: int, hop_size: int, sample_rate: int, frame_size: int) -> np.ndarray:
    """Center time (sec) of each frame."""
    return (np.arange(n_frames) * hop_size + frame_size / 2) / sample_rate

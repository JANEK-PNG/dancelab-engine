"""Shared descriptor normalization helpers."""

from __future__ import annotations

import numpy as np

from dancelab.core.normalization import robust_01


def prepare_curve(values: np.ndarray, *, keep_constant: float | None = None) -> np.ndarray:
    """Normalize one descriptor cue to [0,1] without inventing shape."""
    curve = np.asarray(values, dtype=np.float64)
    if curve.ndim != 1:
        raise ValueError("descriptor cues must be 1-D arrays")
    if curve.size == 0:
        return curve
    if np.isnan(curve).any():
        raise ValueError("descriptor cues must not contain NaN")
    if curve.min() >= 0.0 and curve.max() <= 1.0:
        return np.clip(curve, 0.0, 1.0)
    out = robust_01(curve)
    if keep_constant is not None and np.allclose(curve, curve[0]):
        out[:] = keep_constant
    return out


def validate_same_length(*arrays: np.ndarray) -> None:
    lengths = {len(np.asarray(array)) for array in arrays}
    if len(lengths) > 1:
        raise ValueError("descriptor cue arrays must have the same length")

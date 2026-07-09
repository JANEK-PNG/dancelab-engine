"""Normalization Protocol v0.1 (Sprint 3).

Two comparable-scale conversions used across descriptors:

    Norm_0_100(z)       = 100 · (z − z_min) / (z_max − z_min + ε)
    RobustNorm_0_100(z) = 100 · (z − P5)   / (P95 − P5   + ε)   (outlier-safe)

Both return [0, 1] via the 0..1 variants (engine works in [0,1] internally;
the 0..100 variants exist for spec parity / reporting). Constant input maps to
0.5 (neutral) — never NaN (deterministic, ADR-005).
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def minmax_01(z: np.ndarray) -> np.ndarray:
    """Min-max to [0,1]. Constant input → 0.5."""
    z = np.asarray(z, dtype=np.float64)
    lo, hi = float(z.min()), float(z.max())
    if hi - lo < _EPS:
        return np.full_like(z, 0.5)
    return (z - lo) / (hi - lo)


def robust_01(z: np.ndarray, low_pct: float = 5.0, high_pct: float = 95.0) -> np.ndarray:
    """Robust percentile (P5–P95) to [0,1], clipped. Outlier-safe. Constant → 0.5."""
    z = np.asarray(z, dtype=np.float64)
    lo, hi = np.percentile(z, low_pct), np.percentile(z, high_pct)
    if hi - lo < _EPS:
        return np.full_like(z, 0.5)
    return np.clip((z - lo) / (hi - lo), 0.0, 1.0)


def norm_0_100(z: np.ndarray) -> np.ndarray:
    return 100.0 * minmax_01(z)


def robust_norm_0_100(z: np.ndarray) -> np.ndarray:
    return 100.0 * robust_01(z)

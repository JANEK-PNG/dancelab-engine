"""Shared tempo primitives for the decision layer.

AUD-M8: the half/double-time BPM logic was copy-pasted across set_builder,
next_track and rules. A single source keeps the octave-folding convention
identical everywhere — a subtle divergence (e.g. one module forgetting
half-time) would silently skew mixability, next-track and set-ordering scores
against each other.
"""

from __future__ import annotations

import numpy as np

# ×1 direct, ×2 double-time, ÷2 half-time — the tempos a DJ can beatmatch.
BPM_OCTAVE_FACTORS: tuple[float, ...] = (1.0, 2.0, 0.5)


def bpm_octave_variants(bpm: float) -> tuple[float, ...]:
    """The direct/double/half-time tempos of ``bpm``."""
    return tuple(bpm * factor for factor in BPM_OCTAVE_FACTORS)


def nearest_bpm_variant(reference_bpm: float | None, candidate_bpm: float | None) -> float | None:
    """The octave variant of ``candidate_bpm`` closest to ``reference_bpm``."""
    if not reference_bpm or not candidate_bpm:
        return None
    return float(min(bpm_octave_variants(candidate_bpm), key=lambda v: abs(reference_bpm - v)))


def min_relative_bpm_distance(bpm_a: float | None, bpm_b: float | None) -> float | None:
    """Smallest |bpm_a - variant(bpm_b)| / bpm_a across octave variants, or None."""
    if not bpm_a or not bpm_b:
        return None
    return float(min(abs(bpm_a - v) / bpm_a for v in bpm_octave_variants(bpm_b)))


def tempo_proximity_score(
    bpm_a: float | None,
    bpm_b: float | None,
    tolerance_pct: float = 0.06,
) -> float:
    """1.0 at equal BPM → 0 beyond 2×tolerance, half/double-time aware.

    Returns the neutral 0.5 when either tempo is unknown.
    """
    distance = min_relative_bpm_distance(bpm_a, bpm_b)
    if distance is None:
        return 0.5
    return float(np.clip(1.0 - distance / (2.0 * tolerance_pct), 0.0, 1.0))

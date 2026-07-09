"""Bass Salience (spec §3.2). STATUS: candidate — experimental, ADR-005.

B_sal(t) = a1*~B_energy(t) + a2*A_kick_align(t) + a3*C_rhythm(t) − a4*C_mask(t)

Bass salience ≠ bass quantity: it rewards normalized bass energy, kick-bass
alignment and rhythmic readability, and penalizes masking.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.config import WeightGroup
from dancelab.descriptors._shared import prepare_curve, validate_same_length

STATUS = "candidate"


def bass_salience(
    bass_energy_norm: np.ndarray,
    kick_alignment: np.ndarray,
    rhythm_clarity: np.ndarray,
    masking_penalty: np.ndarray,
    weights: WeightGroup,
) -> np.ndarray:
    validate_same_length(
        bass_energy_norm,
        kick_alignment,
        rhythm_clarity,
        masking_penalty,
    )
    bass_curve = prepare_curve(bass_energy_norm, keep_constant=0.5)
    kick_curve = prepare_curve(kick_alignment, keep_constant=0.5)
    rhythm_curve = prepare_curve(rhythm_clarity, keep_constant=0.5)
    mask_curve = prepare_curve(masking_penalty, keep_constant=0.5)

    w = weights.weights
    score = (
        w.get("bass_energy_norm", 0.0) * bass_curve
        + w.get("kick_alignment", 0.0) * kick_curve
        + w.get("rhythm_clarity", 0.0) * rhythm_curve
        - w.get("masking_penalty", 0.0) * mask_curve
    )
    return np.clip(score, 0.0, 1.0)

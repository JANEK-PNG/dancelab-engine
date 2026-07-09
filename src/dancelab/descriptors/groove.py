"""Groove Density (spec §2.4). STATUS: candidate — experimental, ADR-005.

G_audio(t) = w1*C_pulse(t) + w2*S_sync(t) + w3*D_onset(t) + w4*B_sal(t) + w5*M_micro(t)
G_eff(t|s,c) = G_audio(t|s) * C_fit(t|c)

Weights come from configs/descriptor_weights.yaml (groove_density).
Inputs must be normalized to comparable ranges before weighting — normalization
strategy is an open Sprint 1 decision (see docs/assumptions.md).
"""

from __future__ import annotations

import numpy as np

from dancelab.core.config import WeightGroup
from dancelab.descriptors._shared import prepare_curve, validate_same_length

STATUS = "candidate"


def groove_density(
    pulse_clarity: np.ndarray,
    syncopation: np.ndarray,
    onset_density: np.ndarray,
    bass_salience: np.ndarray,
    microtiming: np.ndarray,
    weights: WeightGroup,
) -> np.ndarray:
    validate_same_length(
        pulse_clarity,
        syncopation,
        onset_density,
        bass_salience,
        microtiming,
    )
    pulse_curve = prepare_curve(pulse_clarity, keep_constant=0.5)
    sync_curve = prepare_curve(syncopation, keep_constant=0.0)
    onset_curve = prepare_curve(onset_density, keep_constant=0.5)
    bass_curve = prepare_curve(bass_salience, keep_constant=0.5)
    micro_curve = prepare_curve(microtiming, keep_constant=0.0)

    # Moderate microtiming tends to read as groove; too rigid or too loose
    # both flatten the feel. This keeps the cue candidate and interpretable.
    micro_sweet_spot = np.clip(1.0 - np.abs(micro_curve - 0.25) / 0.75, 0.0, 1.0)

    w = weights.weights
    score = (
        w.get("pulse_clarity", 0.0) * pulse_curve
        + w.get("syncopation", 0.0) * sync_curve
        + w.get("onset_density", 0.0) * onset_curve
        + w.get("bass_salience", 0.0) * bass_curve
        + w.get("microtiming", 0.0) * micro_sweet_spot
    )
    return np.clip(score, 0.0, 1.0)

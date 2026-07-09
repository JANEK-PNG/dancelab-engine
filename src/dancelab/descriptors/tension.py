"""Tension (spec §5.1). STATUS: candidate — experimental, ADR-005.

T_audio(t) = b1*Z_rise + b2*Z_delay + b3*Z_spectral + b4*Z_instability + b5*Z_expect
T_eff(t|s,c) = T_audio(t|s) * C_fit(t|c)

Z_* are z-scored tension cues: energy rise, delayed resolution, spectral
brightness/rolloff shifts, rhythmic instability, expectation violation.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.config import WeightGroup
from dancelab.descriptors._shared import prepare_curve, validate_same_length

STATUS = "candidate"


def tension_curve(cues: dict[str, np.ndarray], weights: WeightGroup) -> np.ndarray:
    required = ("rise", "delay", "spectral", "instability", "expectation")
    missing = [name for name in required if name not in cues]
    if missing:
        raise ValueError(f"missing tension cues: {', '.join(missing)}")

    cue_arrays = [np.asarray(cues[name], dtype=np.float64) for name in required]
    validate_same_length(*cue_arrays)

    normalized = {
        name: prepare_curve(cues[name], keep_constant=0.5)
        for name in required
    }
    w = weights.weights
    score = sum(w.get(name, 0.0) * normalized[name] for name in required)
    return np.clip(score, 0.0, 1.0)

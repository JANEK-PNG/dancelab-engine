"""Quality heuristics for the optional stem-aware preprocessing layer.

These heuristics are intentionally lightweight and conservative. They are not a
replacement for a DJ validation pilot; they only decide whether it is safe to
surface candidate stem-aware signals or whether the pipeline should fall back to
full-mix descriptors.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.models import ArtifactFlag

_SEVERITY = {
    ArtifactFlag.none: 0,
    ArtifactFlag.mild: 1,
    ArtifactFlag.clear: 2,
    ArtifactFlag.severe: 3,
}


def energy_share(stem: np.ndarray, mix: np.ndarray) -> float:
    """Mean stem energy as a fraction of mean full-mix energy."""
    stem_arr = np.asarray(stem, dtype=np.float64)
    mix_arr = np.asarray(mix, dtype=np.float64)
    if stem_arr.ndim > 1:
        stem_arr = stem_arr.mean(axis=0)
    if mix_arr.ndim > 1:
        mix_arr = mix_arr.mean(axis=0)
    n = min(len(stem_arr), len(mix_arr))
    if n == 0:
        return 0.0
    stem_energy = float(np.mean(stem_arr[:n] ** 2))
    mix_energy = float(np.mean(mix_arr[:n] ** 2))
    return float(np.clip(stem_energy / max(mix_energy, 1e-9), 0.0, 2.0))


def artifact_flag_from_residual(residual: float) -> ArtifactFlag:
    """Translate energy-balance residual into a conservative artifact flag."""
    if residual < 0.15:
        return ArtifactFlag.none
    if residual < 0.35:
        return ArtifactFlag.mild
    if residual < 0.65:
        return ArtifactFlag.clear
    return ArtifactFlag.severe


def confidence_from_energy_shares(shares: dict[object, float], expected_stems: int = 4) -> float:
    """Simple confidence proxy from stem coverage and energy-balance residual."""
    if not shares:
        return 0.0
    coverage = min(len(shares) / float(expected_stems), 1.0)
    residual = min(abs(sum(max(v, 0.0) for v in shares.values()) - 1.0), 1.0)
    return float(np.clip(coverage * (1.0 - residual), 0.0, 1.0))


def severity(flag: ArtifactFlag | str) -> int:
    return _SEVERITY[ArtifactFlag(flag)]


def should_fallback(
    *,
    confidence: float,
    artifact_flag: ArtifactFlag,
    confidence_threshold: float,
    max_artifact_flag: ArtifactFlag | str,
    available_stems: int,
    min_required_stems: int,
) -> bool:
    """Whether stem-aware outputs should be suppressed in favor of full-mix fallback."""
    if available_stems < min_required_stems:
        return True
    if confidence < confidence_threshold:
        return True
    return severity(artifact_flag) > severity(max_artifact_flag)

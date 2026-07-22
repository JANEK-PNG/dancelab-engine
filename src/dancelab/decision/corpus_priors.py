"""Corpus-measured transition priors — likelihood-ratio lifts from real DJs.

Source: data/reports/corpus_priors/priors_v1.json, measured by
scripts/corpus_priors.py from 6,144 aligned real-DJ transitions against a
within-mix chance baseline. Each lift answers: how much MORE (or less) likely
are real DJs to make this kind of transition than chance would?

Honest scope (ADR-005):
- lifts MODULATE the engine's transition score multiplicatively; they never
  fabricate a score where components are missing;
- when the priors file or an input (bpm/key) is unavailable the lift is a
  neutral 1.0 with a note — no guessing;
- the blend exponent lives in DescriptorWeights.corpus_priors_weight
  (0 = off, 1 = full measured strength), so the choice is explicit and
  versioned with the weights file, not hidden in code.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dancelab.decision._common import nearest_bpm_variant

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PRIORS_PATH = _REPO_ROOT / "data/reports/corpus_priors/priors_v1.json"
ENV_OVERRIDE = "DANCELAB_CORPUS_PRIORS"

# keep the sane range of the measured lifts; a corrupt file must not explode scores
LIFT_CLAMP = (0.4, 2.0)

_BPM_BUCKETS = ("0-2%", "2-4%", "4-6%", "6-10%", ">10%")


def _priors_path() -> Path:
    override = os.environ.get(ENV_OVERRIDE)
    return Path(override) if override else DEFAULT_PRIORS_PATH


@lru_cache(maxsize=4)
def _load(path_str: str) -> dict | None:
    """Parsed lift tables or None when unavailable (graceful, honest)."""
    path = Path(path_str)
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        rel_real = payload["camelot_relation_pct"]["real_djs"]
        rel_chance = payload["camelot_relation_pct"]["chance_baseline"]
        bpm_real = payload["bpm_delta_folded_pct"]["real_djs"]
        bpm_chance = payload["bpm_delta_folded_pct"]["chance_baseline"]
    except (KeyError, TypeError):
        return None

    def ratio(real: dict, chance: dict) -> dict[str, float]:
        keys = set(real) | set(chance)
        return {
            k: max(LIFT_CLAMP[0], min(LIFT_CLAMP[1],
                   float(real.get(k, 0.1)) / max(float(chance.get(k, 0.1)), 0.1)))
            for k in keys
        }

    return {"harmonic": ratio(rel_real, rel_chance), "bpm": ratio(bpm_real, bpm_chance)}


def priors_available() -> bool:
    return _load(str(_priors_path())) is not None


def bpm_delta_bucket(bpm_a: float, bpm_b: float) -> str:
    """Octave-folded BPM delta bucket — same vocabulary as the measurement."""
    folded = nearest_bpm_variant(bpm_a, bpm_b)
    delta_pct = abs(folded - bpm_a) / bpm_a * 100
    if delta_pct < 2:
        return "0-2%"
    if delta_pct < 4:
        return "2-4%"
    if delta_pct < 6:
        return "4-6%"
    if delta_pct < 10:
        return "6-10%"
    return ">10%"


def transition_prior_lift(
    harmonic_relation: str | None,
    bpm_a: float | None,
    bpm_b: float | None,
) -> tuple[float, list[str]]:
    """Multiplicative lift for one A→B transition + honest reasoning notes.

    Missing priors file or missing inputs → neutral 1.0 (never a guess).
    """
    tables = _load(str(_priors_path()))
    if tables is None:
        return 1.0, ["corpus priors unavailable — neutral"]

    lift = 1.0
    notes: list[str] = []
    if bpm_a and bpm_b and bpm_a > 0:
        bucket = bpm_delta_bucket(bpm_a, bpm_b)
        factor = tables["bpm"].get(bucket)
        if factor is not None:
            lift *= factor
            notes.append(f"corpus bpm prior {bucket}: x{factor:.2f}")
    if harmonic_relation:
        factor = tables["harmonic"].get(harmonic_relation)
        if factor is not None:
            lift *= factor
            notes.append(f"corpus harmonic prior {harmonic_relation}: x{factor:.2f}")
    lift = max(LIFT_CLAMP[0], min(LIFT_CLAMP[1], lift))
    if not notes:
        notes.append("corpus priors: no usable inputs — neutral")
    return float(lift), notes

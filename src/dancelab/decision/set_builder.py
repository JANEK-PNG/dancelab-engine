"""Set Builder v0.1 — order a library of analyzed tracks into a DJ set.

Greedy harmonic/energy chain: start from an opener, then at each step pick the
unplayed track that maximizes a transition score combining
- **harmonic** compatibility on the Camelot wheel (same / adjacent ±1 / relative
  major-minor = good; else dissonant),
- **BPM** proximity (half/double-time aware),
- **energy arc** (default "build": gentle rise; also "flat", "peak"),
- **mixability** (the pairwise engine — tempo/bass/vocal/style/context).

STATUS: candidate — a heuristic ordering, not a proven optimal set. Harmonic
rules are standard DJ practice; the weighting and arc model are DanceLab
inference to be validated against DJ-built sets. cannot_claim: this is the best
possible set order, or that it will work live.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.config import DescriptorWeights
from dancelab.core.models import (
    AnalysisResult,
    MixabilityInput,
    SetPlan,
    SetTransition,
)
from dancelab.core.provenance import provenance_for
from dancelab.decision.harmonic import harmonic_compatibility, harmonic_relation, parse_camelot
from dancelab.decision.mixability import compute_mixability

MODEL_VERSION = "set_builder_v0.1"

__all__ = ["build_set", "transition_score", "bpm_score", "track_energy",
           "harmonic_relation", "parse_camelot", "MODEL_VERSION"]


def bpm_score(bpm_a: float | None, bpm_b: float | None, tolerance_pct: float = 0.06) -> float:
    """1.0 at equal BPM → 0 beyond 2×tolerance, half/double-time aware."""
    if not bpm_a or not bpm_b:
        return 0.5
    ratios = (bpm_b, bpm_b * 2.0, bpm_b / 2.0)
    best = min(abs(bpm_a - r) / bpm_a for r in ratios)
    return float(np.clip(1.0 - best / (2 * tolerance_pct), 0.0, 1.0))


def track_energy(analysis: AnalysisResult) -> float:
    """Mean RMS as a coarse energy proxy."""
    vals = [f.rms for f in analysis.features if f.rms is not None]
    return float(np.mean(vals)) if vals else 0.0


def _energy_score(delta: float, arc: str) -> float:
    """Reward energy change appropriate to the set arc."""
    if arc == "build":              # gentle rise preferred; punish big drops
        return float(np.clip(0.6 + 4.0 * delta, 0.0, 1.0)) if delta >= -0.02 else \
            float(np.clip(0.6 + 8.0 * delta, 0.0, 1.0))
    if arc == "peak":               # keep energy high/flat
        return float(np.clip(1.0 - 6.0 * abs(delta), 0.0, 1.0))
    return float(np.clip(1.0 - 5.0 * abs(delta), 0.0, 1.0))  # "flat": small changes


def transition_score(
    a: AnalysisResult,
    b: AnalysisResult,
    weights: DescriptorWeights,
    arc: str,
    energy_a: float,
    energy_b: float,
    energy_range: float,
) -> tuple[float, str, list[str]]:
    """Combined A→B transition score in [0,1] + harmonic relation + reasoning."""
    harm = harmonic_compatibility(
        a.track.key_estimate, b.track.key_estimate,
        a.track.key_confidence, b.track.key_confidence,
    )
    rel = harm.harmonic_relation
    h = harm.harmonic_compatibility_score
    bp = bpm_score(a.track.bpm_estimate, b.track.bpm_estimate)
    d_energy = (energy_b - energy_a) / (energy_range + 1e-9)
    en = _energy_score(d_energy, arc)
    mix = compute_mixability(
        MixabilityInput(track_a=a, track_b=b), weights.mixability, weights.mixability_conflict
    ).mixability_score

    w = weights.set_builder.weights
    score = w["harmonic"] * h + w["bpm"] * bp + w["energy"] * en + w["mixability"] * mix
    reasoning = [
        f"harmonic {rel} ({a.track.key_estimate}->{b.track.key_estimate}) score {h:.2f}",
        f"bpm {a.track.bpm_estimate}->{b.track.bpm_estimate} score {bp:.2f}",
        f"energy Δ {d_energy:+.2f} ({arc}) score {en:.2f}",
        f"mixability {mix:.2f}",
    ]
    return float(score), rel, reasoning


def build_set(
    analyses: list[AnalysisResult],
    weights: DescriptorWeights,
    arc: str = "build",
    start_track_id: str | None = None,
) -> SetPlan:
    """Greedy harmonic/energy set ordering. Deterministic for fixed input order."""
    provenance = provenance_for("set_builder")
    if len(analyses) < 2:
        return SetPlan(
            track_order=[a.track.track_id for a in analyses],
            arc=arc, model_version=MODEL_VERSION, provenance=provenance,
            warnings=["need >=2 tracks to build a set"],
        )

    by_id = {a.track.track_id: a for a in analyses}
    energy = {tid: track_energy(a) for tid, a in by_id.items()}
    e_range = max(energy.values()) - min(energy.values()) or 1.0

    # opener: user pick, else lowest-energy track (typical warm-up start)
    if start_track_id and start_track_id in by_id:
        current = start_track_id
    else:
        current = min(energy, key=energy.get)

    order = [current]
    remaining = set(by_id) - {current}
    transitions: list[SetTransition] = []

    while remaining:
        a = by_id[current]
        best_id, best_score, best_rel, best_reason = None, -1.0, "", []
        for cand in remaining:
            b = by_id[cand]
            score, rel, reason = transition_score(
                a, b, weights, arc, energy[current], energy[cand], e_range
            )
            if score > best_score:
                best_id, best_score, best_rel, best_reason = cand, score, rel, reason

        b = by_id[best_id]
        d_bpm = None
        if a.track.bpm_estimate and b.track.bpm_estimate:
            d_bpm = round((b.track.bpm_estimate - a.track.bpm_estimate) / a.track.bpm_estimate * 100, 1)
        warns = []
        if best_rel == "risky":
            warns.append("risky key change — consider an echo-out / effect transition")
        transitions.append(SetTransition(
            from_track_id=current, to_track_id=best_id,
            transition_score=round(best_score, 4), harmonic_relation=best_rel,
            key_from=a.track.key_estimate, key_to=b.track.key_estimate,
            bpm_from=a.track.bpm_estimate, bpm_to=b.track.bpm_estimate, bpm_delta_pct=d_bpm,
            energy_delta=round(energy[best_id] - energy[current], 4),
            reasoning=best_reason, warnings=warns,
        ))
        order.append(best_id)
        remaining.remove(best_id)
        current = best_id

    mean_score = round(float(np.mean([t.transition_score for t in transitions])), 4)
    return SetPlan(
        track_order=order, transitions=transitions, arc=arc,
        mean_transition_score=mean_score, model_version=MODEL_VERSION,
        provenance=provenance,
    )

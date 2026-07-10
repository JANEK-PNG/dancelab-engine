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

from collections.abc import Mapping, Sequence

import numpy as np

from dancelab.core.config import DescriptorWeights
from dancelab.core.models import (
    AnalysisResult,
    MixabilityInput,
    SetPlan,
    SetTransition,
)
from dancelab.core.provenance import provenance_for
from dancelab.decision._common import tempo_proximity_score
from dancelab.decision.harmonic import harmonic_compatibility, harmonic_relation, parse_camelot
from dancelab.decision.mixability import compute_mixability

MODEL_VERSION = "set_builder_v0.1"

__all__ = ["build_set", "transition_score", "bpm_score", "track_energy",
           "harmonic_relation", "parse_camelot", "MODEL_VERSION"]


def bpm_score(bpm_a: float | None, bpm_b: float | None, tolerance_pct: float = 0.06) -> float:
    """1.0 at equal BPM → 0 beyond 2×tolerance, half/double-time aware."""
    return tempo_proximity_score(bpm_a, bpm_b, tolerance_pct)


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


def _normalize_locked_positions(
    locked_positions: Mapping[int | str, str] | None,
) -> dict[int, str]:
    normalized: dict[int, str] = {}
    for raw_position, raw_track_id in (locked_positions or {}).items():
        try:
            position = int(raw_position)
        except (TypeError, ValueError) as exc:
            raise ValueError("locked_positions keys must be 1-based integer positions") from exc
        track_id = str(raw_track_id).strip()
        if not track_id:
            raise ValueError("locked_positions values must be non-empty track IDs")
        normalized[position] = track_id
    return normalized


def _normalize_pinned_track_ids(pinned_track_ids: Sequence[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw_track_id in pinned_track_ids or []:
        track_id = str(raw_track_id).strip()
        if track_id and track_id not in seen:
            normalized.append(track_id)
            seen.add(track_id)
    return normalized


def _validate_build_constraints(
    by_id: dict[str, AnalysisResult],
    *,
    target_track_count: int | None,
    locked_positions: dict[int, str],
    pinned_track_ids: list[str],
    start_track_id: str | None,
) -> tuple[int, list[str]]:
    target_count = target_track_count or len(by_id)
    if target_count < 1:
        raise ValueError("target_track_count must be >= 1")
    if target_count > len(by_id):
        raise ValueError("target_track_count cannot exceed the number of available tracks")

    warnings: list[str] = []
    unknown_locked = sorted(set(locked_positions.values()) - set(by_id))
    if unknown_locked:
        raise ValueError(f"locked_positions reference unknown tracks: {', '.join(unknown_locked)}")
    unknown_pinned = sorted(set(pinned_track_ids) - set(by_id))
    if unknown_pinned:
        raise ValueError(f"pinned_track_ids reference unknown tracks: {', '.join(unknown_pinned)}")

    invalid_positions = sorted(position for position in locked_positions if position < 1 or position > target_count)
    if invalid_positions:
        raise ValueError(
            "locked_positions must be within the final 1-based set length: "
            + ", ".join(str(position) for position in invalid_positions)
        )

    locked_track_ids = list(locked_positions.values())
    duplicate_locked_ids = sorted({track_id for track_id in locked_track_ids if locked_track_ids.count(track_id) > 1})
    if duplicate_locked_ids:
        raise ValueError(
            "a track cannot be locked to multiple positions: " + ", ".join(duplicate_locked_ids)
        )

    required_ids = set(locked_track_ids) | set(pinned_track_ids)
    if len(required_ids) > target_count:
        raise ValueError("locked/pinned tracks exceed target_track_count")

    if start_track_id and start_track_id not in by_id:
        warnings.append(f"start_track_id `{start_track_id}` is unknown and was ignored")
    elif start_track_id and locked_positions.get(1) and locked_positions[1] != start_track_id:
        warnings.append("start_track_id ignored because locked position 1 defines the opener")
    elif start_track_id and start_track_id in locked_track_ids and locked_positions.get(1) != start_track_id:
        warnings.append("start_track_id is locked to a later position, so opener was chosen by constraints")

    return target_count, warnings


def _best_successor(
    current: str,
    candidates: list[str],
    *,
    by_id: dict[str, AnalysisResult],
    weights: DescriptorWeights,
    arc: str,
    energy: dict[str, float],
    energy_range: float,
) -> str:
    best_id, best_score = candidates[0], -1.0
    for candidate in candidates:
        score, _, _ = transition_score(
            by_id[current],
            by_id[candidate],
            weights,
            arc,
            energy[current],
            energy[candidate],
            energy_range,
        )
        if score > best_score:
            best_id, best_score = candidate, score
    return best_id


def _build_transition(
    from_track_id: str,
    to_track_id: str,
    *,
    by_id: dict[str, AnalysisResult],
    weights: DescriptorWeights,
    arc: str,
    energy: dict[str, float],
    energy_range: float,
) -> SetTransition:
    a = by_id[from_track_id]
    b = by_id[to_track_id]
    score, rel, reason = transition_score(
        a, b, weights, arc, energy[from_track_id], energy[to_track_id], energy_range
    )
    d_bpm = None
    if a.track.bpm_estimate and b.track.bpm_estimate:
        d_bpm = round((b.track.bpm_estimate - a.track.bpm_estimate) / a.track.bpm_estimate * 100, 1)
    warnings = []
    if rel == "risky":
        warnings.append("risky key change — consider an echo-out / effect transition")
    return SetTransition(
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        transition_score=round(score, 4),
        harmonic_relation=rel,
        key_from=a.track.key_estimate,
        key_to=b.track.key_estimate,
        bpm_from=a.track.bpm_estimate,
        bpm_to=b.track.bpm_estimate,
        bpm_delta_pct=d_bpm,
        energy_delta=round(energy[to_track_id] - energy[from_track_id], 4),
        reasoning=reason,
        warnings=warnings,
    )


def _constrained_order(
    by_id: dict[str, AnalysisResult],
    *,
    weights: DescriptorWeights,
    arc: str,
    start_track_id: str | None,
    target_count: int,
    locked_positions: dict[int, str],
    pinned_track_ids: list[str],
    energy: dict[str, float],
    energy_range: float,
) -> list[str]:
    locked_slots = {position - 1: track_id for position, track_id in locked_positions.items()}
    locked_track_ids = set(locked_positions.values())
    remaining = set(by_id) - locked_track_ids
    order: list[str] = []
    current: str | None = None

    for index in range(target_count):
        if index in locked_slots:
            chosen = locked_slots[index]
        else:
            open_slots = sum(1 for slot in range(index, target_count) if slot not in locked_slots)
            remaining_pinned = [track_id for track_id in pinned_track_ids if track_id in remaining]
            candidates = sorted(remaining_pinned if len(remaining_pinned) >= open_slots else remaining)
            if not candidates:
                raise ValueError("constraints left no candidate track for an unlocked position")
            if current is None:
                chosen = start_track_id if start_track_id in candidates else min(candidates, key=lambda tid: (energy[tid], tid))
            else:
                chosen = _best_successor(
                    current,
                    candidates,
                    by_id=by_id,
                    weights=weights,
                    arc=arc,
                    energy=energy,
                    energy_range=energy_range,
                )
            remaining.remove(chosen)

        order.append(chosen)
        current = chosen

    return order


def build_set(
    analyses: list[AnalysisResult],
    weights: DescriptorWeights,
    arc: str = "build",
    start_track_id: str | None = None,
    target_track_count: int | None = None,
    locked_positions: Mapping[int | str, str] | None = None,
    pinned_track_ids: Sequence[str] | None = None,
) -> SetPlan:
    """Greedy harmonic/energy set ordering with optional lock/pin constraints.

    `locked_positions` uses 1-based final playlist slots. Pinned tracks must
    appear somewhere in the final plan; `target_track_count` lets the planner
    choose a constrained subset from a larger candidate pool.
    """
    provenance = provenance_for("set_builder")
    locked = _normalize_locked_positions(locked_positions)
    pinned = _normalize_pinned_track_ids(pinned_track_ids)
    by_id = {a.track.track_id: a for a in analyses}
    if not by_id:
        if target_track_count or locked or pinned:
            raise ValueError("no tracks available for requested set constraints")
        return SetPlan(
            track_order=[],
            arc=arc,
            target_track_count=target_track_count,
            locked_positions=locked,
            pinned_track_ids=pinned,
            model_version=MODEL_VERSION,
            provenance=provenance,
            warnings=["need >=2 tracks to build a set"],
        )

    target_count, constraint_warnings = _validate_build_constraints(
        by_id,
        target_track_count=target_track_count,
        locked_positions=locked,
        pinned_track_ids=pinned,
        start_track_id=start_track_id,
    )
    energy = {tid: track_energy(a) for tid, a in by_id.items()}
    e_range = max(energy.values()) - min(energy.values()) or 1.0

    order = _constrained_order(
        by_id,
        weights=weights,
        arc=arc,
        start_track_id=start_track_id,
        target_count=target_count,
        locked_positions=locked,
        pinned_track_ids=pinned,
        energy=energy,
        energy_range=e_range,
    )
    transitions = [
        _build_transition(
            current,
            successor,
            by_id=by_id,
            weights=weights,
            arc=arc,
            energy=energy,
            energy_range=e_range,
        )
        for current, successor in zip(order, order[1:], strict=False)
    ]
    mean_score = round(float(np.mean([t.transition_score for t in transitions])), 4) if transitions else None
    warnings = [*constraint_warnings]
    if len(order) < 2:
        warnings.append("need >=2 tracks to build a set")

    return SetPlan(
        track_order=order, transitions=transitions, arc=arc,
        target_track_count=target_count,
        locked_positions=locked,
        pinned_track_ids=pinned,
        dropped_track_ids=sorted(set(by_id) - set(order)),
        mean_transition_score=mean_score, model_version=MODEL_VERSION,
        warnings=warnings,
        provenance=provenance,
    )

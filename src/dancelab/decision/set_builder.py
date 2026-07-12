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

import re
import unicodedata
from collections.abc import Mapping, Sequence

import numpy as np

from dancelab.core.config import DescriptorWeights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    MixabilityInput,
    SetPlan,
    SetTransition,
)
from dancelab.core.provenance import provenance_for
from dancelab.decision._common import tempo_proximity_score
from dancelab.decision.harmonic import harmonic_compatibility, harmonic_relation, parse_camelot
from dancelab.decision.history import NoveltyContext, PlaylistFingerprint
from dancelab.decision.library_profile import bpm_in_range, normalize_style_list, style_matches
from dancelab.decision.mixability import compute_mixability

MODEL_VERSION = "set_builder_v0.1"
PLANNER_MODE_SMART = "smart"
PLANNER_MODE_HARMONIC = "harmonic"
PLANNER_MODE_BPM = "bpm"
PLANNER_MODES = (PLANNER_MODE_SMART, PLANNER_MODE_HARMONIC, PLANNER_MODE_BPM)

# AUD-M10: every weighted term resolves to a formula_terms.yaml entry (no
# anonymous variables). Test-enforced by test_every_set_builder_component_has_a_term.
COMPONENTS = ("harmonic", "bpm", "energy", "mixability")

__all__ = [
    "build_set",
    "transition_score",
    "bpm_score",
    "track_energy",
    "harmonic_relation",
    "parse_camelot",
    "MODEL_VERSION",
    "COMPONENTS",
    "PLANNER_MODES",
]


_ARTIST_SPLIT_RE = re.compile(
    r"\s*(?:,|&|/|\+|\band\b|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b)\s*|\s+x\s+",
    re.IGNORECASE,
)
_TITLE_ARTIST_RE = re.compile(r"\s[-–—]\s")


def _normalize_artist_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = re.sub(r"\([^)]*\)", " ", ascii_text)
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", " ", ascii_text).strip().lower()
    return re.sub(r"\s+", " ", ascii_text)


def _artist_tokens(analysis: AnalysisResult) -> set[str]:
    """Artist tokens used for playlist diversity.

    Metadata is preferred. When files only expose titles like
    "Artist - Track", infer the artist from the title prefix. Collaboration
    strings produce multiple tokens so a solo track and a collab still count as
    the same artist when they share a name.
    """
    track = analysis.track
    raw_artist = (track.artist or "").strip()
    if not raw_artist and track.title:
        parts = _TITLE_ARTIST_RE.split(track.title, maxsplit=1)
        if len(parts) == 2:
            raw_artist = parts[0].strip()
    if not raw_artist:
        return set()
    tokens = {
        _normalize_artist_token(part)
        for part in _ARTIST_SPLIT_RE.split(raw_artist)
        if part.strip()
    }
    return {token for token in tokens if token}


def _share_artist(track_id_a: str | None, track_id_b: str | None, artist_tokens: dict[str, set[str]]) -> bool:
    if not track_id_a or not track_id_b:
        return False
    artists_a = artist_tokens.get(track_id_a, set())
    artists_b = artist_tokens.get(track_id_b, set())
    return bool(artists_a and artists_b and artists_a & artists_b)


def _used_artist_tokens(order: Sequence[str], artist_tokens: dict[str, set[str]]) -> set[str]:
    used: set[str] = set()
    for track_id in order:
        used.update(artist_tokens.get(track_id, set()))
    return used


def _artist_diverse_candidates(
    candidates: list[str],
    *,
    order: Sequence[str],
    index: int,
    target_count: int,
    locked_slots: dict[int, str],
    artist_tokens: dict[str, set[str]],
) -> list[str]:
    """Prefer unseen artists; when impossible, at least avoid adjacency."""
    if not candidates:
        return candidates

    result = candidates
    used = _used_artist_tokens(order, artist_tokens)
    unseen = [
        track_id
        for track_id in result
        if not artist_tokens.get(track_id) or not (artist_tokens[track_id] & used)
    ]
    if unseen:
        result = unseen

    previous = order[-1] if order else None
    non_adjacent = [
        track_id
        for track_id in result
        if not _share_artist(previous, track_id, artist_tokens)
    ]
    if non_adjacent:
        result = non_adjacent
    else:
        fallback_non_adjacent = [
            track_id
            for track_id in candidates
            if not _share_artist(previous, track_id, artist_tokens)
        ]
        if fallback_non_adjacent:
            result = fallback_non_adjacent

    next_locked = locked_slots.get(index + 1) if index + 1 < target_count else None
    if next_locked:
        before_locked = [
            track_id
            for track_id in result
            if not _share_artist(track_id, next_locked, artist_tokens)
        ]
        if before_locked:
            result = before_locked
    return result


def _artist_diversity_warnings(
    order: Sequence[str],
    artist_tokens: dict[str, set[str]],
) -> list[str]:
    warnings: list[str] = []
    seen: set[str] = set()
    repeated: set[str] = set()
    for track_id in order:
        tokens = artist_tokens.get(track_id, set())
        repeated.update(tokens & seen)
        seen.update(tokens)
    if repeated:
        warnings.append(
            "artist diversity relaxed - repeated artist(s): "
            + ", ".join(sorted(repeated))
        )

    adjacent: list[str] = []
    for left, right in zip(order, order[1:], strict=False):
        overlap = artist_tokens.get(left, set()) & artist_tokens.get(right, set())
        adjacent.extend(sorted(overlap))
    if adjacent:
        warnings.append(
            "artist diversity warning - adjacent repeated artist(s): "
            + ", ".join(sorted(set(adjacent)))
        )
    return warnings


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


def _normalize_planner_mode(planner_mode: str | None) -> str:
    mode = (planner_mode or PLANNER_MODE_SMART).strip().lower()
    if mode in {"auto", "balanced", "smart_playlist"}:
        return PLANNER_MODE_SMART
    if mode in {"key", "camelot", "harmonic_match"}:
        return PLANNER_MODE_HARMONIC
    if mode in {"tempo", "bpm_match"}:
        return PLANNER_MODE_BPM
    if mode not in PLANNER_MODES:
        raise ValueError(
            "planner_mode must be one of: " + ", ".join(PLANNER_MODES)
        )
    return mode


def _planner_component_weights(
    weights: DescriptorWeights,
    planner_mode: str,
) -> dict[str, float]:
    """Score weights for user-facing playlist preferences.

    The components remain the same measured descriptors. Modes only rebalance
    their contribution: Smart = balanced, Harmonic = Camelot/key-first, BPM =
    tempo-continuity-first.
    """
    if planner_mode == PLANNER_MODE_HARMONIC:
        return {"harmonic": 0.55, "bpm": 0.15, "energy": 0.10, "mixability": 0.20}
    if planner_mode == PLANNER_MODE_BPM:
        return {"harmonic": 0.15, "bpm": 0.55, "energy": 0.10, "mixability": 0.20}
    return dict(weights.set_builder.weights)


def transition_score(
    a: AnalysisResult,
    b: AnalysisResult,
    weights: DescriptorWeights,
    arc: str,
    energy_a: float,
    energy_b: float,
    energy_range: float,
    planner_mode: str = PLANNER_MODE_SMART,
    context: ContextProfile | None = None,
) -> tuple[float, str, list[str]]:
    """Combined A→B transition score in [0,1] + harmonic relation + reasoning."""
    planner_mode = _normalize_planner_mode(planner_mode)
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
        MixabilityInput(track_a=a, track_b=b, context=context),
        weights.mixability,
        weights.mixability_conflict,
    ).mixability_score

    w = _planner_component_weights(weights, planner_mode)
    component_values = {"harmonic": h, "bpm": bp, "energy": en, "mixability": mix}
    score = sum(w[name] * component_values[name] for name in COMPONENTS)
    reasoning = [
        f"planner mode {planner_mode}",
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
    planner_mode: str,
    context: ContextProfile | None,
    novelty: "NoveltyContext | None" = None,
) -> str:
    scored: list[tuple[float, str]] = []
    for candidate in candidates:
        score, _, _ = transition_score(
            by_id[current],
            by_id[candidate],
            weights,
            arc,
            energy[current],
            energy[candidate],
            energy_range,
            planner_mode,
            context,
        )
        if novelty is not None:
            # §14: soft penalties inside the gate-passing candidate set —
            # relevance ordering first, history discourages repeats
            score -= novelty.penalty(current, candidate)
        scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored[0][0]
    if novelty is not None and novelty.rng is not None and novelty.epsilon > 0:
        # seeded tie-break ONLY among candidates within the honest score
        # resolution — variation never sacrifices relevance
        ties = [cand for score, cand in scored if best_score - score <= novelty.epsilon]
        if len(ties) > 1:
            return novelty.rng.choice(ties)
    return scored[0][1]


def _build_transition(
    from_track_id: str,
    to_track_id: str,
    *,
    by_id: dict[str, AnalysisResult],
    weights: DescriptorWeights,
    arc: str,
    energy: dict[str, float],
    energy_range: float,
    planner_mode: str,
    context: ContextProfile | None,
) -> SetTransition:
    a = by_id[from_track_id]
    b = by_id[to_track_id]
    score, rel, reason = transition_score(
        a,
        b,
        weights,
        arc,
        energy[from_track_id],
        energy[to_track_id],
        energy_range,
        planner_mode,
        context,
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
    artist_tokens: dict[str, set[str]],
    planner_mode: str,
    context: ContextProfile | None,
    novelty: "NoveltyContext | None" = None,
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
            candidates = _artist_diverse_candidates(
                candidates,
                order=order,
                index=index,
                target_count=target_count,
                locked_slots=locked_slots,
                artist_tokens=artist_tokens,
            )
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
                    planner_mode=planner_mode,
                    context=context,
                    novelty=novelty,
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
    planner_mode: str = PLANNER_MODE_SMART,
    context: ContextProfile | None = None,
    preferred_styles: Sequence[str] | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    novelty_mode: str = "deterministic",
    history: Sequence["PlaylistFingerprint"] | None = None,
    seed: int | None = None,
) -> SetPlan:
    """Greedy harmonic/energy set ordering with optional lock/pin constraints.

    `locked_positions` uses 1-based final playlist slots. Pinned tracks must
    appear somewhere in the final plan; `target_track_count` lets the planner
    choose a constrained subset from a larger candidate pool.

    §14 novelty: `novelty_mode` (deterministic/conservative/balanced/fresh/
    exploratory) applies soft history penalties and a seeded ε tie-break.
    Default "deterministic" = byte-stable, identical to pre-novelty behavior.
    Pinned tracks are exempt from overuse penalties (§15.10 — intentional
    carryover). Hard gates are never overridden by novelty pressure.
    """
    provenance = provenance_for("set_builder")
    planner_mode = _normalize_planner_mode(planner_mode)
    locked = _normalize_locked_positions(locked_positions)
    pinned = _normalize_pinned_track_ids(pinned_track_ids)
    by_id_all = {a.track.track_id: a for a in analyses}
    by_id = by_id_all
    if not by_id:
        if target_track_count or locked or pinned:
            raise ValueError("no tracks available for requested set constraints")
        return SetPlan(
            track_order=[],
            arc=arc,
            planner_mode=planner_mode,
            target_track_count=target_track_count,
            locked_positions=locked,
            pinned_track_ids=pinned,
            model_version=MODEL_VERSION,
            provenance=provenance,
            warnings=["need >=2 tracks to build a set"],
        )

    preference_warnings: list[str] = []
    target_count_for_preferences = target_track_count or len(by_id)
    required_ids = set(locked.values()) | set(pinned)
    if start_track_id:
        required_ids.add(start_track_id)

    style_preferences = normalize_style_list(preferred_styles)
    if not style_preferences and context is not None:
        style_preferences = normalize_style_list(context.style_focus)
    if style_preferences:
        style_ids = {
            track_id
            for track_id, analysis in by_id_all.items()
            if style_matches(analysis.track.style_label, style_preferences)
        }
        preferred_pool = style_ids | required_ids
        if len(preferred_pool & set(by_id_all)) >= target_count_for_preferences:
            by_id = {track_id: by_id_all[track_id] for track_id in by_id_all if track_id in preferred_pool}
            dropped = len(by_id_all) - len(by_id)
            if dropped:
                preference_warnings.append(
                    f"style preference applied ({', '.join(style_preferences)}); "
                    f"{dropped} non-matching track(s) left out"
                )
        else:
            preference_warnings.append(
                "style preference relaxed - not enough analyzed tracks match "
                + ", ".join(style_preferences)
            )

    resolved_bpm_min = bpm_min if bpm_min is not None else (context.bpm_min if context else None)
    resolved_bpm_max = bpm_max if bpm_max is not None else (context.bpm_max if context else None)
    if resolved_bpm_min is not None or resolved_bpm_max is not None:
        bpm_ids = {
            track_id
            for track_id, analysis in by_id.items()
            if bpm_in_range(analysis.track.bpm_estimate, resolved_bpm_min, resolved_bpm_max)
        }
        preferred_pool = bpm_ids | required_ids
        if len(preferred_pool & set(by_id)) >= target_count_for_preferences:
            before = len(by_id)
            by_id = {track_id: analysis for track_id, analysis in by_id.items() if track_id in preferred_pool}
            dropped = before - len(by_id)
            if dropped:
                preference_warnings.append(
                    f"BPM range applied ({resolved_bpm_min or '-∞'}-{resolved_bpm_max or '+∞'}); "
                    f"{dropped} out-of-range track(s) left out"
                )
        else:
            preference_warnings.append(
                "BPM range relaxed - not enough analyzed tracks match "
                f"{resolved_bpm_min or '-∞'}-{resolved_bpm_max or '+∞'}"
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
    artist_tokens = {tid: _artist_tokens(analysis) for tid, analysis in by_id.items()}

    novelty = NoveltyContext.build(
        mode=novelty_mode,
        history=list(history or []),
        seed=seed,
        exempt_ids=set(pinned),
    )

    def _run_order(active_novelty: NoveltyContext) -> list[str]:
        return _constrained_order(
            by_id,
            weights=weights,
            arc=arc,
            start_track_id=start_track_id,
            target_count=target_count,
            locked_positions=locked,
            pinned_track_ids=pinned,
            energy=energy,
            energy_range=e_range,
            artist_tokens=artist_tokens,
            planner_mode=planner_mode,
            context=context,
            novelty=active_novelty,
        )

    order = _run_order(novelty)
    novelty_warnings: list[str] = []
    if novelty_mode != "deterministic" and history:
        last = history[-1]
        if list(order) == list(last.track_ids_ordered):
            # §14 same-sequence guard: one retry with next seed + doubled edge
            # penalty; if STILL identical the library is too small to vary —
            # keep the honest result, never fake-shuffle.
            retry = NoveltyContext.build(
                mode=novelty_mode,
                history=list(history),
                seed=(seed or 0) + 1,
                exempt_ids=set(pinned),
            )
            retry.edge_penalty *= 2
            retry_order = _run_order(retry)
            if list(retry_order) == list(order):
                novelty_warnings.append(
                    "library too small to vary — identical set returned"
                )
            else:
                order = retry_order
    transitions = [
        _build_transition(
            current,
            successor,
            by_id=by_id,
            weights=weights,
            arc=arc,
            energy=energy,
            energy_range=e_range,
            planner_mode=planner_mode,
            context=context,
        )
        for current, successor in zip(order, order[1:], strict=False)
    ]
    mean_score = round(float(np.mean([t.transition_score for t in transitions])), 4) if transitions else None
    warnings = [
        *preference_warnings,
        *constraint_warnings,
        *_artist_diversity_warnings(order, artist_tokens),
        *novelty_warnings,
    ]
    if len(order) < 2:
        warnings.append("need >=2 tracks to build a set")

    return SetPlan(
        track_order=order, transitions=transitions, arc=arc, planner_mode=planner_mode,
        target_track_count=target_count,
        locked_positions=locked,
        pinned_track_ids=pinned,
        dropped_track_ids=sorted(set(by_id_all) - set(order)),
        mean_transition_score=mean_score, model_version=MODEL_VERSION,
        warnings=warnings,
        provenance=provenance,
    )

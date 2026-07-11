"""Playlist history & novelty (PRODUCT_SPEC §14).

Relevance first, diversity as soft penalties, seeded variation only as a
tie-breaker inside the honest score resolution. Hard gates are never touched
here — penalties apply to candidates that already passed them.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def edge_hash(from_id: str, to_id: str) -> str:
    return _sha1(f"{from_id}→{to_id}")


def context_hash(**parts: object) -> str:
    return _sha1(json.dumps(parts, sort_keys=True, default=str))


@dataclass
class PlaylistFingerprint:
    sequence_hash: str
    track_set_hash: str
    edge_hashes: list[str]
    track_ids_ordered: list[str]
    opening_id: str | None
    closing_id: str | None
    context_hash: str
    seed: int | None
    novelty_mode: str
    created_at: float
    pinned_ids: list[str] = field(default_factory=list)


def fingerprint_plan(
    track_order: list[str],
    *,
    ctx_hash: str,
    seed: int | None,
    novelty_mode: str,
    pinned_ids: list[str] | None = None,
) -> PlaylistFingerprint:
    return PlaylistFingerprint(
        sequence_hash=_sha1("|".join(track_order)),
        track_set_hash=_sha1("|".join(sorted(track_order))),
        edge_hashes=[edge_hash(a, b) for a, b in zip(track_order, track_order[1:])],
        track_ids_ordered=list(track_order),
        opening_id=track_order[0] if track_order else None,
        closing_id=track_order[-1] if track_order else None,
        context_hash=ctx_hash,
        seed=seed,
        novelty_mode=novelty_mode,
        created_at=time.time(),
        pinned_ids=list(pinned_ids or []),
    )


class HistoryStore:
    """JSONL store of playlist fingerprints (cache-root/history)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, fingerprint: PlaylistFingerprint) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(fingerprint)) + "\n")

    def recent(self, ctx_hash: str | None = None, limit: int = 20) -> list[PlaylistFingerprint]:
        if not self.path.exists():
            return []
        records: list[PlaylistFingerprint] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                records.append(PlaylistFingerprint(**data))
            except (json.JSONDecodeError, TypeError):
                continue  # skip corrupt lines, keep history usable
        if ctx_hash is not None:
            records = [r for r in records if r.context_hash == ctx_hash]
        return records[-limit:]


# mode → (edge_penalty, overuse_penalty, epsilon, carryover_allowance)
NOVELTY_MODES = {
    "deterministic": (0.0, 0.0, 0.0, 10**9),
    "conservative": (0.03, 0.02, 0.02, 5),
    "balanced": (0.06, 0.04, 0.02, 3),
    "fresh": (0.12, 0.08, 0.02, 1),
    "exploratory": (0.15, 0.12, 0.05, 0),
}


@dataclass
class NoveltyContext:
    """Consumed by the planner's successor choice. Built from history."""

    mode: str = "deterministic"
    edge_penalty: float = 0.0
    overuse_penalty: float = 0.0
    epsilon: float = 0.0
    carryover_allowance: int = 10**9
    recent_edges: set[str] = field(default_factory=set)
    appearance_counts: Counter = field(default_factory=Counter)
    exempt_ids: set[str] = field(default_factory=set)  # pins/Must Have — §15.10
    rng: random.Random | None = None

    @classmethod
    def build(
        cls,
        *,
        mode: str,
        history: list[PlaylistFingerprint],
        seed: int | None,
        exempt_ids: set[str] | None = None,
    ) -> "NoveltyContext":
        if mode not in NOVELTY_MODES:
            raise ValueError(f"novelty_mode must be one of {sorted(NOVELTY_MODES)}")
        edge_pen, overuse_pen, epsilon, carryover = NOVELTY_MODES[mode]
        counts: Counter = Counter()
        edges: set[str] = set()
        for fingerprint in history:
            edges.update(fingerprint.edge_hashes)
            counts.update(set(fingerprint.track_ids_ordered))
        return cls(
            mode=mode,
            edge_penalty=edge_pen,
            overuse_penalty=overuse_pen,
            epsilon=epsilon,
            carryover_allowance=carryover,
            recent_edges=edges,
            appearance_counts=counts,
            exempt_ids=set(exempt_ids or []),
            rng=random.Random(seed) if seed is not None else None,
        )

    def penalty(self, from_id: str, candidate_id: str) -> float:
        """Soft penalty for this candidate edge — never a gate."""
        total = 0.0
        if self.edge_penalty and edge_hash(from_id, candidate_id) in self.recent_edges:
            total += self.edge_penalty
        if (
            self.overuse_penalty
            and candidate_id not in self.exempt_ids
            and self.appearance_counts.get(candidate_id, 0) > self.carryover_allowance
        ):
            total += self.overuse_penalty
        return total

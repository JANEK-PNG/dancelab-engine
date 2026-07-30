"""Give the engine the records a DJ actually played, and see if it plays them the same.

The strongest test available: same pool, same length, one order to compare against.
It is fair for ordering because the weights the planner uses were measured on a
corpus of other people's mixes, not on this DJ's sets. It would not be fair for
blend length or entry point — those came from these very recordings, and are kept
out of this comparison for that reason.

Agreement is meaningless without a control, because a set of sixteen has plenty of
orders that look close by accident. Every figure here is printed next to the same
figure computed over random permutations of the same pool.
"""

from __future__ import annotations

import argparse
import json
from itertools import permutations
from pathlib import Path

import numpy as np

from dancelab.core.config import load_config, load_weights
from dancelab.decision.set_builder import build_set
from dancelab.storage.repositories import FileAnalysisRepository

from cue_parse import parse_cue


def played_order(cue_path: str) -> list[str]:
    """The DJ's sequence, one entry per record, in the order first heard.

    A record that comes back later is the same record, not a new choice, so the
    repeat is dropped — the planner has no way to express "and then return to it"
    and comparing against something it cannot say would only measure that gap.
    """
    _, entries = parse_cue(cue_path)
    seen, order = set(), []
    for e in entries:
        stem = Path(e.path).stem
        if stem not in seen:
            seen.add(stem)
            order.append(stem)
    return order


def agreement(mine: list[str], theirs: list[str]) -> dict:
    """How close two orders are, in the three ways that mean different things."""
    common = [t for t in theirs if t in mine]
    pos_mine = {t: i for i, t in enumerate(mine)}
    pos_theirs = {t: i for i, t in enumerate(theirs)}
    same_slot = sum(1 for t in common if pos_mine[t] == pos_theirs[t])

    # adjacency: the DJ's actual handovers, kept as handovers regardless of where
    # in the set they ended up — the thing a DJ would recognise as "same move"
    pairs_theirs = set(zip(theirs, theirs[1:]))
    pairs_mine = set(zip(mine, mine[1:]))
    shared = pairs_theirs & pairs_mine
    shared_either = pairs_theirs & (pairs_mine | {(b, a) for a, b in pairs_mine})

    ranks_a = np.array([pos_theirs[t] for t in common])
    ranks_b = np.array([pos_mine[t] for t in common])
    rho = float(np.corrcoef(ranks_a, ranks_b)[0, 1]) if len(common) > 2 else float("nan")
    return {"n_common": len(common), "same_slot": same_slot,
            "pairs_exact": len(shared), "pairs_either_way": len(shared_either),
            "pairs_total": len(pairs_theirs), "rho": rho,
            "shared_pairs": sorted(shared)}


def control(theirs: list[str], pool: list[str], n: int = 4000) -> dict:
    """The same three numbers from shuffling, so 'close' has something to beat."""
    rng = np.random.default_rng(7)
    slots, pairs, rhos = [], [], []
    pos_t = {t: i for i, t in enumerate(theirs)}
    pairs_t = set(zip(theirs, theirs[1:]))
    for _ in range(n):
        cand = list(rng.permutation(pool))[: len(theirs)]
        common = [t for t in theirs if t in cand]
        pos_c = {t: i for i, t in enumerate(cand)}
        slots.append(sum(1 for t in common if pos_c[t] == pos_t[t]))
        pairs.append(len(pairs_t & set(zip(cand, cand[1:]))))
        if len(common) > 2:
            rhos.append(float(np.corrcoef([pos_t[t] for t in common],
                                          [pos_c[t] for t in common])[0, 1]))
    return {"same_slot": float(np.mean(slots)), "pairs_exact": float(np.mean(pairs)),
            "rho": float(np.mean(rhos)),
            "pairs_p95": float(np.percentile(pairs, 95)),
            "slot_p95": float(np.percentile(slots, 95))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--arc", default="build")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = load_config(args.config)
    weights = load_weights(cfg.weights_file)
    repo = FileAnalysisRepository(args.processed)
    analyses = [repo.get(t) for t in repo.list_track_ids()]
    by_stem = {Path(a.track.source_path).stem: a for a in analyses}

    theirs = [t for t in played_order(args.cue) if t in by_stem]
    pool = list(by_stem)
    print(f"pula {len(pool)} utworów · DJ zagrał {len(theirs)} unikalnych\n")

    runs = {}
    for label, seed_first in (("wolny start", False), ("ten sam pierwszy utwór", True)):
        kwargs = {}
        if seed_first:
            kwargs["seed_track_id"] = by_stem[theirs[0]].track.track_id
        try:
            plan = build_set(analyses, weights, arc=args.arc, planner_mode="smart",
                             target_length=len(theirs), **kwargs)
        except TypeError:
            # older signature: no seeding, no target length
            plan = build_set(analyses, weights, arc=args.arc, planner_mode="smart")
        stem_of = {a.track.track_id: Path(a.track.source_path).stem for a in analyses}
        mine = [stem_of[t] for t in plan.track_order][: len(theirs)]
        runs[label] = {"order": mine, **agreement(mine, theirs)}
        a = runs[label]
        print(f"{label}:")
        print(f"  te same miejsca      {a['same_slot']:2d} / {len(theirs)}")
        print(f"  te same przejścia    {a['pairs_exact']:2d} / {a['pairs_total']}"
              f"   (w dowolną stronę {a['pairs_either_way']})")
        print(f"  korelacja pozycji    {a['rho']:+.3f}\n")

    ctrl = control(theirs, pool)
    print("kontrola (losowe kolejności z tej samej puli):")
    print(f"  te same miejsca      {ctrl['same_slot']:.2f}  (p95 {ctrl['slot_p95']:.0f})")
    print(f"  te same przejścia    {ctrl['pairs_exact']:.2f}  (p95 {ctrl['pairs_p95']:.0f})")
    print(f"  korelacja pozycji    {ctrl['rho']:+.3f}")

    Path(args.out).write_text(json.dumps(
        {"theirs": theirs, "pool": pool, "runs": runs, "control": ctrl},
        ensure_ascii=False))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

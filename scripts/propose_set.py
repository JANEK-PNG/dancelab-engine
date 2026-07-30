"""Propose a set from the DJ's library — the engine choosing, not copying.

Every render so far replayed his own order. This is the other half of the question:
given the same records, what would the engine play, and can it say why in words a DJ
would use rather than in weights.

Tempo comes from the rigid grids, not the analysis, and it is a hard filter before
anything else is considered: records that cannot reach the set's tempo on a pitch
fader are out, because a pair that will not beatmatch is not a pair however well it
scores on key or energy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import seam_decompose as S
from dancelab.core.rigid_grid import fit_rigid_grid

from dancelab.core.config import load_config, load_weights
from dancelab.decision.harmonic import harmonic_relation
from dancelab.decision.set_builder import build_set
from dancelab.storage.repositories import FileAnalysisRepository

GRIDS = Path(__file__).resolve().parents[1] / "experiments_priv/_cache/rigid_grids.json"

RELATION_PL = {
    "exact": "ta sama tonacja",
    "relative_major_minor": "równoległa dur/moll",
    "adjacent_same_mode": "sąsiad na kole",
    "cautious": "ostrożnie",
    "risky": "ryzykownie",
    "unknown": "tonacja nieznana",
}


def tempo_note(delta: float) -> str:
    """How far apart the two records sit before either is pitched."""
    if abs(delta) < 0.5:
        return "identyczne tempo w oryginale"
    if abs(delta) < 2.5:
        return f"{delta:+.1f} BPM, suwak ledwo ruszony"
    if abs(delta) < 6:
        return f"{delta:+.1f} BPM, wyraźny ruch suwaka"
    return f"{delta:+.1f} BPM, na granicy"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", required=True)
    ap.add_argument("--count", type=int, default=14)
    ap.add_argument("--arc", default="build")
    ap.add_argument("--max-pitch", type=float, default=0.08)
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    weights = load_weights(cfg.weights_file)
    repo = FileAnalysisRepository(args.processed)
    analyses = [repo.get(t) for t in repo.list_track_ids()]
    # Fit any grid the cache is missing rather than treating an absent entry as a
    # failed fit — the first run silently dropped sixteen records that way and read
    # as "no rigid grid fits", which was a lie about the music.
    grids = json.loads(GRIDS.read_text()) if GRIDS.exists() else {}
    todo = [a for a in analyses if a.track.source_path not in grids]
    for i, a in enumerate(todo, 1):
        print(f"  siatka {i}/{len(todo)}: {Path(a.track.source_path).stem[:44]}",
              flush=True)
        got = fit_rigid_grid(S.load_mono(a.track.source_path), S.SR)
        grids[a.track.source_path] = ({"bpm": got.bpm, "first": got.first_beat_sec,
                                       "contrast": got.contrast} if got else None)
    if todo:
        GRIDS.write_text(json.dumps(grids))

    def bpm_of(a):
        g = grids.get(a.track.source_path)
        return g["bpm"] if g and g["contrast"] >= 2.0 else None

    with_tempo = [(a, bpm_of(a)) for a in analyses]
    usable = [(a, b) for a, b in with_tempo if b]
    master = float(np.median([b for _, b in usable]))
    pool = [a for a, b in usable if abs(master / b - 1) <= args.max_pitch]

    print(f"biblioteka {len(analyses)} · z pewną siatką {len(usable)} · "
          f"w zasięgu suwaka przy {master:.0f} BPM {len(pool)}\n")
    for a, b in with_tempo:
        if b is None:
            print(f"  poza pulą: {Path(a.track.source_path).stem[:44]:44s} "
                  f"— żaden sztywny grid nie pasuje")
        elif abs(master / b - 1) > args.max_pitch:
            print(f"  poza pulą: {Path(a.track.source_path).stem[:44]:44s} "
                  f"— {b:.0f} BPM, {abs(master / b - 1) * 100:.0f}% od tempa setu")

    plan = build_set(pool, weights, arc=args.arc,
                     target_track_count=min(args.count, len(pool)),
                     planner_mode="smart")
    by_id = {a.track.track_id: a for a in pool}

    keys = sum(1 for a in pool if getattr(a.track, "key", None))
    print(f"\nPROPOZYCJA — {len(plan.track_order)} utworów, set na {master:.0f} BPM")
    if not keys:
        print("UWAGA: żaden utwór w puli nie ma rozpoznanej tonacji, więc harmonia "
              "NIE brała udziału w tym ułożeniu.\n")
    prev = None
    for i, tid in enumerate(plan.track_order, 1):
        a = by_id[tid]
        bpm = bpm_of(a)
        name = Path(a.track.source_path).stem
        who, _, what = name.partition(" - ")
        pitch = (master / bpm - 1) * 100
        print(f"{i:2d}. {who[:26]:26s} {what[:40]:40s} {bpm:5.0f} → {master:.0f} "
              f"({pitch:+5.1f}%)")
        if prev is not None:
            rel = harmonic_relation(getattr(prev.track, "key", None),
                                    getattr(a.track, "key", None))
            rname = rel.relation if hasattr(rel, "relation") else str(rel)
            print(f"      ↳ {tempo_note(bpm - bpm_of(prev))} · "
                  f"{RELATION_PL.get(rname, rname)}")
        prev = a
    print(f"\nśrednia zgodność przejść: {plan.mean_transition_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

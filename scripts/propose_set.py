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

from dancelab.core.config import load_config, load_weights
from dancelab.decision.harmonic import harmonic_relation
from dancelab.decision.set_builder import build_set
from dancelab.storage.repositories import FileAnalysisRepository
from grid_cache import flush, grid_for

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
    ap.add_argument("--out", help="Write the chosen order here, one path per line")
    ap.add_argument("--exclude-cue", action="append", default=[],
                    help="Drop everything this DJ already played in these sets")
    args = ap.parse_args()

    cfg = load_config(args.config)
    weights = load_weights(cfg.weights_file)
    repo = FileAnalysisRepository(args.processed)
    analyses = [repo.get(t) for t in repo.list_track_ids()]

    # Proposing from records he has already played is not a proposal, it is a
    # reshuffle of his own set — which is what the first run did.
    if args.exclude_cue:
        from cue_parse import parse_cue

        played = {e.path for c in args.exclude_cue for e in parse_cue(c)[1]}
        keep = [a for a in analyses if a.track.source_path not in played]
        print(f"pomijam {len(analyses) - len(keep)} utworów, które już zagrałeś\n")
        analyses = keep
    # Fit whatever the cache is missing rather than treating an absent entry as a
    # failed fit — an earlier run silently dropped sixteen records that way and
    # reported "no rigid grid fits", which was a lie about the music.
    def bpm_of(a):
        g = grid_for(a.track.source_path)
        return g["bpm"] if g else None

    # Our own output had leaked back into the input: two entries in the first set
    # were the same drum stem this project exported, once from a directory and once
    # from its smoke-test copy. A drum stem scores beautifully — it agrees with
    # every key and fights nothing — so the planner picked it twice. Anything this
    # toolchain produced, and anything named after a stem, is not music.
    STEM_NAMES = {"drums", "bass", "other", "vocals", "instrumental", "acapella"}
    n_before = len(analyses)
    analyses = [a for a in analyses
                if "DanceLab_Stem_Export" not in a.track.source_path
                and Path(a.track.source_path).stem.lower() not in STEM_NAMES]
    # and the same record can sit in two folders — keep the first, by name
    seen_names, deduped = set(), []
    for a in analyses:
        name = Path(a.track.source_path).stem.lower()
        if name not in seen_names:
            seen_names.add(name)
            deduped.append(a)
    if n_before != len(deduped):
        print(f"odrzucam {n_before - len(deduped)} pozycji: nasze własne stemy "
              f"i duplikaty tego samego utworu\n")
    analyses = deduped

    # Hand the planner the rigid-grid tempo, not the tracker's. The corpus prior
    # buckets a pair by how far apart their tempos are, so a BPM that is out by a
    # percent — or by an octave — files the pair under the wrong bucket and the
    # measured behaviour of 551 DJs lands on the wrong transition. The whole point
    # of that prior is that it knows what real DJs do between two records; feeding
    # it a wrong distance is the same as not having it.
    for a in analyses:
        b = bpm_of(a)
        if b:
            a.track.bpm_estimate = b

    print(f"dopasowuję siatki bitów do {len(analyses)} utworów …", flush=True)
    with_tempo = [(a, bpm_of(a)) for a in analyses]
    flush()
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

    # key_estimate, not "key": reading a field that does not exist returned None
    # for every record and produced the claim that the engine cannot hear harmony,
    # which it has been doing all along.
    keys = sum(1 for a in pool if a.track.key_estimate)
    print(f"\nPROPOZYCJA — {len(plan.track_order)} utworów, set na {master:.0f} BPM")
    weak = sum(1 for a in pool if (a.track.key_confidence or 0) < 0.35)
    print(f"tonacja rozpoznana w {keys} z {len(pool)} utworów"
          + (f", z czego {weak} z niską pewnością (<0,35)" if weak else "") + "\n")
    prev = None
    for i, tid in enumerate(plan.track_order, 1):
        a = by_id[tid]
        bpm = bpm_of(a)
        name = Path(a.track.source_path).stem
        who, _, what = name.partition(" - ")
        pitch = (master / bpm - 1) * 100
        key = a.track.key_estimate or "—"
        conf = a.track.key_confidence or 0.0
        print(f"{i:2d}. {who[:24]:24s} {what[:34]:34s} {bpm:5.0f} → {master:.0f} "
              f"({pitch:+5.1f}%)  {key:>3s}{'?' if conf < 0.35 else ' '}")
        if prev is not None:
            rel = harmonic_relation(prev.track.key_estimate, a.track.key_estimate)
            rname = rel.relation if hasattr(rel, "relation") else str(rel)
            print(f"      ↳ {tempo_note(bpm - bpm_of(prev))} · "
                  f"{RELATION_PL.get(rname, rname)}")
        prev = a
    print(f"\nśrednia zgodność przejść: {plan.mean_transition_score}")
    if args.out:
        Path(args.out).write_text("\n".join(by_id[t].track.source_path
                                            for t in plan.track_order))
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

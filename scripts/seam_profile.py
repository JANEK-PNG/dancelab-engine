"""Turn measured seams into a DJ's signature — how this person sews, in numbers.

This is the third layer of a user profile, and the only one that is about craft
rather than taste. The library says what someone owns and the play history says
what they chose; neither says anything about the join, which is the part a DJ
actually practises.

Coverage is printed next to every figure. A profile built from ten seams is a
sketch, and saying so is part of the measurement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# NOT comparable to the corpus, and the temptation to try is why this says so.
#
# The corpus median of 77 beats (3278 seams, 2026-07-30) is the gap between where
# DTW stopped matching the outgoing record and where it started matching the
# incoming one — the stretch it could not attribute to either. What is measured
# here is the audible overlap: from the incoming record rising above its noise
# floor to the outgoing one dropping below. Through a long blend the alignment
# usually keeps matching whichever record is louder, so its gap is shorter than
# the overlap by construction. Dividing one by the other invents a ratio.
#
# Comparing them honestly means running this pipeline on corpus mixes, which
# needs both source recordings for each seam — not yet counted.
CORPUS_NOTE = ("korpus mierzy inną wielkość (luka w dopasowaniu DTW, nie nakładanie) "
               "— porównanie wymagałoby przeliczenia korpusu tą samą metodą")

# A hold that covers most of the blend is more likely the fit losing the decks
# apart in the bass — its worst band, 30 % noise floor — than a hand holding a
# knob down the whole way. Flagged, not dropped: on the one seam checked by ear
# the measure was right, so these may be real.
HOLD_SUSPECT_SHARE = 0.7


def quantiles(v):
    a = np.asarray(v, dtype=float)
    return {"n": int(a.size), "min": float(a.min()), "p25": float(np.percentile(a, 25)),
            "median": float(np.median(a)), "p75": float(np.percentile(a, 75)),
            "max": float(a.max())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("summaries", nargs="+", help="summary.json files from seam_batch")
    ap.add_argument("--bpm", type=float, default=136.0,
                    help="Set tempo, for reading blend lengths in beats")
    ap.add_argument("--out", default="experiments_priv/seam_profile.json")
    args = ap.parse_args()

    seams, skipped, sets = [], [], []
    for path in args.summaries:
        d = json.loads(Path(path).read_text())
        seams += d["seams"]
        skipped += d["skipped"]
        sets.append(Path(d["mix"]).stem)

    if not seams:
        print("brak zmierzonych szwów")
        return 1

    blend = [s["blend_sec"] for s in seams if s.get("blend_sec")]
    held = [s.get("b_bass_held_sec") or 0.0 for s in seams]
    thin = [s.get("a_thinned_sec") or 0.0 for s in seams]
    beats = [b * args.bpm / 60 for b in blend]

    q = quantiles(blend)
    total = len(seams) + len(skipped)
    print(f"\nPROFIL SZYCIA — {', '.join(sets)}")
    print(f"zmierzone {len(seams)} z {total} szwów ({len(seams)/total*100:.0f}%); "
          f"reszta bez zamka lub bez nakładania nad podłogą\n")

    print(f"Długość nakładania")
    print(f"  mediana {q['median']:5.1f} s  ({np.median(beats):5.0f} uderzeń przy {args.bpm:.0f} BPM)")
    print(f"  zakres  {q['min']:5.1f} – {q['max']:.1f} s   (kwartyle {q['p25']:.0f}–{q['p75']:.0f} s)")
    print(f"  UWAGA: {CORPUS_NOTE}\n")

    n_held = sum(1 for h in held if h >= 4)
    hand = [s for s in seams if s.get("b_bass_hold_is_hand")]
    record = [s for s in seams if s.get("b_bass_hold_verdict") == "utwór sam nie ma tam basu"]
    unsure = [s for s in seams if s.get("b_bass_hold_verdict") == "niepewne"]
    print(f"Bas wchodzącego wstrzymany")
    print(f"  zgłoszonych {n_held} z {len(seams)} szwów — ale to jeszcze nie ruch ręki:")
    print(f"    {len(hand):2d} potwierdzone jako RĘKA (utwór miał tam swój bas)")
    print(f"    {len(record):2d} to właściwość nagrania (utwór sam nie ma tam basu)")
    print(f"    {len(unsure):2d} niepewne")
    if hand:
        hq = quantiles([s["b_bass_held_sec"] for s in hand])
        print(f"  z potwierdzonych: mediana {hq['median']:.1f} s, "
              f"zakres {hq['min']:.1f}–{hq['max']:.1f} s")
    print(f"  → RĘKA w {len(hand)/len(seams)*100:.0f}% zmierzonych przejść\n")

    n_thin = sum(1 for x in thin if x >= 2)
    print(f"Wychodzący wychudzony przed wyjściem (filtr lub zdjęty bas)")
    print(f"  w {n_thin} z {len(seams)} szwów ({n_thin/len(seams)*100:.0f}%)")
    if n_thin:
        tq = quantiles([x for x in thin if x >= 2])
        print(f"  mediana {tq['median']:.1f} s, zakres {tq['min']:.1f}–{tq['max']:.1f} s\n")

    print("Każdy szew z osobna")
    print(f"  {'blend':>7s} {'bas B':>7s} {'filtr A':>8s}   przejście")
    for s in sorted(seams, key=lambda x: -(x.get("blend_sec") or 0)):
        print(f"  {s['blend_sec']:6.1f}s {s.get('b_bass_held_sec') or 0:6.1f}s "
              f"{s.get('a_thinned_sec') or 0:7.1f}s   "
              f"{s['from'].split('—')[-1].strip()[:26]} → "
              f"{s['to'].split('—')[-1].strip()[:26]}")

    Path(args.out).write_text(json.dumps({
        "sets": sets, "n_measured": len(seams), "n_total": total,
        "blend_sec": q, "blend_beats_median": float(np.median(beats)),
        "corpus_comparable": False, "corpus_note": CORPUS_NOTE,
        "bass_hold_hand_share": len(hand) / len(seams), "bass_hold_reported": n_held,
        "thinned_share": n_thin / len(seams),
        "seams": seams, "skipped": skipped}, ensure_ascii=False))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

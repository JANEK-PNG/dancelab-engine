"""Are the two decks locked? Answered from the grids, not from listening to the mix.

Every audio-side attempt to measure this lied. Fitting a line to the render's own
detected beats reported 12 ms while the galloping was plainly audible, because a mix
dominated by one deck looks even while the other walks away from it. Correlating
each source against the render reported four seconds of slip — nine beats — because
an unbounded search finds the neighbouring bar as readily as the right one, and
bounding it to half a beat still measures a deck that has gone quiet by the end.

With both decks on rigid grids at one tempo, drift is impossible: identical periods
cannot diverge however long the blend runs, and each cue sits on a bar line of its
own grid, so the two grids coincide in the render exactly. That part needs no
measurement and this script confirms it comes out at zero — which is a check that
the snapping is consistent, and nothing more. It is tautological on purpose.

The question it cannot answer is whether each grid is right about its own record.
For that see check_grid_vs_mix.py, which asks the DJ's own recording — where these
records were beatmatched by hand and sounded correct — whether our grid predicts
where its kicks actually landed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

QUARTER_BEAT_MS = 110.0        # at 136 BPM, roughly where tight becomes a stumble


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--grids", default="experiments_priv/_cache/rigid_grids.json")
    args = ap.parse_args()

    grids = json.loads(Path(args.grids).read_text())
    rows = json.loads(Path(args.pairs).read_text())

    print(f"{'szew':18s} {'BPM A':>7s} {'BPM B':>7s} {'faza':>8s}  ocena")
    offsets = []
    for r in rows:
        if not r.get("mine"):
            continue
        ga, gb = grids.get(r["deck_a_path"]), grids.get(r["deck_b_path"])
        if not ga or not gb:
            continue
        period = 60.0 / r["target_bpm"]

        # Each deck's beats, moved onto the render's clock. Both are periodic with
        # the same period there, so their whole relationship is one offset.
        def on_render(g, cue, rate):
            first = (g["first"] - cue) / rate
            return np.mod(first, period)

        oa = on_render(ga, r["cue_a_sec"], r["rate_a"])
        ob = on_render(gb, r["cue_b_sec"], r["rate_b"])
        gap = (ob - oa) % period
        gap = min(gap, period - gap) * 1000
        offsets.append(gap)
        verdict = ("zablokowane" if gap < 15 else
                   "ciasne" if gap < 40 else
                   "słyszalne" if gap < QUARTER_BEAT_MS else "KOŃ")
        print(f"{r['seam']:18s} {60 / (60 / ga['bpm']):7.1f} {gb['bpm']:7.1f} "
              f"{gap:6.0f}ms  {verdict}")

    if offsets:
        a = np.array(offsets)
        print(f"\nrozjazd faz: mediana {np.median(a):.0f} ms · najgorszy {a.max():.0f} ms")
        print(f"  zablokowane <15 ms: {(a < 15).sum()}/{a.size}   "
              f"poniżej słyszalności <40 ms: {(a < 40).sum()}/{a.size}   "
              f"konie >{QUARTER_BEAT_MS:.0f} ms: {(a > QUARTER_BEAT_MS).sum()}/{a.size}")
        print("\nrozjazd W CZASIE jest zerowy z konstrukcji: identyczne okresy "
              "nie mogą się rozejść.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

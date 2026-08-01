"""What the outgoing record vacated, and what the incoming one brought.

The gesture measurements say how a seam was executed — how long, bass down, filter
on the way out. They say nothing about why *these two records*. Asked about one
seam, the DJ did not describe his hands at all: the outgoing track ended on drums
alone, the incoming one opened on a quiet vocal with no bassline, and so there was
room to breathe. That is a statement about content, and content is what a chooser
needs, because the gesture is downstream of the choice.

The claim to test is complementarity: the incoming record fills what the outgoing
one left empty. Stems are expressed as shares of the moment's energy rather than
absolute level, so a quiet record and a loud one are comparable, and each share is
read against that same record's own average — the question is what this track is
doing *unusually* here, not what it generally sounds like.

A shuffled control is not optional. Pairing every exit with an entry from some
other seam gives the correlation this measure produces from unrelated music; only
the distance between the two numbers means anything.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

import seam_decompose as S

STEMS = ("drums", "bass", "other", "vocals")
WINDOW_SEC = 15.0


def shares(path: str, origin: float, rate: float,
           t0: float, t1: float) -> np.ndarray | None:
    """Each stem's share of energy in a window, minus its share in the whole track.

    Positive means the record leans on that stem here more than it usually does.
    Shares rather than levels because a fader position must not register as a
    change of content.
    """
    stems = S.separate(path)
    here, whole = [], []
    for name in STEMS:
        seg = S.warp(stems[name], origin, rate, t0, t1)
        here.append(float((seg ** 2).mean()))
        whole.append(float((stems[name][: S.SR * 240] ** 2).mean()))
    here, whole = np.array(here), np.array(whole)
    if here.sum() <= 0 or whole.sum() <= 0:
        return None
    return here / here.sum() - whole / whole.sum()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seam_dirs", nargs="+")
    ap.add_argument("--out", default="experiments_priv/seam_content.json")
    args = ap.parse_args()

    rows = []
    for d in args.seam_dirs:
        for f in sorted(glob.glob(str(Path(d) / "seam_*.json"))):
            s = json.loads(Path(f).read_text())
            if not s.get("blend_sec"):
                continue
            a, b = s["deck_a"], s["deck_b"]
            exit_t = s["a_out_sec"]
            entry_t = s["b_in_sec"]
            va = shares(a["path"], a["origin"], a["rate"], exit_t - WINDOW_SEC, exit_t)
            vb = shares(b["path"], b["origin"], b["rate"], entry_t, entry_t + WINDOW_SEC)
            if va is None or vb is None:
                continue
            rows.append({"seam": Path(f).stem, "from": s["from"], "to": s["to"],
                         "exit": va.tolist(), "entry": vb.tolist()})
            print(f"  {Path(f).parent.name[:9]}/{Path(f).stem[-2:]}  "
                  f"wyjście " + " ".join(f"{n[:3]}{x:+.2f}" for n, x in zip(STEMS, va)) +
                  "   wejście " + " ".join(f"{n[:3]}{x:+.2f}" for n, x in zip(STEMS, vb)),
                  flush=True)

    if len(rows) < 5:
        print("za mało szwów")
        return 1

    E = np.array([r["exit"] for r in rows])
    N = np.array([r["entry"] for r in rows])
    real = float(np.corrcoef(E.ravel(), N.ravel())[0, 1])

    # Control: the same exits against entries that belong to other seams. Every
    # rotation is used rather than random draws, so the number does not move
    # between runs and there is no seed to argue about.
    ctrl = [float(np.corrcoef(E.ravel(), np.roll(N, k, axis=0).ravel())[0, 1])
            for k in range(1, len(rows))]

    print(f"\n{len(rows)} szwów, {len(STEMS)} stemów → {E.size} punktów")
    print(f"  korelacja wyjście ~ wejście, PRAWDZIWE PARY : {real:+.3f}")
    print(f"  ta sama miara na parach przetasowanych      : {np.mean(ctrl):+.3f} "
          f"(zakres {min(ctrl):+.3f} … {max(ctrl):+.3f})")
    print(f"  sygnał ponad przypadek                      : {real - np.mean(ctrl):+.3f}")
    print("\n  ujemna korelacja = wchodzący wypełnia to, co wychodzący zwolnił")

    print(f"\n  per stem (prawdziwe pary):")
    for i, name in enumerate(STEMS):
        r = float(np.corrcoef(E[:, i], N[:, i])[0, 1])
        c = np.mean([float(np.corrcoef(E[:, i], np.roll(N[:, i], k))[0, 1])
                     for k in range(1, len(rows))])
        print(f"    {name:7s} {r:+.3f}   (przetasowane {c:+.3f})")

    Path(args.out).write_text(json.dumps(
        {"stems": list(STEMS), "window_sec": WINDOW_SEC, "rows": rows,
         "corr_real": real, "corr_shuffled_mean": float(np.mean(ctrl))},
        ensure_ascii=False))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

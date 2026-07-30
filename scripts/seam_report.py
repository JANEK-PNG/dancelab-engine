"""Turn a seam fit into a picture and a sentence a DJ can argue with.

Two rules are enforced here rather than left to the reader. A gain measured on a
band the record barely fills is not a small gain, it is no measurement at all —
you cannot tell that someone closed a tap that had nothing running through it.
And a gain under the null-test floor is indistinguishable from a record that is
not playing. Both are shown as gaps, never as zeros.
"""

from __future__ import annotations

import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BANDS = ("bas", "środek", "góra")
COL = {"A": "#c94f4f", "B": "#3f7fb5"}


def _content_mask(report, deck, times, band):
    """True where the record actually carries energy in this band."""
    # stem_content is sampled on the STFT grid; resample onto the gain grid
    stems = report["stem_content"][deck]
    hop = report["hop_sec"]
    t0 = report["seam"][0]
    carriers = {"bas": ["bass", "drums"], "środek": ["other", "vocals", "drums"],
                "góra": ["drums", "other", "vocals"]}[band]
    energy = np.sum([np.asarray(stems[s]) for s in carriers], axis=0)
    # Smoothed to the same ~1 s scale the gains were fitted on. Raw frames dip
    # to nothing between kick hits, which would flag a playing record as silent
    # several times a bar.
    win = max(1, int(round(1.0 / hop)))
    energy = np.convolve(energy, np.ones(win) / win, mode="same")
    grid = t0 + np.arange(len(energy)) * hop
    on_gain_grid = np.interp(times, grid, energy)
    return on_gain_grid > 0.08 * np.percentile(energy, 95)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--out", default="experiments_priv/seam.png")
    args = ap.parse_args()
    r = json.load(open(args.report))

    floor = {}
    for band in BANDS:
        vals = [r["noise_floor"][k][band]["median"] for k in r["noise_floor"]]
        floor[band] = max(vals) if vals else 0.0

    fig, axes = plt.subplots(len(BANDS) + 1, 1, figsize=(13, 9), sharex=True)
    for ax, band in zip(axes, BANDS):
        t = np.asarray(r["bands"][band]["t"])
        for deck in ("A", "B"):
            g = np.asarray(r["bands"][band]["a" if deck == "A" else "b"])
            has = _content_mask(r, deck, t, band)
            shown = np.where(has & (g > floor[band]), g, np.nan)
            ax.plot(t, shown, color=COL[deck], lw=2, label=f"deck {deck}")
            # what was dropped, and why — drawn faintly so it cannot be read as zero
            ax.plot(t, np.where(~has, 0.02, np.nan), color=COL[deck], lw=6, alpha=.18)
        ax.axhspan(0, floor[band], color="k", alpha=.07)
        ax.text(t[0], floor[band], f" podłoga szumu {floor[band]*100:.0f}%",
                va="bottom", fontsize=7, color="#555")
        ax.set_ylabel(band)
        ax.set_ylim(0, 1.6)
        ax.grid(alpha=.2)
    axes[0].legend(loc="upper right", fontsize=8)

    res = np.mean([r["bands"][b]["residual"] for b in BANDS], axis=0)
    axes[-1].plot(r["bands"]["bas"]["t"], np.asarray(res) * 100, color="#777")
    axes[-1].set_ylabel("reszta %")
    axes[-1].set_xlabel("czas w miksie [s]")
    axes[-1].grid(alpha=.2)
    fig.suptitle("Szew: co zrobiły ręce  ·  szara strefa = niemierzalne  ·  "
                 "gruba blada linia = w tym paśmie utwór nic nie grał", fontsize=10)
    fig.tight_layout()
    fig.savefig(args.out, dpi=130)
    print(f"Wrote {args.out}")

    # ---------------------------------------------------------------- summary
    print(f"\n{'czas':>7s}  {'A bas':>7s} {'A śr':>7s} {'A góra':>7s}   "
          f"{'B bas':>7s} {'B śr':>7s} {'B góra':>7s}")
    t = np.asarray(r["bands"]["bas"]["t"])
    cells = {}
    for band in BANDS:
        for deck in ("A", "B"):
            g = np.asarray(r["bands"][band]["a" if deck == "A" else "b"])
            has = _content_mask(r, deck, t, band)
            cells[(deck, band)] = [
                "  —  " if not h else ("  ·  " if v <= floor[band] else f"{v:5.2f}")
                for v, h in zip(g, has)]
    for i in range(0, len(t), 6):
        row = "  ".join(cells[(d, b)][i] for d in ("A", "B") for b in BANDS)
        print(f"{t[i]:7.1f}  {row}")
    print("\n  —  = utwór nic nie gra w tym paśmie (niemierzalne)")
    print("  ·  = poniżej podłogi szumu (nieodróżnialne od nieobecności)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

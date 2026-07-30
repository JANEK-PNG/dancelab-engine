"""Does our beat grid predict where the kicks actually landed in the DJ's mix?

A grid can only be checked against something that is known to be right. The DJ's
own recording is exactly that: these records were beatmatched by hand, played out,
and sounded correct to him. So each record's fitted grid is carried onto the mix's
clock through the alignment, and we ask how much of the mix's low-end onset energy
sits on those predicted beats.

The control is the same measurement at deliberately wrong phases. A grid that only
looks good because kick energy is everywhere would score the same off the beat as
on it; a grid that is right scores far higher on it.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

import seam_decompose as S
from dancelab.core.rigid_grid import KICK_HZ

HOP = 128


def kick_onsets(path, t0, t1):
    import librosa
    from scipy.signal import butter, sosfiltfilt

    y = S.load_mono(path, t0, t1)
    sos = butter(4, KICK_HZ / (S.SR / 2), btype="lowpass", output="sos")
    env = librosa.onset.onset_strength(y=sosfiltfilt(sos, y).astype(np.float32),
                                       sr=S.SR, hop_length=HOP)
    return np.maximum(env - np.median(env), 0.0)


def energy_at(env, times, tol=0.035):
    """Share of onset energy within tol of the predicted beats."""
    idx = np.round(times * S.SR / HOP).astype(int)
    reach = max(1, int(tol * S.SR / HOP))
    mask = np.zeros(env.size, dtype=bool)
    for i in idx[(idx >= 0) & (idx < env.size)]:
        mask[max(i - reach, 0): i + reach + 1] = True
    if not mask.any() or env.sum() <= 0:
        return 0.0
    return float(env[mask].sum() / env.sum() / (mask.sum() / mask.size))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seam-dirs", nargs="+", required=True)
    ap.add_argument("--mix", action="append", required=True)
    ap.add_argument("--grids", default="experiments_priv/_cache/rigid_grids.json")
    args = ap.parse_args()
    grids = json.loads(Path(args.grids).read_text())
    mixes = dict(m.split("=", 1) for m in args.mix)

    print(f"{'utwór w miksie':40s} {'na bicie':>9s} {'obok':>7s} {'przewaga':>9s}")
    on_all, off_all = [], []
    seen = set()
    for d in args.seam_dirs:
        mix = mixes.get(Path(d).name)
        for f in sorted(glob.glob(str(Path(d) / "seam_*.json"))):
            s = json.loads(Path(f).read_text())
            if not s.get("blend_sec"):
                continue
            for deck in ("deck_a", "deck_b"):
                dk = s[deck]
                g = grids.get(dk["path"])
                key = (dk["path"], round(dk["origin"], 1))
                if not g or key in seen:
                    continue
                seen.add(key)
                # a stretch where this record plays and the other one does not
                t0 = s["b_in_sec"] - 45 if deck == "deck_a" else s["a_out_sec"] + 5
                t1 = t0 + 35
                if t0 < 0:
                    continue
                env = kick_onsets(mix, t0, t1)
                period = 60.0 / g["bpm"] / dk["rate"]      # beat period in mix time
                first = dk["origin"] + g["first"] / dk["rate"]
                beats = first + np.arange(-4000, 4000) * period - t0
                beats = beats[(beats >= 0) & (beats < t1 - t0)]
                if beats.size < 20:
                    continue
                on = energy_at(env, beats)
                off = energy_at(env, beats + period / 2)    # deliberately wrong phase
                on_all.append(on); off_all.append(off)
                print(f"{Path(dk['path']).stem[:40]:40s} {on:9.2f} {off:7.2f} "
                      f"{on / max(off, 1e-9):8.2f}×")
    if on_all:
        on, off = np.array(on_all), np.array(off_all)
        print(f"\nmediana: na bicie {np.median(on):.2f} · obok {np.median(off):.2f} "
              f"· przewaga {np.median(on / np.maximum(off, 1e-9)):.2f}×")
        print(f"siatka trafia lepiej niż faza obok: {(on > off).sum()}/{on.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

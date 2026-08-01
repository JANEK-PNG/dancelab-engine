"""Spectrograms of a seam and its rebuild — the picture the three curves throw away.

The band curves answer "how much of each record, in three bands". They cannot show
a filter sweeping, a kick sitting under a pad, or where a record's air actually
lives, because all of that happens between the bands. The full transform is already
computed for the fit; only the display was collapsing it.

Frequency is log-spaced because that is how the ear and every mixer divide it —
linear axes give three quarters of the picture to the top octave, where almost
nothing a DJ decides about happens. The dB range is fixed across every image so
two of them can be compared by eye at all.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

N_FFT = 4096
HOP = 1024
F_LO, F_HI = 30.0, 16000.0
DB_FLOOR, DB_CEIL = -72.0, 0.0      # relative to each clip's own peak


def spectrogram(path: Path, out: Path, width=6.2, height=1.75, bare: bool = True) -> bool:
    import librosa

    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if y.size < N_FFT:
        return False
    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

    # Log frequency axis, built by interpolating in dB rather than by averaging
    # the bins that fall in each row. Below about 500 Hz a log row is narrower
    # than the transform's own 10.8 Hz spacing, so most rows down there contain no
    # bin at all and averaging leaves black stripes across exactly the region a DJ
    # cares most about.
    db_lin = 20 * np.log10(S + 1e-9)
    edges = np.geomspace(F_LO, F_HI, 257)
    centres = np.sqrt(edges[:-1] * edges[1:])
    db = np.stack([np.interp(centres, freqs, db_lin[:, t])
                   for t in range(db_lin.shape[1])], axis=1)
    # Levels are read against each clip's own peak: his recording and my render sit
    # at different absolute gains, and comparing those would only measure the
    # normalisation, not the sound.
    db = np.clip(db - db.max(), DB_FLOOR, DB_CEIL)

    # Saved bare — no axes, no margins — so the page can lay its own markers over
    # the image at exact time fractions. Axis furniture baked into the PNG would
    # make every overlay guess where the plot area actually starts.
    fig = plt.figure(figsize=(width, height), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(db, origin="lower", aspect="auto", cmap="magma",
              vmin=DB_FLOOR, vmax=DB_CEIL,
              extent=[0, y.size / sr, 0, db.shape[0]])
    ax.set_axis_off()
    out.parent.mkdir(parents=True, exist_ok=True)
    # JPEG, not PNG: a spectrogram is dense noise, which lossless compression
    # barely touches — the same set of images came to 16 MB as PNG and 1.8 MB here,
    # and the artefacts land well below anything being read off the picture.
    fig.savefig(out, pad_inches=0, facecolor="#12141a",
                pil_kwargs={"quality": 78, "optimize": True})
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    base = Path(args.pairs).parent
    out = Path(args.out) if args.out else base / "spektro"
    rows = json.loads(Path(args.pairs).read_text())
    made = 0
    for r in rows:
        for side in ("his", "mine"):
            src = r.get(side)
            if not src:
                continue
            name = f"{'twoje' if side == 'his' else 'moje'}_{r['seam']}.jpg"
            if spectrogram(base / src, out / name):
                made += 1
        print(f"  {r['seam']}", flush=True)
    print(f"\nzrobione {made} obrazów w {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

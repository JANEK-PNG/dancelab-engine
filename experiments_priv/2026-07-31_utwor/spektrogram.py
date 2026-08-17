"""Spektrogram autoportretu — obraz tego, co słychać.

Dwa panele, bo utwór ma dwie skale, na których dzieje się coś innego.

  GÓRA — cały utwór. Widać cztery podejścia oddzielone ciszą, i widać, że
  nic między nimi nie przechodzi: każde zaczyna się od zera. Widać też, że
  linie robią się z podejścia na podejście CIEŃSZE — to jest czterdzieści
  głosów, które za każdym razem zgadzają się ze sobą bardziej.

  DÓŁ — jedna poprawiona nuta z bliska. Ląduje pół tonu za wysoko, stoi tam
  dwie trzecie swojej długości, i schodzi. Na obrazku to jest schodek.

Skala częstotliwości logarytmiczna, bo tak słyszy ucho: oktawa niżej to ta
sama odległość co oktawa wyżej, choć w hercach różnica jest ośmiokrotna.
"""

from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.signal import stft

SRC = pathlib.Path("experiments_priv/2026-07-31_utwor/autoportret.wav")
OUT = pathlib.Path("experiments_priv/2026-07-31_utwor/autoportret_spektrogram.png")

PAPER = "#efece4"
INK = "#141414"
ACC = "#e0483c"


def spec(y: np.ndarray, sr: int, nper: int):
    f, t, Z = stft(y, sr, nperseg=nper, noverlap=int(nper * 0.82), window="hann")
    S = 20 * np.log10(np.abs(Z) + 1e-10)
    return f, t, S


def main() -> int:
    y, sr = sf.read(SRC, dtype="float64")
    m = y.mean(axis=1)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9.5), height_ratios=[2.05, 1],
        facecolor=PAPER, gridspec_kw={"hspace": 0.34})

    # ── cały utwór ──
    f, t, S = spec(m, sr, 8192)
    lo, hi = 90.0, 4200.0
    k = (f >= lo) & (f <= hi)
    top = S[k].max()
    ax1.pcolormesh(t, f[k], np.clip(S[k], top - 74, top),
                   shading="gouraud", cmap="magma", rasterized=True)
    ax1.set_yscale("log")
    ax1.set_ylim(lo, hi)
    ax1.set_yticks([110, 220, 440, 880, 1760, 3520])
    ax1.set_yticklabels(["110", "220", "440", "880", "1,8k", "3,5k"])
    ax1.set_ylabel("częstotliwość [Hz]", color=INK, fontsize=9)
    ax1.set_xlabel("czas [s]", color=INK, fontsize=9)

    # gdzie zaczyna się każde podejście — z ciszy w sygnale, nie z mojej pamięci
    w = int(0.25 * sr)
    env = np.array([np.sqrt((m[i:i + w] ** 2).mean()) for i in range(0, len(m) - w, w)])
    quiet = env < env.max() * 0.012
    starts = [i * 0.25 for i in range(1, len(quiet)) if quiet[i - 1] and not quiet[i]]
    starts = [s for i, s in enumerate(starts) if i == 0 or s - starts[i - 1] > 4]
    for i, s in enumerate(starts[:4]):
        ax1.axvline(s, color=ACC, lw=1.0, alpha=0.8, ls=(0, (4, 3)))
        ax1.text(s + 0.6, 3750, f"podejście {i + 1}", color=ACC, fontsize=8.5,
                 family="monospace")
    ax1.set_title(
        "AUTOPORTRET — cztery podejścia do jednej frazy, za każdym razem od zera",
        color=INK, fontsize=12, loc="left", pad=12, family="monospace")

    # ── jedna poprawka z bliska ──
    # trzecia nuta pierwszego podejścia: tam pomyłka jest największa (pół tonu)
    a = (starts[0] if starts else 6.0) + 2.9
    b = a + 1.9
    seg = m[int(a * sr): int(b * sr)]
    f2, t2, S2 = spec(seg, sr, 8192)
    k2 = (f2 >= 270) & (f2 <= 950)
    top2 = S2[k2].max()
    ax2.pcolormesh(t2 + a, f2[k2], np.clip(S2[k2], top2 - 56, top2),
                   shading="gouraud", cmap="magma", rasterized=True)
    ax2.set_yscale("log")
    ax2.set_ylim(270, 950)
    # Bez tego matplotlib dokłada własne podziałki logarytmiczne NA nazwy dźwięków
    # i oś robi się nieczytelna.
    from matplotlib.ticker import NullFormatter, NullLocator
    ax2.yaxis.set_minor_locator(NullLocator())
    ax2.yaxis.set_minor_formatter(NullFormatter())
    ax2.set_yticks([294, 330, 349, 392, 440, 494, 587, 698, 880])
    ax2.set_yticklabels(["D", "E", "F", "G", "A", "H", "d", "f", "a"])
    ax2.yaxis.set_major_formatter(matplotlib.ticker.FixedFormatter(
        ["D", "E", "F", "G", "A", "H", "d", "f", "a"]))
    ax2.set_ylabel("wysokość", color=INK, fontsize=9)
    ax2.set_xlabel("czas [s]", color=INK, fontsize=9)
    ax2.set_title(
        "z bliska: nuta ląduje pół tonu obok, stoi tam dwie trzecie swojej "
        "długości, i schodzi",
        color=INK, fontsize=11, loc="left", pad=10, family="monospace")

    for ax in (ax1, ax2):
        ax.set_facecolor(PAPER)
        for s in ax.spines.values():
            s.set_color(INK)
            s.set_linewidth(0.8)
        ax.tick_params(colors=INK, labelsize=8)

    fig.text(0.008, 0.012,
             "jasność = głośność · szerokość prążka = niezgoda 40 głosów · "
             "skala logarytmiczna, bo tak słyszy ucho",
             color=INK, fontsize=8, alpha=0.65, family="monospace")
    fig.savefig(OUT, dpi=150, facecolor=PAPER, bbox_inches="tight")
    print(f"{OUT}  ({OUT.stat().st_size // 1024} kB)")
    print("wejścia podejść [s]:", [round(s, 1) for s in starts[:4]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

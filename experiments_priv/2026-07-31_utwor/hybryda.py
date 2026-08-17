"""Hybryda: linie plus szum — pełny model Serry (SMS) na naszym negatywie.

Poprzednie wywołanie zagrało tylko linie: 45 % energii obrazu, czysto, ale
chudo, bo plamy — w tym trzeci materiał Φ — nie układają się w linie i znikły.
Serra domknął to tak: po wyczytaniu linii ODEJMIJ je od obrazu, a to, co
zostanie, potraktuj jako szum o zadanym kształcie widmowym.

Dwa tory, każdy syntezowany właściwą sobie metodą:

  LINIE — bank oscylatorów z fazą całkowaną, jak poprzednio. Dla tonu faza
  musi być ciągła, więc jest liczona, nie losowana.

  PLAMY — negatyw minus odmalowane linie. To z definicji materiał szumowy,
  a szum ma fazę LOSOWĄ z natury — więc tutaj losowa faza nie jest zgadywaniem
  (jak w Griffin–Limie dla tonów), tylko poprawnym modelem. Jedna odwrotna
  transformata i gotowe, bez iteracji.

Wagi obu torów nie są ustawione ręcznie: energia szumu względem linii jest
taka, jaką miały plamy względem linii w samym obrazie.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter
from scipy.signal import istft

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wzor_kordiego as W                                     # noqa: E402
from calkowanie import synthesize, track_partials             # noqa: E402
from dluga_ekspozycja import expose, paint_same_negative      # noqa: E402

DIR = W.DIR
SR = W.SR
DF = float(W.BHZ[1] - W.BHZ[0])


def repaint(tracks, shape) -> np.ndarray:
    """Linie odmalowane z powrotem na siatkę — do odjęcia od negatywu."""
    R = np.zeros(shape)
    prof = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)
    for tr in tracks:
        for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
            b = int(round((f - W.BHZ[0]) / DF))
            lo, hi = max(0, b - 4), min(shape[0], b + 5)
            R[lo:hi, t] = np.maximum(R[lo:hi, t], a * prof[lo - b + 4: hi - b + 4])
    return R


def noise_from(N: np.ndarray) -> np.ndarray:
    """Plamy jako ukształtowany szum: losowa faza JEST tu poprawnym modelem."""
    rng = np.random.default_rng(9)
    mag = np.zeros((len(W.FREQS), N.shape[1]))
    mag[W.BAND] = gaussian_filter(N, sigma=(1.0, 2.0))
    Z = mag * np.exp(2j * np.pi * rng.random(mag.shape))
    _, x = istft(Z, SR, nperseg=W.NPER, noverlap=W.NPER - W.HOP)
    return x


def main() -> int:
    print("negatyw…", flush=True)
    S = expose(paint_same_negative()).astype(np.float64)

    print("linie…", flush=True)
    tracks = track_partials(S)
    R = repaint(tracks, S.shape)
    N = np.maximum(S - R, 0.0)
    e_lin = float((np.minimum(R, S) ** 2).sum())
    e_pla = float((N ** 2).sum())
    print(f"  {len(tracks)} linii · energia obrazu: linie {e_lin / (e_lin + e_pla) * 100:.0f}%"
          f" · plamy {e_pla / (e_lin + e_pla) * 100:.0f}%")

    n_samp = int(W.TOTAL * SR)
    print("gram linie (oscylatory, faza całkowana)…", flush=True)
    x_sin = synthesize(tracks, n_samp)
    print("szumię plamy (losowa faza, jedna transformata)…", flush=True)
    x_noi = noise_from(N)[:n_samp]
    if len(x_noi) < n_samp:
        x_noi = np.pad(x_noi, (0, n_samp - len(x_noi)))

    # wagi z obrazu, nie z ręki
    g = np.sqrt(e_pla / (e_lin + 1e-12)) * (np.sqrt((x_sin ** 2).mean())
                                            / (np.sqrt((x_noi ** 2).mean()) + 1e-12))
    x = x_sin + g * x_noi
    x *= 0.89 / (np.abs(x).max() + 1e-9)
    sf.write(DIR / "wzor_kordiego_hybryda.wav", np.stack([x, x]).T, SR,
             subtype="PCM_24")

    def purity(y):
        y = y[int(28 * SR): int(34 * SR)]
        F = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        fr = np.fft.rfftfreq(len(y), 1 / SR)
        i = np.argmax(F * ((fr > 200) & (fr < 1000)))
        peak = float((F[i - 3: i + 4] ** 2).sum())
        halo = float((F[i - 220: i + 221] ** 2).sum()) - peak
        return 10 * np.log10(peak / (halo + 1e-12))

    print(f"  czystość trzymanej składowej: {purity(x):.1f} dB "
          f"(same linie miały +7,1; zdjęcie −9,9)")

    # obraz: rozkład negatywu na dwa tory
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), facecolor=W.PAPER,
                                   gridspec_kw={"hspace": 0.35})
    for ax, M, title in ((ax1, R, "LINIE — grane oscylatorami, faza całkowana"),
                         (ax2, N, "PLAMY — grane jako ukształtowany szum "
                                  "(w tym trzeci materiał Φ)")):
        Md = 20 * np.log10(M + 1e-6)
        top = 20 * np.log10(S.max())
        ax.pcolormesh(W.T_AX, W.BHZ, np.clip(Md, top - 64, top),
                      shading="gouraud", cmap="magma", rasterized=True)
        ax.set_yscale("log")
        ax.set_ylim(W.F_LO, W.F_HI)
        ax.set_yticks([110, 440, 1760])
        ax.set_yticklabels(["110", "440", "1,8k"])
        ax.set_title(title, color=W.INK, fontsize=11, loc="left", pad=8,
                     family="monospace")
        ax.set_facecolor(W.PAPER)
        for sp in ax.spines.values():
            sp.set_color(W.INK)
        ax.tick_params(colors=W.INK, labelsize=8)
    ax2.set_xlabel("czas [s]", color=W.INK, fontsize=9)
    fig.savefig(DIR / "wzor_kordiego_hybryda.png", dpi=150, facecolor=W.PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'wzor_kordiego_hybryda.wav'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

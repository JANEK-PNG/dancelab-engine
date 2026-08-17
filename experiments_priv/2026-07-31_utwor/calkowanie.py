"""Całkowanie: ten sam negatyw, ale zamiast zdjęcia — wykonanie.

Griffin–Lim ZGADUJE fazę: sto dziesięć rund poprawiania na chybił trafił,
i wciąż 18 % rozjazdu, słyszalnego jako szklistość. Tutaj faza nie jest
zgadywana ani razu.

Obraz czytany jest jak partytura:

  1. GRZBIETY. W każdej kolumnie spektrogramu (co 23 ms) znajdywane są
     szczyty — jasne punkty, w których energia góruje nad sąsiadami.
     Wysokość szczytu doprecyzowana parabolą między binami.
  2. LINIE. Szczyty z kolejnych klatek łączone są w tory: szczyt kontynuuje
     linię, jeśli leży blisko jej ostatniej częstotliwości; inaczej rodzi
     nową. Linia bez kontynuacji umiera. (Klasyczne śledzenie partialsów
     McAulay–Quatieri.)
  3. OSCYLATORY. Każda linia dostaje własny oscylator: jego częstotliwość
     płynie po linii, głośność po jej jasności, a FAZA JEST CAŁKOWANA —
     co próbkę dokłada się dokładnie tyle obrotu, ile wynika z bieżącej
     częstotliwości: φ[n+1] = φ[n] + 2π·f[n]/SR. Licznik obrotów, nie
     zgadywanka. To ta sama zasada co sztywna siatka bitów: pozycja wynika
     z prędkości i startu, więc rozjazd jest nieosiągalny z definicji.

Cena, powiedziana wprost: partytura czyta tylko to, co jest LINIĄ. Plamy —
w tym część trzeciego materiału Φ — do linii się nie składają i znikają.
Ile dokładnie znikło, jest zmierzone i wypisane, nie przemilczane.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wzor_kordiego as W                                     # noqa: E402
from dluga_ekspozycja import expose, paint_same_negative      # noqa: E402

DIR = W.DIR
SR = W.SR
HOP = W.HOP
DF = float(W.BHZ[1] - W.BHZ[0])

MAX_POLY = 70            # ile linii może grać naraz
MIN_FRAMES = 4           # linia krótsza niż ~90 ms to pyłek, nie nuta
FADE = int(0.005 * SR)   # 5 ms na narodziny i śmierć linii


def find_peaks_col(col: np.ndarray, thresh: float):
    """Szczyty jednej kolumny, z parabolicznym doprecyzowaniem wysokości."""
    c = col
    idx = np.where((c[1:-1] > c[:-2]) & (c[1:-1] > c[2:]) & (c[1:-1] > thresh))[0] + 1
    out = []
    for i in idx:
        d = 0.5 * (c[i - 1] - c[i + 1]) / (c[i - 1] - 2 * c[i] + c[i + 1] + 1e-12)
        d = float(np.clip(d, -0.5, 0.5))
        out.append((float(W.BHZ[i] + d * DF), float(c[i])))
    out.sort(key=lambda p: -p[1])
    return out[:MAX_POLY]


def track_partials(S: np.ndarray):
    """Łączenie szczytów w linie — partytura wyczytana z obrazu."""
    thresh = S.max() * 3e-4
    live: list[dict] = []
    done: list[dict] = []
    for t in range(S.shape[1]):
        peaks = find_peaks_col(S[:, t], thresh)
        used = [False] * len(peaks)
        for tr in live:
            best, bd = -1, 1e9
            for k, (f, a) in enumerate(peaks):
                if used[k]:
                    continue
                d = abs(f - tr["f"][-1])
                if d < bd:
                    best, bd = k, d
            tol = max(0.035 * tr["f"][-1], 1.6 * DF)
            if best >= 0 and bd <= tol:
                f, a = peaks[best]
                used[best] = True
                tr["t"].append(t)
                tr["f"].append(f)
                tr["a"].append(a)
            else:
                tr["dead"] = True
        done += [tr for tr in live if tr.get("dead")]
        live = [tr for tr in live if not tr.get("dead")]
        for k, (f, a) in enumerate(peaks):
            if not used[k]:
                live.append({"t": [t], "f": [f], "a": [a]})
    done += live
    return [tr for tr in done
            if len(tr["t"]) >= MIN_FRAMES and max(tr["a"]) > S.max() * 1e-3]


def synthesize(tracks: list[dict], n_samples: int) -> np.ndarray:
    """Bank oscylatorów: każda linia gra, faza sumowana co próbkę."""
    out = np.zeros(n_samples)
    rng = np.random.default_rng(3)
    for tr in tracks:
        fr = np.array(tr["t"], dtype=np.float64)
        p0 = int(fr[0] * HOP)
        p1 = min(int(fr[-1] * HOP) + FADE, n_samples)
        if p1 - p0 < FADE * 2:
            continue
        n = np.arange(p0, p1)
        f = np.interp(n / HOP, fr, tr["f"])
        a = np.interp(n / HOP, fr, tr["a"])
        # CAŁKOWANIE FAZY: licznik obrotów. Start losowy (żeby narodziny
        # tysiąca linii nie klikały w zgodnej fazie), dalej czysta suma.
        ph = 2 * np.pi * np.cumsum(f) / SR + rng.uniform(0, 2 * np.pi)
        seg = a * np.sin(ph)
        m = len(seg)
        k = min(FADE, m // 2)
        seg[:k] *= np.linspace(0, 1, k)
        seg[-k:] *= np.linspace(1, 0, k)
        out[p0:p1] += seg
    return out


def main() -> int:
    print("maluję ten sam negatyw…", flush=True)
    S = expose(paint_same_negative()).astype(np.float64)

    print("czytam grzbiety…", flush=True)
    tracks = track_partials(S)
    print(f"  linii w partyturze: {len(tracks)}")

    # ile obrazu weszło do partytury: odmalowanie linii z powrotem na siatkę
    R = np.zeros_like(S)
    prof = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)
    for tr in tracks:
        for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
            b = int(round((f - W.BHZ[0]) / DF))
            lo, hi = max(0, b - 4), min(S.shape[0], b + 5)
            R[lo:hi, t] = np.maximum(R[lo:hi, t], a * prof[lo - b + 4: hi - b + 4])
    cap = float((np.minimum(R, S) ** 2).sum() / (S ** 2).sum())
    print(f"  energia obrazu przeczytana jako linie: {cap * 100:.0f}% "
          f"(reszta to plamy — one znikają, to cena partytury)")

    print("gram…", flush=True)
    x = synthesize(tracks, int(W.TOTAL * SR))
    x *= 0.89 / (np.abs(x).max() + 1e-9)
    sf.write(DIR / "wzor_kordiego_calkowanie.wav", np.stack([x, x]).T, SR,
             subtype="PCM_24")

    # czystość: jedna trzymana składowa, ile energii siedzi W niej,
    # a ile rozlane obok — na obu wersjach, ta sama chwila
    def purity(path):
        y, _ = sf.read(path, dtype="float64")
        y = y.mean(axis=1)[int(28 * SR): int(34 * SR)]
        F = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        fr = np.fft.rfftfreq(len(y), 1 / SR)
        band = (fr > 200) & (fr < 1000)
        i = np.argmax(F * band)
        peak = float((F[i - 3: i + 4] ** 2).sum())
        halo = float((F[i - 220: i + 221] ** 2).sum()) - peak
        return 10 * np.log10(peak / (halo + 1e-12))

    for lab, p in (("zdjęcie (Griffin–Lim ×110)", DIR / "wzor_kordiego_ekspozycja.wav"),
                   ("całkowanie (oscylatory)  ", DIR / "wzor_kordiego_calkowanie.wav")):
        print(f"  {lab}: składowa nad własnym halo {purity(p):5.1f} dB")

    # obraz: partytura naniesiona na negatyw
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=W.PAPER)
    Sd = 20 * np.log10(S + 1e-6)
    top = Sd.max()
    ax.pcolormesh(W.T_AX, W.BHZ, np.clip(Sd, top - 64, top),
                  shading="gouraud", cmap="magma", rasterized=True)
    for tr in tracks:
        if len(tr["t"]) < 12:
            continue
        ax.plot(np.array(tr["t"]) * HOP / SR, tr["f"], color="#7fd8d8",
                lw=0.45, alpha=0.5)
    ax.set_yscale("log")
    ax.set_ylim(W.F_LO, W.F_HI)
    ax.set_yticks([110, 220, 440, 880, 1760, 3520])
    ax.set_yticklabels(["110", "220", "440", "880", "1,8k", "3,5k"])
    ax.set_xlabel("czas [s]", color=W.INK, fontsize=9)
    ax.set_ylabel("częstotliwość [Hz]", color=W.INK, fontsize=9)
    ax.set_title(f"partytura wyczytana z negatywu — {len(tracks)} linii, "
                 f"każda gra własnym oscylatorem z fazą całkowaną",
                 color=W.INK, fontsize=12, loc="left", pad=10, family="monospace")
    ax.set_facecolor(W.PAPER)
    for sp in ax.spines.values():
        sp.set_color(W.INK)
    ax.tick_params(colors=W.INK, labelsize=8)
    fig.savefig(DIR / "wzor_kordiego_calkowanie.png", dpi=150, facecolor=W.PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'wzor_kordiego_calkowanie.wav'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Co jest między moimi dźwiękami, tam gdzie jest czarno.

Pytanie Janka, zadane jego własnym wzorem: miks minus źródła = to, co pomiędzy.
W szwie źródłami były dwa utwory i reszta była ruchami rąk. Tutaj źródłem są
nuty zagrane na sucho, a resztą jest wszystko, czego żadna nuta nie zagrała.

Więc: utwór minus wersja sucha (dopasowana najmniejszymi kwadratami, żeby nie
odjąć za dużo ani za mało) = wnętrze czerni. Metoda ta sama co w seam_decompose,
dosłownie ten sam ruch.

Trzy pomiary tego, co zostało:

  1. ILE TEGO JEST — energia reszty względem całości, w oknach 1 s, na osi
     czasu. Osobno w miejscach, gdzie nuty grają, i w przerwach między
     podejściami, gdzie „nie ma nic".
  2. JAK DŁUGO TRWA — po ostatniej nucie każdego podejścia mierzymy, ile
     sekund mija, zanim reszta zejdzie o 60 dB. To jest czas, przez który
     przestrzeń jeszcze odpowiada, choć nikt już nie gra.
  3. CO PAMIĘTA — widmo reszty w przerwie porównane z widmem nut, które
     grały tuż przed nią. Korelacja mówi, na ile czerń jest echem tego,
     co było, a na ile własnym dźwiękiem pokoju.

Wynik gra też jako plik: sama reszta, podniesiona do słyszalności.
"""

from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.signal import stft

DIR = pathlib.Path("experiments_priv/2026-07-31_utwor")
PAPER = "#efece4"
INK = "#141414"
ACC = "#e0483c"


def main() -> int:
    wet, sr = sf.read(DIR / "autoportret.wav", dtype="float64")
    dry, _ = sf.read(DIR / "autoportret_dry.wav", dtype="float64")
    wet = wet.mean(axis=1)
    # wersja mokra ma stereo z przesunięć ±130 próbek — środek jest wspólny
    n = min(len(wet), len(dry))
    wet, dry = wet[:n], dry[:n]

    # Dopasowanie suchego do miksu najmniejszymi kwadratami — jak fit_gains
    # w seam_decompose: nie zakładamy, ile suchego jest w środku, mierzymy.
    g = float(np.dot(wet, dry) / (np.dot(dry, dry) + 1e-12))
    rest = wet - g * dry
    print(f"udział suchego sygnału w miksie: {g:.3f}")
    print(f"energia reszty: {np.sqrt((rest ** 2).mean()) / np.sqrt((wet ** 2).mean()) * 100:.1f}% RMS całości")

    # ── 1. ile tego jest, w czasie ──
    w = int(0.5 * sr)
    tt, share, level = [], [], []
    for i in range(0, n - w, w):
        e_all = float((wet[i:i + w] ** 2).mean())
        e_r = float((rest[i:i + w] ** 2).mean())
        tt.append(i / sr)
        share.append(e_r / (e_all + 1e-15) * 100)
        level.append(10 * np.log10(e_r + 1e-15))
    tt, share, level = np.array(tt), np.array(share), np.array(level)

    # przerwy = tam gdzie suchy sygnał praktycznie nie istnieje
    dry_env = np.array([np.sqrt((dry[i:i + w] ** 2).mean()) for i in range(0, n - w, w)])
    gap = dry_env < dry_env.max() * 0.004
    print(f"\nudział reszty tam, gdzie nuty grają : {share[~gap].mean():5.1f}%")
    print(f"udział reszty w czerni (przerwy)    : {share[gap].mean():5.1f}%")

    # ── 2. jak długo czerń dźwięczy ──
    # koniec każdego bloku nut: ostatnia chwila, gdzie dry jest żywy przed >2 s ciszy
    ends = []
    for i in range(1, len(gap)):
        if not gap[i - 1] and gap[i] and (i + 4 >= len(gap) or gap[i:i + 4].all()):
            ends.append(i * 0.5)
    # Zanik wolno mierzyć tylko DO wejścia następnych nut — pierwsza wersja
    # tego nie pilnowała, wpadała w pogłos kolejnego podejścia i raportowała
    # 70 s tam, gdzie przerwa ma pięć. Zamiast progu absolutnego: ile decybeli
    # czerń zdążyła opaść przez całą przerwę, i ile to daje na sekundę.
    starts_next = []
    for e in ends[:4]:
        nx = [i * 0.5 for i in range(1, len(gap)) if gap[i - 1] and not gap[i]
              and i * 0.5 > e + 0.5]
        starts_next.append(min(nx) if nx else n / sr)
    print("\njak czerń wybrzmiewa (w obrębie własnej przerwy):")
    for k, (e, nx) in enumerate(zip(ends[:4], starts_next)):
        i0, i1 = int((e + 0.2) * sr), int(max(e + 0.7, nx - 0.3) * sr)
        if i1 <= i0 + sr // 2:
            continue
        e0 = float((rest[i0:i0 + sr // 2] ** 2).mean())
        e1 = float((rest[i1 - sr // 2:i1] ** 2).mean())
        drop = 10 * np.log10((e0 + 1e-15) / (e1 + 1e-15))
        span = (i1 - i0) / sr
        print(f"  po podejściu {k + 1}: {drop:5.1f} dB w {span:4.1f} s "
              f"({drop / span:4.1f} dB/s → do -60 dB potrzeba {60 / max(drop / span, 1e-3):.0f} s)")

    # ── 3. co czerń pamięta ──
    corrs = []
    for e in ends[:4]:
        i0 = int(e * sr)
        before = wet[max(0, i0 - int(3 * sr)):i0]
        after = rest[i0 + int(0.3 * sr): i0 + int(3.3 * sr)]
        if len(after) < sr:
            continue
        fb, _, Sb = stft(before, sr, nperseg=4096)
        fa, _, Sa = stft(after, sr, nperseg=4096)
        mb = np.abs(Sb).mean(axis=1)
        ma = np.abs(Sa).mean(axis=1)
        k = (fb > 150) & (fb < 5000)
        c = float(np.corrcoef(np.log(mb[k] + 1e-12), np.log(ma[k] + 1e-12))[0, 1])
        corrs.append(c)
    print("\nkorelacja widma czerni z tym, co grało przed nią:")
    for k, c in enumerate(corrs):
        print(f"  po podejściu {k + 1}: {c:.3f}")

    # ── obraz ──
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), facecolor=PAPER,
                                   height_ratios=[1.15, 1],
                                   gridspec_kw={"hspace": 0.4})
    f, t, S = stft(rest, sr, nperseg=8192, noverlap=int(8192 * 0.82))
    Sd = 20 * np.log10(np.abs(S) + 1e-10)
    kk = (f >= 90) & (f <= 4200)
    top = Sd[kk].max()
    ax1.pcolormesh(t, f[kk], np.clip(Sd[kk], top - 70, top),
                   shading="gouraud", cmap="magma", rasterized=True)
    ax1.set_yscale("log")
    ax1.set_ylim(90, 4200)
    ax1.set_yticks([110, 220, 440, 880, 1760, 3520])
    ax1.set_yticklabels(["110", "220", "440", "880", "1,8k", "3,5k"])
    ax1.set_title("TO, CZEGO ŻADNA NUTA NIE ZAGRAŁA — miks minus źródła, "
                  "twoim wzorem", color=INK, fontsize=12, loc="left", pad=10,
                  family="monospace")
    ax1.set_ylabel("częstotliwość [Hz]", color=INK, fontsize=9)

    ax2.fill_between(tt, 0, share, color=ACC, alpha=0.75, lw=0)
    for e in ends[:4]:
        ax2.axvline(e, color=INK, lw=0.8, ls=(0, (3, 3)), alpha=0.5)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("udział reszty w całości [%]", color=INK, fontsize=9)
    ax2.set_xlabel("czas [s]", color=INK, fontsize=9)
    ax2.set_title("w przerwach reszta to CAŁOŚĆ tego, co słychać",
                  color=INK, fontsize=11, loc="left", pad=8, family="monospace")

    for ax in (ax1, ax2):
        ax.set_facecolor(PAPER)
        for sp in ax.spines.values():
            sp.set_color(INK)
            sp.set_linewidth(0.8)
        ax.tick_params(colors=INK, labelsize=8)

    fig.savefig(DIR / "czern.png", dpi=150, facecolor=PAPER, bbox_inches="tight")
    print(f"\nobraz: {DIR / 'czern.png'}")

    # sama czerń jako dźwięk, podniesiona do słyszalności
    out = rest / (np.abs(rest).max() + 1e-9) * 0.85
    sf.write(DIR / "czern.wav", np.stack([out, out]).T, sr, subtype="PCM_24")
    print(f"dźwięk: {DIR / 'czern.wav'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

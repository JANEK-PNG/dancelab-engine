"""Dowód przewidziane-kontra-zmierzone dla pełnego T — i jego uczciwy wynik.

Pytanie: czy odstępstwo od legendy (cele kwantyzacji z żywego B zamiast
wiecznej drabiny) DOCIERA do dźwięku? Miara: policz obraz S dwa razy na tych
samych polach (legenda / żywe cele), weź różnicę ΔS — to jest PRZEWIDZIANA
zmiana; weź różnicę widm obu wyrenderowanych plików po wyrównaniu gainu —
to jest ZMIERZONA zmiana; skoreluj.

Wynik (2026-08-04, pliki rubato.wav i pelne_t.wav):

  skala przewidzianej zmiany:  środek 1,0% RMS obrazu · góra 0,4%
  podłoga chaosu render-render: środek 9,3% RMS widma · góra 15,5%
  r(przewidziane, zmierzone):  środek +0,18 · góra +0,05 · nachylenie ~0

WERDYKT: odstępstwo jest we wzorze i w obrazie, ale 10–40× PONIŻEJ podłogi
chaosu silnika (losowe fazy startowe torów i realizacja szumu różnią dwa
rendery mocniej niż nowe T). Przy parametrach legendy (siła 0,65, ±9 binów,
wygładzenie 0,45 s) żywe cele pokrywają się z drabiną na ~92% energii ręki —
legenda była już w 92% pełnym T. Odstępstwo mieszka tylko tam, gdzie
harmoniczne różnych dźwięków zlewają się w jeden grzbiet, i tam, gdzie
w ostatniej tercji Φ wlewa się w B.

Wcześniejsze podejścia do dowodu (dla historii, obie miary ODRZUCONE):
  1. mediana odległości szczytów audio do celów vs drabiny — zbiory różnej
     gęstości, gęstszy zawsze wygrywa;
  2. głosowanie „bliżej żywego" w strefach rozstrzygających — pręt zakładał
     pełną kwantyzację, a siła 0,65 + wygładzenie zostawiają energię w pół
     drogi; do tego bez wyrównania gainu różnica widm to głównie głośność
     (35 tys. komórek „pojawionych" vs 2,4 tys. „znikłych" — po wyrównaniu
     6,3 tys. vs 6,4 tys.).
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.signal import stft

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hybryda_wielorozdzielcza as hw                          # noqa: E402
ORIG_BA = hw.transform_BA                   # legenda — ZANIM pelne_t podmieni
import pelne_t as pt                                            # noqa: E402
import rubato as rb                                             # noqa: E402

SR = hw.SR
T0, T1 = 40.0, 148.0


def pelny_S(transform, fields0):
    hw.transform_BA = transform
    pt.PELNE_B.update({n: fields0[n][1] for n in fields0})
    pt.PASS = 1
    p1, _ = hw.one_pass(fields0)
    f2 = {}
    for name, c in hw.CAN.items():
        A, B = fields0[name]
        Phic = p1[name][1]
        fb = c.fb[None, :]
        f2[name] = ((A + 0.35 * fb * Phic * A.max()).astype(np.float32),
                    (B + 0.25 * fb * Phic * B.max()).astype(np.float32))
    pt.PELNE_B.update({n: f2[n][1] for n in f2})
    pt.PASS = 0
    p2, _ = hw.one_pass(f2)
    out = {}
    for name, c in hw.CAN.items():
        g = np.interp(c.tax, rb.T, rb.GAM).astype(np.float32)
        out[name] = p2[name][0] * c.intro[None, :] * g[None, :]
    return out


def stft_band(path, nper, lo, hi):
    hop = {8192: 2048, 1024: 512}[nper]
    y, _ = sf.read(path, start=int(T0 * SR), stop=int(T1 * SR), dtype="float64")
    f, t, Z = stft(y.mean(axis=1), SR, nperseg=nper, noverlap=nper - hop)
    sel = (f >= lo) & (f <= hi)
    return np.abs(Z[sel])


def main() -> int:
    przes = rb.paint_all_rubato(rb.EV)
    fields0 = {n: (c.A, c.B) for n, c in hw.CAN.items()}
    print("obraz z żywym T…", flush=True)
    S_liv = pelny_S(pt.transform_BA_zywe, fields0)
    pt.ODSTEPSTWO.clear()
    print("obraz z legendą…", flush=True)
    S_leg = pelny_S(ORIG_BA, fields0)
    hw.transform_BA = pt.transform_BA_zywe

    for name, nper in (("srodek", 8192), ("gora", 1024)):
        c = hw.CAN[name]
        j0, j1 = int(T0 / c.dt), int(T1 / c.dt)
        dS = (S_liv[name] - S_leg[name])[:, j0:j1].astype(np.float64)
        S0 = S_leg[name][:, j0:j1]
        Ma = stft_band(DIR_RUB, nper, c.bhz[0], c.bhz[-1])
        Mb = stft_band(DIR_PEL, nper, c.bhz[0], c.bhz[-1])
        n = min(Ma.shape[1], Mb.shape[1], dS.shape[1])
        nb = min(Ma.shape[0], dS.shape[0])
        Ma, Mb, dS = Ma[:nb, :n], Mb[:nb, :n], dS[:nb, :n]
        g = np.sqrt((Ma ** 2).sum() / (Mb ** 2).sum())
        dA = Mb * g - Ma
        sel = np.abs(dS) > np.percentile(np.abs(dS), 99)
        r = float(np.corrcoef(dS[sel], dA[sel])[0, 1])
        print(f"{name}: ΔS/S {np.sqrt((dS**2).mean()) / np.sqrt((S0**2).mean()) * 100:.1f}%"
              f" · chaos {np.sqrt((dA**2).mean()) / np.sqrt((Ma**2).mean()) * 100:.1f}%"
              f" · r(przewidziane, zmierzone) {r:+.3f}")
    print("\nwerdykt: odstępstwo w obrazie realne (patrz strażnicy pelne_t),")
    print("ale przy parametrach legendy ginie pod podłogą chaosu renderów —")
    print("z audio NIEDOWODLIWE. Legenda była już w ~92% pełnym T.")
    return 0


DIR = pathlib.Path(__file__).resolve().parent
DIR_RUB = DIR / "rubato.wav"
DIR_PEL = DIR / "pelne_t.wav"

if __name__ == "__main__":
    raise SystemExit(main())

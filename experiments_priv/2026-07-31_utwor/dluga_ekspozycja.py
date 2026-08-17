"""Ten sam negatyw, nowe wywołanie: ISO 100 i długi czas naświetlania.

Janek o pierwszym renderze wzoru Kordiego powiedział to samo, co kiedyś
o automiksie: zdejmij ISO z 6000 do 100 i naświetlaj długo. W tym syntezatorze
te pokrętła istnieją naprawdę:

  ISO = szum odzyskiwania fazy. Griffin–Lim po 38 iteracjach zostawia szkliste
  ziarno, które potem normalizacja do szczytu podbija — czyli czułość w górę na
  słabym świetle. Schodzimy: okno analizy 4096 → 8192 (dłuższa migawka na
  klatkę), zakładka 75 % → 87,5 % (więcej klatek uśrednia to samo światło),
  i 110 iteracji Z PĘDEM zamiast 38 (faza zbiega, ziarno znika u źródła,
  zamiast być maskowane głośnością).

  DŁUGI CZAS NAŚWIETLANIA = akumulacja światła. Na namalowany spektrogram
  nakładamy nieszczelną całkę wzdłuż czasu: każda nuta zostawia smugę, która
  gaśnie ze stałą ~1,4 s — dokładnie jak smugi reflektorów na nocnym zdjęciu.
  To nie jest pogłos dodany do dźwięku; to jest naświetlanie samego obrazu,
  zanim stanie się dźwiękiem.

Kompozycja jest identyczna co do liczby — ten sam seed, te same pola A, B,
C·R_D, Syn·Φ, ta sama pamięć H. Zmienia się wyłącznie wywołanie.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.signal import istft, lfilter, stft

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wzor_kordiego as W                                    # noqa: E402

DIR = W.DIR
PAPER, INK, ACC = W.PAPER, W.INK, W.ACC
SR = W.SR

# nowe wywołanie
NPER2, HOP2 = 8192, 512          # dłuższa migawka, gęstsza zakładka
GL_ITERS = 110
GL_MOMENTUM = 0.99
TRAIL_SEC = 1.4                  # czas naświetlania: stała zaniku smugi


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def paint_same_negative() -> np.ndarray:
    """Dokładnie ta sama kompozycja co w wzor_kordiego.main(), bez renderu."""
    A = W.paint_A()
    B = W.paint_B()
    T_AX = W.T_AX
    mA = np.clip(smoothstep((20 - T_AX) / 6) + smoothstep((T_AX - 34) / 6), 0, 1)
    mB = smoothstep((T_AX - 20) / 6)
    fade_out = 1 - smoothstep((T_AX - 148) / 14)
    mA = mA * fade_out
    mB = mB * np.clip(fade_out + 0.15, 0, 1)

    _, _, _, _, Phi1, _, _ = W.one_pass(A, B, mA, mB)
    fb = smoothstep((T_AX - 112) / 20)[None, :]
    A2 = A + 0.35 * (fb * Phi1) * A.max()
    B2 = B + 0.25 * (fb * Phi1) * B.max()
    S, *_ = W.one_pass(A2.astype(np.float32), B2.astype(np.float32), mA, mB)
    S *= smoothstep(T_AX / 4)[None, :]
    return S


def expose(S: np.ndarray) -> np.ndarray:
    """Długi czas naświetlania: nuty zostawiają smugi na kliszy."""
    lam = float(np.exp(-(W.HOP / SR) / TRAIL_SEC))
    trail = lfilter([1 - lam], [1, -lam], S, axis=1)
    return S + 1.1 * trail.astype(np.float32)


def to_fine_grid(S: np.ndarray) -> np.ndarray:
    """Negatyw malowany na siatce 4096/1024 → klisza 8192/512."""
    freqs2 = np.fft.rfftfreq(NPER2, 1 / SR)
    frames2 = int(W.TOTAL * SR / HOP2)
    t2 = np.arange(frames2) * HOP2 / SR
    # najpierw czas
    St = np.empty((S.shape[0], frames2), dtype=np.float64)
    for r in range(S.shape[0]):
        St[r] = np.interp(t2, W.T_AX, S[r])
    # potem częstotliwość
    out = np.zeros((len(freqs2), frames2), dtype=np.float64)
    for c in range(frames2):
        out[:, c] = np.interp(freqs2, W.FREQS[W.BAND], St[:, c],
                              left=0.0, right=0.0)
    return out


def griffin_lim_momentum(mag: np.ndarray) -> tuple[np.ndarray, float]:
    """Odzyskiwanie fazy z pędem (szybki Griffin–Lim)."""
    rng = np.random.default_rng(5)
    phase = np.exp(2j * np.pi * rng.random(mag.shape))
    prev = None
    x = None
    for _ in range(GL_ITERS):
        _, x = istft(mag * phase, SR, nperseg=NPER2, noverlap=NPER2 - HOP2)
        _, _, Z = stft(x, SR, nperseg=NPER2, noverlap=NPER2 - HOP2)
        Z = Z[:, : mag.shape[1]]
        if Z.shape[1] < mag.shape[1]:
            Z = np.pad(Z, ((0, 0), (0, mag.shape[1] - Z.shape[1])))
        step = Z if prev is None else Z + GL_MOMENTUM * (Z - prev)
        prev = Z
        phase = np.exp(1j * np.angle(step))
    err = float(np.linalg.norm(np.abs(Z) - mag) / (np.linalg.norm(mag) + 1e-12))
    return x, err


def main() -> int:
    print("maluję ten sam negatyw…", flush=True)
    S = paint_same_negative()
    S = expose(S)
    print("przenoszę na drobniejszą kliszę (8192/512)…", flush=True)
    mag = to_fine_grid(S)
    mag /= mag.max() + 1e-12
    print(f"wywołuję: Griffin–Lim ×{GL_ITERS} z pędem {GL_MOMENTUM}…", flush=True)
    x, err = griffin_lim_momentum(mag)
    x = x[: int(W.TOTAL * SR)]
    x *= 0.89 / (np.abs(x).max() + 1e-9)
    print(f"błąd rekonstrukcji fazy: {err * 100:.1f}% (v1 przy 38 iteracjach był liczony bez pędu)")

    sf.write(DIR / "wzor_kordiego_ekspozycja.wav", np.stack([x, x]).T, SR,
             subtype="PCM_24")

    # ile światła realnie wpadło: gęstość energii względem szczytu
    v1, _ = sf.read(DIR / "wzor_kordiego.wav", dtype="float64")
    v1 = v1.mean(axis=1)
    for lab, y in (("ISO 6000 (v1)", v1), ("ISO 100 + smugi (v2)", x)):
        rms = 20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-12)
        print(f"  {lab:22s} rms {rms:6.1f} dBFS (szczyt -1)")

    # obraz naświetlonej kliszy
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=PAPER)
    Sd = 20 * np.log10(S + 1e-6)
    top = Sd.max()
    ax.pcolormesh(W.T_AX, W.BHZ, np.clip(Sd, top - 64, top),
                  shading="gouraud", cmap="magma", rasterized=True)
    ax.set_yscale("log")
    ax.set_ylim(W.F_LO, W.F_HI)
    ax.set_yticks([110, 220, 440, 880, 1760, 3520])
    ax.set_yticklabels(["110", "220", "440", "880", "1,8k", "3,5k"])
    ax.set_ylabel("częstotliwość [Hz]", color=INK, fontsize=9)
    ax.set_xlabel("czas [s]", color=INK, fontsize=9)
    ax.set_title("ta sama kompozycja, długi czas naświetlania — każda nuta "
                 "zostawia smugę (stała 1,4 s)",
                 color=INK, fontsize=12, loc="left", pad=10, family="monospace")
    ax.set_facecolor(PAPER)
    for sp in ax.spines.values():
        sp.set_color(INK)
    ax.tick_params(colors=INK, labelsize=8)
    fig.savefig(DIR / "wzor_kordiego_ekspozycja.png", dpi=150, facecolor=PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'wzor_kordiego_ekspozycja.wav'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

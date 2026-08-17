"""S(f,t;F) = A + B + C·R_D(A,B) + Syn·Φ(A,B,H;F) — wzór Kordiego, zagrany.

Utwór jest MALOWANY na spektrogramie: najpierw powstaje obraz energii S(f,t),
dopiero potem faza jest odzyskiwana iteracyjnie (Griffin–Lim) i obraz staje się
dźwiękiem. Czyli dosłownie tak, jak napisał Kord — to reguła kompozycyjna do
malowania relacji, nie równanie fizyczne.

Jak każdy składnik wzoru wygląda tutaj:

  A(f,t)   ręka — trzy meandrujące linie melodyczne w d-doryckiej, szerokie
           i dryfujące. Ta sama natura co głos A w in_between.
  B(f,t)   siatka — akord w dokładnych stosunkach harmonicznych, bramkowany
           ósemkami w tempie ramy. Wysokie, wąskie prążki.
  C(f,t)   sprzężenie — rośnie w czasie i tylko tam, gdzie oba pola mają
           energię: C = rampa(t) · √(Ā·B̄). Na początku zero: A i B
           przedstawiają się OSOBNO, zgodnie z mapą Kordiego.
  D(f,t)   kierunek — dodatni na starcie (ręka odkształca siatkę), przechodzi
           przez zero w połowie i kończy ujemnie (siatka dyscyplinuje rękę).
           Do tego zależność od pasma: w dole D bardziej dodatni.
  T_(A→B)  siatka gięta przez rękę: prążki B są przeciągane wzdłuż osi f
           w stronę grzbietów A (deformacja geometrii, nie głośności),
           a bramka B rozmywa się tam, gdzie A jest obecne.
  T_(B→A)  ręka kwantowana przez siatkę: energia A jest ściągana w stronę
           najbliższej harmonicznej B i częściowo przejmuje jej bramkę.
  R_D      = σ(D)·T_(A→B) + [1−σ(D)]·T_(B→A) — dosłownie.
  Φ        trzeci materiał: sploty widm A i B wzdłuż osi częstotliwości,
           czyli składowe sumacyjne i różnicowe — energia na częstotliwościach,
           których NIE MA w żadnym źródle. To jest to samo zjawisko, które
           w in_between robił tanh, tu namalowane wprost.
  H        pamięć: nieszczelna całka po historii oddziaływań C·R_D.
           Φ jest ważone przez H, więc trzeci materiał rośnie tam, gdzie
           WCZEŚNIEJ działo się dużo — przeszłość kształtuje dalszy rozwój.
  F        rama: 168 s, ósemki przy 84 BPM, d-dorycka, pasmo 55–6800 Hz,
           dynamika bez kompresji, szczyt −1 dBFS.

Sprzężenie zwrotne (ostatnie zdanie mapy Kordiego): po pierwszym przebiegu
Φ wpływa z powrotem na A i B w ostatniej jednej trzeciej utworu i cały wzór
jest liczony DRUGI raz z tak zmienionymi polami. Utwór kończy się na Φ.
"""

from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from scipy.signal import istft, stft

DIR = pathlib.Path("experiments_priv/2026-07-31_utwor")
PAPER, INK, ACC = "#efece4", "#141414", "#e0483c"

SR = 44100
NPER, HOP = 4096, 1024
TOTAL = 168.0
BPM = 84.0                       # rama F: ósemka = 0,357 s
F_LO, F_HI = 55.0, 6800.0

rng = np.random.default_rng(13)

FRAMES = int(TOTAL * SR / HOP)
FREQS = np.fft.rfftfreq(NPER, 1 / SR)
BAND = np.where((FREQS >= F_LO) & (FREQS <= F_HI))[0]
NB = len(BAND)
BHZ = FREQS[BAND]
T_AX = np.arange(FRAMES) * HOP / SR

DORIAN = [50, 52, 53, 55, 57, 59, 60]     # D E F G A H C


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def bin_of(f: float) -> float:
    return float(np.interp(f, BHZ, np.arange(NB)))


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ridge(field: np.ndarray, fb: float, t0: int, t1: int,
          amp: float, width: float) -> None:
    """Jedna pozioma smuga energii: nuta od klatki t0 do t1."""
    b = np.arange(NB)
    prof = np.exp(-0.5 * ((b - fb) / width) ** 2)
    n = t1 - t0
    if n <= 0:
        return
    env = np.ones(n)
    a = min(n, max(3, n // 6))
    env[:a] = np.linspace(0, 1, a) ** 1.5
    env[-a:] *= np.linspace(1, 0.25, a)
    field[:, t0:t1] += amp * prof[:, None] * env[None, :]


# ── A: ręka ─────────────────────────────────────────────────────────
def paint_A() -> np.ndarray:
    A = np.zeros((NB, FRAMES), dtype=np.float32)
    for _ in range(3):
        deg = int(rng.integers(0, 7))
        octv = int(rng.integers(0, 2))
        t = int(rng.uniform(0, 4) * SR / HOP)
        while t < FRAMES - 10:
            dur = int(rng.uniform(3.2, 6.5) * SR / HOP)
            deg = int(np.clip(deg + rng.integers(-2, 3), 0, 6))
            if rng.random() < 0.15:
                octv = 1 - octv
            m = DORIAN[deg] + 12 * octv
            drift = rng.normal(0, 0.35)              # ręka nie trafia idealnie
            for h in range(1, 6):
                fb = bin_of(hz(m + drift) * h)
                if fb < NB - 3:
                    ridge(A, fb, t, min(t + dur, FRAMES),
                          1.0 / h ** 1.3, 2.6 + 0.5 * h)
            t += dur + int(rng.uniform(0.2, 1.2) * SR / HOP)
    return gaussian_filter(A, sigma=(1.2, 2.0))


# ── B: siatka ───────────────────────────────────────────────────────
B_PITCHES = [50, 57, 62, 66, 69]           # D A d fis a — siatka ma własne zdanie
B_HARM_BINS: list[float] = []
for m in B_PITCHES:
    for h in range(1, 9):
        f = hz(m) * h
        if F_LO < f < F_HI:
            B_HARM_BINS.append(bin_of(f))
B_HARM_BINS = sorted(B_HARM_BINS)


def gate_of() -> np.ndarray:
    """Bramka ósemkowa ramy F: ostra, z akcentem co cztery."""
    g = np.zeros(FRAMES, dtype=np.float32)
    step = 60.0 / BPM / 2
    k = 0
    tt = 0.0
    while tt < TOTAL:
        i = int(tt * SR / HOP)
        L = int(step * 0.72 * SR / HOP)
        j = min(i + L, FRAMES)
        if j > i:
            g[i:j] = np.linspace(1, 0.15, j - i) ** 1.4 * (1.3 if k % 4 == 0 else 1.0)
        tt += step
        k += 1
    return g


GATE = gate_of()


def paint_B() -> np.ndarray:
    B = np.zeros((NB, FRAMES), dtype=np.float32)
    for m in B_PITCHES:
        for h, a in ((1, 1.0), (2, 0.45), (3, 0.25), (4, 0.14), (6, 0.07), (8, 0.04)):
            f = hz(m) * h
            if not (F_LO < f < F_HI):
                continue
            fb = bin_of(f)
            prof = np.exp(-0.5 * ((np.arange(NB) - fb) / 1.1) ** 2)
            B += a * prof[:, None] * GATE[None, :]
    return B.astype(np.float32)


# ── deformacje ──────────────────────────────────────────────────────
def warp_columns(X: np.ndarray, disp: np.ndarray) -> np.ndarray:
    """Przesuń każdą kolumnę wzdłuż osi f o pole disp (w binach)."""
    out = np.empty_like(X)
    idx = np.arange(NB, dtype=np.float64)
    for t in range(X.shape[1]):
        src = np.clip(idx - disp[:, t], 0, NB - 1)
        out[:, t] = np.interp(src, idx, X[:, t])
    return out


def transform_AB(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """T_(A→B): siatka gięta przez rękę — geometria B idzie za grzbietami A."""
    grad = np.gradient(gaussian_filter(A, sigma=(3.0, 6.0)), axis=0)
    disp = 7.0 * grad / (np.abs(grad).max() + 1e-9)
    envA = gaussian_filter1d(A.mean(axis=0), 8)
    envA /= envA.max() + 1e-9
    bent = warp_columns(B, disp)
    # bramka rozmywa się tam, gdzie ręka jest obecna
    soft = gaussian_filter1d(bent, sigma=4, axis=1)
    return bent * (1 - 0.6 * envA)[None, :] + soft * (0.6 * envA)[None, :]


def transform_BA(A: np.ndarray) -> np.ndarray:
    """T_(B→A): ręka kwantowana do najbliższej harmonicznej siatki."""
    idx = np.arange(NB, dtype=np.float64)
    harm = np.array(B_HARM_BINS)
    near = harm[np.argmin(np.abs(idx[:, None] - harm[None, :]), axis=1)]
    disp = np.clip(near - idx, -9, 9)[:, None] * np.ones((1, FRAMES)) * 0.65
    quant = warp_columns(A, disp)
    return quant * (0.5 + 0.5 * GATE)[None, :]     # i częściowo przejmuje bramkę


def phi_of(A: np.ndarray, B: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Φ: składowe sumacyjne i różnicowe A i B, ważone pamięcią H."""
    nfft = 2 * NB
    FA = np.fft.rfft(A, n=nfft, axis=0)
    FB = np.fft.rfft(B, n=nfft, axis=0)
    ssum = np.fft.irfft(FA * FB, n=nfft, axis=0)[:NB]          # f1 + f2
    FBr = np.fft.rfft(B[::-1], n=nfft, axis=0)
    sdif = np.fft.irfft(FA * FBr, n=nfft, axis=0)[:NB]         # |f1 − f2|
    raw = np.abs(ssum) + np.abs(sdif)
    raw = gaussian_filter(raw, sigma=(2.0, 3.0))
    raw /= raw.max() + 1e-12
    return raw * (0.30 + 0.70 * H)[None, :]


def one_pass(A: np.ndarray, B: np.ndarray, mA: np.ndarray, mB: np.ndarray):
    """Jeden pełny obrót wzoru. Zwraca S i pola do obrazka."""
    An = A / (A.max() + 1e-9)
    Bn = B / (B.max() + 1e-9)

    # C: sprzężenie — czas × przestrzeń wspólna
    c_t = smoothstep((T_AX - 40) / 34)
    C = (c_t[None, :] * np.sqrt(gaussian_filter(An, 3) * gaussian_filter(Bn, 3)))
    C = C.astype(np.float32)

    # D: kierunek — dodatni na starcie, zero w połowie sprzężonego czasu, ujemny w finale
    d_t = 3.0 * np.cos(np.pi * np.clip((T_AX - 40) / (TOTAL - 40), 0, 1))
    fn = (np.arange(NB) / NB)[:, None]
    D = d_t[None, :] + 0.8 * (1 - 2 * fn)
    sig = 1.0 / (1.0 + np.exp(-D))

    R = sig * transform_AB(A, B) + (1 - sig) * transform_BA(A)

    # H: nieszczelna pamięć oddziaływań (stała czasowa ~3 s)
    inter = (C * R).mean(axis=0)
    lam = float(np.exp(-(HOP / SR) / 3.0))
    H = np.zeros(FRAMES, dtype=np.float32)
    acc = 0.0
    for t in range(FRAMES):
        acc = lam * acc + (1 - lam) * float(inter[t])
        H[t] = acc
    H /= H.max() + 1e-12

    syn_f = np.exp(-0.5 * ((np.log(BHZ) - np.log(900)) / 0.9) ** 2)[:, None]
    syn_t = smoothstep((T_AX - 70) / 50)[None, :]
    Syn = (syn_f * syn_t).astype(np.float32)

    Phi = phi_of(An, Bn, H)

    S = mA[None, :] * A + mB[None, :] * B + 1.15 * C * R + 2.1 * Syn * Phi
    return S.astype(np.float32), C, R, Syn, Phi, H, sig


def griffin_lim(mag_full: np.ndarray, iters: int = 38) -> np.ndarray:
    phase = np.exp(2j * np.pi * rng.random(mag_full.shape))
    x = None
    for _ in range(iters):
        _, x = istft(mag_full * phase, SR, nperseg=NPER, noverlap=NPER - HOP)
        _, _, Z = stft(x, SR, nperseg=NPER, noverlap=NPER - HOP)
        Z = Z[:, : mag_full.shape[1]]
        if Z.shape[1] < mag_full.shape[1]:
            pad = mag_full.shape[1] - Z.shape[1]
            Z = np.pad(Z, ((0, 0), (0, pad)))
        phase = np.exp(1j * np.angle(Z))
    return x


def main() -> int:
    A = paint_A()
    B = paint_B()

    # rama: A przedstawia się samo (0–20 s), potem B samo (20–40), potem razem
    mA = smoothstep((20 - T_AX) / 6) + smoothstep((T_AX - 34) / 6)
    mA = np.clip(mA, 0, 1)
    mB = smoothstep((T_AX - 20) / 6)
    # w finale oba pola schodzą — zostaje trzeci materiał
    fade_out = 1 - smoothstep((T_AX - 148) / 14)
    mA = mA * fade_out
    mB = mB * np.clip(fade_out + 0.15, 0, 1)

    S1, *_ = one_pass(A, B, mA, mB)

    # sprzężenie zwrotne: Φ z pierwszego obrotu wraca do A i B w ostatniej tercji
    fb = smoothstep((T_AX - 112) / 20)[None, :]
    _, _, _, Syn1, Phi1, _, _ = one_pass(A, B, mA, mB)
    A2 = A + 0.35 * (fb * Phi1) * A.max()
    B2 = B + 0.25 * (fb * warp_columns(Phi1, np.zeros((NB, FRAMES)))) * B.max()
    S, C, R, Syn, Phi, H, sig = one_pass(A2.astype(np.float32),
                                         B2.astype(np.float32), mA, mB)

    # rama F: dynamika — bez kompresji, tylko miękkie wejście całości
    S *= smoothstep(T_AX / 4)[None, :]

    mag = np.zeros((len(FREQS), FRAMES), dtype=np.float64)
    mag[BAND] = S
    mag = mag / (mag.max() + 1e-12)

    print("odzyskiwanie fazy (Griffin–Lim, 38 iteracji)…", flush=True)
    x = griffin_lim(mag)
    x = x[: int(TOTAL * SR)]
    x *= 0.89 / (np.abs(x).max() + 1e-9)

    sf.write(DIR / "wzor_kordiego.wav", np.stack([x, x]).T, SR, subtype="PCM_24")

    # ── weryfikacja: czy dźwięk ma strukturę, którą namalowałem ──
    m = x
    for a, b, lab in [(2, 18, "A samo"), (22, 38, "B samo"), (46, 68, "C·R_D"),
                      (80, 110, "Syn·Φ rośnie"), (118, 145, "sprzężenie zwrotne"),
                      (152, 166, "zostaje Φ")]:
        s = slice(int(a * SR), int(b * SR))
        print(f"  {lab:20s} {a:3d}–{b:3d}s  "
              f"{20 * np.log10(np.sqrt((m[s] ** 2).mean()) + 1e-12):6.1f} dB")

    # ── obraz: namalowany S + krzywe sterujące ──
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8.4), facecolor=PAPER,
                                   height_ratios=[2, 0.8],
                                   gridspec_kw={"hspace": 0.34})
    Sd = 20 * np.log10(S + 1e-6)
    top = Sd.max()
    ax1.pcolormesh(T_AX, BHZ, np.clip(Sd, top - 64, top),
                   shading="gouraud", cmap="magma", rasterized=True)
    ax1.set_yscale("log")
    ax1.set_ylim(F_LO, F_HI)
    ax1.set_yticks([110, 220, 440, 880, 1760, 3520])
    ax1.set_yticklabels(["110", "220", "440", "880", "1,8k", "3,5k"])
    ax1.set_ylabel("częstotliwość [Hz]", color=INK, fontsize=9)
    ax1.set_title("S(f,t;F) = A + B + C·R_D(A,B) + Syn·Φ(A,B,H;F) — namalowane",
                  color=INK, fontsize=12, loc="left", pad=10, family="monospace")
    for tx, lab in [(2, "A"), (22, "B"), (44, "C·R_D"), (84, "Syn·Φ"),
                    (116, "Φ→A,B"), (152, "Φ")]:
        ax1.text(tx, 5400, lab, color=ACC, fontsize=9, family="monospace")

    ax2.plot(T_AX, sig.mean(axis=0), color=INK, lw=1.4,
             label="σ(D̄): 1 = ręka odkształca siatkę, 0 = siatka rękę")
    ax2.plot(T_AX, smoothstep((T_AX - 40) / 34), color=ACC, lw=1.2, ls="--",
             label="C(t): sprzężenie")
    ax2.plot(T_AX, H, color="#3a6ea5", lw=1.2, label="H(t): pamięć")
    ax2.set_ylim(0, 1.05)
    ax2.set_xlabel("czas [s]", color=INK, fontsize=9)
    ax2.legend(loc="upper right", fontsize=7.5, framealpha=0.9)

    for ax in (ax1, ax2):
        ax.set_facecolor(PAPER)
        for sp in ax.spines.values():
            sp.set_color(INK)
        ax.tick_params(colors=INK, labelsize=8)
    fig.savefig(DIR / "wzor_kordiego.png", dpi=150, facecolor=PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'wzor_kordiego.wav'} · {DIR / 'wzor_kordiego.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

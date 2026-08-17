"""Analiza wielorozdzielcza + rama otwarta ponad słyszenie.

Dwa polecenia Janka w jednym:

  1. WIELOROZDZIELCZOŚĆ. Prawo nieoznaczoności mówi: dokładność w czasie ×
     dokładność w wysokości = stała. Ale to jest budżet NA JEDNO OKNO — nikt
     nie każe wydawać go wszędzie tak samo. Więc trzy płótna:

        DÓŁ    10–220 Hz     okno 341 ms → co 2,9 Hz, krok 85 ms
        ŚRODEK 220–6000 Hz   okno  85 ms → co 11,7 Hz, krok 21 ms
        GÓRA   6000–46000 Hz okno  10,7 ms → co 94 Hz, krok 5,3 ms

     Dół dostaje precyzję wysokości (basowi wolno być powolnym), góra dostaje
     precyzję czasu (transjent musi być ostry, a 94 Hz przy 12 kHz to i tak
     mniej niż ćwierć półtonu). Dokładnie tak działa ucho — i falki.

  2. RAMA PONAD SŁYSZENIE. Próbkowanie 96 kHz, sufit Nyquista 48 kHz, malujemy
     do 46 kHz. Siatka dostaje chór powietrzny (9,4–23,7 kHz z harmonicznymi
     po 46 k), a składowe sumacyjne Φ lądują tam naturalnie. Jeśli nie
     usłyszysz — zobaczysz: plik niesie wszystko, obraz pokazuje wszystko,
     granica słyszenia jest narysowana, nie udawana.

  Dół gra w mono — to nie kompromis, to nasza własna lekcja z automiksu:
  klubowy system i tak sumuje sub, a szeroki dół kasuje się w mono.
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

SR = 96000
TOTAL = 150.0
BPM = 84.0
DORIAN = [50, 52, 53, 55, 57, 59, 60]
rng = np.random.default_rng(21)


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class Canvas:
    """Jedno płótno: własne pasmo i własny podział budżetu nieoznaczoności."""

    def __init__(self, lo, hi, nper, hop, max_poly):
        self.lo, self.hi, self.nper, self.hop, self.max_poly = lo, hi, nper, hop, max_poly
        self.freqs = np.fft.rfftfreq(nper, 1 / SR)
        self.band = np.where((self.freqs >= lo) & (self.freqs <= hi))[0]
        self.bhz = self.freqs[self.band]
        self.df = float(self.bhz[1] - self.bhz[0])
        self.cols = int(TOTAL * SR / hop)
        self.tax = np.arange(self.cols) * hop / SR
        self.S = np.zeros((len(self.band), self.cols), dtype=np.float32)

    def bin_of(self, f):
        return (f - self.bhz[0]) / self.df

    def ridge(self, f, t0s, t1s, amp, width_hz):
        fb = self.bin_of(f)
        if not (0 <= fb < len(self.band)):
            return
        t0, t1 = int(t0s * SR / self.hop), int(t1s * SR / self.hop)
        t0, t1 = max(0, t0), min(self.cols, t1)
        n = t1 - t0
        if n <= 0:
            return
        w = max(0.8, width_hz / self.df)
        prof = np.exp(-0.5 * ((np.arange(len(self.band)) - fb) / w) ** 2)
        env = np.ones(n)
        a = min(n, max(2, n // 6))
        env[:a] = np.linspace(0, 1, a) ** 1.5
        env[-a:] *= np.linspace(1, 0.25, a)
        self.S[:, t0:t1] += amp * prof[:, None].astype(np.float32) * env[None, :].astype(np.float32)


CAN = {
    "dol": Canvas(10, 220, 32768, 8192, 16),
    "srodek": Canvas(220, 6000, 8192, 2048, 70),
    "gora": Canvas(6000, 46000, 1024, 512, 36),
}


def paint_into_all(f, t0, t1, amp, width):
    for c in CAN.values():
        if c.lo <= f <= c.hi:
            c.ridge(f, t0, t1, amp, width)


# ── kompozycja: zdarzenia, nie piksele — te same nuty na każde płótno ──
def compose():
    # A: ręka, trzy głosy
    events_A = []
    for _ in range(3):
        deg, octv, t = int(rng.integers(0, 7)), int(rng.integers(0, 2)), rng.uniform(0, 4)
        while t < TOTAL - 6:
            dur = rng.uniform(3.2, 6.5)
            deg = int(np.clip(deg + rng.integers(-2, 3), 0, 6))
            if rng.random() < 0.15:
                octv = 1 - octv
            events_A.append((t, dur, DORIAN[deg] + 12 * octv, rng.normal(0, 0.35)))
            t += dur + rng.uniform(0.2, 1.2)
    for t, dur, m, dr in events_A:
        for h in range(1, 25):
            f = hz(m + dr) * h
            if f < 46000:
                paint_into_all(f, t, t + dur, 1.0 / h ** 1.25, 12 + 2 * h)
        if hz(m + dr) / 2 > 10:
            paint_into_all(hz(m + dr) / 2, t, t + dur, 0.5, 8)

    # B: siatka + chór powietrzny nad słyszeniem
    pitches = [38, 50, 57, 62, 66, 69]
    air = [122, 129, 134, 138]          # 9,4 k · 14,1 k · 18,8 k · 23,7 k
    step = 60.0 / BPM / 2
    k, tt = 0, 0.0
    while tt < TOTAL:
        dur = step * 0.72
        acc = 1.3 if k % 4 == 0 else 1.0
        for m in pitches:
            for h in range(1, 25):
                f = hz(m) * h
                if f < 46000:
                    paint_into_all(f, tt, tt + dur, acc / h ** 1.1, 6)
        for m in air:
            for h in (1, 2):
                f = hz(m) * h
                if f < 46000:
                    paint_into_all(f, tt, tt + dur, acc * 0.10 / h, 60)
        tt += step
        k += 1
    return events_A


def masks(c: Canvas):
    mA = np.clip(smoothstep((20 - c.tax) / 6) + smoothstep((c.tax - 34) / 6), 0, 1)
    mB = smoothstep((c.tax - 20) / 6)
    fade = 1 - smoothstep((c.tax - TOTAL + 18) / 13)
    return mA * fade, mB * np.clip(fade + 0.15, 0, 1)


def phi_global():
    """Φ na zgrubnym płótnie pełnopasmowym; sumy lecą w ultradźwięk."""
    g = Canvas(10, 46000, 4096, 2048, 0)
    # rzut wszystkich płócien na wspólną siatkę
    for c in CAN.values():
        for i, f in enumerate(c.bhz[:: max(1, len(c.bhz) // 160)]):
            pass
    # taniej: użyj środka i góry wprost przez interpolację kolumn
    cols = g.cols
    A = np.zeros((len(g.band), cols), dtype=np.float32)
    for c in (CAN["dol"], CAN["srodek"], CAN["gora"]):
        t_src = c.tax
        S_t = np.empty((c.S.shape[0], cols), dtype=np.float32)
        for r in range(c.S.shape[0]):
            S_t[r] = np.interp(g.tax, t_src, c.S[r])
        for r, f in enumerate(c.bhz):
            b = int(g.bin_of(f))
            if 0 <= b < len(g.band):
                A[b] = np.maximum(A[b], S_t[r])
    An = A / (A.max() + 1e-9)
    nfft = 2 * len(g.band)
    FA = np.fft.rfft(An, n=nfft, axis=0)
    ssum = np.fft.irfft(FA * FA, n=nfft, axis=0)[: len(g.band)]
    raw = gaussian_filter(np.abs(ssum), sigma=(2.0, 2.0))
    raw /= raw.max() + 1e-12
    syn_t = smoothstep((g.tax - 60) / 45)
    return g, (raw * syn_t[None, :]).astype(np.float32)


def track_partials(c: Canvas):
    S = c.S
    thresh = S.max() * 3e-4
    live, done = [], []
    for t in range(S.shape[1]):
        col = S[:, t]
        idx = np.where((col[1:-1] > col[:-2]) & (col[1:-1] > col[2:])
                       & (col[1:-1] > thresh))[0] + 1
        peaks = sorted(((float(c.bhz[i]), float(col[i])) for i in idx),
                       key=lambda p: -p[1])[: c.max_poly]
        used = [False] * len(peaks)
        for tr in live:
            best, bd = -1, 1e9
            for k, (f, a) in enumerate(peaks):
                if not used[k] and abs(f - tr["f"][-1]) < bd:
                    best, bd = k, abs(f - tr["f"][-1])
            if best >= 0 and bd <= max(0.035 * tr["f"][-1], 1.6 * c.df):
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
    return [tr for tr in done if len(tr["t"]) >= 3 and max(tr["a"]) > S.max() * 1e-3]


def synth(tracks, c: Canvas, n_samp, pan_of):
    L = np.zeros(n_samp)
    R = np.zeros(n_samp)
    prng = np.random.default_rng(3)
    fade = int(0.004 * SR)
    for j, tr in enumerate(tracks):
        fr = np.array(tr["t"], dtype=np.float64)
        p0 = int(fr[0] * c.hop)
        p1 = min(int(fr[-1] * c.hop) + fade, n_samp)
        if p1 - p0 < fade * 2:
            continue
        n = np.arange(p0, p1)
        f = np.interp(n / c.hop, fr, tr["f"])
        a = np.interp(n / c.hop, fr, tr["a"])
        ph = 2 * np.pi * np.cumsum(f) / SR + prng.uniform(0, 2 * np.pi)
        seg = a * np.sin(ph)
        k = min(fade, len(seg) // 2)
        seg[:k] *= np.linspace(0, 1, k)
        seg[-k:] *= np.linspace(1, 0, k)
        th = (pan_of(tr, j) + 1) * np.pi / 4
        L[p0:p1] += seg * np.cos(th)
        R[p0:p1] += seg * np.sin(th)
    return L, R


def noise_of(c: Canvas, N, n_samp, seed):
    prng = np.random.default_rng(seed)
    mag = np.zeros((len(c.freqs), c.cols), dtype=np.float32)
    mag[c.band] = gaussian_filter(N, sigma=(1.0, 2.0))
    Z = mag * np.exp(2j * np.pi * prng.random(mag.shape).astype(np.float32))
    _, x = istft(Z, SR, nperseg=c.nper, noverlap=c.nper - c.hop)
    x = x[:n_samp]
    return np.pad(x, (0, n_samp - len(x)))


def main() -> int:
    print("tabela rozdzielczości (budżet nieoznaczoności wydany osobno):")
    for name, c in CAN.items():
        print(f"  {name:7s} {c.lo:6.0f}–{c.hi:6.0f} Hz · okno {c.nper / SR * 1000:6.1f} ms "
              f"· Δf {c.df:6.2f} Hz · krok {c.hop / SR * 1000:5.1f} ms")

    compose()
    g, Phi = phi_global()

    # Φ wraca na płótna — każde bierze swój wycinek pasma
    for c in CAN.values():
        sel = (g.bhz >= c.lo) & (g.bhz <= c.hi)
        rows = np.where(sel)[0]
        P_t = np.empty((len(rows), c.cols), dtype=np.float32)
        for i, r in enumerate(rows):
            P_t[i] = np.interp(c.tax, g.tax, Phi[r])
        for i, r in enumerate(rows):
            b = int(c.bin_of(g.bhz[r]))
            if 0 <= b < c.S.shape[0]:
                c.S[b] += 1.8 * P_t[i]
        mA, mB = masks(c)
        c.S *= np.maximum(mA, np.maximum(mB, smoothstep((c.tax - 40) / 30)))[None, :]
        c.S *= smoothstep(c.tax / 4)[None, :]

    over = CAN["gora"]
    above = over.bhz > 20000
    frac_ultra = float((over.S[above] ** 2).sum()
                       / (sum((c.S ** 2).sum() for c in CAN.values()) + 1e-12))
    print(f"\nenergia nad granicą słyszenia (20 kHz): {frac_ultra * 100:.1f}% "
          f"— tego nie usłyszysz, ale zobaczysz")

    n_samp = int(TOTAL * SR)
    Lm = np.zeros(n_samp)
    Rm = np.zeros(n_samp)
    report = {}
    for name, c in CAN.items():
        tracks = track_partials(c)
        R = np.zeros_like(c.S)
        prof = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)
        for tr in tracks:
            for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
                b = int(round(c.bin_of(f)))
                lo, hi = max(0, b - 4), min(c.S.shape[0], b + 5)
                R[lo:hi, t] = np.maximum(R[lo:hi, t], a * prof[lo - b + 4: hi - b + 4])
        N = np.maximum(c.S - R, 0.0)
        e_lin = float((np.minimum(R, c.S) ** 2).sum())
        e_pla = float((N ** 2).sum())
        report[name] = (len(tracks), e_lin, e_pla)

        if name == "dol":
            pan_of = lambda tr, j: 0.0                 # dół w mono — lekcja z automiksu
        elif name == "gora":
            pan_of = lambda tr, j: 0.5 if j % 2 else -0.5
        else:
            pan_of = lambda tr, j: float(np.clip(
                -0.62 + 1.24 * (np.mean(tr["f"]) % 700) / 700, -0.62, 0.62))
        Ls, Rs = synth(tracks, c, n_samp, pan_of)
        xn = noise_of(c, N, n_samp, seed=11)
        yn = xn if name == "dol" else noise_of(c, N, n_samp, seed=12)
        s_rms = np.sqrt(((Ls + Rs) ** 2).mean()) + 1e-12
        n_rms = np.sqrt(((xn + yn) ** 2).mean()) + 1e-12
        gN = np.sqrt(e_pla / (e_lin + 1e-9)) * s_rms / n_rms
        Lm += Ls + gN * xn
        Rm += Rs + gN * yn
        print(f"  {name:7s} linii {len(tracks):5d} · linie "
              f"{e_lin / (e_lin + e_pla + 1e-9) * 100:3.0f}% · plamy "
              f"{e_pla / (e_lin + e_pla + 1e-9) * 100:3.0f}%")

    mix = np.stack([Lm, Rm])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    sf.write(DIR / "wielorozdzielcza.wav", mix.T.astype(np.float32), SR,
             subtype="PCM_24")
    print(f"\nplik: 96 kHz / 24 bit — niesie pasmo do 46 kHz")

    # obraz: trzy płótna jedno nad drugim + granica słyszenia
    m = mix.mean(axis=0)
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor=PAPER,
                             gridspec_kw={"hspace": 0.3},
                             height_ratios=[1.25, 1, 0.8])
    plans = [("gora", 1024, 6000, 46000, axes[0]),
             ("srodek", 8192, 220, 6000, axes[1]),
             ("dol", 32768, 20, 220, axes[2])]
    for name, nper, lo, hi, ax in plans:
        f, t, Z = stft(m, SR, nperseg=nper, noverlap=int(nper * 0.75))
        Sd = 20 * np.log10(np.abs(Z) + 1e-10)
        k = (f >= lo) & (f <= hi)
        top = Sd[k].max()
        ax.pcolormesh(t, f[k], np.clip(Sd[k], top - 66, top),
                      shading="gouraud", cmap="magma", rasterized=True)
        ax.set_yscale("log")
        ax.set_ylim(lo, hi)
        c = CAN[name]
        ax.set_title(f"{name.upper()}  {lo}–{hi} Hz · okno {c.nper / SR * 1000:.0f} ms "
                     f"· Δf {c.df:.1f} Hz · krok {c.hop / SR * 1000:.1f} ms",
                     color=INK, fontsize=10, loc="left", pad=6, family="monospace")
        ax.set_facecolor(PAPER)
        for sp in ax.spines.values():
            sp.set_color(INK)
        ax.tick_params(colors=INK, labelsize=8)
    axes[0].axhline(20000, color="#7fd8d8", lw=1.4, ls=(0, (5, 4)))
    axes[0].text(2, 22500, "granica słyszenia — wyżej już tylko oczami",
                 color="#7fd8d8", fontsize=9, family="monospace")
    axes[2].set_xlabel("czas [s]", color=INK, fontsize=9)
    fig.suptitle("WIELOROZDZIELCZOŚĆ — trzy płótna, jeden budżet nieoznaczoności "
                 "wydany trzy razy inaczej", color=INK, fontsize=12,
                 family="monospace", x=0.123, ha="left")
    fig.savefig(DIR / "wielorozdzielcza.png", dpi=150, facecolor=PAPER,
                bbox_inches="tight")
    print(f"{DIR / 'wielorozdzielcza.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

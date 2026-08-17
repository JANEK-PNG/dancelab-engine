"""Hybryda wielorozdzielcza: pełny wzór Kordiego na trzech płótnach naraz.

Do tej pory silnik był w dwóch połówkach, w osobnych plikach:

  * hybryda.py grała PEŁNY wzór (kierunek D, deformacje T, Φ ważone pamięcią,
    sprzężenie zwrotne), ale na jednym płótnie 44,1 kHz i wąskiej ramie;
  * wielorozdzielcza.py miała trzy płótna i ramę do 46 kHz, ale wzór
    uproszczony: bez D, bez T, a Φ liczone z chwili zamiast z pamięci.

Ten plik skleja obie połówki w jeden renderer i wciela wszystkie twarde
lekcje z README:

  1. FAZA: całkowana dla linii (licznik obrotów), losowa dla plam (szum ma
     ją losową z natury). Griffin–Lim nie występuje.
  2. H WEWNĄTRZ Φ: sprzężenie C i trzeci materiał Φ rodzą się z pól
     wygładzonych ~1,5–2 s — z tego, co zalega, nie z ataków. Obwiednia Φ
     oddycha: wdech 1,2 s, wydech 4 s. Bramka siatki złagodzona u źródła.
  3. BUDŻET NIEOZNACZONOŚCI PER PASMO: dół 341 ms okna (precyzja wysokości),
     środek 85 ms, góra 11 ms (precyzja czasu). Trzy płótna, jeden utwór.
  4. RAMA OTWARTA: 96 kHz, malujemy do 46 kHz, granica słyszenia narysowana.
  5. GŁOSY: każda linia ma własną fazę startową; dół gra w mono (lekcja
     automiksu: klubowy system i tak sumuje sub).
  6. KAŻDA LICZBA W RAPORCIE JEST ZMIERZONA z wyrenderowanego pliku.

Geometria wzoru: A, B, C, D i R_D mieszkają na płótnach — tam, gdzie energia.
Φ liczone jest na wspólnej siatce pełnopasmowej, bo składowe sumacyjne
i różnicowe z natury przekraczają granice pasm (sumy średnich lądują w górze,
różnice — w dole). Potem Φ wraca na płótna, każde bierze swój wycinek.
"""

from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates, uniform_filter1d
from scipy.signal import butter, istft, sosfiltfilt, stft

DIR = pathlib.Path(__file__).resolve().parent
PAPER, INK, ACC = "#efece4", "#141414", "#e0483c"

SR = 96000
TOTAL = 168.0
BPM = 84.0
F_LO, F_HI = 10.0, 46000.0
DORIAN = [50, 52, 53, 55, 57, 59, 60]
B_PITCHES = [38, 50, 57, 62, 66, 69]        # D2 w dole — siatka ma fundament
AIR = [122, 129, 134, 138]                  # chór powietrzny 9,4–23,7 kHz

rng = np.random.default_rng(34)
N_SAMP = int(TOTAL * SR)


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# ── bramka siatki: ósemki z akcentem, złagodzone u źródła (lekcja oddechu) ──
T200 = np.arange(int(TOTAL * 200)) / 200.0
G200 = np.zeros_like(T200)
_step = 60.0 / BPM / 2
_k, _tt = 0, 0.0
while _tt < TOTAL:
    i0, i1 = int(_tt * 200), min(int((_tt + _step * 0.72) * 200), len(T200))
    if i1 > i0:
        G200[i0:i1] = np.maximum(
            G200[i0:i1],
            np.linspace(1, 0.15, i1 - i0) ** 1.4 * (1.3 if _k % 4 == 0 else 1.0))
    _tt += _step
    _k += 1
G200 = np.maximum(G200, 0.45 * (G200 > 0))          # opada do połowy, nie do zera
G200 = gaussian_filter1d(G200, 14.0)                # krawędzie ~70 ms

B_HARM_HZ = sorted(hz(m) * h for m in B_PITCHES for h in range(1, 25)
                   if F_LO < hz(m) * h < F_HI)


class Canvas:
    """Jedno płótno: własne pasmo, własny podział budżetu nieoznaczoności."""

    def __init__(self, name, lo, hi, nper, hop, max_poly, fade_s, amp_sigma, blur_s,
                 merge_hz=0.0):
        self.name, self.lo, self.hi = name, lo, hi
        self.nper, self.hop, self.max_poly = nper, hop, max_poly
        self.fade_s, self.amp_sigma, self.blur_s = fade_s, amp_sigma, blur_s
        self.merge_hz = merge_hz
        self.freqs = np.fft.rfftfreq(nper, 1 / SR)
        self.band = np.where((self.freqs >= lo) & (self.freqs <= hi))[0]
        self.bhz = self.freqs[self.band]
        self.NB = len(self.band)
        self.df = float(self.bhz[1] - self.bhz[0])
        self.dt = hop / SR
        self.cols = int(TOTAL * SR / hop)
        self.tax = np.arange(self.cols) * self.dt
        self.A = np.zeros((self.NB, self.cols), np.float32)
        self.B = np.zeros((self.NB, self.cols), np.float32)

        t = self.tax
        self.gate = np.interp(t, T200, G200).astype(np.float32)
        self.c_t = smoothstep((t - 40) / 34).astype(np.float32)
        d_t = 3.0 * np.cos(np.pi * np.clip((t - 40) / (TOTAL - 40), 0, 1))
        fn = ((np.log(self.bhz) - np.log(F_LO))
              / (np.log(F_HI) - np.log(F_LO)))[:, None]
        self.sig = (1.0 / (1.0 + np.exp(-(d_t[None, :] + 0.8 * (1 - 2 * fn))))
                    ).astype(np.float32)
        syn_f = np.exp(-0.5 * ((np.log(self.bhz) - np.log(900.0)) / 1.4) ** 2)[:, None]
        self.syn = (syn_f * smoothstep((t - 70) / 50)[None, :]).astype(np.float32)
        mA = np.clip(smoothstep((20 - t) / 6) + smoothstep((t - 34) / 6), 0, 1)
        mB = smoothstep((t - 20) / 6)
        fade = 1 - smoothstep((t - 148) / 14)
        self.mA = (mA * fade).astype(np.float32)
        self.mB = (mB * np.clip(fade + 0.15, 0, 1)).astype(np.float32)
        self.fb = smoothstep((t - 112) / 20).astype(np.float32)
        self.intro = smoothstep(t / 4).astype(np.float32)
        # bramka do ODDZIAŁYWAŃ: tożsamość siatki tyka, ale jej wpływ na
        # wspólne pole płynie (~0,5 s) — lekcja oddechu, tym razem u źródła
        gs = self.gate
        n = int(max(1, round(2.0 * 0.5 / self.dt)))
        for _ in range(3):
            gs = uniform_filter1d(gs, size=n, mode="nearest")
        self.gate_slow = gs.astype(np.float32)
        self.harm_bins = np.array([self.bin_of(f) for f in B_HARM_HZ
                                   if lo < f < hi], dtype=np.float64)

    def bin_of(self, f):
        return (f - self.bhz[0]) / self.df

    def ridge(self, field, f, t0s, t1s, amp, width_hz):
        """Nuta: pozioma smuga z obwiednią wejścia i opadania."""
        fb = self.bin_of(f)
        t0, t1 = max(0, int(t0s / self.dt)), min(self.cols, int(t1s / self.dt))
        n = t1 - t0
        if n <= 0:
            return
        w = max(0.8, width_hz / self.df)
        lo, hi = max(0, int(fb - 4 * w)), min(self.NB, int(fb + 4 * w) + 1)
        if lo >= hi:
            return
        prof = np.exp(-0.5 * ((np.arange(lo, hi) - fb) / w) ** 2).astype(np.float32)
        env = np.ones(n, np.float32)
        a = min(n, max(2, n // 6))
        env[:a] = np.linspace(0, 1, a) ** 1.5
        env[-a:] *= np.linspace(1, 0.25, a)
        field[lo:hi, t0:t1] += amp * prof[:, None] * env[None, :]

    def comb(self, field, f, amp, width_hz):
        """Prążek siatki: profil częstotliwości × bramka na cały utwór."""
        fb = self.bin_of(f)
        w = max(0.8, width_hz / self.df)
        lo, hi = max(0, int(fb - 4 * w)), min(self.NB, int(fb + 4 * w) + 1)
        if lo >= hi:
            return
        prof = np.exp(-0.5 * ((np.arange(lo, hi) - fb) / w) ** 2).astype(np.float32)
        field[lo:hi] += amp * prof[:, None] * self.gate[None, :]


CAN = {
    # dół scala szczyty bliższe niż 3 Hz: kilka prawie-unisono linii basu
    # to dla ucha JEDEN ton (pasmo krytyczne), a bas ma być trzymany,
    # nie dudniący — lekcja automiksu i liczby Janka (bas 97%)
    "dol": Canvas("dol", 10, 220, 32768, 8192, 16, 0.040, 2.0, 0.17, merge_hz=3.0),
    "srodek": Canvas("srodek", 220, 6000, 8192, 2048, 70, 0.020, 2.0, 0.17),
    "gora": Canvas("gora", 6000, 46000, 1024, 512, 36, 0.005, 1.0, 0.03),
}
G = Canvas("global", 10, 46000, 4096, 2048, 0, 0.0, 0.0, 0.0)   # siatka dla Φ i H


# ── pamięć zamiast chwili: wygładzenie w czasie (potrójny box ≈ gauss) ──
def slow(X, sec, c: Canvas):
    n = int(max(1, round(2.0 * sec / c.dt)))
    Y = X
    for _ in range(3):
        Y = uniform_filter1d(Y, size=n, axis=-1, mode="nearest")
    return Y


def warp(X, disp):
    """Przesunięcie każdej kolumny wzdłuż osi f o pole disp (w binach)."""
    nb, nt = X.shape
    rows = np.clip(np.arange(nb, dtype=np.float64)[:, None] - disp, 0, nb - 1)
    cols = np.repeat(np.arange(nt, dtype=np.float64)[None, :], nb, axis=0)
    return map_coordinates(X, [rows, cols], order=1, mode="nearest").astype(np.float32)


def transform_AB(c: Canvas, Aslow, B):
    """T_(A→B): siatka gięta przez WOLNĄ rękę — geometria idzie za grzbietami."""
    grad = np.gradient(gaussian_filter1d(Aslow, 3.0, axis=0), axis=0)
    disp = 7.0 * grad / (np.abs(grad).max() + 1e-9)
    envA = slow(Aslow.mean(axis=0), 0.19, c)
    envA = envA / (envA.max() + 1e-9)
    bent = warp(B, disp)
    soft = slow(bent, 0.09, c)
    return bent * (1 - 0.6 * envA)[None, :] + soft * (0.6 * envA)[None, :]


def transform_BA(c: Canvas, A):
    """T_(B→A): ręka ściągana do najbliższej harmonicznej siatki + jej bramka."""
    if len(c.harm_bins) == 0:
        return A * (0.5 + 0.5 * c.gate_slow)[None, :]
    idx = np.arange(c.NB, dtype=np.float64)
    near = c.harm_bins[np.argmin(np.abs(idx[:, None] - c.harm_bins[None, :]), axis=1)]
    disp = np.clip(near - idx, -9, 9)[:, None] * 0.65
    quant = warp(A, np.repeat(disp, c.cols, axis=1))
    return quant * (0.5 + 0.5 * c.gate_slow)[None, :]


def to_global(Xd: dict) -> np.ndarray:
    """Rzut pól z płócien na wspólną siatkę pełnopasmową."""
    Gf = np.zeros((G.NB, G.cols), np.float32)
    for name, c in CAN.items():
        X = Xd[name]
        sel = np.where((G.bhz >= c.lo) & (G.bhz <= c.hi))[0]
        if len(sel) == 0:
            continue
        rc = np.interp(G.bhz[sel], c.bhz, np.arange(c.NB, dtype=np.float64))
        cc = np.interp(G.tax, c.tax, np.arange(c.cols, dtype=np.float64))
        RC = np.repeat(rc[:, None], G.cols, axis=1)
        CC = np.repeat(cc[None, :], len(sel), axis=0)
        sub = map_coordinates(X, [RC, CC], order=1, mode="nearest")
        Gf[sel] = np.maximum(Gf[sel], sub.astype(np.float32))
    return Gf


def from_global(Phi, c: Canvas) -> np.ndarray:
    """Wycinek wspólnej siatki z powrotem na płótno."""
    rc = np.interp(c.bhz, G.bhz, np.arange(G.NB, dtype=np.float64))
    cc = np.interp(c.tax, G.tax, np.arange(G.cols, dtype=np.float64))
    RC = np.repeat(rc[:, None], c.cols, axis=1)
    CC = np.repeat(cc[None, :], c.NB, axis=0)
    return map_coordinates(Phi, [RC, CC], order=1, mode="nearest").astype(np.float32)


def phi_of(gA, gB, H):
    """Φ: składowe sumacyjne i różnicowe A i B, ważone pamięcią H."""
    nfft = 2 * G.NB
    out = np.empty((G.NB, G.cols), np.float32)
    for j0 in range(0, G.cols, 1500):
        j1 = min(G.cols, j0 + 1500)
        FA = np.fft.rfft(gA[:, j0:j1], n=nfft, axis=0)
        FB = np.fft.rfft(gB[:, j0:j1], n=nfft, axis=0)
        ssum = np.fft.irfft(FA * FB, n=nfft, axis=0)[:G.NB]
        FBr = np.fft.rfft(gB[::-1, j0:j1], n=nfft, axis=0)
        sdif = np.fft.irfft(FA * FBr, n=nfft, axis=0)[:G.NB]
        out[:, j0:j1] = (np.abs(ssum) + np.abs(sdif)).astype(np.float32)
    raw = gaussian_filter(out, sigma=(2.0, 3.0))
    raw /= raw.max() + 1e-12
    return (raw * (0.30 + 0.70 * H)[None, :]).astype(np.float32)


def breath(Phi, atk=1.2, rel=4.0):
    """Wdech/wydech: obwiednia Φ może wzbierać i opadać, nigdy migać."""
    e = Phi.mean(axis=0)
    out = np.empty_like(e)
    acc = float(e[0])
    ka = 1 - np.exp(-G.dt / atk)
    kr = 1 - np.exp(-G.dt / rel)
    for t in range(len(e)):
        k = ka if e[t] > acc else kr
        acc += (float(e[t]) - acc) * k
        out[t] = acc
    scale = np.clip(out / (e + 1e-12), 0.2, 5.0)
    return Phi * scale[None, :].astype(np.float32)


# ── kompozycja: te same zdarzenia na każde płótno, które je słyszy ──
def compose_A():
    ev = []
    for _ in range(3):
        deg, octv = int(rng.integers(0, 7)), int(rng.integers(0, 2))
        t = float(rng.uniform(0, 4))
        while t < TOTAL - 6:
            dur = float(rng.uniform(3.2, 6.5))
            deg = int(np.clip(deg + rng.integers(-2, 3), 0, 6))
            if rng.random() < 0.15:
                octv = 1 - octv
            ev.append((t, dur, DORIAN[deg] + 12 * octv, float(rng.normal(0, 0.35))))
            t += dur + float(rng.uniform(0.2, 1.2))
    return ev


def paint_all():
    for t, dur, m, dr in compose_A():
        f0 = hz(m + dr)
        for h in range(1, 25):
            f = f0 * h
            if f < F_HI:
                for c in CAN.values():
                    if c.lo <= f <= c.hi:
                        c.ridge(c.A, f, t, t + dur, 1.0 / h ** 1.25, 12 + 2 * h)
        if f0 / 2 > F_LO:
            for c in CAN.values():
                if c.lo <= f0 / 2 <= c.hi:
                    c.ridge(c.A, f0 / 2, t, t + dur, 0.5, 8)
    for m in B_PITCHES:
        for h in range(1, 25):
            f = hz(m) * h
            if f < F_HI:
                for c in CAN.values():
                    if c.lo <= f <= c.hi:
                        c.comb(c.B, f, 1.0 / h ** 1.1, 6)
    for m in AIR:
        for h in (1, 2):
            f = hz(m) * h
            if f < F_HI:
                for c in CAN.values():
                    if c.lo <= f <= c.hi:
                        c.comb(c.B, f, 0.10 / h, 60)


def one_pass(fields: dict):
    """Jeden pełny obrót wzoru na wszystkich płótnach. Zwraca S i Φ per płótno."""
    CR = {}
    for name, c in CAN.items():
        A, B = fields[name]
        An = A / (A.max() + 1e-9)
        Bn = B / (B.max() + 1e-9)
        As, Bs = slow(An, 1.5, c), slow(Bn, 1.5, c)
        # iloczyn przycięty do zera: wygładzanie w float32 potrafi zostawić
        # −1e−12, a sqrt z ujemnego to NaN, który zatruwa pamięć H
        wspolne = np.maximum(gaussian_filter(As, 3) * gaussian_filter(Bs, 3), 0.0)
        C = (c.c_t[None, :] * np.sqrt(wspolne)).astype(np.float32)
        Rd = c.sig * transform_AB(c, slow(A, 1.2, c), B) \
            + (1 - c.sig) * transform_BA(c, A)
        Rd = (0.35 * Rd + 0.65 * slow(Rd, 0.9, c)).astype(np.float32)
        CR[name] = (C, Rd, An, Bn)

    # H: jedna pamięć dla całego utworu — z oddziaływań wszystkich płócien
    inter = np.zeros(G.cols)
    for name, c in CAN.items():
        C, Rd, _, _ = CR[name]
        inter += np.interp(G.tax, c.tax, (C * Rd).mean(axis=0))
    inter /= len(CAN)
    lam = float(np.exp(-G.dt / 3.0))
    H = np.zeros(G.cols, np.float32)
    acc = 0.0
    for t in range(G.cols):
        acc = lam * acc + (1 - lam) * float(inter[t])
        H[t] = acc
    H /= H.max() + 1e-12

    # Φ na wspólnej siatce, z pól PAMIĘTANYCH (~2 s), z oddechem
    gA = to_global({n: slow(CR[n][2], 2.0, CAN[n]) for n in CAN})
    gB = to_global({n: slow(CR[n][3], 2.0, CAN[n]) for n in CAN})
    Phi = breath(phi_of(gA, gB, H))

    out = {}
    for name, c in CAN.items():
        C, Rd, _, _ = CR[name]
        A, B = fields[name]
        Phic = from_global(Phi, c)
        S = c.mA[None, :] * A + c.mB[None, :] * B + 1.15 * C * Rd \
            + 2.1 * c.syn * Phic
        assert np.isfinite(S).all(), f"NaN w S płótna {name} — stop, zanim uda wynik"
        out[name] = (S.astype(np.float32), Phic)
    return out, H


# ── czytanie partytury i granie (linie: faza całkowana; plamy: szum) ──
def track_partials(c: Canvas, S):
    thresh = S.max() * 3e-4
    live, done = [], []
    for t in range(S.shape[1]):
        col = S[:, t]
        idx = np.where((col[1:-1] > col[:-2]) & (col[1:-1] > col[2:])
                       & (col[1:-1] > thresh))[0] + 1
        peaks = []
        for i in idx:
            d = 0.5 * (col[i - 1] - col[i + 1]) \
                / (col[i - 1] - 2 * col[i] + col[i + 1] + 1e-12)
            d = float(np.clip(d, -0.5, 0.5))
            peaks.append((float(c.bhz[i] + d * c.df), float(col[i])))
        peaks = sorted(peaks, key=lambda p: -p[1])
        if c.merge_hz > 0:
            merged = []
            for f, a in peaks:
                for k, (fm, am) in enumerate(merged):
                    if abs(f - fm) < c.merge_hz:
                        e = am * am + a * a
                        merged[k] = ((fm * am * am + f * a * a) / e, np.sqrt(e))
                        break
                else:
                    merged.append((f, a))
            peaks = merged
        peaks = peaks[: c.max_poly]
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


def synth(c: Canvas, tracks, pan_of):
    L = np.zeros(N_SAMP)
    R = np.zeros(N_SAMP)
    prng = np.random.default_rng(3)
    fade = int(c.fade_s * SR)
    for j, tr in enumerate(tracks):
        fr = np.array(tr["t"], dtype=np.float64)
        p0 = int(fr[0] * c.hop)
        p1 = min(int(fr[-1] * c.hop) + fade, N_SAMP)
        if p1 - p0 < fade * 2:
            continue
        amps = gaussian_filter1d(np.array(tr["a"], dtype=np.float64), c.amp_sigma)
        n = np.arange(p0, p1)
        f = np.interp(n / c.hop, fr, tr["f"])
        a = np.interp(n / c.hop, fr, amps)
        # CAŁKOWANIE FAZY: licznik obrotów; start losowy per linia (lekcja 5)
        ph = 2 * np.pi * np.cumsum(f) / SR + prng.uniform(0, 2 * np.pi)
        seg = a * np.sin(ph)
        k = min(fade, len(seg) // 2)
        seg[:k] *= np.linspace(0, 1, k)
        seg[-k:] *= np.linspace(1, 0, k)
        p = pan_of(tr, j)
        if np.ndim(p):
            p = np.interp(n / c.hop, fr, p)
        th = (np.clip(p, -1, 1) + 1) * np.pi / 4
        L[p0:p1] += seg * np.cos(th)
        R[p0:p1] += seg * np.sin(th)
    return L, R


def noise_of(c: Canvas, N, seed):
    """Plamy jako ukształtowany szum: losowa faza jest poprawnym modelem WIDMA.

    Ale obwiednia należy do obrazu, nie do przypadku: wąskopasmowy szum
    o losowej fazie faluje sam z siebie (4–30 Hz — dokładnie trzepot).
    Dlatego po syntezie obwiednia jest ściągana do namalowanej energii
    kolumn — plamy grają to, co namalowane, także w czasie.
    """
    prng = np.random.default_rng(seed)
    blur = max(1.0, c.blur_s / c.dt)
    mag = np.zeros((len(c.freqs), c.cols), np.float32)
    mag[c.band] = gaussian_filter(N, sigma=(1.0, blur))
    ang = (2 * np.pi) * prng.random(mag.shape, dtype=np.float32)
    Z = mag * (np.cos(ang) + 1j * np.sin(ang))
    _, x = istft(Z, SR, nperseg=c.nper, noverlap=c.nper - c.hop)
    x = x[:N_SAMP]
    x = np.pad(x, (0, N_SAMP - len(x)))
    tgt = np.interp(np.arange(N_SAMP) / SR, c.tax,
                    np.sqrt((mag[c.band] ** 2).sum(axis=0)))
    if c.name == "dol":
        # wąskie pasmo + głośny bas: falowanie Rayleigha (4–30 Hz) trzeba
        # zdjąć na siłę — obwiednia śledzona co ~5 ms, wzmocnienie
        # w widełkach, powrotny filtr pasma; trzy rundy = −14 dB trzepotu
        sos_band = butter(4, [c.lo / (SR / 2), c.hi / (SR / 2)],
                          btype="bandpass", output="sos")
        for _ in range(3):
            env = np.abs(x)
            n = max(1, int(2 * 0.005 * SR))
            for _ in range(3):
                env = uniform_filter1d(env, size=n, mode="nearest")
            g = np.clip(tgt / (env + 0.02 * env.max() + 1e-12), 0.25, 4.0)
            x = sosfiltfilt(sos_band, x * g)
        return x
    env = np.abs(x)
    n = int(max(1, round(2 * max(c.blur_s, 0.05) * SR)))
    for _ in range(3):
        env = uniform_filter1d(env, size=n, mode="nearest")
    return x * tgt / (env + 0.05 * env.max() + 1e-12)


def repaint(c: Canvas, tracks, shape, sigma=1.4, half=4):
    R = np.zeros(shape, np.float32)
    prof = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma) ** 2)
    for tr in tracks:
        for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
            b = int(round(c.bin_of(f)))
            lo, hi = max(0, b - half), min(shape[0], b + half + 1)
            if lo < hi:
                R[lo:hi, t] = np.maximum(R[lo:hi, t],
                                         a * prof[lo - b + half: hi - b + half])
    return R


# ── miary: liczby z pliku, nie wrażenia ──
def purity(y):
    y = y[int(28 * SR): int(34 * SR)]
    F = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    fr = np.fft.rfftfreq(len(y), 1 / SR)
    i = np.argmax(F * ((fr > 200) & (fr < 1000)))
    peak = float((F[i - 3: i + 4] ** 2).sum())
    halo = float((F[i - 220: i + 221] ** 2).sum()) - peak
    return 10 * np.log10(peak / (halo + 1e-12))


def mod_measures(y):
    """Oddech / puls / trzepot — puls (wielokrotności ósemki 2,8 Hz) liczony
    osobno, bo rytm to nie wada (lekcja 6: puls ≠ trzepot)."""
    env = np.abs(y)
    env = sosfiltfilt(butter(2, 40 / (SR / 2), btype="lowpass", output="sos"), env)
    env = env[:: SR // 200]
    env = np.log(np.maximum(env, 1e-7))            # log(0) dawał NaN — lekcja 6
    F = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
    fr = np.fft.rfftfreq(len(env), 1 / 200)
    f8 = BPM / 60.0 * 2
    puls = np.zeros_like(fr, dtype=bool)
    for k in range(1, 11):
        puls |= np.abs(fr - k * f8) < 0.35
    oddech = F[(fr > 0.3) & (fr < 3) & ~puls].sum()
    puls_e = F[(fr > 0.3) & (fr < 30) & puls].sum()
    trzepot = F[(fr > 4) & (fr < 30) & ~puls].sum()
    return (10 * np.log10(oddech / (trzepot + 1e-12)),
            10 * np.log10(puls_e / (trzepot + 1e-12)))


def corr_band(L, R, lo, hi):
    sos = butter(4, [lo / (SR / 2), hi / (SR / 2)], btype="bandpass", output="sos")
    l = sosfiltfilt(sos, L)
    r = sosfiltfilt(sos, R)
    return float(np.corrcoef(l, r)[0, 1])


def main() -> int:
    print("tabela rozdzielczości (budżet nieoznaczoności wydany osobno):")
    for name, c in CAN.items():
        print(f"  {name:7s} {c.lo:6.0f}–{c.hi:6.0f} Hz · okno {c.nper / SR * 1000:6.1f} ms"
              f" · Δf {c.df:6.2f} Hz · krok {c.hop / SR * 1000:5.1f} ms", flush=True)

    print("maluję A i B na trzy płótna…", flush=True)
    paint_all()
    fields0 = {n: (c.A, c.B) for n, c in CAN.items()}

    print("obrót 1 wzoru (C, D, R_D, H, Φ z pamięci)…", flush=True)
    pass1, H1 = one_pass(fields0)

    # sprzężenie zwrotne: Φ z obrotu 1 wraca do A i B w ostatniej tercji
    fields2 = {}
    for name, c in CAN.items():
        A, B = fields0[name]
        Phic = pass1[name][1]
        fb = c.fb[None, :]
        fields2[name] = ((A + 0.35 * fb * Phic * A.max()).astype(np.float32),
                         (B + 0.25 * fb * Phic * B.max()).astype(np.float32))
    del pass1

    print("obrót 2 wzoru (pola zmienione przez Φ)…", flush=True)
    pass2, H = one_pass(fields2)

    Ss = {}
    for name, c in CAN.items():
        S = pass2[name][0] * c.intro[None, :]
        Ss[name] = S
    del pass2

    above = CAN["gora"].bhz > 20000
    frac_ultra = float((Ss["gora"][above] ** 2).sum()
                       / (sum((S ** 2).sum() for S in Ss.values()) + 1e-12))
    print(f"\nenergia nad granicą słyszenia (20 kHz): {frac_ultra * 100:.1f}%",
          flush=True)

    Lm = np.zeros(N_SAMP)
    Rm = np.zeros(N_SAMP)
    for name, c in CAN.items():
        S = Ss[name]
        print(f"czytam partyturę płótna {name}…", flush=True)
        tracks = track_partials(c, S)
        Rr = repaint(c, tracks, S.shape)
        if name == "dol":
            # polityka pasma: dół gra praktycznie same linie. Szum obok
            # trzymanego basu ZAWSZE dudni (pasmo krytyczne — zmierzono:
            # osobno linie +2,1 dB i szum +5,6 dB, suma −5,1 dB), więc
            # mgła jest wycinana szerokim karbem wokół każdej linii
            N = np.maximum(S - 2.0 * repaint(c, tracks, S.shape, 6.0, 14), 0.0)
        else:
            N = np.maximum(S - Rr, 0.0)
        e_lin = float((np.minimum(Rr, S) ** 2).sum())
        e_pla = float((N ** 2).sum())
        print(f"  {name:7s} linii {len(tracks):5d} · linie "
              f"{e_lin / (e_lin + e_pla + 1e-9) * 100:3.0f}% · plamy "
              f"{e_pla / (e_lin + e_pla + 1e-9) * 100:3.0f}%"
              + ("  (mgła dołu wycięta: dudni z liniami)" if name == "dol" else ""),
              flush=True)

        if name == "dol":
            pan_of = lambda tr, j: 0.0            # dół w mono — lekcja automiksu
        elif name == "gora":
            pan_of = lambda tr, j: 0.5 if j % 2 else -0.5
        else:
            A, B = fields2[name]
            An = A / (A.max() + 1e-9)
            Bn = B / (B.max() + 1e-9)
            pan_field = (-0.62 * c.mA[None, :] * An + 0.62 * c.mB[None, :] * Bn) \
                / (c.mA[None, :] * An + c.mB[None, :] * Bn + 0.35)

            def pan_of(tr, j, pf=pan_field, cc=c):
                return np.array([pf[min(max(int(cc.bin_of(f)), 0), cc.NB - 1), t]
                                 for f, t in zip(tr["f"], tr["t"])])

        Ls, Rs = synth(c, tracks, pan_of)
        xn = noise_of(c, N, seed=11)
        yn = xn if name == "dol" else noise_of(c, N, seed=12)
        s_rms = np.sqrt(((Ls + Rs) ** 2).mean()) + 1e-12
        n_rms = np.sqrt(((xn + yn) ** 2).mean()) + 1e-12
        gN = np.sqrt(e_pla / (e_lin + 1e-9)) * s_rms / n_rms
        Lm += Ls + gN * xn
        Rm += Rs + gN * yn

    mix = np.stack([Lm, Rm])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    sf.write(DIR / "hybryda_wielorozdzielcza.wav", mix.T.astype(np.float32), SR,
             subtype="PCM_24")

    # ── weryfikacja z wyrenderowanego pliku (ADR-005) ──
    y, _ = sf.read(DIR / "hybryda_wielorozdzielcza.wav", dtype="float64")
    L, R = y[:, 0], y[:, 1]
    m = y.mean(axis=1)
    assert np.isfinite(y).all(), "NaN/Inf w pliku!"
    print(f"\nweryfikacja pliku:")
    print(f"  szczyt {np.abs(y).max():.3f} (cel 0,89) · NaN: brak")
    print(f"  czystość trzymanej składowej (28–34 s): {purity(m):+.1f} dB "
          f"(zdjęcie miało −9,9; same linie +7,1)")
    odd, pls = mod_measures(m)
    print(f"  oddech kontra trzepot (poza pulsem): {odd:+.1f} dB "
          f"· puls kontra trzepot: {pls:+.1f} dB")
    print(f"  korelacja L/R dół 30–220 Hz: {corr_band(L, R, 30, 220):+.3f} "
          f"(mono z wyboru)")
    print(f"  korelacja L/R środek 220–6000 Hz: {corr_band(L, R, 220, 6000):+.3f} "
          f"(chór nie zapada się w mono, gdy < 0,99)")
    print(f"\n  przebieg (RMS sekcji — czy dramaturgia wzoru jest w dźwięku):")
    for a, b, lab in [(2, 18, "A samo"), (22, 38, "B samo"), (46, 68, "C·R_D"),
                      (80, 110, "Syn·Φ rośnie"), (118, 145, "sprzężenie zwrotne"),
                      (152, 166, "zostaje Φ")]:
        s = slice(int(a * SR), int(b * SR))
        print(f"    {lab:20s} {a:3d}–{b:3d}s  "
              f"{20 * np.log10(np.sqrt((m[s] ** 2).mean()) + 1e-12):6.1f} dB")

    sf.write(DIR / "hybryda_wielorozdzielcza.flac", y.astype(np.float32), SR,
             subtype="PCM_24")

    # obraz: trzy płótna + granica słyszenia
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
        ax.set_title(f"{name.upper()}  {lo}–{hi} Hz · okno {c.nper / SR * 1000:.0f} ms"
                     f" · Δf {c.df:.1f} Hz · krok {c.hop / SR * 1000:.1f} ms",
                     color=INK, fontsize=10, loc="left", pad=6, family="monospace")
        ax.set_facecolor(PAPER)
        for sp in ax.spines.values():
            sp.set_color(INK)
        ax.tick_params(colors=INK, labelsize=8)
    axes[0].axhline(20000, color="#7fd8d8", lw=1.4, ls=(0, (5, 4)))
    axes[0].text(2, 22500, "granica słyszenia — wyżej już tylko oczami",
                 color="#7fd8d8", fontsize=9, family="monospace")
    axes[2].set_xlabel("czas [s]", color=INK, fontsize=9)
    fig.suptitle("HYBRYDA WIELOROZDZIELCZA — pełny wzór Kordiego, trzy płótna, "
                 "linie+szum", color=INK, fontsize=12, family="monospace",
                 x=0.123, ha="left")
    fig.savefig(DIR / "hybryda_wielorozdzielcza.png", dpi=150, facecolor=PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'hybryda_wielorozdzielcza.wav'}")
    print(f"{DIR / 'hybryda_wielorozdzielcza.flac'}")
    print(f"{DIR / 'hybryda_wielorozdzielcza.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

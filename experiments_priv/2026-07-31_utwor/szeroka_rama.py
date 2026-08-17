"""Szeroka rama: to samo równanie, płótno na całe słyszenie.

Spostrzeżenie Janka: McAulay i Quatieri mieli wąskie radio — ich rama była
przymusem technicznym. Nasza rama 55–6800 Hz też była przymusem, tylko
odziedziczonym z pierwszego skryptu bez decyzji. A ramę wybiera ten, kto
patrzy. Więc: 25 Hz – 18 kHz, całe słyszenie.

I tu jest rzecz, która z metafory robi pomiar: trzeci materiał Φ to składowe
SUMACYJNE (f1+f2, lądują wysoko) i RÓŻNICOWE (|f1−f2|, lądują nisko). Wąska
rama ucinała oba końce — czyli obcinała dokładnie IN BETWEEN, zostawiając
jego środek. Ile obcinała, jest tu policzone i wypisane.

Druga szerokość: przestrzeń. Płótno dostaje trzeci wymiar — panoramę.
Ręka mieszka po lewej, siatka po prawej, a trzeci materiał jest SZEROKI:
plamy grają w obu kanałach niezależną fazą, więc nie mają jednego miejsca,
tylko rozpiętość. Dokładnie jak w in_between: ręka | między | siatka.

Synteza jak w hybrydzie — linie oscylatorami z fazą całkowaną (oscylator nie
ma limitu rozdzielczości, więc dół gra precyzyjnie mimo szerokiej ramy),
plamy jako ukształtowany szum. Rama F przestała być ścianą, została decyzją.
"""

from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from scipy.signal import istft

DIR = pathlib.Path("experiments_priv/2026-07-31_utwor")
PAPER, INK, ACC = "#efece4", "#141414", "#e0483c"

SR = 44100
NPER, HOP = 4096, 1024
TOTAL = 168.0
BPM = 84.0
F_LO, F_HI = 25.0, 18000.0            # rama: całe słyszenie
OLD_LO, OLD_HI = 55.0, 6800.0         # stara rama — do pomiaru, ile ucinała

rng = np.random.default_rng(13)

FRAMES = int(TOTAL * SR / HOP)
FREQS = np.fft.rfftfreq(NPER, 1 / SR)
BAND = np.where((FREQS >= F_LO) & (FREQS <= F_HI))[0]
NB = len(BAND)
BHZ = FREQS[BAND]
DF = float(BHZ[1] - BHZ[0])
T_AX = np.arange(FRAMES) * HOP / SR
DORIAN = [50, 52, 53, 55, 57, 59, 60]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def bin_of(f: float) -> float:
    return float((f - BHZ[0]) / DF)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ridge(field, fb, t0, t1, amp, width):
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


def paint_A():
    """Ręka — teraz z cieniem oktawę niżej: szeroka rama dała jej dół."""
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
            drift = rng.normal(0, 0.35)
            for h in range(1, 9):
                f = hz(m + drift) * h
                if f < F_HI:
                    ridge(A, bin_of(f), t, min(t + dur, FRAMES),
                          1.0 / h ** 1.25, 2.6 + 0.5 * h)
            sub = hz(m + drift) / 2
            if sub > F_LO:
                ridge(A, bin_of(sub), t, min(t + dur, FRAMES), 0.5, 3.5)
            t += dur + int(rng.uniform(0.2, 1.2) * SR / HOP)
    return gaussian_filter(A, sigma=(1.2, 2.0))


B_PITCHES = [38, 50, 57, 62, 66, 69]         # D1 na dole — fundament z szerokiej ramy
B_HARM = []
for m in B_PITCHES:
    for h in range(1, 24):
        f = hz(m) * h
        if F_LO < f < F_HI:
            B_HARM.append(f)
B_HARM = np.array(sorted(B_HARM))


def gate_of():
    g = np.zeros(FRAMES, dtype=np.float32)
    step = 60.0 / BPM / 2
    k, tt = 0, 0.0
    while tt < TOTAL:
        i = int(tt * SR / HOP)
        j = min(i + int(step * 0.72 * SR / HOP), FRAMES)
        if j > i:
            g[i:j] = np.linspace(1, 0.15, j - i) ** 1.4 * (1.3 if k % 4 == 0 else 1.0)
        tt += step
        k += 1
    return g


GATE = gate_of()


def paint_B():
    """Siatka — harmoniczne aż po powietrze, 1/h^1.1 zamiast urwania na szóstej."""
    B = np.zeros((NB, FRAMES), dtype=np.float32)
    for m in B_PITCHES:
        for h in range(1, 24):
            f = hz(m) * h
            if not (F_LO < f < F_HI):
                continue
            a = 1.0 / h ** 1.1
            prof = np.exp(-0.5 * ((np.arange(NB) - bin_of(f)) / 1.1) ** 2)
            B += a * prof[:, None] * GATE[None, :]
    return B


def warp_columns(X, disp):
    out = np.empty_like(X)
    idx = np.arange(NB, dtype=np.float64)
    for t in range(X.shape[1]):
        out[:, t] = np.interp(np.clip(idx - disp[:, t], 0, NB - 1), idx, X[:, t])
    return out


def transform_AB(A, B):
    grad = np.gradient(gaussian_filter(A, sigma=(3.0, 6.0)), axis=0)
    disp = 7.0 * grad / (np.abs(grad).max() + 1e-9)
    envA = gaussian_filter1d(A.mean(axis=0), 8)
    envA /= envA.max() + 1e-9
    bent = warp_columns(B, disp)
    soft = gaussian_filter1d(bent, sigma=4, axis=1)
    return bent * (1 - 0.6 * envA)[None, :] + soft * (0.6 * envA)[None, :]


def transform_BA(A):
    idx = np.arange(NB, dtype=np.float64)
    hb = (B_HARM - BHZ[0]) / DF
    near = hb[np.argmin(np.abs(idx[:, None] - hb[None, :]), axis=1)]
    disp = np.clip(near - idx, -9, 9)[:, None] * np.ones((1, FRAMES)) * 0.65
    return warp_columns(A, disp) * (0.5 + 0.5 * GATE)[None, :]


def phi_of(An, Bn, H):
    nfft = 2 * NB
    FA = np.fft.rfft(An, n=nfft, axis=0)
    FB = np.fft.rfft(Bn, n=nfft, axis=0)
    ssum = np.fft.irfft(FA * FB, n=nfft, axis=0)[:NB]
    FBr = np.fft.rfft(Bn[::-1], n=nfft, axis=0)
    sdif = np.fft.irfft(FA * FBr, n=nfft, axis=0)[:NB]
    raw = gaussian_filter(np.abs(ssum) + np.abs(sdif), sigma=(2.0, 3.0))
    raw /= raw.max() + 1e-12
    return raw * (0.30 + 0.70 * H)[None, :]


def one_pass(A, B, mA, mB):
    An = A / (A.max() + 1e-9)
    Bn = B / (B.max() + 1e-9)
    c_t = smoothstep((T_AX - 40) / 34)
    C = (c_t[None, :] * np.sqrt(gaussian_filter(An, 3) * gaussian_filter(Bn, 3))).astype(np.float32)
    d_t = 3.0 * np.cos(np.pi * np.clip((T_AX - 40) / (TOTAL - 40), 0, 1))
    fn = (np.arange(NB) / NB)[:, None]
    sig = 1.0 / (1.0 + np.exp(-(d_t[None, :] + 0.8 * (1 - 2 * fn))))
    R = sig * transform_AB(A, B) + (1 - sig) * transform_BA(A)
    inter = (C * R).mean(axis=0)
    lam = float(np.exp(-(HOP / SR) / 3.0))
    H = np.zeros(FRAMES, dtype=np.float32)
    acc = 0.0
    for t in range(FRAMES):
        acc = lam * acc + (1 - lam) * float(inter[t])
        H[t] = acc
    H /= H.max() + 1e-12
    syn_f = np.exp(-0.5 * ((np.log(BHZ + 1e-9) - np.log(900)) / 1.4) ** 2)[:, None]
    Syn = (syn_f * smoothstep((T_AX - 70) / 50)[None, :]).astype(np.float32)
    Phi = phi_of(An, Bn, H)
    S = mA[None, :] * A + mB[None, :] * B + 1.15 * C * R + 2.1 * Syn * Phi
    return S.astype(np.float32), Phi, H


# ── partytura (jak w calkowanie.py, z panoramą) ─────────────────────
MAX_POLY, MIN_FRAMES = 90, 4
FADE = int(0.005 * SR)


def track_partials(S):
    thresh = S.max() * 3e-4
    live, done = [], []
    for t in range(S.shape[1]):
        c = S[:, t]
        idx = np.where((c[1:-1] > c[:-2]) & (c[1:-1] > c[2:]) & (c[1:-1] > thresh))[0] + 1
        peaks = sorted(((float(BHZ[i]), float(c[i])) for i in idx),
                       key=lambda p: -p[1])[:MAX_POLY]
        used = [False] * len(peaks)
        for tr in live:
            best, bd = -1, 1e9
            for k, (f, a) in enumerate(peaks):
                if not used[k] and abs(f - tr["f"][-1]) < bd:
                    best, bd = k, abs(f - tr["f"][-1])
            if best >= 0 and bd <= max(0.035 * tr["f"][-1], 1.6 * DF):
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


def synthesize_stereo(tracks, pan_field, n_samples):
    """Oscylatory z panoramą: linia gra tam, skąd pochodzi na płótnie."""
    L = np.zeros(n_samples)
    Rr = np.zeros(n_samples)
    prng = np.random.default_rng(3)
    for tr in tracks:
        fr = np.array(tr["t"], dtype=np.float64)
        p0, p1 = int(fr[0] * HOP), min(int(fr[-1] * HOP) + FADE, n_samples)
        if p1 - p0 < FADE * 2:
            continue
        n = np.arange(p0, p1)
        f = np.interp(n / HOP, fr, tr["f"])
        a = np.interp(n / HOP, fr, tr["a"])
        ph = 2 * np.pi * np.cumsum(f) / SR + prng.uniform(0, 2 * np.pi)
        seg = a * np.sin(ph)
        k = min(FADE, len(seg) // 2)
        seg[:k] *= np.linspace(0, 1, k)
        seg[-k:] *= np.linspace(1, 0, k)
        # panorama z pola: gdzie na płótnie leżała ta linia
        pans = [float(pan_field[min(int(bin_of(ff)), NB - 1), int(tt)])
                for ff, tt in zip(tr["f"], tr["t"])]
        p = np.interp(n / HOP, fr, pans)
        th = (p + 1) * np.pi / 4                      # stała moc
        L[p0:p1] += seg * np.cos(th)
        Rr[p0:p1] += seg * np.sin(th)
    return L, Rr


def noise_stereo(N):
    """Plamy: niezależna faza w kanałach — trzeci materiał nie ma miejsca, ma rozpiętość."""
    out = []
    for seed in (9, 10):
        prng = np.random.default_rng(seed)
        mag = np.zeros((len(FREQS), N.shape[1]), dtype=np.float32)
        mag[BAND] = gaussian_filter(N, sigma=(1.0, 2.0))
        Z = mag * np.exp(2j * np.pi * prng.random(mag.shape).astype(np.float32))
        _, x = istft(Z, SR, nperseg=NPER, noverlap=NPER - HOP)
        out.append(x)
    return out


def main() -> int:
    print(f"rama: {F_LO:.0f} Hz – {F_HI / 1000:.0f} kHz (stara była "
          f"{OLD_LO:.0f}–{OLD_HI:.0f})", flush=True)
    A, B = paint_A(), paint_B()
    mA = np.clip(smoothstep((20 - T_AX) / 6) + smoothstep((T_AX - 34) / 6), 0, 1)
    mB = smoothstep((T_AX - 20) / 6)
    fade = 1 - smoothstep((T_AX - 148) / 14)
    mA, mB = mA * fade, mB * np.clip(fade + 0.15, 0, 1)

    _, Phi1, _ = one_pass(A, B, mA, mB)
    fb = smoothstep((T_AX - 112) / 20)[None, :]
    S, Phi, H = one_pass((A + 0.35 * fb * Phi1 * A.max()).astype(np.float32),
                         (B + 0.25 * fb * Phi1 * B.max()).astype(np.float32),
                         mA, mB)
    S *= smoothstep(T_AX / 4)[None, :]

    # ILE IN BETWEEN UCINAŁA STARA RAMA — to jest liczba tego eksperymentu
    outside = ((BHZ < OLD_LO) | (BHZ > OLD_HI))
    cut = float((Phi[outside] ** 2).sum() / ((Phi ** 2).sum() + 1e-12))
    print(f"trzeci materiał Φ poza starą ramą: {cut * 100:.0f}% jego energii "
          f"— tyle in between było ucinane", flush=True)

    # panorama: ręka w lewo, siatka w prawo, oddziaływanie w środku
    An = A / (A.max() + 1e-9)
    Bn = B / (B.max() + 1e-9)
    wa, wb = mA[None, :] * An, mB[None, :] * Bn
    pan = (-0.62 * wa + 0.62 * wb) / (wa + wb + 0.35)

    print("czytam partyturę…", flush=True)
    tracks = track_partials(S)
    R = np.zeros_like(S)
    prof = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)
    for tr in tracks:
        for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
            b = int(round(bin_of(f)))
            lo, hi = max(0, b - 4), min(NB, b + 5)
            R[lo:hi, t] = np.maximum(R[lo:hi, t], a * prof[lo - b + 4: hi - b + 4])
    N = np.maximum(S - R, 0.0)
    e_lin = float((np.minimum(R, S) ** 2).sum())
    e_pla = float((N ** 2).sum())
    print(f"  {len(tracks)} linii · linie {e_lin / (e_lin + e_pla) * 100:.0f}% · "
          f"plamy {e_pla / (e_lin + e_pla) * 100:.0f}%", flush=True)

    n_samp = int(TOTAL * SR)
    print("gram linie w przestrzeni…", flush=True)
    Ls, Rs = synthesize_stereo(tracks, pan, n_samp)
    print("szumię plamy na szeroko…", flush=True)
    Ln, Rn = noise_stereo(N)
    Ln, Rn = Ln[:n_samp], Rn[:n_samp]
    Ln = np.pad(Ln, (0, n_samp - len(Ln)))
    Rn = np.pad(Rn, (0, n_samp - len(Rn)))

    sin_rms = np.sqrt(((Ls + Rs) ** 2).mean())
    noi_rms = np.sqrt(((Ln + Rn) ** 2).mean())
    g = np.sqrt(e_pla / (e_lin + 1e-12)) * sin_rms / (noi_rms + 1e-12)
    L = Ls + g * Ln
    Rr = Rs + g * Rn
    mix = np.stack([L, Rr])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    sf.write(DIR / "szeroka_rama.wav", mix.T, SR, subtype="PCM_24")
    print(f"korelacja kanałów {np.corrcoef(mix[0], mix[1])[0, 1]:.3f} "
          f"(ręka lewo · siatka prawo · Φ szeroko)")

    # obraz: pełne płótno, stara rama jako ramka — widać, co było za ścianą
    fig, ax = plt.subplots(figsize=(14, 6.4), facecolor=PAPER)
    Sd = 20 * np.log10(S + 1e-6)
    top = Sd.max()
    ax.pcolormesh(T_AX, BHZ, np.clip(Sd, top - 64, top),
                  shading="gouraud", cmap="magma", rasterized=True)
    ax.axhline(OLD_LO, color="#7fd8d8", lw=1.3, ls=(0, (5, 4)))
    ax.axhline(OLD_HI, color="#7fd8d8", lw=1.3, ls=(0, (5, 4)))
    ax.text(2, OLD_HI * 1.25, "stara rama — wszystko powyżej i poniżej było ucinane",
            color="#7fd8d8", fontsize=9, family="monospace")
    ax.set_yscale("log")
    ax.set_ylim(F_LO, F_HI)
    ax.set_yticks([31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
    ax.set_yticklabels(["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"])
    ax.set_xlabel("czas [s]", color=INK, fontsize=9)
    ax.set_ylabel("częstotliwość [Hz]", color=INK, fontsize=9)
    ax.set_title(f"SZEROKA RAMA — {F_LO:.0f} Hz do {F_HI / 1000:.0f} kHz; "
                 f"{cut * 100:.0f}% trzeciego materiału żyło za starą ścianą",
                 color=INK, fontsize=12, loc="left", pad=10, family="monospace")
    ax.set_facecolor(PAPER)
    for sp in ax.spines.values():
        sp.set_color(INK)
    ax.tick_params(colors=INK, labelsize=8)
    fig.savefig(DIR / "szeroka_rama.png", dpi=150, facecolor=PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'szeroka_rama.wav'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

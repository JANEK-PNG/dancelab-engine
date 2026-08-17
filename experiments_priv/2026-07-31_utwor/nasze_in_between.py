"""NASZE IN BETWEEN — na dobranoc. Wszystko z dzisiaj, w jednym utworze.

Dwa głosy, jak rano: ręka (dryf, formanty, nic się nie powtarza) i siatka
(dokładne stosunki, puls). Ale teraz z całą wiedzą dnia:

  RAMA SZEROKA        25 Hz – 18 kHz; składowe różnicowe i sumacyjne trzeciego
                      materiału nie są ucinane (rano traciliśmy ich 48 %).
  WEJŚCIE POLICZONE   siatka wchodzi tam, gdzie ręka opiera się na środku
                      i schodzi z dołu — reguła Janka, 71 % jego wejść.
  SZEW = 171 UDERZEŃ  mediana jego własnych szwów; dół zmienia właściciela
                      na 97 % szwu, nie w połowie.
  TEMPO SCHODAMI      78 → 84 → 90, nigdy w dół — klatka schodowa.
  IN BETWEEN Z PAMIĘCI sprzężenie i Φ rodzą się z tego, co zalega (~2 s),
                      nie z ataków; Φ oddycha: wdech 1,2 s, wydech 4 s.
  DŁUGIE NAŚWIETLANIE nuty zostawiają smugi (1,4 s) — światło się akumuluje.
  WYKONANIE, NIE ZDJĘCIE linie grają oscylatorami z fazą całkowaną, plamy
                      jako ukształtowany szum — zero zgadywania fazy.
  PRZESTRZEŃ          ręka po lewej, siatka po prawej, in between szerokie;
                      dół w mono, bo tak gra klub.

Dramaturgia: ręka sama → siatka wchodzi w policzonym miejscu → szew 171 uderzeń
→ ZAMROŻENIE: oba głosy schodzą prawie do zera i przez czterdzieści sekund gra
tylko to, co między nimi powstało i co pamięć podtrzymuje → wracają odmienieni
(Φ wpływa zwrotnie na oboje) → i koniec nie na żadnym z głosów, tylko na tym,
co między. Jak zawsze u nas.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from scipy.signal import istft, lfilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import szeroka_rama as Z                                      # noqa: E402
from oddech import breath, slow, synth_smooth                 # noqa: E402

SR = Z.SR
DIR = Z.DIR

# ── nowa oś czasu (dłuższa niż w szerokiej ramie) ──
# 171 uderzeń przy 84 BPM to 122 s szwu — więcej niż w pierwszym planie.
# Wydłużamy utwór, nie szew: szew jest zmierzoną medianą Janka i jego nie ruszamy.
TOTAL = 272.0
Z.TOTAL = TOTAL
Z.FRAMES = int(TOTAL * SR / Z.HOP)
Z.T_AX = np.arange(Z.FRAMES) * Z.HOP / SR
T = Z.T_AX
DT = Z.HOP / SR

FLOORS = [(0.0, 78.0), (None, 84.0), (None, 90.0)]   # progi wstawimy po pomiarze
BLEND_BEATS = 171
BASS_AT = 0.97


def stair_gate(floors):
    """Bramka ósemkowa po klatce schodowej — tempo nigdy w dół."""
    g = np.zeros(Z.FRAMES, dtype=np.float32)
    tt, k = 0.0, 0
    while tt < TOTAL:
        bpm = [b for t0, b in floors if t0 is not None and tt >= t0][-1]
        step = 60.0 / bpm / 2
        i = int(tt * SR / Z.HOP)
        j = min(i + int(step * 0.72 * SR / Z.HOP), Z.FRAMES)
        if j > i:
            g[i:j] = np.linspace(1, 0.15, j - i) ** 1.4 * (1.3 if k % 4 == 0 else 1.0)
        tt += step
        k += 1
    # lekcja z oddechu: krawędzie miękkie, podłoga wyżej
    return gaussian_filter1d(np.maximum(g, 0.45 * (g > 0)), 3.0).astype(np.float32)


def seg(t0, t1, up=4.0):
    """Maska: wejdź w t0, zejdź w t1, miękko."""
    return Z.smoothstep((T - t0) / up) * (1 - Z.smoothstep((T - t1) / up))


def main() -> int:
    print("maluję rękę…", flush=True)
    A = Z.paint_A()

    # WEJŚCIE POLICZONE — na polu ręki, regułą Janka: środek w górę, dół w dół
    low = A[Z.BHZ < 200].mean(axis=0)
    mid = A[(Z.BHZ > 200) & (Z.BHZ < 3000)].mean(axis=0)
    lo_s = gaussian_filter1d(low, int(4 / DT))
    mi_s = gaussian_filter1d(mid, int(4 / DT))
    win = (T > 30) & (T < 62)
    score = mi_s / (mi_s.mean() + 1e-9) - lo_s / (lo_s.mean() + 1e-9)
    entry = float(T[win][np.argmax(score[win])])
    blend = BLEND_BEATS * 60.0 / 84.0
    t_freeze = entry + blend
    t_back = t_freeze + 42.0
    swap = entry + BASS_AT * blend
    print(f"siatka wchodzi w {entry:.0f} s (środek w górę, dół w dół — twoja reguła)")
    print(f"szew {blend:.0f} s = {BLEND_BEATS} uderzeń · dół oddany w {swap:.0f} s "
          f"(97 %) · zamrożenie {t_freeze:.0f}–{t_back:.0f} s")

    FLOORS[1] = (entry, 84.0)
    FLOORS[2] = (t_back, 90.0)
    Z.GATE = stair_gate(FLOORS)
    print("maluję siatkę…", flush=True)
    B = Z.paint_B()

    # maski dramaturgii
    mA = seg(0, t_freeze, 5) + 0.18 * seg(t_freeze, t_back, 6) \
        + 0.75 * seg(t_back, TOTAL - 26, 6)
    mB = seg(entry, t_freeze, 8) * Z.smoothstep((T - entry) / 10) \
        + 0.25 * seg(t_freeze, t_back, 6) + 0.8 * seg(t_back, TOTAL - 24, 6)
    mA, mB = np.clip(mA, 0, 1), np.clip(mB, 0, 1)

    def one_pass(Af, Bf):
        An = Af / (Af.max() + 1e-9)
        Bn = Bf / (Bf.max() + 1e-9)
        As, Bs = slow(An, 1.5), slow(Bn, 1.5)
        c_t = Z.smoothstep((T - entry) / (blend * 0.5))
        C = (c_t[None, :] * np.sqrt(gaussian_filter(As, 3) * gaussian_filter(Bs, 3))
             ).astype(np.float32)
        d_t = 3.0 * np.cos(np.pi * np.clip((T - entry) / (TOTAL - entry), 0, 1))
        fn = (np.arange(Z.NB) / Z.NB)[:, None]
        sig = 1.0 / (1.0 + np.exp(-(d_t[None, :] + 0.8 * (1 - 2 * fn))))
        R = sig * Z.transform_AB(slow(Af, 1.2), Bf) + (1 - sig) * Z.transform_BA(Af)
        R = 0.45 * R + 0.55 * slow(R, 0.9)
        inter = (C * R).mean(axis=0)
        lam = float(np.exp(-DT / 3.0))
        H = np.zeros(Z.FRAMES, dtype=np.float32)
        acc = 0.0
        for t in range(Z.FRAMES):
            acc = lam * acc + (1 - lam) * float(inter[t])
            H[t] = acc
        H /= H.max() + 1e-12
        syn_f = np.exp(-0.5 * ((np.log(Z.BHZ + 1e-9) - np.log(900)) / 1.4) ** 2)[:, None]
        syn_t = Z.smoothstep((T - (entry + 0.4 * blend)) / 26)
        Syn = (syn_f * syn_t[None, :]).astype(np.float32)
        Phi = breath(Z.phi_of(slow(An, 2.0), slow(Bn, 2.0), H))
        return C, R, Syn, Phi, H

    print("pierwszy obrót wzoru…", flush=True)
    _, _, _, Phi1, _ = one_pass(A, B)
    fb = Z.smoothstep((T - t_back) / 14)[None, :]
    print("drugi obrót — Φ wraca do obojga…", flush=True)
    C, R, Syn, Phi, H = one_pass((A + 0.32 * fb * Phi1 * A.max()).astype(np.float32),
                                 (B + 0.24 * fb * Phi1 * B.max()).astype(np.float32))

    # przekazanie dołu na 97 % szwu — rzędy pod 200 Hz zmieniają właściciela
    low_rows = Z.BHZ < 200
    gA = 1 - Z.smoothstep((T - swap) / 3.0)
    gB = Z.smoothstep((T - swap) / 3.0)
    A_lo, B_lo = A * low_rows[:, None], B * low_rows[:, None]
    A_hi, B_hi = A - A_lo, B - B_lo
    S = (mA[None, :] * (A_hi + gA[None, :] * A_lo)
         + mB[None, :] * (B_hi + gB[None, :] * B_lo)
         + 1.15 * C * R
         + 2.3 * Syn * Phi * (1 + 0.9 * seg(t_freeze, t_back, 5))[None, :])
    S *= Z.smoothstep(T / 4)[None, :] * (1 - Z.smoothstep((T - (TOTAL - 9)) / 8))[None, :]

    # długie naświetlanie: smugi 1,4 s
    lam = float(np.exp(-DT / 1.4))
    S = (S + 1.1 * lfilter([1 - lam], [1, -lam], S, axis=1)).astype(np.float32)

    # przestrzeń: ręka lewo, siatka prawo, dół w mono
    An = A / (A.max() + 1e-9)
    Bn = B / (B.max() + 1e-9)
    pan = (-0.62 * mA[None, :] * An + 0.62 * mB[None, :] * Bn) \
        / (mA[None, :] * An + mB[None, :] * Bn + 0.35)
    pan[low_rows] = 0.0

    print("czytam partyturę…", flush=True)
    tracks = Z.track_partials(S)
    Rg = np.zeros_like(S)
    prof = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)
    for tr in tracks:
        for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
            b = int(round(Z.bin_of(f)))
            lo_, hi_ = max(0, b - 4), min(Z.NB, b + 5)
            Rg[lo_:hi_, t] = np.maximum(Rg[lo_:hi_, t], a * prof[lo_ - b + 4: hi_ - b + 4])
    N = np.maximum(S - Rg, 0.0)
    e_lin = float((np.minimum(Rg, S) ** 2).sum())
    e_pla = float((N ** 2).sum())
    print(f"  {len(tracks)} linii · linie {e_lin / (e_lin + e_pla) * 100:.0f}% "
          f"· plamy {e_pla / (e_lin + e_pla) * 100:.0f}%", flush=True)

    n_samp = int(TOTAL * SR)
    print("gram linie…", flush=True)
    Ls, Rs = synth_smooth(tracks, pan, n_samp)

    print("szumię plamy (dół mono, reszta szeroko)…", flush=True)
    def shaped(Nn, seed):
        prng = np.random.default_rng(seed)
        mag = np.zeros((len(Z.FREQS), Nn.shape[1]), dtype=np.float32)
        mag[Z.BAND] = gaussian_filter(Nn, sigma=(1.0, 8.0))
        Zc = mag * np.exp(2j * np.pi * prng.random(mag.shape).astype(np.float32))
        _, x = istft(Zc, SR, nperseg=Z.NPER, noverlap=Z.NPER - Z.HOP)
        x = x[:n_samp]
        return np.pad(x, (0, n_samp - len(x)))
    N_lo, N_hi = N * low_rows[:, None], N * (~low_rows)[:, None]
    mono = shaped(N_lo, 7)
    Lh, Rh = shaped(N_hi, 9), shaped(N_hi, 10)
    g = np.sqrt(e_pla / (e_lin + 1e-12)) * (np.sqrt(((Ls + Rs) ** 2).mean())
        / (np.sqrt(((Lh + Rh + 2 * mono) ** 2).mean()) + 1e-12))
    mix = np.stack([Ls + g * (Lh + mono), Rs + g * (Rh + mono)])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    sf.write(DIR / "nasze_in_between.wav", mix.T, SR, subtype="PCM_24")

    m = mix.mean(axis=0)
    for a, b, lab in [(4, entry - 4, "ręka sama"),
                      (entry + 4, t_freeze - 4, f"szew ({BLEND_BEATS} uderzeń)"),
                      (t_freeze + 4, t_back - 4, "ZAMROŻENIE — samo in between"),
                      (t_back + 4, TOTAL - 28, "razem, odmienieni"),
                      (TOTAL - 22, TOTAL - 10, "zostaje to, co między")]:
        s = slice(int(a * SR), int(b * SR))
        print(f"  {lab:34s} {a:5.0f}–{b:5.0f}s  "
              f"{20 * np.log10(np.sqrt((m[s] ** 2).mean()) + 1e-12):6.1f} dB")
    print(f"korelacja kanałów {np.corrcoef(mix[0], mix[1])[0, 1]:.3f}")
    print(f"\n{DIR / 'nasze_in_between.wav'} — {TOTAL / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

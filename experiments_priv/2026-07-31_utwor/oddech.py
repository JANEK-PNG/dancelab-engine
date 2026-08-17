"""Oddech: in between wygładzone — poprawka wykonania, nie wzoru.

Janek: „zawsze myślałem, że in between jest gładkie, miękkie, oddycha — moment
zamrożenia. A to brzmi falująco i posiekane. Może mam błąd we wzorze?"

Błąd nie jest we wzorze i nie jest w przeczuciu — jest w moim wykonaniu,
a przeczucie Janka zgadza się z naszymi POMIARAMI:

  * jego własne szwy: blend mediana 86 s, gest wolny, bas trzymany i oddany
    raz — ręce się NIE trzęsą w rytmie ósemek;
  * czerń między nutami autoportretu to była pamięć (pogłos) — gładka z natury.

Skąd wzięła się chropowatość: liczyłem Φ Z CHWILI — iloczyn A i B klatka po
klatce — więc trzeci materiał odziedziczył bramkę siatki. A w zapisie Kordiego
H stoi WEWNĄTRZ Φ(A,B,H;F): trzeci materiał powstaje z tego, co zalega,
nie z tego, co kłuje. Czytałem H za płytko — jako mnożnik, nie jako tworzywo.

Trzy zmiany, wszystkie w wykonaniu:

  1. INTERAKCJE Z PAMIĘCI. C oraz Φ liczone z pól wygładzonych w czasie
     (~1,5–2 s): sprzęga się i rodzi trzeci materiał to, co PO dźwiękach
     zostaje, nie ich ataki. Siatka dalej tyka — jej tożsamość zostaje —
     ale jej wpływ na wspólne pole płynie.
  2. ODDECH ZAMIAST BRAMKI. Obwiednia Φ przepuszczona przez wdech/wydech:
     narastanie ~1,2 s, opadanie ~4 s. Nic w trzecim materiale nie może
     mignąć — może tylko wezbrać i opaść.
  3. GŁADKIE LINIE. Amplitudy torów wygładzone, zszycia 40 ms zamiast 5 ms,
     plamy rozmyte w czasie mocniej — szum oddycha zamiast trzepotać.

Miara, nie wrażenie: stosunek wolnych modulacji obwiedni (0,3–3 Hz — oddech)
do szybkich (4–30 Hz — trzepot), przed i po.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from scipy.signal import butter, sosfiltfilt, istft

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import szeroka_rama as Z                                      # noqa: E402

DIR = Z.DIR
SR = Z.SR
DT = Z.HOP / SR


def slow(X: np.ndarray, sec: float) -> np.ndarray:
    """To, co z pola zostaje po geście — pamięć zamiast chwili."""
    return gaussian_filter1d(X, sigma=max(1.0, sec / DT), axis=1)


def breath(Phi: np.ndarray, atk: float = 1.2, rel: float = 4.0) -> np.ndarray:
    """Wdech/wydech: obwiednia Φ może wzbierać i opadać, nigdy migać."""
    e = Phi.mean(axis=0)
    out = np.empty_like(e)
    acc = float(e[0])
    ka = 1 - np.exp(-DT / atk)
    kr = 1 - np.exp(-DT / rel)
    for t in range(len(e)):
        k = ka if e[t] > acc else kr
        acc += (float(e[t]) - acc) * k
        out[t] = acc
    scale = np.clip(out / (e + 1e-12), 0.2, 5.0)
    return Phi * scale[None, :].astype(np.float32)


def one_pass_smooth(A, B, mA, mB):
    """one_pass z szerokiej ramy, ale sprzężenie i Φ rodzą się z pamięci pól."""
    An = A / (A.max() + 1e-9)
    Bn = B / (B.max() + 1e-9)
    As, Bs = slow(An, 1.5), slow(Bn, 1.5)

    c_t = Z.smoothstep((Z.T_AX - 40) / 34)
    C = (c_t[None, :] * np.sqrt(gaussian_filter(As, 3) * gaussian_filter(Bs, 3))
         ).astype(np.float32)

    d_t = 3.0 * np.cos(np.pi * np.clip((Z.T_AX - 40) / (Z.TOTAL - 40), 0, 1))
    fn = (np.arange(Z.NB) / Z.NB)[:, None]
    sig = 1.0 / (1.0 + np.exp(-(d_t[None, :] + 0.8 * (1 - 2 * fn))))

    # geometrię odkształca WOLNE A (ręka porusza się w sekundach, nie ósemkach)
    R = sig * Z.transform_AB(slow(A, 1.2), B) + (1 - sig) * Z.transform_BA(A)
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
    Syn = (syn_f * Z.smoothstep((Z.T_AX - 70) / 50)[None, :]).astype(np.float32)

    Phi = breath(Z.phi_of(slow(An, 2.0), slow(Bn, 2.0), H))
    S = mA[None, :] * A + mB[None, :] * B + 1.15 * C * R + 2.1 * Syn * Phi
    return S.astype(np.float32), Phi, H


def synth_smooth(tracks, pan_field, n_samples):
    """Jak w szerokiej ramie, ale amplitudy płyną i zszycia mają 40 ms."""
    L = np.zeros(n_samples)
    Rr = np.zeros(n_samples)
    prng = np.random.default_rng(3)
    fade = int(0.04 * SR)
    for tr in tracks:
        fr = np.array(tr["t"], dtype=np.float64)
        p0, p1 = int(fr[0] * Z.HOP), min(int(fr[-1] * Z.HOP) + fade, n_samples)
        if p1 - p0 < fade * 2:
            continue
        amps = gaussian_filter1d(np.array(tr["a"], dtype=np.float64), 2.0)
        n = np.arange(p0, p1)
        f = np.interp(n / Z.HOP, fr, tr["f"])
        a = np.interp(n / Z.HOP, fr, amps)
        ph = 2 * np.pi * np.cumsum(f) / SR + prng.uniform(0, 2 * np.pi)
        seg = a * np.sin(ph)
        k = min(fade, len(seg) // 2)
        seg[:k] *= np.linspace(0, 1, k)
        seg[-k:] *= np.linspace(1, 0, k)
        pans = [float(pan_field[min(int(Z.bin_of(ff)), Z.NB - 1), int(tt)])
                for ff, tt in zip(tr["f"], tr["t"])]
        th = (np.interp(n / Z.HOP, fr, pans) + 1) * np.pi / 4
        L[p0:p1] += seg * np.cos(th)
        Rr[p0:p1] += seg * np.sin(th)
    return L, Rr


def noise_breathing(N):
    out = []
    for seed in (9, 10):
        prng = np.random.default_rng(seed)
        mag = np.zeros((len(Z.FREQS), N.shape[1]), dtype=np.float32)
        mag[Z.BAND] = gaussian_filter(N, sigma=(1.0, 8.0))     # plamy oddychają
        Zc = mag * np.exp(2j * np.pi * prng.random(mag.shape).astype(np.float32))
        _, x = istft(Zc, SR, nperseg=Z.NPER, noverlap=Z.NPER - Z.HOP)
        out.append(x)
    return out


def mod_ratio(path):
    """Oddech kontra trzepot: energia modulacji 0,3–3 Hz vs 4–30 Hz."""
    y, sr = sf.read(path, dtype="float64")
    y = y.mean(axis=1)
    env = np.abs(y)
    env = sosfiltfilt(butter(2, 40 / (sr / 2), btype="lowpass", output="sos"), env)
    env = env[:: sr // 200]                                    # 200 Hz
    env = np.log(np.maximum(env, 1e-7))   # log(0) dawał nan w mierze
    F = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
    fr = np.fft.rfftfreq(len(env), 1 / 200)
    slow_e = F[(fr > 0.3) & (fr < 3)].sum()
    fast_e = F[(fr > 4) & (fr < 30)].sum()
    return 10 * np.log10(slow_e / (fast_e + 1e-12))


def main() -> int:
    # Bramka siatki u źródła: ósemki zostają (tożsamość siatki to rytm), ale
    # każda opada do połowy zamiast do 0,15 i ma krawędzie zmiękczone ~70 ms.
    # Trzepot mieszkał głównie tutaj — Φ tylko go dziedziczyło.
    Z.GATE = gaussian_filter1d(
        np.maximum(Z.GATE, 0.45 * (Z.GATE > 0)), 3.0).astype(np.float32)
    A, B = Z.paint_A(), Z.paint_B()
    mA = np.clip(Z.smoothstep((20 - Z.T_AX) / 6) + Z.smoothstep((Z.T_AX - 34) / 6), 0, 1)
    mB = Z.smoothstep((Z.T_AX - 20) / 6)
    fade = 1 - Z.smoothstep((Z.T_AX - 148) / 14)
    mA, mB = mA * fade, mB * np.clip(fade + 0.15, 0, 1)

    _, Phi1, _ = one_pass_smooth(A, B, mA, mB)
    fb = Z.smoothstep((Z.T_AX - 112) / 20)[None, :]
    S, Phi, H = one_pass_smooth((A + 0.35 * fb * Phi1 * A.max()).astype(np.float32),
                                (B + 0.25 * fb * Phi1 * B.max()).astype(np.float32),
                                mA, mB)
    S *= Z.smoothstep(Z.T_AX / 4)[None, :]

    An = A / (A.max() + 1e-9)
    Bn = B / (B.max() + 1e-9)
    pan = (-0.62 * mA[None, :] * An + 0.62 * mB[None, :] * Bn) \
        / (mA[None, :] * An + mB[None, :] * Bn + 0.35)

    print("czytam partyturę…", flush=True)
    tracks = Z.track_partials(S)
    R = np.zeros_like(S)
    prof = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)
    for tr in tracks:
        for t, f, a in zip(tr["t"], tr["f"], tr["a"]):
            b = int(round(Z.bin_of(f)))
            lo, hi = max(0, b - 4), min(Z.NB, b + 5)
            R[lo:hi, t] = np.maximum(R[lo:hi, t], a * prof[lo - b + 4: hi - b + 4])
    N = np.maximum(S - R, 0.0)
    e_lin = float((np.minimum(R, S) ** 2).sum())
    e_pla = float((N ** 2).sum())
    print(f"  {len(tracks)} linii · linie {e_lin / (e_lin + e_pla) * 100:.0f}% "
          f"· plamy {e_pla / (e_lin + e_pla) * 100:.0f}%", flush=True)

    n_samp = int(Z.TOTAL * SR)
    print("gram…", flush=True)
    Ls, Rs = synth_smooth(tracks, pan, n_samp)
    Ln, Rn = noise_breathing(N)
    Ln = np.pad(Ln[:n_samp], (0, max(0, n_samp - len(Ln))))
    Rn = np.pad(Rn[:n_samp], (0, max(0, n_samp - len(Rn))))
    g = np.sqrt(e_pla / (e_lin + 1e-12)) * (np.sqrt(((Ls + Rs) ** 2).mean())
                                            / (np.sqrt(((Ln + Rn) ** 2).mean()) + 1e-12))
    mix = np.stack([Ls + g * Ln, Rs + g * Rn])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    sf.write(DIR / "oddech.wav", mix.T, SR, subtype="PCM_24")

    r_old = mod_ratio(DIR / "szeroka_rama.wav")
    r_new = mod_ratio(DIR / "oddech.wav")
    print(f"\noddech kontra trzepot (0,3–3 Hz vs 4–30 Hz):")
    print(f"  przed: {r_old:+5.1f} dB   po: {r_new:+5.1f} dB   "
          f"zmiana {r_new - r_old:+.1f} dB w stronę oddechu")
    print(f"\n{DIR / 'oddech.wav'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

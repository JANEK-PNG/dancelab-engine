"""Which of my two suspicions actually broke the null test? Test both, separately."""
import sys
sys.path.insert(0, "/Users/jantrybus/Developer/dancelab-engine/scripts")
import numpy as np, librosa
from scipy.optimize import nnls
import seam_decompose as S

MIX = "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.wav"
A = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Skrillex, Ahadadream, Priya Ragu - TAKA (Caribou Remix).aiff"
B = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Caribou - Honey.aiff"
sa, sb = S.separate(A), S.separate(B)


def warp_linear(y, origin, rate, t0, t1):
    return S.warp(y, origin, rate, t0, t1)


def warp_proper(y, origin, rate, t0, t1):
    """Band-limited resampling instead of straight-line interpolation."""
    pad = 2.0
    ts, te = (t0 - origin) * rate - pad, (t1 - origin) * rate + pad
    i0, i1 = int(ts * S.SR), int(te * S.SR)
    seg = np.zeros(i1 - i0, dtype=np.float32)
    lo, hi = max(i0, 0), min(i1, len(y))
    if hi > lo:
        seg[lo - i0: hi - i0] = y[lo:hi]
    out = librosa.resample(seg, orig_sr=int(S.SR * 1000),
                           target_sr=int(S.SR * 1000 / rate), res_type="soxr_hq")
    # seg began at track time i0/SR, i.e. mix time origin + i0/SR/rate
    start_mix = origin + (i0 / S.SR) / rate
    k = int(round((t0 - start_mix) * S.SR))
    n = int(round((t1 - t0) * S.SR))
    res = np.zeros(n, dtype=np.float32)
    a, b = max(k, 0), min(k + n, len(out))
    if b > a:
        res[a - k: b - k] = out[a:b]
    return res


def fit(t0, t1, warpfn, model):
    mix = S.mag(S.load_mono(MIX, t0, t1))
    freqs = librosa.fft_frequencies(sr=S.SR, n_fft=S.N_FFT)
    wa = [S.mag(warpfn(sa[s], 1860.025, 1.0320, t0, t1)) for s in S.STEMS]
    wb = [S.mag(warpfn(sb[s], 1890.0, 1.0320, t0, t1)) for s in S.STEMS]
    n = min(mix.shape[1], *[x.shape[1] for x in wa + wb])
    mix = mix[:, :n]
    if model == "8stem":
        basis = [x[:, :n] for x in wa + wb]
        a_idx, b_idx = range(4), range(4, 8)
    else:                                   # 2 decks: one fader per deck per band
        basis = [sum(x[:, :n] for x in wa), sum(x[:, :n] for x in wb)]
        a_idx, b_idx = [0], [1]
    out = {}
    for band, (lo, hi) in S.BANDS.items():
        bins = np.where((freqs >= lo) & (freqs < hi))[0]
        M = mix[bins]
        BS = np.stack([x[bins] for x in basis])
        g = np.zeros((len(basis), n)); r = np.zeros(n)
        for t in range(n):
            bb = M[:, t]; sc = np.linalg.norm(bb)
            if sc < 1e-9:
                continue
            w, _ = nnls(BS[:, :, t].T / sc, bb / sc)
            g[:, t] = w
            r[t] = np.linalg.norm(bb - BS[:, :, t].T @ w) / sc
        pa = np.sqrt(np.maximum(g[list(a_idx)].sum(0), 0)).mean()
        pb = np.sqrt(np.maximum(g[list(b_idx)].sum(0), 0)).mean()
        out[band] = (pa, pb, pb / max(pa, 1e-9) * 100, r.mean() * 100)
    return out


print("okno 1900-1980 s: gra TYLKO TAKA. B to podstawiony prawdziwy sygnal Honey.")
print("dobry wynik = przeciek maly, reszta mala\n")
print(f"{'wariant':28s} {'pasmo':8s} {'A':>8s} {'B(falsz)':>9s} {'przeciek':>9s} {'reszta':>8s}")
for wname, wfn in [("interp liniowa", warp_linear), ("resampling soxr", warp_proper)]:
    for mname in ["8stem", "2deck"]:
        res = fit(1900, 1980, wfn, mname)
        for band, (pa, pb, leak, r) in res.items():
            print(f"{wname+' + '+mname:28s} {band:8s} {pa:8.2f} {pb:9.2f} {leak:8.1f}% {r:7.1f}%")
        print()

"""Fit sub-band energies over time blocks, not raw bins. Sweep the block length."""
import sys
sys.path.insert(0, "/Users/jantrybus/Developer/dancelab-engine/scripts")
import numpy as np, librosa
from scipy.optimize import nnls
import seam_decompose as S

MIX = "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.wav"
A = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Skrillex, Ahadadream, Priya Ragu - TAKA (Caribou Remix).aiff"
B = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Caribou - Honey.aiff"
ya, yb = S.load_mono(A), S.load_mono(B)

FREQS = librosa.fft_frequencies(sr=S.SR, n_fft=S.N_FFT)
SUB = np.geomspace(30, 18000, 25)                 # 24 sub-bands, log spaced
EQ = {"bas": (30, 300), "środek": (300, 3000), "góra": (3000, 18000)}


def subband_energy(y):
    P = S.mag(y)                                   # power spectrogram
    rows = []
    for lo, hi in zip(SUB[:-1], SUB[1:]):
        b = np.where((FREQS >= lo) & (FREQS < hi))[0]
        rows.append(P[b].sum(axis=0) if len(b) else np.zeros(P.shape[1]))
    return np.stack(rows), (SUB[:-1] + SUB[1:]) / 2


def fit(t0, t1, block_sec, b_origin):
    Em, ctr = subband_energy(S.load_mono(MIX, t0, t1))
    Ea, _ = subband_energy(S.warp(ya, 1860.025, 1.0320, t0, t1))
    Eb, _ = subband_energy(S.warp(yb, b_origin, 1.0320, t0, t1))
    n = min(Em.shape[1], Ea.shape[1], Eb.shape[1])
    Em, Ea, Eb = Em[:, :n], Ea[:, :n], Eb[:, :n]
    blk = max(2, int(round(block_sec * S.SR / S.HOP)))
    out = {}
    for band, (lo, hi) in EQ.items():
        rows = np.where((ctr >= lo) & (ctr < hi))[0]
        ga, gb, rs = [], [], []
        for t in range(0, n - blk + 1, max(1, blk // 2)):
            M = Em[rows, t:t + blk].ravel()
            X = np.stack([Ea[rows, t:t + blk].ravel(),
                          Eb[rows, t:t + blk].ravel()]).T
            sc = np.linalg.norm(M)
            if sc < 1e-12:
                continue
            w, _ = nnls(X / sc, M / sc)
            ga.append(w[0]); gb.append(w[1])
            rs.append(np.linalg.norm(M - X @ w) / sc)
        pa, pb = np.sqrt(np.mean(ga)), np.sqrt(np.mean(gb))
        out[band] = (pa, pb, pb / max(pa, 1e-9) * 100, np.mean(rs) * 100)
    return out


print("okno 1900-1980 s: gra TYLKO TAKA. B = prawdziwy Honey w zlym miejscu (1890).")
print("obserwacje = energie 24 podpasm x klatki w bloku\n")
print(f"{'blok':>8s}  {'pasmo':8s} {'A':>7s} {'B(falsz)':>9s} {'przeciek':>9s} {'reszta':>8s}")
for blk in [0.5, 1, 2, 4, 8]:
    for band, (pa, pb, leak, r) in fit(1900, 1980, blk, 1890.0).items():
        print(f"{blk:7.1f}s  {band:8s} {pa:7.3f} {pb:9.3f} {leak:8.1f}% {r:7.1f}%")
    print()

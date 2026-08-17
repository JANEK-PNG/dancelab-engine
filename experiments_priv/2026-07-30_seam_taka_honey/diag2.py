"""Two fixes at once, measured separately: deck basis = original, and fit over time blocks."""
import sys
sys.path.insert(0, "/Users/jantrybus/Developer/dancelab-engine/scripts")
import numpy as np, librosa
from scipy.optimize import nnls
import seam_decompose as S

MIX = "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.wav"
A = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Skrillex, Ahadadream, Priya Ragu - TAKA (Caribou Remix).aiff"
B = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Caribou - Honey.aiff"

ya = S.load_mono(A)
yb = S.load_mono(B)


def fit(t0, t1, block_sec, use_original=True):
    mix = S.mag(S.load_mono(MIX, t0, t1))
    freqs = librosa.fft_frequencies(sr=S.SR, n_fft=S.N_FFT)
    wa = S.mag(S.warp(ya, 1860.025, 1.0320, t0, t1))
    wb = S.mag(S.warp(yb, 1890.0, 1.0320, t0, t1))     # fake: real Honey, wrong place
    n = min(mix.shape[1], wa.shape[1], wb.shape[1])
    mix, wa, wb = mix[:, :n], wa[:, :n], wb[:, :n]
    blk = max(1, int(round(block_sec * S.SR / S.HOP)))
    out = {}
    for band, (lo, hi) in S.BANDS.items():
        bins = np.where((freqs >= lo) & (freqs < hi))[0]
        ga, gb, rs = [], [], []
        for t in range(0, n - blk + 1, blk):
            M = mix[bins, t:t + blk].ravel()
            X = np.stack([wa[bins, t:t + blk].ravel(), wb[bins, t:t + blk].ravel()]).T
            sc = np.linalg.norm(M)
            if sc < 1e-9:
                continue
            w, _ = nnls(X / sc, M / sc)
            ga.append(w[0]); gb.append(w[1])
            rs.append(np.linalg.norm(M - X @ w) / sc)
        pa, pb = np.sqrt(np.mean(ga)), np.sqrt(np.mean(gb))
        out[band] = (pa, pb, pb / max(pa, 1e-9) * 100, np.mean(rs) * 100)
    return out


print("okno 1900-1980 s: gra TYLKO TAKA. B = prawdziwy Honey podstawiony w zle miejsce.")
print("dobry wynik = przeciek maly, reszta mala. Baza decka = ORYGINAL utworu.\n")
print(f"{'okno czasu':>10s}  {'pasmo':8s} {'A':>7s} {'B(falsz)':>9s} {'przeciek':>9s} {'reszta':>8s}")
for blk in [0.046, 0.25, 1.0, 4.0, 16.0]:
    for band, (pa, pb, leak, r) in fit(1900, 1980, blk).items():
        print(f"{blk:9.3f}s  {band:8s} {pa:7.3f} {pb:9.3f} {leak:8.1f}% {r:7.1f}%")
    print()

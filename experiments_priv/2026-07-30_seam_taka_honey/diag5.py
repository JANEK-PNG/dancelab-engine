"""Does resolving bass NOTES separate the decks? Sweep FFT size and sub-band count."""
import sys
sys.path.insert(0, "/Users/jantrybus/Developer/dancelab-engine/scripts")
import numpy as np, librosa
from scipy.optimize import nnls
import seam_decompose as S

MIX = "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.wav"
A = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Skrillex, Ahadadream, Priya Ragu - TAKA (Caribou Remix).aiff"
B = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Caribou - Honey.aiff"
ya, yb = S.load_mono(A), S.load_mono(B)
EQ = {"bas": (30, 300), "środek": (300, 3000), "góra": (3000, 18000)}


def sub_energy(y, n_fft, hop, n_sub):
    P = (np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop)) ** 2).astype(np.float32)
    fr = librosa.fft_frequencies(sr=S.SR, n_fft=n_fft)
    edges = np.geomspace(30, 18000, n_sub + 1)
    rows = [P[np.where((fr >= lo) & (fr < hi))[0]].sum(axis=0)
            for lo, hi in zip(edges[:-1], edges[1:])]
    return np.stack(rows), (edges[:-1] + edges[1:]) / 2


def fit(n_fft, n_sub, block_sec, t0=1900, t1=1980, b_origin=1890.0):
    hop = n_fft // 4
    Em, ctr = sub_energy(S.load_mono(MIX, t0, t1), n_fft, hop, n_sub)
    Ea, _ = sub_energy(S.warp(ya, 1860.025, 1.0320, t0, t1), n_fft, hop, n_sub)
    Eb, _ = sub_energy(S.warp(yb, b_origin, 1.0320, t0, t1), n_fft, hop, n_sub)
    n = min(Em.shape[1], Ea.shape[1], Eb.shape[1])
    blk = max(2, int(round(block_sec * S.SR / hop)))
    out = {}
    for band, (lo, hi) in EQ.items():
        rows = np.where((ctr >= lo) & (ctr < hi))[0]
        ga, gb, rs = [], [], []
        for t in range(0, n - blk + 1, max(1, blk // 2)):
            M = Em[np.ix_(rows, range(t, t + blk))].ravel()
            X = np.stack([Ea[np.ix_(rows, range(t, t + blk))].ravel(),
                          Eb[np.ix_(rows, range(t, t + blk))].ravel()]).T
            sc = np.linalg.norm(M)
            if sc < 1e-12:
                continue
            w, _ = nnls(X / sc, M / sc)
            ga.append(w[0]); gb.append(w[1]); rs.append(np.linalg.norm(M - X @ w) / sc)
        out[band] = (np.sqrt(np.mean(ga)), np.sqrt(np.mean(gb)),
                     np.sqrt(np.mean(gb)) / max(np.sqrt(np.mean(ga)), 1e-9) * 100,
                     np.mean(rs) * 100)
    return out


print("okno 1900-1980 s: gra TYLKO TAKA. B = prawdziwy Honey, przypadkiem zgrany w takt.")
print(f"{'n_fft':>7s} {'Hz/prazek':>10s} {'podpasm':>8s}  {'pasmo':8s} {'A':>7s} {'B(falsz)':>9s} {'przeciek':>9s} {'reszta':>8s}")
for n_fft in [4096, 16384]:
    for n_sub in [24, 64]:
        for band, (pa, pb, leak, r) in fit(n_fft, n_sub, 1.0).items():
            print(f"{n_fft:7d} {S.SR/n_fft:10.1f} {n_sub:8d}  {band:8s} "
                  f"{pa:7.3f} {pb:9.3f} {leak:8.1f}% {r:7.1f}%")
        print()

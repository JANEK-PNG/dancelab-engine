"""Stop modelling. Look at the two signals directly."""
import sys
sys.path.insert(0, "/Users/jantrybus/Developer/dancelab-engine/scripts")
import numpy as np, librosa
import seam_decompose as S

MIX = "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.wav"
A = "/Users/jantrybus/Music/MAJ 🍃/SET_1/Skrillex, Ahadadream, Priya Ragu - TAKA (Caribou Remix).aiff"

t0, t1 = 1900, 1930
mix = S.load_mono(MIX, t0, t1)
ya = S.load_mono(A)
wa = S.warp(ya, 1860.025, 1.0320, t0, t1)

print(f"RMS  mix={np.sqrt((mix**2).mean()):.4f}   A(warp)={np.sqrt((wa**2).mean()):.4f}")

# 1. fine lag, on audio not envelopes
n = min(len(mix), len(wa))
c = np.correlate(mix[:n] - mix[:n].mean(), wa[:n] - wa[:n].mean(), mode="same")
lag = (np.argmax(np.abs(c)) - n // 2) / S.SR
print(f"best audio lag: {lag*1000:+.1f} ms   (peak corr {np.max(np.abs(c))/ (np.linalg.norm(mix[:n])*np.linalg.norm(wa[:n])):.3f})")

# 2. average spectrum, mix vs source
Fm = np.abs(librosa.stft(mix, n_fft=4096, hop_length=2048)).mean(axis=1)
Fa = np.abs(librosa.stft(wa,  n_fft=4096, hop_length=2048)).mean(axis=1)
freqs = librosa.fft_frequencies(sr=S.SR, n_fft=4096)
print("\n  Hz      mix dB   A dB    roznica")
for f in [40, 80, 150, 300, 700, 1500, 3000, 6000, 10000, 14000, 17000, 19000, 21000]:
    i = int(np.argmin(np.abs(freqs - f)))
    md, ad = 20*np.log10(Fm[i]+1e-9), 20*np.log10(Fa[i]+1e-9)
    print(f"{f:6d}   {md:7.1f} {ad:7.1f}   {md-ad:+7.1f}")

# 3. frame-by-frame correlation of log spectra: does the shape track at all?
Sm = np.abs(librosa.stft(mix, n_fft=4096, hop_length=2048))
Sa = np.abs(librosa.stft(wa,  n_fft=4096, hop_length=2048))
k = min(Sm.shape[1], Sa.shape[1])
for name, lo, hi in [("bas", 20, 200), ("srodek", 200, 2000), ("gora", 2000, 16000)]:
    b = np.where((freqs >= lo) & (freqs < hi))[0]
    em = np.log(Sm[b, :k].sum(axis=0) + 1e-9)
    ea = np.log(Sa[b, :k].sum(axis=0) + 1e-9)
    r = np.corrcoef(em, ea)[0, 1]
    print(f"\n{name:7s} korelacja obwiedni energii w czasie: {r:.3f}")

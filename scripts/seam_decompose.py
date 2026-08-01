"""Measure what a DJ did inside a seam, by subtracting the records from the mix.

The mix is the only recording of the DJ's hands, but the hands are invisible in
it: two tracks are playing and nothing says which sound came from which deck or
what was done to it on the way. The trick is that we hold the inputs. Knowing
exactly what was on both records turns an impossible separation problem into an
ordinary identification problem — how much of each known signal is present right
now — and that one has a stable answer.

Four choices below were forced by measurement, not taste (2026-07-30, seam
TAKA → Honey, all checked against a null window where only one deck plays):

  * Power, not amplitude. Two records never share phase, so their amplitudes do
    not add; fitting |mix| against a sum of |source| left 60-90 % unexplained
    with nothing missing. Powers of incoherent sources do add.
  * Sub-band energies, not raw bins. Requiring agreement bin by bin demands an
    alignment accuracy no method has; band energies track the source at r≈0.97
    while single bins do not track at all.
  * Blocks of time, not single frames. In one instant, inside one band, two
    dance records look alike — what separates them is rhythm. Fitting a block
    of ~1 s dropped false attribution from 1035 % to 6 % in the high band.
  * Two gains per band, not eight per stem. A DJ has one fader and one EQ knob
    per deck per band; letting each stem move independently only gave the fit
    room to explain the mix with a record that was not playing.

Finer frequency resolution was tried on the theory that bass notes would tell
the decks apart. It made attribution worse and is not used.

Everything here is void without the null test: the same fit run where only one
deck plays, with the other deck's real audio offered from the wrong place. What
the absent deck scores there is this method's noise floor, and any reading below
it inside the seam is not a measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.optimize import nnls

SR = 44100
N_FFT = 4096
HOP = 1024
BLOCK_SEC = 1.0                  # gain resolution; a fader move takes seconds
BLOCK_HOP_SEC = 0.25
N_SUB = 24                       # log-spaced sub-bands, 30 Hz … 18 kHz
STEMS = ("drums", "bass", "other", "vocals")
EQ_BANDS = {"bas": (30, 300), "środek": (300, 3000), "góra": (3000, 18000)}
# Never a temp directory: stem separation costs minutes per track and the cache
# has to outlive the session that built it. See experiments_priv/README.md.
CACHE = Path(__file__).resolve().parents[1] / "experiments_priv/_cache/stems"


# --------------------------------------------------------------------- audio
def load_mono(path, start=None, stop=None) -> np.ndarray:
    info = sf.info(str(path))
    kw = {}
    if start is not None:
        kw["start"] = max(0, int(start * info.samplerate))
    if stop is not None:
        kw["stop"] = min(info.frames, int(stop * info.samplerate))
    data, file_sr = sf.read(str(path), dtype="float32", always_2d=True, **kw)
    y = data.mean(axis=1)
    return librosa.resample(y, orig_sr=file_sr, target_sr=SR) if file_sr != SR else y


def separate(path: str) -> dict[str, np.ndarray]:
    """Four stems of a whole track, cached. Descriptive only — see module docs."""
    out = CACHE / hashlib.sha256(str(path).encode()).hexdigest()[:16]
    if (out / "vocals.npy").exists():
        return {s: np.load(out / f"{s}.npy") for s in STEMS}
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    print(f"  separating {Path(path).name} …", flush=True)
    model = get_model("htdemucs")
    model.eval()
    data, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
    stereo = data.T
    if file_sr != model.samplerate:
        stereo = librosa.resample(stereo, orig_sr=file_sr, target_sr=model.samplerate)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    with torch.no_grad():
        raw = apply_model(model, torch.tensor(stereo[None]), device=device, overlap=0.25)[0]
    out.mkdir(parents=True, exist_ok=True)
    stems = {}
    for name in STEMS:
        mono = raw[model.sources.index(name)].cpu().numpy().mean(axis=0)
        if model.samplerate != SR:
            mono = librosa.resample(mono, orig_sr=model.samplerate, target_sr=SR)
        stems[name] = mono.astype(np.float32)
        np.save(out / f"{name}.npy", stems[name])
    return stems


def warp(y: np.ndarray, origin: float, rate: float, t0: float, t1: float,
         hq: bool = False) -> np.ndarray:
    """The record on the mix's clock: mix time t holds track time (t-origin)*rate.

    Straight-line interpolation is the default and is right for measurement — it
    is fast and the features being measured live far below where it does harm.
    It is wrong for anything anyone listens to: at a 3 % pitch it costs 1.4 dB at
    10 kHz, 2.7 dB at 14 kHz and 4 dB at 18 kHz, which is exactly the dullness the
    DJ heard and exactly what the difference spectrogram showed against his own
    recording. Pass hq for audio and take the band-limited resampler.
    """
    n = int(round((t1 - t0) * SR))
    if not hq:
        idx = ((t0 + np.arange(n) / SR - origin) * rate) * SR
        inside = (idx >= 0) & (idx <= len(y) - 1)
        out = np.zeros(n, dtype=np.float32)
        out[inside] = np.interp(idx[inside], np.arange(len(y), dtype=np.float64), y)
        return out

    # Resample the stretch that is actually needed, then place it — resampling the
    # whole record would be slower and would accumulate rounding across minutes of
    # audio that gets thrown away.
    pad = int(SR * 0.5)
    a = int(np.floor((t0 - origin) * rate * SR)) - pad
    b = int(np.ceil((t1 - origin) * rate * SR)) + pad
    seg = np.zeros(b - a, dtype=np.float32)
    lo, hi = max(a, 0), min(b, len(y))
    if hi > lo:
        seg[lo - a: hi - a] = y[lo:hi]
    res = librosa.resample(seg, orig_sr=int(SR * 1000),
                           target_sr=int(SR * 1000 / rate), res_type="soxr_vhq")
    # the segment began at track time a/SR, i.e. mix time origin + (a/SR)/rate
    start_mix = origin + (a / SR) / rate
    k = int(round((t0 - start_mix) * SR))
    out = np.zeros(n, dtype=np.float32)
    lo, hi = max(k, 0), min(k + n, len(res))
    if hi > lo:
        out[lo - k: hi - k] = res[lo:hi]
    return out


_EDGES = np.geomspace(30, 18000, N_SUB + 1)
_CENTRES = (_EDGES[:-1] + _EDGES[1:]) / 2


def sub_energy(y: np.ndarray) -> np.ndarray:
    """Power per log sub-band per frame — the feature the fit actually sees."""
    P = (np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP)) ** 2).astype(np.float32)
    fr = librosa.fft_frequencies(sr=SR, n_fft=N_FFT)
    return np.stack([P[np.where((fr >= lo) & (fr < hi))[0]].sum(axis=0)
                     for lo, hi in zip(_EDGES[:-1], _EDGES[1:])])


# ----------------------------------------------------------------------- fit
def fit_gains(Em, Ea, Eb) -> dict:
    """Per-band amplitude gain of each deck over time, plus what stayed unexplained."""
    n = min(Em.shape[1], Ea.shape[1], Eb.shape[1])
    blk = max(2, int(round(BLOCK_SEC * SR / HOP)))
    step = max(1, int(round(BLOCK_HOP_SEC * SR / HOP)))
    out = {}
    for band, (lo, hi) in EQ_BANDS.items():
        rows = np.where((_CENTRES >= lo) & (_CENTRES < hi))[0]
        times, ga, gb, res = [], [], [], []
        for t in range(0, n - blk + 1, step):
            sl = range(t, t + blk)
            M = Em[np.ix_(rows, sl)].ravel()
            X = np.stack([Ea[np.ix_(rows, sl)].ravel(),
                          Eb[np.ix_(rows, sl)].ravel()]).T
            scale = np.linalg.norm(M)
            if scale < 1e-12:
                continue
            w, _ = nnls(X / scale, M / scale)
            # A record that has run out contributes almost no energy, and asking
            # how loud that nothing was pushed gains to five figures — which the
            # caller then read as the loudest the deck ever got, and so as the
            # moment it left. A source this quiet cannot be weighed at all, so
            # its gain is zero by declaration rather than by division.
            for k in range(X.shape[1]):
                if np.linalg.norm(X[:, k]) < 1e-3 * scale:
                    w[k] = 0.0
            times.append((t + blk / 2) * HOP / SR)
            # gains are fitted on power; report amplitude, which is the fader
            ga.append(float(np.sqrt(max(w[0], 0))))
            gb.append(float(np.sqrt(max(w[1], 0))))
            res.append(float(np.linalg.norm(M - X @ w) / scale))
        out[band] = {"t": times, "a": ga, "b": gb, "residual": res}
    return out


def noise_floor(mix_path, y_absent, present_curves, t0, t1, origin_range, rate,
                n_draws=12) -> dict:
    """What the fit claims for a deck that is provably not playing.

    Several offsets, not one: an offset that lands on the beat is the hardest
    case and a single draw either flatters the method or libels it.
    """
    Em = sub_energy(load_mono(mix_path, t0, t1))
    claims = {band: [] for band in EQ_BANDS}
    for origin in np.linspace(*origin_range, n_draws):
        Eb = sub_energy(warp(y_absent, float(origin), rate, t0, t1))
        got = fit_gains(Em, present_curves, Eb)
        for band in EQ_BANDS:
            a, b = np.mean(got[band]["a"]), np.mean(got[band]["b"])
            claims[band].append(b / max(a, 1e-9))
    return {band: {"median": float(np.median(v)), "p90": float(np.percentile(v, 90)),
                   "max": float(np.max(v))} for band, v in claims.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--a-origin", type=float, required=True)
    ap.add_argument("--a-rate", type=float, required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--b-origin", type=float, required=True)
    ap.add_argument("--b-rate", type=float, required=True)
    ap.add_argument("--seam", nargs=2, type=float, required=True, metavar=("T0", "T1"))
    ap.add_argument("--null-a", nargs=2, type=float, metavar=("T0", "T1"),
                    help="Window where only deck A plays")
    ap.add_argument("--null-b", nargs=2, type=float, metavar=("T0", "T1"))
    ap.add_argument("--out", default="experiments_priv/seam_decompose.json")
    args = ap.parse_args()

    ya, yb = load_mono(args.a), load_mono(args.b)
    t0, t1 = args.seam
    print(f"  fitting seam {t0:.0f}-{t1:.0f}s", flush=True)
    bands = fit_gains(sub_energy(load_mono(args.mix, t0, t1)),
                      sub_energy(warp(ya, args.a_origin, args.a_rate, t0, t1)),
                      sub_energy(warp(yb, args.b_origin, args.b_rate, t0, t1)))
    for band in bands:
        bands[band]["t"] = [t0 + x for x in bands[band]["t"]]

    floors = {}
    if args.null_a:
        n0, n1 = args.null_a
        print("  null A (only A plays, B offered from elsewhere)", flush=True)
        floors["b_when_absent"] = noise_floor(
            args.mix, yb, sub_energy(warp(ya, args.a_origin, args.a_rate, n0, n1)),
            n0, n1, (n0 - 200, n0 - 40), args.b_rate)
    if args.null_b:
        n0, n1 = args.null_b
        print("  null B (only B plays, A offered from elsewhere)", flush=True)
        floors["a_when_absent"] = noise_floor(
            args.mix, ya, sub_energy(warp(yb, args.b_origin, args.b_rate, n0, n1)),
            n0, n1, (n0 - 200, n0 - 40), args.a_rate)

    # Stems are not fitted — they say what each deck was carrying, so a band
    # that goes quiet can be read as "he cut it" or "there was nothing there".
    content = {}
    for label, path, origin, rate in [("A", args.a, args.a_origin, args.a_rate),
                                      ("B", args.b, args.b_origin, args.b_rate)]:
        stems = separate(path)
        content[label] = {
            s: [float(x) for x in
                np.sqrt(sub_energy(warp(stems[s], origin, rate, t0, t1)).sum(axis=0))]
            for s in STEMS}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "mix": args.mix, "seam": [t0, t1],
        "deck_a": {"path": args.a, "origin": args.a_origin, "rate": args.a_rate},
        "deck_b": {"path": args.b, "origin": args.b_origin, "rate": args.b_rate},
        "bands": bands, "noise_floor": floors, "stem_content": content,
        "hop_sec": HOP / SR,
    }))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

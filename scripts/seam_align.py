"""Locate a source track inside a recorded mix: playback rate and time offset.

Everything downstream — stem gains, residual, the name we give the gesture —
is a lie if this step is wrong, so it is its own script with its own evidence.

The search is done on onset-strength envelopes rather than on audio: a DJ's EQ
and fader change the spectrum enormously but barely touch *when* the hits land.
Rate and offset are searched together because a pitched-up track drifts, so a
single offset fitted at one anchor is already wrong a minute later.

Two other strategies were built and measured against this one, then deleted rather
than kept as dead code — what they taught is here so nobody rebuilds them. Voting
every anchor's whole correlation curve onto a shared origin axis survives a DJ
cutting back and forth between decks, but lands 1-4 s out, which is useless for
timing a hand. Constraining the search to the neighbourhood of the recording's own
cue marker picks a neighbouring bar. Only strict agreement between independently
searched anchors is precise enough, and where it fails the answer is that this
record cannot be located, not a looser guess.

Usage:
    seam_align.py MIX TRACK --from 1850 --to 1990
"""

from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SR = 22050          # envelopes only; halving the rate halves the load for free
HOP = 256           # ~86 fps — fine enough to see a single beat move
RATES = np.arange(0.90, 1.1001, 0.0015)   # ±10%: wider than any DJ pitch fader


def onset_env(y: np.ndarray, sr: int = SR) -> np.ndarray:
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    return (env - env.mean()) / (env.std() + 1e-9)


def load_mono(path: str | Path, start: float | None = None,
              stop: float | None = None) -> np.ndarray:
    info = sf.info(str(path))
    kwargs = {}
    if start is not None:
        kwargs["start"] = int(start * info.samplerate)
    if stop is not None:
        kwargs["stop"] = int(stop * info.samplerate)
    data, sr = sf.read(str(path), dtype="float32", always_2d=True, **kwargs)
    y = data.mean(axis=1)
    return librosa.resample(y, orig_sr=sr, target_sr=SR) if sr != SR else y


def _resample_env(env: np.ndarray, rate: float) -> np.ndarray:
    """Stretch an envelope as if the track had been played at `rate` speed."""
    n_out = int(round(len(env) / rate))
    src = np.linspace(0.0, len(env) - 1, n_out)
    return np.interp(src, np.arange(len(env)), env)


def align(mix_env: np.ndarray, track_env: np.ndarray) -> dict:
    """Best (rate, offset) of `track` inside `mix`, by normalised correlation.

    Returns the offset in track-seconds of the mix window's first sample.

    Confidence is peak-over-median, not peak-over-runner-up: dance music repeats
    every phrase, so the second-best position is a bar or two away and is nearly
    as good by construction. Measuring the peak against the whole distribution
    asks the question that actually matters — does this position stand out from
    everywhere else in the track.
    """
    best = None
    m = mix_env - mix_env.mean()
    for rate in RATES:
        t = _resample_env(track_env, rate)
        if len(t) < len(m):
            continue
        t = t - t.mean()
        # sliding dot product, normalised by the local energy of the track
        corr = np.correlate(t, m, mode="valid")
        window = np.convolve(t * t, np.ones(len(m)), mode="valid")
        corr = corr / (np.sqrt(np.maximum(window, 1e-9)) * np.linalg.norm(m) + 1e-9)
        k = int(np.argmax(corr))
        peak = float(corr[k])
        if best is None or peak > best["score"]:
            best = {
                "rate": float(rate),
                "score": peak,
                "prominence": peak / max(float(np.median(np.abs(corr))), 1e-6),
                # frames are in the *stretched* track, so convert back to the
                # original track's own clock before reporting
                "track_sec": k * HOP / SR * rate,
            }
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mix")
    ap.add_argument("track")
    ap.add_argument("--from", dest="t0", type=float, required=True)
    ap.add_argument("--to", dest="t1", type=float, required=True)
    ap.add_argument("--split", type=int, default=2,
                    help="Split the window into N anchors and check they agree")
    args = ap.parse_args()

    track_env = onset_env(load_mono(args.track))
    edges = np.linspace(args.t0, args.t1, args.split + 1)

    print(f"track: {Path(args.track).name}")
    results = []
    for i in range(args.split):
        a, b = float(edges[i]), float(edges[i + 1])
        r = align(onset_env(load_mono(args.mix, a, b)), track_env)
        # Where, in the mix's own clock, this anchor claims the track began.
        # Independent anchors must all name the same instant; that agreement is
        # the only evidence that the lock is real and not a lucky phrase match.
        r["origin"] = a - r["track_sec"] / r["rate"]
        results.append((a, r))
        print(f"  mix {a:7.1f}-{b:7.1f}s → track {r['track_sec']:7.2f}s "
              f"| rate {r['rate']:.4f} | corr {r['score']:.3f} "
              f"| prom {r['prominence']:5.2f} | origin {r['origin']:8.2f}s")

    origins = np.array([r["origin"] for _, r in results])
    med = float(np.median(origins))
    agree = [r for _, r in results if abs(r["origin"] - med) < 0.5]
    print(f"\n  origin (median of anchors): {med:.2f}s  "
          f"[{len(agree)}/{len(results)} anchors within 500 ms]")
    if len(agree) >= 2:
        spread = max(abs(r["origin"] - med) for r in agree) * 1000
        rate = float(np.median([r["rate"] for r in agree]))
        print(f"  spread among agreeing anchors: {spread:.0f} ms | rate {rate:.4f}")
        print(f"\n  USE: --origin {med:.3f} --rate {rate:.4f}")
    else:
        print("  NO LOCK — anchors disagree; do not trust anything downstream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

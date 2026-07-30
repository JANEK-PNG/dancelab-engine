"""Locate a source track inside a recorded mix: playback rate and time offset.

Everything downstream — stem gains, residual, the name we give the gesture —
is a lie if this step is wrong, so it is its own script with its own evidence.

The search is done on onset-strength envelopes rather than on audio: a DJ's EQ
and fader change the spectrum enormously but barely touch *when* the hits land.
Rate and offset are searched together because a pitched-up track drifts, so a
single offset fitted at one anchor is already wrong a minute later.

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


def _corr_curve(mix_env: np.ndarray, track_env: np.ndarray, rate: float) -> np.ndarray:
    t = _resample_env(track_env, rate)
    if len(t) < len(mix_env):
        return np.zeros(1)
    m = mix_env - mix_env.mean()
    t = t - t.mean()
    corr = np.correlate(t, m, mode="valid")
    energy = np.convolve(t * t, np.ones(len(m)), mode="valid")
    return corr / (np.sqrt(np.maximum(energy, 1e-9)) * np.linalg.norm(m) + 1e-9)


def accumulate_lock(mix_path, track_path, t0: float, t1: float,
                    n_anchors: int = 8) -> dict | None:
    """Lock a record onto the mix by letting many short anchors vote.

    Consensus between independently-searched anchors fails whenever the DJ cuts
    back and forth between two decks: half the anchors then land on the other
    record and each names a different, equally convincing phrase. Voting fixes
    this because every anchor casts its whole correlation curve onto one shared
    axis — the record's start time in the mix. A true start collects support from
    every anchor that saw the record; a lucky phrase match collects one vote and
    is buried.
    """
    track_env = onset_env(load_mono(track_path))
    edges = np.linspace(t0, t1, n_anchors + 1)
    anchors = [(float(edges[i]), onset_env(load_mono(mix_path, float(edges[i]),
                                                     float(edges[i + 1]))))
               for i in range(n_anchors) if edges[i + 1] - edges[i] >= 8]
    if len(anchors) < 3:
        return None

    fps = SR / HOP
    grid = np.arange(t0 - len(track_env) / fps, t1, 1.0 / fps)
    best = None
    for rate in RATES:
        total = np.zeros(len(grid))
        votes = np.zeros(len(grid))
        for a, env in anchors:
            curve = _corr_curve(env, track_env, rate)
            if len(curve) < 2:
                continue
            # frame k of the stretched track ↔ mix time a, so the record began at
            # a - (k/fps)*rate — that is this anchor's vote, one value per lag
            origins = a - (np.arange(len(curve)) / fps) * rate
            order = np.argsort(origins)
            on_grid = np.interp(grid, origins[order], curve[order],
                                left=0.0, right=0.0)
            total += np.maximum(on_grid, 0)
            votes += (on_grid > 0.5 * on_grid.max()).astype(float)
        k = int(np.argmax(total))
        if best is None or total[k] > best["score"]:
            best = {"origin": float(grid[k]), "rate": float(rate),
                    "score": float(total[k]), "votes": int(votes[k]),
                    "n_anchors": len(anchors),
                    "margin": float(total[k] / max(np.median(total), 1e-9))}
    return best


def lock_near_marker(mix_path, track_path, marker: float, listen: tuple[float, float],
                     radius: float = 45.0, n_anchors: int = 8,
                     tolerance: float = 0.4, min_anchors: int = 3) -> dict | None:
    """Lock a record using the recording's own marker as the prior.

    Searching a whole record for a match fails on this material: the DJ cuts back
    and forth between two decks, so half the anchors see the other record, and a
    four-minute loop-based track offers a dozen phrases that each fit as well as
    the truth. The .cue already carries a strong hint — rekordbox logged roughly
    when the record came up — and constraining the origin to its neighbourhood
    turns an under-determined search into a well-posed one.

    Measured on this set the marker sat 0.5 s from the true origin twice and 18 s
    away once, so the window is wide; it only has to exclude the *other* phrases.
    Anchors that disagree are dropped, never averaged: a lock is a claim that
    several independent stretches of mix name the same instant.
    """
    track_env = onset_env(load_mono(track_path))
    edges = np.linspace(listen[0], listen[1], n_anchors + 1)
    windows = [(float(edges[i]), float(edges[i + 1])) for i in range(n_anchors)
               if edges[i + 1] - edges[i] >= 8]
    if len(windows) < min_anchors:
        return None
    envs = [(a, onset_env(load_mono(mix_path, a, b))) for a, b in windows]
    fps = SR / HOP

    best = None
    for rate in RATES:
        found = []
        for a, env in envs:
            curve = _corr_curve(env, track_env, rate)
            if len(curve) < 2:
                continue
            origins = a - (np.arange(len(curve)) / fps) * rate
            near = np.where(np.abs(origins - marker) <= radius)[0]
            if not len(near):
                continue
            k = near[int(np.argmax(curve[near]))]
            found.append((float(origins[k]), float(curve[k])))
        if len(found) < min_anchors:
            continue
        med = float(np.median([o for o, _ in found]))
        agree = [(o, c) for o, c in found if abs(o - med) < tolerance]
        if len(agree) < min_anchors:
            continue
        score = sum(c for _, c in agree)
        if best is None or score > best["_score"]:
            best = {"origin": float(np.median([o for o, _ in agree])),
                    "rate": float(rate), "anchors": f"{len(agree)}/{len(found)}",
                    "spread_ms": float(max(abs(o - med) for o, _ in agree) * 1000),
                    "marker_offset_sec": float(np.median([o for o, _ in agree]) - marker),
                    "_score": score}
    if best:
        best.pop("_score")
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

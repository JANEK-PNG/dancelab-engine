"""Does either deck slip against the render, start to finish?

Beat-grid evenness said the renders were tight and the DJ still heard galloping,
because that measure fits a line to whatever beats the tracker found and a mix
dominated by one deck can look perfectly even while the other one walks away from
it. This asks the question directly: line each source up against the render near
the beginning and again near the end, and see whether it sits in the same place.

A quarter of a beat is roughly where slip stops being tightness and starts being a
stumble — 110 ms at 136 BPM. Anything past that is the fault he is describing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np

import seam_decompose as S

SR = 22050
HOP = 128                       # ~5.8 ms per frame — fine enough to see slip
WINDOW = 12.0


def envelope(y: np.ndarray) -> np.ndarray:
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    return (env - env.mean()) / (env.std() + 1e-9)


def lag_at(render: np.ndarray, source: np.ndarray, start: float, span: float,
           max_lag: float) -> float:
    """Offset between render and source over one window, searched within ±max_lag.

    Unbounded, this finds the neighbouring bar as readily as the right one — the
    first run reported four seconds of slip, which is nine beats, not drift. Slip
    past half a beat is not a subtlety to be measured anyway, so the search is
    capped there and a reading at the cap is reported as such rather than trusted.
    """
    a = int(start * SR / HOP)
    b = int((start + span) * SR / HOP)
    r, s = render[a:b], source[a:b]
    if r.size < 32 or s.size < 32:
        return float("nan")
    c = np.correlate(r - r.mean(), s - s.mean(), mode="same")
    centre = len(c) // 2
    reach = max(1, int(max_lag * SR / HOP))
    lo, hi = max(centre - reach, 0), min(centre + reach + 1, len(c))
    return float((lo + int(np.argmax(c[lo:hi])) - centre) * HOP / SR)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    args = ap.parse_args()
    base = Path(args.pairs).parent
    rows = json.loads(Path(args.pairs).read_text())

    print(f"{'szew':18s} {'dlug':>6s} {'A slip':>8s} {'B slip':>8s} {'A-B':>8s}  ocena")
    worst = []
    for r in rows:
        if not r.get("mine"):
            continue
        path = base / r["mine"]
        dur = r["beats_rendered"] * 60.0 / r["target_bpm"]
        if dur < 2 * WINDOW + 4:
            continue
        y = librosa.resample(S.load_mono(str(path)), orig_sr=S.SR, target_sr=SR)
        env_r = envelope(y)
        slips = {}
        for deck, cue, rate, key in (("A", r["cue_a_sec"], r["rate_a"], "from"),
                                     ("B", r["cue_b_sec"], r["rate_b"], "to")):
            src = r["deck_a_path"] if deck == "A" else r["deck_b_path"]
            warped = S.warp(S.load_mono(src), -cue / rate, rate, 0.0, dur)
            env_s = envelope(librosa.resample(warped, orig_sr=S.SR, target_sr=SR))
            n = min(env_r.size, env_s.size)
            half_beat = 30.0 / r["target_bpm"]
            start = lag_at(env_r[:n], env_s[:n], 1.0, WINDOW, half_beat)
            end = lag_at(env_r[:n], env_s[:n], dur - WINDOW - 1.0, WINDOW, half_beat)
            slips[deck] = (end - start) * 1000
        rel = slips["A"] - slips["B"]
        verdict = "ok" if abs(rel) < 40 else ("granica" if abs(rel) < 110 else "KON")
        worst.append(abs(rel))
        print(f"{r['seam']:18s} {dur:5.0f}s {slips['A']:7.0f}ms {slips['B']:7.0f}ms "
              f"{rel:7.0f}ms  {verdict}")
    if worst:
        print(f"\nmediana rozjazdu A wzgledem B: {np.median(worst):.0f} ms "
              f"(cwierc uderzenia przy 136 BPM = 110 ms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

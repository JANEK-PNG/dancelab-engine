"""Corpus transition analysis — phase 0 (quality) + phase 1/2 pilots.

Reads aligned mixes from `alignments/*.json`, joins genre tags from the
dataset, and tests the pre-registered predictions in docs/corpus_predictions.md:

  P1  octave-cross transitions are near-zero (adjacent matched tracks ~2x apart)
  P2  D&B BPM clusters high (~170-185), not folded to 85-95
  P3  transition length ordered by genre (D&B < house/techno < trance)
  Q0  coverage funnel + match_rate distribution (quality gate)

Honest scope: per-track playback-stretch (DLASOT-13 tempo-change, P4) needs the
DTW path persisted — not in current alignment JSON — so it is reported as
DEFERRED, not faked. Bootstrap CIs on headline rates.

Usage: PYTHONPATH=src python3 scripts/corpus_stats.py --root /Volumes/MY_PC/DanceLabCorpus
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path

BASS = ("drum & bass", "jungle", "dubstep", "uk garage", "breakbeat")
HOUSE = ("house", "tech house", "deep house")
TECHNO = ("techno", "minimal")
TRANCE = ("trance",)


def genre_of(tags: list[str]) -> str:
    low = " ".join(tags).lower()
    if any(g in low for g in BASS):
        return "bass"
    if any(g in low for g in TRANCE):
        return "trance"
    if any(g in low for g in TECHNO):
        return "techno"
    if any(g in low for g in HOUSE):
        return "house"
    return "other"


def fold_octave(bpm: float, lo: float = 90.0, hi: float = 180.0) -> float:
    """Fold to [lo, hi) — the true musical tempo, mirroring the engine."""
    if bpm <= 0:
        return bpm
    guard = 0
    while bpm < lo and guard < 8:
        bpm *= 2.0
        guard += 1
    while bpm >= hi and guard < 16:
        bpm /= 2.0
        guard += 1
    return bpm


def median_iqr(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return (float("nan"),) * 3
    s = sorted(values)
    n = len(s)

    def q(p: float) -> float:
        idx = p * (n - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        return s[lo] + (s[hi] - s[lo]) * (idx - lo)

    return q(0.25), q(0.5), q(0.75)


def bootstrap_ci(flags: list[bool], n_boot: int = 2000) -> tuple[float, float, float]:
    """Rate + 95% percentile CI via non-parametric bootstrap."""
    if not flags:
        return (float("nan"),) * 3
    rng = random.Random(20260715)
    n = len(flags)
    point = sum(flags) / n
    boots = []
    for _ in range(n_boot):
        s = sum(flags[rng.randrange(n)] for _ in range(n))
        boots.append(s / n)
    boots.sort()
    return point, boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--match-threshold", type=float, default=0.4)
    args = ap.parse_args()
    root = Path(args.root)

    dataset = {m["id"]: m for m in json.loads((root / "djmix-dataset.json").read_text())}
    # exclude macOS AppleDouble shadow files (._foo.json) that exFAT spawns
    reports = sorted(p for p in (root / "alignments").glob("*.json") if not p.name.startswith("._"))
    if not reports:
        print("no aligned mixes yet.")
        return 0

    genre_counts: Counter[str] = Counter()
    all_match_rates: list[float] = []
    valid_flags: list[bool] = []
    trans_lengths_by_genre: dict[str, list[float]] = {}
    bpm_by_genre: dict[str, list[float]] = {}
    octave_cross_flags: list[bool] = []
    adjacent_pairs = 0

    skipped = 0
    for rp in reports:
        try:
            rep = json.loads(rp.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"  WARN skip corrupt {rp.name}: {type(exc).__name__}")
            skipped += 1
            continue
        mix_id = rep["mix_id"]
        genre = genre_of([t["key"] for t in dataset.get(mix_id, {}).get("tags", [])])
        genre_counts[genre] += 1

        matched = [r for r in rep["results"] if r["alignment"]["matched"]]
        for r in rep["results"]:
            all_match_rates.append(r["alignment"]["match_rate"])
        # BPM histogram input (matched only, folded to true tempo) — P2 + octave bug
        for r in matched:
            bpm = r["track_beatgrid"].get("bpm")
            if bpm:
                bpm_by_genre.setdefault(genre, []).append(fold_octave(float(bpm)))

        # P1: octave-cross between adjacent matched tracks (in mix play order)
        seq = [r for r in matched]
        for a, b in zip(seq, seq[1:]):
            ba, bb = a["track_beatgrid"].get("bpm"), b["track_beatgrid"].get("bpm")
            if ba and bb:
                adjacent_pairs += 1
                # true tempos both fold to same band; octave-cross = raw ratio ~2
                ratio = max(ba, bb) / min(ba, bb)
                octave_cross_flags.append(1.8 <= ratio <= 2.2)

        # P3 + Q0: transition lengths (valid only)
        for t in rep["transitions"]:
            valid_flags.append(bool(t["valid"]))
            if t["valid"] and t.get("transition_length_beats"):
                trans_lengths_by_genre.setdefault(genre, []).append(float(t["transition_length_beats"]))

    print(f"=== PILOT on {len(reports) - skipped} aligned mixes ({skipped} corrupt skipped) ===\n")
    print("genres:", dict(genre_counts))

    print("\n--- Q0 quality gate ---")
    q1, q2, q3 = median_iqr(all_match_rates)
    print(f"match_rate: median {q2:.2f} (IQR {q1:.2f}-{q3:.2f}), n={len(all_match_rates)} tracks")
    vr, vlo, vhi = bootstrap_ci(valid_flags)
    print(f"valid transitions: {vr:.1%} (95% CI {vlo:.1%}-{vhi:.1%}), n={len(valid_flags)}")

    print("\n--- P1 octave-cross rate (Janek: <2%) ---")
    if octave_cross_flags:
        r, lo, hi = bootstrap_ci(octave_cross_flags)
        print(f"adjacent tracks ~2x apart: {r:.1%} (95% CI {lo:.1%}-{hi:.1%}), n={adjacent_pairs} pairs")
    else:
        print("no adjacent matched pairs yet")

    print("\n--- P2 BPM clusters by genre (Janek: D&B ~170-185, no 85-92 twin peak) ---")
    for g, bpms in sorted(bpm_by_genre.items()):
        if not bpms:
            continue
        q1, q2, q3 = median_iqr(bpms)
        low_peak = sum(1 for b in bpms if 82 <= b <= 96) / len(bpms)
        print(f"  {g:8} median {q2:5.1f} (IQR {q1:.0f}-{q3:.0f}) n={len(bpms):4}  |  {low_peak:.0%} fell in 82-96 band")

    print("\n--- P3 transition length by genre (Claude: D&B < house/techno < trance) ---")
    for g, lens in sorted(trans_lengths_by_genre.items()):
        if not lens:
            continue
        q1, q2, q3 = median_iqr(lens)
        print(f"  {g:8} median {q2:5.1f} beats (IQR {q1:.0f}-{q3:.0f}) n={len(lens)}")

    print("\n--- P4 per-track tempo stretch: DEFERRED (needs DTW path persisted; not faked) ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

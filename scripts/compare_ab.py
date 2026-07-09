"""A/B: mixing-simulation quality, normal (HPSS full-mix) vs deep (demucs) analysis.

For a set of tracks analyzed both ways, run the mixability engine on every pair
in each mode and report where the two disagree — especially vocal-clash risk,
which is the component the deep (source-separated) vocal proxy is meant to fix.

Usage: .venv/bin/python scripts/compare_ab.py <normal_dir> <deep_dir> [tracklist.txt]
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

from dancelab.core.config import load_config, load_weights
from dancelab.core.models import MixabilityInput, TransitionWindowInput
from dancelab.decision.mixability import compute_mixability, vocal_conflict
from dancelab.decision.transition_windows import detect_transition_windows
from dancelab.ingestion.metadata import make_track_id
from dancelab.storage.repositories import FileAnalysisRepository


def load_pair_mode(repo, weights, cfg, tid_a, tid_b):
    a, b = repo.get(tid_a), repo.get(tid_b)
    tw = {}
    for tid, an in ((tid_a, a), (tid_b, b)):
        tw[tid] = detect_transition_windows(
            TransitionWindowInput(track_id=tid, segments=an.segments,
                                  feature_frames=an.features, beatgrid=an.beatgrid),
            weights.transition_window, top_k=cfg.analysis.transition_top_n).windows
    out = compute_mixability(
        MixabilityInput(track_a=a, track_b=b,
                        transition_windows_a=tw[tid_a], transition_windows_b=tw[tid_b]),
        weights.mixability, weights.mixability_conflict)
    return {
        "score": out.mixability_score,
        "vocal_clash": vocal_conflict(a, b),
        "risks": out.risks,
        "confidence": out.confidence,
        "n_windows": len(out.best_pair_windows),
        "titles": (a.track.title, b.track.title),
    }


def main() -> int:
    normal_dir, deep_dir = sys.argv[1], sys.argv[2]
    tracklist = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/ab_tracks.txt")
    cfg = load_config()
    weights = load_weights(cfg.weights_file)
    rn = FileAnalysisRepository(normal_dir)
    rd = FileAnalysisRepository(deep_dir)

    paths = [ln.strip() for ln in tracklist.read_text().splitlines() if ln.strip()]
    tids = [make_track_id(p) for p in paths]
    # keep only tracks present in BOTH arms
    both = [t for t in tids if (Path(normal_dir) / f"{t}.json").exists()
            and (Path(deep_dir) / f"{t}.json").exists()]
    print(f"tracks in both arms: {len(both)}/{len(tids)}")
    if len(both) < 2:
        print("need >=2 tracks in both arms — run the normal batch and wait for the deep pilot")
        return 1

    rows = []
    for ta, tb in itertools.combinations(both, 2):
        n = load_pair_mode(rn, weights, cfg, ta, tb)
        d = load_pair_mode(rd, weights, cfg, ta, tb)
        rows.append((n, d))

    # report: pairs sorted by vocal-clash divergence (deep - normal)
    def clash(x):
        return x["vocal_clash"] if x["vocal_clash"] is not None else 0.0

    print(f"\n{'pair':52} {'clash N→D':>12} {'mix N→D':>14} {'Δmix':>7}")
    for n, d in sorted(rows, key=lambda r: -abs(clash(r[1]) - clash(r[0]))):
        ta = (n["titles"][0] or "?")[:24]
        tb = (n["titles"][1] or "?")[:24]
        cn, cd = clash(n), clash(d)
        dm = d["score"] - n["score"]
        print(f"{ta[:24]:24}×{tb[:24]:24} {cn:.2f}→{cd:.2f}   {n['score']:.3f}→{d['score']:.3f}  {dm:+.3f}")

    # divergence summary
    flips = sum(1 for n, d in rows
                if bool(any('vocal' in r for r in d['risks'])) != bool(any('vocal' in r for r in n['risks'])))
    print(f"\npairs where vocal-clash FLAG differs between modes: {flips}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

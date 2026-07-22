"""Re-measure Janek's 35 blind ratings against the CURRENT engine.

Step 1 of the weight-calibration path: the octave-fold fix (evidence-gated,
tag never disables folding) landed after his first blind test, so his cached
analyses carry stale BPMs. This script:

  1. re-analyzes the 36 rated tracks with the current engine into a SEPARATE
     repository (data/processed/rescore_v2) — the original cache stays intact
     as evidence;
  2. recomputes transition_score for the same 35 pairs with the same default
     weights/arc as the original smart_playlist run;
  3. writes a comparison CSV + summary JSON (old rho vs new rho).

The summary intentionally goes to a file, not stdout — per the mentor
protocol the number is revealed only after Janek registers his prediction.

Usage: PYTHONPATH=src .venv/bin/python scripts/rescore_janek_ratings.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from dancelab.core.config import load_config, load_weights
from dancelab.core.pipeline import analyze_track
from dancelab.decision.set_builder import track_energy, transition_score
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.validation.dj_decision_metrics import kendall_tau, rating_correlation

RATINGS = Path.home() / "Library/Application Support/DanceLab/cache/validation/Janek_transition_ratings.csv"
OLD_REPO = Path("data/processed/smart_playlist")
NEW_REPO = Path("data/processed/rescore_v2")
OUT_DIR = Path("data/reports/rescore_v2")


def main() -> int:
    config = load_config("configs/default.yaml")
    weights = load_weights()  # default descriptor_weights.yaml — same as the original run
    rows = list(csv.DictReader(open(RATINGS, encoding="utf-8")))
    # drop the duplicated first pair (rated twice in the session)
    seen: set[str] = set()
    pairs = []
    for row in rows:
        if row["pair_id"] in seen:
            continue
        seen.add(row["pair_id"])
        pairs.append(row)

    track_ids = sorted({r["track_id_a"] for r in pairs} | {r["track_id_b"] for r in pairs})
    print(f"pairs: {len(pairs)} | unique tracks: {len(track_ids)}")

    NEW_REPO.mkdir(parents=True, exist_ok=True)
    new_repo = FileAnalysisRepository(str(NEW_REPO))
    analyses = {}
    bpm_changes = []
    for index, tid in enumerate(track_ids, 1):
        old = json.loads((OLD_REPO / f"{tid}.json").read_text())
        source = Path(old["track"]["source_path"])
        cached = NEW_REPO / f"{tid}.json"
        if cached.exists():
            result = new_repo.get(tid)
        else:
            result = analyze_track(source, config)
            new_repo.save(result)
        analyses[tid] = result
        old_bpm = old["track"].get("bpm_estimate")
        new_bpm = result.track.bpm_estimate
        if old_bpm and new_bpm and abs(old_bpm - new_bpm) > 1.0:
            bpm_changes.append((tid, old["track"].get("title") or source.name, old_bpm, new_bpm))
        print(f"[{index}/{len(track_ids)}] {tid} bpm {old_bpm} -> {new_bpm}", flush=True)

    energies = {tid: track_energy(a) for tid, a in analyses.items()}
    e_values = list(energies.values())
    e_range = (max(e_values) - min(e_values)) if e_values else 0.0

    old_scores, new_scores, ratings = [], [], []
    detail_rows = []
    for row in pairs:
        a, b = analyses[row["track_id_a"]], analyses[row["track_id_b"]]
        result = transition_score(
            a, b, weights, "build",
            energies[row["track_id_a"]], energies[row["track_id_b"]], e_range,
        )
        new_score = float(result[0] if isinstance(result, tuple) else result)
        old_scores.append(float(row["engine_score"]))
        new_scores.append(new_score)
        ratings.append(float(row["dj_mixability_rating"]))
        detail_rows.append({
            "pair_id": row["pair_id"],
            "old_engine_score": row["engine_score"],
            "new_engine_score": round(new_score, 4),
            "dj_rating": row["dj_mixability_rating"],
        })

    summary = {
        "n_pairs": len(pairs),
        "rho_old": rating_correlation(old_scores, ratings),
        "rho_new": rating_correlation(new_scores, ratings),
        "tau_old": kendall_tau(old_scores, ratings),
        "tau_new": kendall_tau(new_scores, ratings),
        "bpm_changes": [
            {"track_id": t, "title": n, "old_bpm": o, "new_bpm": w}
            for t, n, o, w in bpm_changes
        ],
        "note": "arc/weights = default config; old scores came from the original session run",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    with open(OUT_DIR / "pairs.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)
    print(f"done. summary sealed at {OUT_DIR}/summary.json (reveal after the prediction)")
    print(f"tracks with BPM changed >1: {len(bpm_changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

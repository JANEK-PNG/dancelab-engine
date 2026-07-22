"""H (handcrafted) analysis pass for the ordering model gate.

Runs the engine's standard analyze_track (no stems) over every track in the
frozen ordering dataset, writing one AnalysisResult JSON per track plus the
analysis index the gate reads. Feeds Kord's `revealed repertoire` gate H
coverage. Resumable: existing analysis JSONs are skipped.

Contract (from validation/djmix): index = {schema_version, tracks:{catalog_id:
relative_path}}; each file is an AnalysisResult that handcrafted_features_from_
analysis accepts. analysis files named {engine_track_id}.json.

Usage: PYTHONPATH=src python3 scripts/corpus_h_analysis.py [--limit N] [--workers 5]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CORPUS_ROOT = Path("/Volumes/MY_PC/DanceLabCorpus")
DATASET = ROOT / "data/reports/corpus_ordering/dataset.json"
ANALYSIS_ROOT = ROOT / "data/reports/corpus_ordering/h_analysis"
INDEX_PATH = ROOT / "data/reports/corpus_ordering/analysis_index.json"
INDEX_SCHEMA = "ordering-analysis-index-v1"


def required_ids() -> tuple[str, ...]:
    data = json.loads(DATASET.read_text())
    ids: set[str] = set()
    for obs in data["observations"]:
        ids.update(obs.get("candidate_track_ids", []))
        ids.update(obs.get("history_track_ids", []))
    return tuple(sorted(ids))


def analyze_one(track_id: str, source_rel: str, engine_track_id: str) -> tuple[str, str, str, str]:
    out = ANALYSIS_ROOT / f"{engine_track_id}.json"
    if out.is_file():
        return (track_id, engine_track_id, "cached", "")
    from dancelab.core.config import load_config
    from dancelab.core.pipeline import analyze_track
    try:
        cfg = load_config(str(ROOT / "configs/default.yaml"))
        result = analyze_track(CORPUS_ROOT / source_rel, cfg)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(result.model_dump_json(), encoding="utf-8")
        tmp.replace(out)
        return (track_id, engine_track_id, "ok", "")
    except Exception as exc:  # keep the batch alive; one bad track must not kill it
        return (track_id, engine_track_id, "failed", f"{type(exc).__name__}: {exc}"[:200])


def build_index() -> int:
    """(Re)build the analysis index from whatever analysis JSONs exist."""
    from dancelab.validation.djmix.model_gate import inspect_audio_inventory

    inv = inspect_audio_inventory(CORPUS_ROOT, required_ids())
    tracks = {}
    for track_id, source in inv.resolved_sources.items():
        rel = f"{source.engine_track_id}.json"
        if (ANALYSIS_ROOT / rel).is_file():
            tracks[track_id] = rel
    INDEX_PATH.write_text(
        json.dumps({"schema_version": INDEX_SCHEMA, "tracks": tracks}, sort_keys=True),
        encoding="utf-8",
    )
    return len(tracks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--index-only", action="store_true", help="just rebuild the index")
    args = ap.parse_args()

    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    if args.index_only:
        print(f"index: {build_index()} tracks", flush=True)
        return 0

    from dancelab.validation.djmix.model_gate import inspect_audio_inventory

    inv = inspect_audio_inventory(CORPUS_ROOT, required_ids())
    jobs = [
        (tid, src.source_relative_path, src.engine_track_id)
        for tid, src in inv.resolved_sources.items()
    ]
    if args.limit:
        jobs = jobs[: args.limit]
    print(f"required: {len(inv.resolved_sources)} | to analyze: {len(jobs)} | workers {args.workers}", flush=True)

    done = ok = cached = failed = 0
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(analyze_one, *j) for j in jobs]
        for fut in as_completed(futs):
            tid, eid, status, err = fut.result()
            done += 1
            ok += status == "ok"
            cached += status == "cached"
            failed += status == "failed"
            if status == "failed":
                print(f"  FAIL {tid}: {err}", flush=True)
            if done % 50 == 0 or done == len(jobs):
                rate = done / max(time.time() - t0, 1e-9)
                print(f"[{done}/{len(jobs)}] ok={ok} cached={cached} failed={failed} "
                      f"({rate:.1f}/s)", flush=True)

    total = build_index()
    print(f"index rebuilt: {total} tracks covered.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

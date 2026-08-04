"""Resumable DanceLab analysis for every corpus track with a frozen CLAP vector.

This is deliberately separate from ``corpus_h_analysis.py``.  That script is
part of the immutable 2,881-track ordering gate; this pass expands coverage to
the full 12,668-track CLAP catalogue without changing the frozen dataset.

The full pass has its own versioned output directory.  The frozen 2,881-track
gate was computed before the 2026-07-31 tempo-refinement change and must not be
mixed with current-pipeline results.  Each new result is written through a
temporary file and renamed atomically, so interrupting the process is safe.  A
full catalogue-id -> analysis-file index is rebuilt at the end.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/corpus_h_analysis_full.py --workers 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TRACKS_ROOT = Path("/Volumes/MY_PC/DanceLabCorpus/tracks")
EMBEDDINGS = ROOT / "data/reports/corpus_embeddings_full.json"
ANALYSIS_ROOT = ROOT / "data/reports/corpus_ordering/h_analysis_full_20260801"
INDEX_PATH = ROOT / "data/reports/corpus_ordering/analysis_index_full.json"
FAILURES_PATH = ROOT / "data/reports/corpus_ordering/h_analysis_full_20260801_failures.json"
INDEX_SCHEMA = "full-corpus-analysis-index-v1"

_CONFIG = None


def _init_worker() -> None:
    global _CONFIG
    from dancelab.core.config import load_config

    _CONFIG = load_config(str(ROOT / "configs/default.yaml"))


def _analyze_one(catalog_id: str, source_path: str, engine_track_id: str) -> tuple[str, str, str]:
    from dancelab.core.pipeline import analyze_track

    out = ANALYSIS_ROOT / f"{engine_track_id}.json"
    try:
        result = analyze_track(source_path, _CONFIG)
        tmp = out.with_suffix(f".json.tmp.{os.getpid()}")
        tmp.write_text(result.model_dump_json(), encoding="utf-8")
        tmp.replace(out)
        return catalog_id, engine_track_id, ""
    except Exception as exc:  # one damaged source must not stop a 12k-track pass
        return catalog_id, engine_track_id, f"{type(exc).__name__}: {exc}"[:400]


def _catalogue() -> list[tuple[str, Path, str]]:
    from dancelab.ingestion.loader import SUPPORTED_EXTENSIONS
    from dancelab.ingestion.metadata import make_track_id

    embedded = set(json.loads(EMBEDDINGS.read_text(encoding="utf-8"))["tracks"])
    by_stem: dict[str, list[Path]] = {}
    for path in sorted(TRACKS_ROOT.iterdir(), key=lambda item: item.name):
        if path.name.startswith("._") or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if path.is_file() and not path.is_symlink():
            by_stem.setdefault(path.stem, []).append(path.resolve())

    missing = sorted(embedded - by_stem.keys())
    ambiguous = sorted(track_id for track_id in embedded if len(by_stem.get(track_id, ())) > 1)
    if missing or ambiguous:
        raise RuntimeError(
            f"unsafe corpus inventory: missing={len(missing)}, ambiguous={len(ambiguous)}"
        )

    return [
        (track_id, by_stem[track_id][0], make_track_id(str(by_stem[track_id][0])))
        for track_id in sorted(embedded)
    ]


def _write_index(catalogue: list[tuple[str, Path, str]]) -> int:
    tracks = {
        catalog_id: f"{engine_track_id}.json"
        for catalog_id, _source, engine_track_id in catalogue
        if (ANALYSIS_ROOT / f"{engine_track_id}.json").is_file()
    }
    payload = {
        "schema_version": INDEX_SCHEMA,
        "analysis_root": str(ANALYSIS_ROOT),
        "embeddings_source": str(EMBEDDINGS),
        "tracks": tracks,
    }
    tmp = INDEX_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp.replace(INDEX_PATH)
    return len(tracks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="analyze only N missing tracks")
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")

    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    catalogue = _catalogue()
    complete_before = sum(
        (ANALYSIS_ROOT / f"{engine_track_id}.json").is_file()
        for _catalog_id, _source, engine_track_id in catalogue
    )
    missing_jobs = [
        (catalog_id, str(source), engine_track_id)
        for catalog_id, source, engine_track_id in catalogue
        if not (ANALYSIS_ROOT / f"{engine_track_id}.json").is_file()
    ]
    if args.limit:
        missing_jobs = missing_jobs[: args.limit]

    print(
        f"pełny katalog CLAP: {len(catalogue)} | gotowe: {complete_before} | "
        f"do policzenia: {len(missing_jobs)} | workers: {args.workers}",
        flush=True,
    )
    if args.index_only or not missing_jobs:
        print(f"pełny indeks: {_write_index(catalogue)} utworów", flush=True)
        return 0

    started = time.time()
    ok = failed = 0
    failures: dict[str, str] = {}

    def record(result: tuple[str, str, str]) -> None:
        nonlocal ok, failed
        catalog_id, _engine_track_id, error = result
        if error:
            failed += 1
            failures[catalog_id] = error
            print(f"FAIL {catalog_id}: {error}", flush=True)
        else:
            ok += 1

        done = ok + failed
        if done % args.progress_every == 0 or done == len(missing_jobs):
            elapsed = max(time.time() - started, 1e-9)
            rate = done / elapsed
            eta_hours = (len(missing_jobs) - done) / max(rate, 1e-9) / 3600
            total_complete = complete_before + ok
            print(
                f"[{done}/{len(missing_jobs)}] razem={total_complete}/{len(catalogue)} "
                f"ok={ok} failed={failed} | {rate:.3f}/s | ETA {eta_hours:.1f} h",
                flush=True,
            )

    if args.workers == 1:
        _init_worker()
        for job in missing_jobs:
            record(_analyze_one(*job))
    else:
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as pool:
            futures = [pool.submit(_analyze_one, *job) for job in missing_jobs]
            for future in as_completed(futures):
                record(future.result())

    FAILURES_PATH.write_text(
        json.dumps({"schema_version": "full-corpus-analysis-failures-v1", "failures": failures},
                   ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    indexed = _write_index(catalogue)
    print(
        f"GOTOWE: indeks={indexed}/{len(catalogue)} | nowe_ok={ok} | failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

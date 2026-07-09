"""One-off enrichment: add demucs vocal_density_proxy to existing analyses.

Surgical bolt-on — loads each data/processed/<id>.json, runs vocal separation on
its source audio, patches vocal_density_proxy into the existing feature frames,
and re-saves. Beatgrid, onsets and segments are preserved untouched.

Idempotent: `--skip-existing` (default) skips tracks whose frames already carry
vocal_density_proxy, so an interrupted run resumes cleanly.

Usage: .venv/bin/python scripts/enrich_vocals.py [--limit N] [--recompute]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from dancelab.core.config import load_config
from dancelab.features.vocals import vocal_activity
from dancelab.ingestion.loader import load_audio
from dancelab.storage.repositories import FileAnalysisRepository


def enrich_one(analysis, config) -> int:
    """Fill vocal_density_proxy on an analysis in place. Returns frames updated."""
    signal = load_audio(analysis.track.source_path, config)
    vp = vocal_activity(
        signal.samples, signal.sample_rate,
        frame_size=config.audio.frame_size, hop_size=config.audio.hop_size,
        method="demucs",
    )
    # aggregate per-STFT-frame proxy to the 1-second frames already stored
    hop, sr = config.audio.hop_size, signal.sample_rate
    for frame in analysis.features:
        lo = int(frame.timestamp_sec * sr / hop)
        hi = int((frame.timestamp_sec + 1.0) * sr / hop)
        window = vp[lo:hi]
        frame.vocal_density_proxy = round(float(window.mean()), 4) if len(window) else 0.0
    return len(analysis.features)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--recompute", action="store_true", help="re-enrich even if present")
    args = ap.parse_args()

    config = load_config()
    repo = FileAnalysisRepository(config.paths.processed_dir)
    ids = repo.list_track_ids()
    if args.limit:
        ids = ids[: args.limit]

    done = skipped = failed = 0
    for i, tid in enumerate(ids, 1):
        analysis = repo.get(tid)
        already = any(f.vocal_density_proxy is not None for f in analysis.features)
        if already and not args.recompute:
            skipped += 1
            continue
        try:
            enrich_one(analysis, config)
            repo.save(analysis)
            done += 1
            vd = [f.vocal_density_proxy for f in analysis.features if f.vocal_density_proxy]
            mean = float(np.mean(vd)) if vd else 0.0
            print(f"[{i}/{len(ids)}] ok  {analysis.track.title[:45]:45} vocal_mean={mean:.3f}", flush=True)
        except Exception as exc:  # per-file isolation
            failed += 1
            print(f"[{i}/{len(ids)}] fail {tid}: {exc}", flush=True)

    print(f"done: {done} enriched, {skipped} skipped, {failed} failed")
    return 1 if failed and failed == len(ids) else 0


if __name__ == "__main__":
    sys.exit(main())

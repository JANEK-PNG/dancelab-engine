"""Re-analyze a curated pilot list with the full feature package (incl. demucs
vocal). Writes fresh AnalysisResult JSONs to data/processed, overwriting stale
ones. Used for demos / EXP validation on a subset — not the whole library.

Usage: .venv/bin/python scripts/analyze_pilot.py [list.txt] [config.yaml]
"""

from __future__ import annotations

import sys
from pathlib import Path

from dancelab.core.config import load_config
from dancelab.core.pipeline import analyze_track
from dancelab.storage.repositories import FileAnalysisRepository


def main() -> int:
    list_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/pilot_tracks.txt")
    config_path = sys.argv[2] if len(sys.argv) > 2 else "configs/pilot_demucs.yaml"
    config = load_config(config_path)
    repo = FileAnalysisRepository(config.paths.processed_dir)

    tracks = [ln.strip() for ln in list_path.read_text().splitlines() if ln.strip()]
    done = failed = 0
    for i, path in enumerate(tracks, 1):
        try:
            result = analyze_track(path, config)
            repo.save(result)
            vd = [f.vocal_density_proxy for f in result.features if f.vocal_density_proxy is not None]
            pc = [f.pulse_clarity_proxy for f in result.features if f.pulse_clarity_proxy is not None]
            vmean = sum(vd) / len(vd) if vd else 0.0
            pmean = sum(pc) / len(pc) if pc else 0.0
            done += 1
            print(f"[{i}/{len(tracks)}] ok  {Path(path).stem[:42]:42} "
                  f"vocal={vmean:.3f} pulse={pmean:.3f}", flush=True)
        except Exception as exc:  # per-file isolation
            failed += 1
            print(f"[{i}/{len(tracks)}] fail {Path(path).name}: {exc}", flush=True)

    print(f"done: {done} analyzed, {failed} failed")
    return 1 if failed == len(tracks) else 0


if __name__ == "__main__":
    sys.exit(main())

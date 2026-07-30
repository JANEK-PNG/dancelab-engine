#!/usr/bin/env python
"""E2E helper: cached analyses -> SetPlan -> transition windows -> cue-export
bundle JSON that `dancelab cues` consumes.

Reuses the proven four_tet recipe (build_set + detect_transition_windows). Uses
ONLY already-cached analyses (no re-analysis, no CLAP). Touches no database.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

from dancelab.core.models import AnalysisResult, TransitionWindowInput
from dancelab.core.config import load_weights
from dancelab.decision.set_builder import build_set
from dancelab.decision.transition_windows import detect_transition_windows

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/reports/library_analysis_cache"
OUT = ROOT / "data/reports/cue_export_bundle.json"
MAX_TRACKS = 5
TOP_K = 4


def main() -> None:
    analyses: list[AnalysisResult] = []
    for f in sorted(glob.glob(str(CACHE / "*.json"))):
        a = AnalysisResult.model_validate_json(Path(f).read_text())
        if a.track.source_path and Path(a.track.source_path).exists() and a.beatgrid:
            analyses.append(a)
    analyses = analyses[:MAX_TRACKS]
    if len(analyses) < 2:
        raise SystemExit(f"need >=2 cached analyses with audio; got {len(analyses)}")

    weights = load_weights("configs/descriptor_weights.yaml")
    plan = build_set(analyses, weights, arc="build")

    windows = {
        an.track.track_id: detect_transition_windows(
            TransitionWindowInput(track_id=an.track.track_id, segments=an.segments,
                                  feature_frames=an.features, beatgrid=an.beatgrid),
            weights.transition_window, top_k=TOP_K).windows
        for an in analyses
    }

    bundle = {
        "set_plan": plan.model_dump(mode="json"),
        "analyses": {a.track.track_id: a.model_dump(mode="json") for a in analyses},
        "windows": {k: [w.model_dump(mode="json") for w in v] for k, v in windows.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle))
    print(f"bundle: {OUT}")
    print(f"tracks in set ({len(plan.track_order)}):")
    by_id = {a.track.track_id: a for a in analyses}
    for tid in plan.track_order:
        a = by_id.get(tid)
        if a:
            print(f"  {a.track.title}  |  {a.track.source_path}")


if __name__ == "__main__":
    main()

"""Live test of the Apple Music playlist road with three tracks from the owner's library.

Run only after the owner agreed in chat. Prints counts, never tokens.
Usage: .venv/bin/python experiments_priv/2026-09-10_apple_playlista/wyslij_test.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.core.models import AnalysisResult, Track  # noqa: E402
from dancelab.ingestion import apple_playlist as ap  # noqa: E402
from dancelab.ingestion.apple_music_api import AppleMusicClient  # noqa: E402

NAME = "DanceLab test 2026-09-10"
IDS = [("t1", "1687954211"), ("t2", "1893195285"), ("t3", "370892956")]


def main() -> None:
    analizy = {tid: AnalysisResult(engine_version="live-test",
                                   track=Track(track_id=tid, title=tid,
                                               source_path=f"apple-music:tracks:{cid}"))
               for tid, cid in IDS}
    plan = ap.plan_apple_playlist([t for t, _ in IDS], analizy, NAME)
    print("plan:", plan.to_dict())
    client = AppleMusicClient.from_config()
    out = ap.publish_apple_playlist(client, plan)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    (ROOT / "experiments_priv/2026-09-10_apple_playlista/wynik.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

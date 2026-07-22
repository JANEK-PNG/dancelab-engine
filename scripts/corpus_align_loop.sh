#!/bin/bash
# Keep aligning as the downloader feeds new tracks. Alignment is compute-fast
# and repeatedly catches up to the rate-limited downloader, so a single pass
# exits early. This loop re-runs the (resumable) batch every SLEEP seconds:
# each pass only processes mixes that newly reached >=4 downloaded tracks.
# Exits when the downloader is done AND no alignable mixes remain.

ROOT="/Volumes/MY_PC/DanceLabCorpus"
ENGINE="/Users/jantrybus/Desktop/AI/dancelab-engine"
SLEEP=900   # 15 min between passes
WORKERS=5

cd "$ENGINE" || exit 1
while true; do
    PYTHONPATH=src .venv/bin/python scripts/corpus_align.py \
        --root "$ROOT" --workers "$WORKERS" --min-tracks 4

    # stop only when downloading is finished and nothing is left to align
    remaining=$(PYTHONPATH=src .venv/bin/python -c "
import sys; sys.path.insert(0,'scripts')
from corpus_align import build_jobs
from pathlib import Path
print(len(build_jobs(Path('$ROOT'),4,Path('$ROOT/alignments'))))
" 2>/dev/null)
    if ! pgrep -f corpus_downloader.py >/dev/null && [ "$remaining" = "0" ]; then
        echo "downloader done + nothing left to align — loop exiting."
        break
    fi
    echo "pass done; $remaining alignable now; sleeping ${SLEEP}s..."
    sleep "$SLEEP"
done

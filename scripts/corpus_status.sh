#!/bin/bash
# DanceLab corpus download status — one-glance summary.
ROOT="/Volumes/MY_PC/DanceLabCorpus"
M="$ROOT/manifest.csv"
[ -f "$M" ] || { echo "brak manifestu — pobieranie jeszcze nie wystartowalo?"; exit 1; }

mix_ok=$(awk -F, '$2=="mix" && $3=="ok"' "$M" | wc -l | tr -d ' ')
mix_dead=$(awk -F, '$2=="mix" && $3=="dead"' "$M" | wc -l | tr -d ' ')
trk_ok=$(awk -F, '$2=="track" && $3=="ok"' "$M" | wc -l | tr -d ' ')
trk_dead=$(awk -F, '$2=="track" && $3=="dead"' "$M" | wc -l | tr -d ' ')
size=$(du -sh "$ROOT" 2>/dev/null | cut -f1)
free=$(df -h "$ROOT" | tail -1 | awk '{print $4}')

echo "=== DanceLab Corpus ==="
echo "mixy:   $mix_ok OK / $mix_dead martwe (kolejka: 1857)"
echo "tracki: $trk_ok OK / $trk_dead martwe"
echo "rozmiar: $size | wolne na dysku: $free"
pgrep -f corpus_downloader.py >/dev/null && echo "proces: DZIALA" || echo "proces: NIE DZIALA (wznow komenda z notatki)"
echo "ostatnie 3 linie:"
tail -3 "$ROOT"/logs/downloader_*.log 2>/dev/null

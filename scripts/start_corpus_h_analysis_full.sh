#!/bin/zsh
set -eu

PROJECT_DIR="/Users/jantrybus/Developer/dancelab-engine"
LOG_DIR="/Volumes/MY_PC/DanceLabCorpus/logs"
LOG_FILE="$LOG_DIR/h_analysis_full_current_pipeline_20260801.log"
PID_FILE="$LOG_DIR/h_analysis_full_current_pipeline_20260801.pid"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(tr -dc '0-9' < "$PID_FILE")"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Analiza już działa (PID $old_pid). Pokazuję jej log:"
    exec tail -n 40 -f "$LOG_FILE"
  fi
fi

nohup env PYTHONPATH=src .venv/bin/python scripts/corpus_h_analysis_full.py \
  --workers 5 --progress-every 25 >"$LOG_FILE" 2>&1 &
worker_pid=$!
echo "$worker_pid" > "$PID_FILE"

echo "DanceLab: pełna analiza korpusu uruchomiona w tle."
echo "PID: $worker_pid"
echo "Log: $LOG_FILE"
echo "Zamknięcie tego okna nie zatrzyma obliczeń. Ctrl+C zatrzymuje tylko podgląd."
echo
exec tail -n 40 -f "$LOG_FILE"

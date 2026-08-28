#!/usr/bin/env bash
# Start, stop and check every DanceLab panel with one command.
#
#   ./scripts/panele.sh start   uruchamia wszystko (baza + panele) i otwiera spis
#   ./scripts/panele.sh stan    mówi, co odpowiada, a co nie
#   ./scripts/panele.sh stop    zatrzymuje panele (kontener bazy zostaje)
#
# Panels are plain HTTP servers, so "działa" means the port answers — not that
# a process exists. A dead server that still holds the port would otherwise
# pass a process check and fail the user.

set -uo pipefail
KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KORZEN"

LOGI="$KORZEN/data/logi-paneli"
mkdir -p "$LOGI"

# nazwa|port|ścieżka do serwera|dodatkowe pakiety
PANELE=(
  "baza|8656|docs/baza-podglad/serwer.py|"
  "karty DJ|8649|docs/mockup-dj-karty/serwer.py|"
  "scena v2|8652|docs/scena-v2/serwer.py|"
  "VJ / portret|8653|docs/vj-system/serwer.py|"
  "szew|8654|docs/warstwa-graficzna/szew/serwer.py|"
  "konsola FLX4|8655|docs/flx4-konsola/serwer.py|--with mido --with python-rtmidi"
  "sprzęt klubowy|8657|docs/sprzet-klubowy/serwer.py|"
  "makieta GUI|8658|docs/gui/serwer.py|"
)

zyje() { curl -s --max-time 2 -o /dev/null "http://localhost:$1/"; }

start_baze() {
  if docker compose ps db 2>/dev/null | grep -q healthy; then
    echo "  baza danych           już chodzi"
    return
  fi
  echo "  baza danych           uruchamiam…"
  docker compose up -d db >/dev/null 2>&1
  for _ in $(seq 1 30); do
    docker compose ps db 2>/dev/null | grep -q healthy && break
    sleep 2
  done
}

case "${1:-start}" in
  start)
    echo "Uruchamiam:"
    start_baze
    for wiersz in "${PANELE[@]}"; do
      IFS='|' read -r nazwa port plik dodatki <<< "$wiersz"
      [ -f "$plik" ] || { printf "  %-21s brak pliku %s\n" "$nazwa" "$plik"; continue; }
      if zyje "$port"; then
        printf "  %-21s już chodzi na %s\n" "$nazwa" "$port"
        continue
      fi
      # shellcheck disable=SC2086
      nohup uv run $dodatki python "$plik" "$port" \
        > "$LOGI/${port}.log" 2>&1 &
      printf "  %-21s startuje na %s\n" "$nazwa" "$port"
    done

    echo
    echo "Czekam, aż odpowiedzą…"
    sleep 6
    "$0" stan
    ;;

  stan)
    echo
    printf "%-21s %-6s %s\n" "PANEL" "PORT" "STAN"
    docker compose ps db 2>/dev/null | grep -q healthy \
      && printf "%-21s %-6s %s\n" "baza danych" "5432" "działa" \
      || printf "%-21s %-6s %s\n" "baza danych" "5432" "NIE DZIAŁA"
    for wiersz in "${PANELE[@]}"; do
      IFS='|' read -r nazwa port _ _ <<< "$wiersz"
      if zyje "$port"; then
        printf "%-21s %-6s %s\n" "$nazwa" "$port" "http://localhost:$port/"
      else
        printf "%-21s %-6s %s\n" "$nazwa" "$port" "nie odpowiada (log: data/logi-paneli/$port.log)"
      fi
    done
    echo
    ;;

  stop)
    for wiersz in "${PANELE[@]}"; do
      IFS='|' read -r nazwa _ plik _ <<< "$wiersz"
      pkill -f "$plik" 2>/dev/null && echo "  zatrzymany: $nazwa"
    done
    echo "Kontener bazy zostawiam — zatrzymasz go: docker compose stop db"
    ;;

  *)
    echo "użycie: $0 [start|stan|stop]"; exit 1;;
esac

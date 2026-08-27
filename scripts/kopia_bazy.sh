#!/usr/bin/env bash
# Dump the catalog to data/kopie/. A Postgres database cannot be backed up by
# copying a file the way SQLite could, so this script is the backup.
set -euo pipefail

KATALOG="${1:-data/kopie}"
KONTENER="${KONTENER:-dancelab-engine-db-1}"
mkdir -p "$KATALOG"
PLIK="$KATALOG/dancelab_$(date +%Y%m%d_%H%M%S).sql.gz"

docker exec "$KONTENER" pg_dump -U dancelab -d dancelab --clean --if-exists \
  | gzip > "$PLIK"

echo "zapisano: $PLIK ($(du -h "$PLIK" | cut -f1))"

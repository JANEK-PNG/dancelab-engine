"""Sam odsiew — playlista kandydatów w Rekordboksie, bez czekania na analizę.

Janek gra w środę i chce zobaczyć pulę TERAZ, a nie za dwadzieścia minut. Odsiew
nie potrzebuje analizy: tempo i gatunek ma już Rekordbox, a wybór z briefu to
filtr po tych dwóch polach. Analiza jest potrzebna dopiero, żeby to UŁOŻYĆ —
kolejność, energia, cue.

Więc to jest lista, nie set. Kolejność: rosnące tempo, bo brief mówi „krzywa
tylko w górę" i to jest najuczciwsze, co da się powiedzieć bez policzonej energii.
Nazwa playlisty mówi wprost „kandydaci", żeby nikt nie pomylił jej z setem.

Zapis idzie tą samą drogą co cue: `write_plan` z pustym planem. Dzięki temu odmowa
przy otwartym Rekordboksie, kopia zapasowa przed zapisem, podmiana zweryfikowanej
kopii i sprawdzenie po fakcie są DOKŁADNIE te same, a nie napisane drugi raz obok.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import unicodedata as U
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DEFAULT_DB = pathlib.Path.home() / "Library/Pioneer/rekordbox/master.db"
DEFAULT_BACKUP = pathlib.Path.home() / "Library/Pioneer/rekordbox/DanceLab_backups"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpm-min", type=float, default=130.0)
    ap.add_argument("--bpm-max", type=float, default=135.0)
    ap.add_argument("--name", default=None)
    ap.add_argument("--db", type=pathlib.Path, default=None)
    ap.add_argument("--write", action="store_true", help="Naprawdę zapisz")
    ap.add_argument("--allow-live", action="store_true", help="Wymagane dla ŻYWEJ biblioteki")
    ap.add_argument("--keep-daytime", action="store_true")
    args = ap.parse_args()

    from brief_set import candidates
    from dancelab.decision.cue_export_models import CuePlan
    from dancelab.ingestion.rekordbox_cue_writer import write_plan
    from pyrekordbox import Rekordbox6Database

    name = args.name or f"Kandydaci {args.bpm_min:.0f}-{args.bpm_max:.0f}"
    target = pathlib.Path(args.db) if args.db else DEFAULT_DB
    is_live = target.resolve() == DEFAULT_DB.resolve()
    if args.write and is_live and not args.allow_live:
        print("Odmawiam zapisu do ŻYWEJ biblioteki bez --allow-live.")
        return 2

    pool, skipped = candidates(args.bpm_min, args.bpm_max, exclude=not args.keep_daytime)
    if not pool:
        print("brief nie zostawił żadnego kandydata")
        return 2

    # ContentID po ścieżce pliku — jedyny klucz, który na pewno się zgadza.
    db = Rekordbox6Database(path=str(target))
    by_path = {}
    for c in db.get_content():
        if c.FolderPath:
            by_path[U.normalize("NFC", str(c.FolderPath))] = c.ID
    ids, brak = [], []
    for _, p, title, _ in pool:
        cid = by_path.get(U.normalize("NFC", str(p)))
        (ids.append(cid) if cid else brak.append(title))
    db.close()

    print(f"{name}: {len(ids)} utworów  (odrzuconych przez brief: {len(skipped)})")
    for bpm, _, title, genre in pool:
        print(f"  {bpm:6.2f}  {title[:44]:44s} {genre or '— gatunek nieopisany'}")
    for t in brak:
        print(f"  ⚠ bez dopasowania w bazie: {t[:44]}")

    if not args.write:
        print("\n(sam podgląd — nic nie zapisane; dodaj --write, żeby założyć playlistę)")
        return 0

    result = write_plan(
        CuePlan(),                     # zero cue: to jest lista, nie set
        db_path=target,
        backup_dir=DEFAULT_BACKUP,
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
        meta={"kind": "candidates_only"},
        safe_swap=True,
        playlist_name=name,
        playlist_content_ids=ids,
    )
    print(f"\n✓ playlista '{name}' ({len(ids)} utworów) w folderze DanceLab · "
          f"zweryfikowana={result.verified} · kopia={result.backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

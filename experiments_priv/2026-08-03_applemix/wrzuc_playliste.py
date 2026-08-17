"""Playlista z setem prosto do Rekordboxa — z backupem i weryfikacją.

Zgoda Janka 2026-08-03 („wrzuć tę playlistę"). Zapis do ŻYWEJ bazy, więc
trzymamy reguły z audytu 24.07: backup przed każdym zapisem, Rekordbox musi
być zamknięty, weryfikacja po zapisie, a przy niejednoznaczności odmowa
zamiast zgadywania.

NIE dotyka BPM ani beatgridu — tylko tworzy folder, playlistę i kolejność.
Cue nie są zapisywane; to osobna komenda i osobna decyzja.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import unicodedata as U
from datetime import datetime

N = lambda s: U.normalize("NFC", str(s))  # noqa: E731
PIONEER = pathlib.Path.home() / "Library/Pioneer/rekordbox"
BACKUPS = PIONEER / "DanceLab_backups"


def _norm_title(stem: str) -> str:
    s = re.sub(r"^\d+\s+", "", stem)
    s = re.sub(r"\((original|extended|radio)[^)]*\)", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", default="/tmp/set_2h.txt")
    ap.add_argument("--name", default=None)
    ap.add_argument("--folder", default="DanceLab")
    ap.add_argument("--write", action="store_true",
                    help="bez tego tylko plan, nic nie zapisuje")
    args = ap.parse_args()

    import psutil
    if any("rekordbox" in (p.name() or "").lower() for p in psutil.process_iter()):
        print("❌ Rekordbox działa — zamknij go przed zapisem.")
        return 1

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    want = [l.strip() for l in pathlib.Path(args.paths).read_text().splitlines()
            if l.strip()]
    db = Rekordbox6Database()
    rows = db.session.query(tables.DjmdContent).all()
    by_path = {N(r.FolderPath or ""): r for r in rows}

    # bliźniaki: ten sam utwór w innym folderze (biblioteka ma dublety)
    by_title: dict[str, list] = {}
    for r in rows:
        fp = r.FolderPath or ""
        if not fp.startswith("/"):
            continue
        by_title.setdefault(_norm_title(pathlib.Path(fp).stem), []).append(r)

    picked, notes = [], []
    for p in want:
        r = by_path.get(N(p))
        if r is not None:
            picked.append(r)
            continue
        stem = pathlib.Path(p).stem
        cands = by_title.get(_norm_title(stem), [])
        if not cands and " - " in stem:      # „Artysta - Tytuł" kontra „01 Tytuł"
            cands = by_title.get(_norm_title(stem.split(" - ", 1)[1]), [])
        if not cands:                        # i odwrotnie
            key = _norm_title(stem)
            cands = [r for t, rs in by_title.items() if t.endswith(key) or key.endswith(t)
                     for r in rs]
            cands = list({id(r): r for r in cands}.values())
        if len(cands) == 1:
            picked.append(cands[0])
            notes.append(f"podmieniony bliźniak: {pathlib.Path(p).name[:44]}")
        else:
            notes.append(f"POMINIĘTY ({len(cands)} kandydatów): "
                         f"{pathlib.Path(p).name[:44]}")

    name = args.name or f"Set {datetime.now():%Y-%m-%d} 135-140"
    print(f"playlista: {args.folder} / {name}")
    print(f"utworów: {len(picked)} z {len(want)}")
    for n in notes:
        print(f"  · {n}")
    for i, r in enumerate(picked, 1):
        print(f"  {i:>3}. {(r.Title or '?')[:52]}")

    if not args.write:
        print("\n(plan — nic nie zapisano; dodaj --write)")
        db.close()
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    bak = BACKUPS / f"master.PRE_PLAYLIST_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(PIONEER / "master.db", bak)
    print(f"\nbackup: {bak.name} ({bak.stat().st_size/1_048_576:.1f} MB)")

    from dancelab.ingestion.rekordbox_playlist import (  # noqa: PLC0415
        create_set_playlist,
    )
    pl = create_set_playlist(db, tables, name=name,
                             content_ids=[str(r.ID) for r in picked],
                             folder_name=args.folder)
    db.commit()
    print("zapisane.")

    # weryfikacja: odczyt z bazy, nie z pamięci
    db2 = Rekordbox6Database()
    got = db2.session.query(tables.DjmdSongPlaylist).filter(
        tables.DjmdSongPlaylist.PlaylistID == pl.ID,
        tables.DjmdSongPlaylist.rb_local_deleted == 0).all()
    print(f"weryfikacja: w bazie {len(got)} utworów w playliście")
    ok = len(got) == len(picked)
    db2.close()
    db.close()
    print("✅ zgadza się" if ok else "❌ ROZJAZD — sprawdź, backup jest w " + str(bak))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

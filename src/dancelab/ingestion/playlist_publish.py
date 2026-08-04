"""Publikacja playlisty do Rekordboxa — produktowa wersja skryptu z 03.08.

Skrypt `experiments_priv/.../wrzuc_playliste.py` wykonał tę robotę pięć razy
z rzędu bez wpadki; TUI potrzebuje tego jako modułu (klawisz `W`), więc reguły
przenoszą się do produktu w niezmienionej postaci:

  * Rekordbox musi być ZAMKNIĘTY — inaczej odmowa przed dotknięciem czegokolwiek;
  * backup master.db PRZED każdym zapisem, do `DanceLab_backups/`;
  * dopasowanie po pełnej ścieżce (NFC); gdy pliku nie ma w kolekcji —
    bliźniak po znormalizowanym tytule, ale TYLKO przy dokładnie jednym
    kandydacie. Niejednoznaczność = pominięcie z raportem, nigdy zgadywanie
    (audyt 24.07: biblioteka ma duplikaty tytułów i to strzelało);
  * po zapisie weryfikacja ODCZYTEM z bazy, nie stanem w pamięci.

Zapis nie dotyka BPM, beatgridów ani cue — wyłącznie folder/playlista/kolejność.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

PIONEER = pathlib.Path.home() / "Library/Pioneer/rekordbox"
BACKUP_DIR = PIONEER / "DanceLab_backups"


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s))


def _norm_title(stem: str) -> str:
    s = re.sub(r"^\d+\s+", "", stem)
    s = re.sub(r"\((original|extended|radio)[^)]*\)", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


@dataclass(frozen=True)
class PublishReport:
    ok: bool
    playlist_name: str
    requested: int
    matched: int
    written: int
    backup_path: str | None
    notes: list[str] = field(default_factory=list)


def rekordbox_running() -> bool:
    """Czy Rekordbox chodzi. Odpornie na wyścig: proces może umrzeć między
    listowaniem a pytaniem o nazwę (złapane na żywo 04.08 — `triald_system`
    zszedł w trakcie iteracji i wywalił cały pasek statusu TUI).
    `process_iter(["name"])` pobiera nazwy hurtem i połyka zniknięte procesy;
    pojedynczy wybuch nie może kłaść wyniku, więc pas i szelki."""
    import psutil
    try:
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "")
            if "rekordbox" in name.lower():
                return True
    except Exception:  # noqa: BLE001 — brak odpowiedzi to nie "zamknięty"
        return False
    return False


def publish_playlist(
    paths: list[str],
    *,
    name: str,
    folder: str = "DanceLab",
    dry_run: bool = False,
) -> PublishReport:
    """Utwórz playlistę o tej kolejności w Rekordboksie. Domyślnie NA SERIO
    dopiero po `dry_run=False` — wołający (TUI) pokazuje najpierw plan."""
    notes: list[str] = []
    if rekordbox_running():
        return PublishReport(False, name, len(paths), 0, 0, None,
                             ["Rekordbox działa — zamknij go przed zapisem"])

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    try:
        rows = db.session.query(tables.DjmdContent).all()
        by_path = {_nfc(r.FolderPath or ""): r for r in rows}
        by_title: dict[str, list] = {}
        for r in rows:
            fp = r.FolderPath or ""
            if fp.startswith("/"):
                by_title.setdefault(_norm_title(pathlib.Path(fp).stem), []).append(r)

        picked = []
        for p in paths:
            row = by_path.get(_nfc(p))
            if row is None:
                cands = by_title.get(_norm_title(pathlib.Path(p).stem), [])
                if len(cands) == 1:
                    row = cands[0]
                    notes.append(f"bliźniak: {pathlib.Path(p).name[:48]}")
            if row is None:
                notes.append(f"POMINIĘTY (brak/niejednoznaczny): {pathlib.Path(p).name[:48]}")
                continue
            picked.append(row)

        if dry_run:
            return PublishReport(True, name, len(paths), len(picked), 0, None, notes)

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"master.PRE_TUI_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(PIONEER / "master.db", backup)

        from dancelab.ingestion.rekordbox_playlist import create_set_playlist
        pl = create_set_playlist(db, tables, name=name,
                                 content_ids=[str(r.ID) for r in picked],
                                 folder_name=folder)
        db.commit()
        playlist_id = pl.ID
    finally:
        db.close()

    # weryfikacja świeżym połączeniem — z dysku, nie z pamięci
    db2 = Rekordbox6Database()
    try:
        got = db2.session.query(tables.DjmdSongPlaylist).filter(
            tables.DjmdSongPlaylist.PlaylistID == playlist_id,
            tables.DjmdSongPlaylist.rb_local_deleted == 0).count()
    finally:
        db2.close()
    ok = got == len(picked)
    if not ok:
        notes.append(f"ROZJAZD po zapisie: w bazie {got}, oczekiwano {len(picked)} "
                     f"— backup: {backup}")
    return PublishReport(ok, name, len(paths), len(picked), got, str(backup), notes)

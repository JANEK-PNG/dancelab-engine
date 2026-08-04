"""Co Rekordbox wie o jednym pliku — TYLKO odczyt master.db.

Dla karty INFO w TUI (klawisz I, prośba Janka 04.08): BPM z analizy Rekordboxa
(niezależny sędzia tempa), komentarz DJ-a i playlisty, w których utwór
aktualnie leży (z nazwą folderu, gdy playlist ma rodzica).

Czytanie działa przy OTWARTYM Rekordboksie — dokładnie tą samą drogą czyta
dokarmianie gatunków. Dopasowanie jak w sprawdzonym publikatorze playlist:
najpierw pełna ścieżka (NFC), potem bliźniak po znormalizowanym tytule, ale
TYLKO przy dokładnie jednym kandydacie — niejednoznaczność ani brak to None
z prawdą w polu, nigdy zgadywanie.
"""

from __future__ import annotations

import pathlib

from dancelab.ingestion.playlist_publish import _nfc, _norm_title


def track_in_rekordbox(source_path: str) -> dict | None:
    """Zwraca {bpm, comment, playlists, matched_by} albo None (brak w kolekcji)."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    try:
        rows = db.session.query(tables.DjmdContent).all()
        by_path = {_nfc(r.FolderPath or ""): r for r in rows}
        row = by_path.get(_nfc(source_path))
        matched_by = "path"
        if row is None:
            stem = _norm_title(pathlib.Path(source_path).stem)
            cands = [r for r in rows
                     if (r.FolderPath or "").startswith("/")
                     and _norm_title(pathlib.Path(r.FolderPath).stem) == stem]
            if len(cands) != 1:
                return None
            row, matched_by = cands[0], "twin"

        links = (db.session.query(tables.DjmdSongPlaylist)
                 .filter(tables.DjmdSongPlaylist.ContentID == row.ID,
                         tables.DjmdSongPlaylist.rb_local_deleted == 0).all())
        names: list[str] = []
        for link in links:
            pl = (db.session.query(tables.DjmdPlaylist)
                  .filter(tables.DjmdPlaylist.ID == link.PlaylistID)
                  .one_or_none())
            if pl is None:
                continue
            parent = None
            if getattr(pl, "ParentID", None) not in (None, "", "root"):
                parent = (db.session.query(tables.DjmdPlaylist)
                          .filter(tables.DjmdPlaylist.ID == pl.ParentID)
                          .one_or_none())
            names.append(f"{parent.Name}/{pl.Name}" if parent is not None
                         else str(pl.Name))
        return {
            "bpm": ((row.BPM or 0) / 100.0) or None,
            "comment": getattr(row, "Commnt", None) or None,
            "playlists": sorted(set(names)),
            "matched_by": matched_by,
        }
    finally:
        db.close()

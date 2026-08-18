"""Playlisty DANCELAB 01–15 z pulpitu → Rekordbox, dopasowanie po strumieniach.

DECYZJA JANKA (2026-08-17): utwory z 15 tracklist są już przeanalizowane
w zakładce Apple Music Rekordboxa, playlisty nigdy nie powstały — „wystarczy,
że teraz tylko zrobisz playlisty". To jest jego słowo na zapis do master.db.

DLACZEGO NIE `publish_playlist` WPROST: tamta droga dopasowuje po ŚCIEŻCE
pliku, a te utwory to strumienie Apple Music — ścieżek nie mają. Dopasowanie
idzie po wykonawcy i tytule, znormalizowanych tym samym wzorcem, którego
używa porównywarka tonacji (NFC, casefold, nawiasy won). Fundamenty zapisu
te same, co w udowodnionej ścieżce: Rekordbox musi być ZAMKNIĘTY, kopia
całego kompletu plików bazy przed zapisem, weryfikacja świeżym połączeniem po.

UCZCIWOŚĆ DOPASOWANIA:
  * wiersz bez jednoznacznego trafienia jest POMIJANY i wypisany imiennie —
    nigdy nie zgadujemy („pominięto N" to stan, nie wstyd);
  * przy kilku kandydatach (strumień + plik lokalny tego samego utworu)
    wybieramy PRZEANALIZOWANY strumień, bo playlisty są z zakładki Apple;
  * bramka całości: jeśli dopasowanie ogółem < 70%, NIE zapisujemy nic.

Tryby: bez argumentu = PRÓBA NA SUCHO (zero zapisu). `--na-serio` = zapis.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import sys
import unicodedata as U
from collections import defaultdict
from datetime import datetime

FOLDER_TXT = pathlib.Path.home() / "Desktop" / "DanceLab playlisty"
PIONEER = pathlib.Path.home() / "Library" / "Pioneer" / "rekordbox"


def norm(s: str) -> str:
    s = U.normalize("NFC", s or "").casefold()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)      # (Original Mix), [Remaster]…
    s = re.sub(r"feat\.?.*$", " ", s)
    s = re.sub(r"[^0-9a-zà-ɏ]+", " ", s)
    return " ".join(s.split())


def wczytaj_tracklisty() -> dict[str, list[tuple[str, str, str]]]:
    """nazwa playlisty → [(artysta, tytuł, surowa linia)] w kolejności."""
    out = {}
    for p in sorted(FOLDER_TXT.glob("DANCELAB *.txt")):
        pozycje = []
        for linia in p.read_text(encoding="utf-8").splitlines():
            linia = linia.strip()
            if not linia or " - " not in linia:
                continue
            artysta, tytul = linia.split(" - ", 1)
            pozycje.append((artysta.strip(), tytul.strip(), linia))
        out[p.stem] = pozycje
    return out


def main() -> int:
    na_serio = "--na-serio" in sys.argv

    from dancelab.ingestion.playlist_publish import BACKUP_DIR, rekordbox_running

    if rekordbox_running():
        print("⛔ Rekordbox działa — zamknij go przed zapisem")
        return 2

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    listy = wczytaj_tracklisty()
    print(f"tracklist: {len(listy)} · pozycji łącznie: "
          f"{sum(len(v) for v in listy.values())}")

    db = Rekordbox6Database()
    try:
        wiersze = db.session.query(tables.DjmdContent).all()
        indeks: dict[tuple[str, str], list] = defaultdict(list)
        indeks_tytul: dict[str, list] = defaultdict(list)
        for r in wiersze:
            art = r.Artist.Name if getattr(r, "Artist", None) else ""
            indeks[(norm(art), norm(r.Title or ""))].append(r)
            indeks_tytul[norm(r.Title or "")].append(r)

        def dopasuj(artysta: str, tytul: str):
            kand = indeks.get((norm(artysta), norm(tytul)), [])
            if not kand:
                kand = [r for r in indeks_tytul.get(norm(tytul), [])
                        if norm(artysta) in norm(
                            r.Artist.Name if getattr(r, "Artist", None) else "")]
            if not kand:
                return None, "brak"
            if len(kand) > 1:
                analizowane = [r for r in kand if int(r.Analysed or 0)]
                kand = analizowane or kand
            if len(kand) > 1:
                # strumień + plik: playlisty są z zakładki Apple — bierz strumień
                strumienie = [r for r in kand
                              if not str(r.FolderPath or "").startswith("/")]
                kand = strumienie or kand
            return (kand[0], "ok") if len(kand) == 1 else (None, "niejednoznaczny")

        plan = {}
        for nazwa, pozycje in listy.items():
            trafienia, braki = [], []
            for artysta, tytul, surowa in pozycje:
                r, status = dopasuj(artysta, tytul)
                if r is not None:
                    trafienia.append(r)
                else:
                    braki.append((status, surowa))
            plan[nazwa] = (trafienia, braki)
            print(f"  {nazwa}: {len(trafienia)}/{len(pozycje)}"
                  + (f" · pominięte: {len(braki)}" if braki else ""))
            for status, surowa in braki:
                print(f"      POMINIĘTY ({status}): {surowa[:60]}")

        razem = sum(len(t) for t, _ in plan.values())
        wszystkich = sum(len(v) for v in listy.values())
        procent = 100 * razem / wszystkich
        print(f"\ndopasowanie ogółem: {razem}/{wszystkich} ({procent:.1f}%)")
        if procent < 70:
            print("⛔ poniżej bramki 70% — nie zapisuję nic")
            return 2
        if not na_serio:
            print("\nPRÓBA NA SUCHO — nic nie zapisano. Zapis: --na-serio")
            return 0

        # kopia CAŁEGO kompletu plików bazy przed zapisem
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stempel = f"{datetime.now():%Y%m%d_%H%M%S}"
        backup = BACKUP_DIR / f"master.PRE_DANCELAB_{stempel}.db"
        shutil.copy2(PIONEER / "master.db", backup)
        for boczny in (".db-wal", ".db-shm"):
            src = (PIONEER / "master.db").with_suffix(boczny)
            if src.exists():
                shutil.copy2(src, backup.with_suffix(boczny))
        print(f"\nkopia zapasowa: {backup.name}")

        from dancelab.ingestion.rekordbox_playlist import create_set_playlist
        id_playlist = {}
        for nazwa, (trafienia, _) in plan.items():
            pl = create_set_playlist(db, tables, name=nazwa,
                                     content_ids=[str(r.ID) for r in trafienia],
                                     folder_name="DanceLab")
            id_playlist[nazwa] = (str(pl.ID), len(trafienia))
        db.commit()
    finally:
        db.close()

    # weryfikacja świeżym połączeniem — z dysku, nie z pamięci
    db2 = Rekordbox6Database()
    rozjazdy = 0
    try:
        for nazwa, (pid, oczekiwane) in id_playlist.items():
            got = db2.session.query(tables.DjmdSongPlaylist).filter(
                tables.DjmdSongPlaylist.PlaylistID == pid,
                tables.DjmdSongPlaylist.rb_local_deleted == 0).count()
            znak = "✓" if got == oczekiwane else "⛔"
            if got != oczekiwane:
                rozjazdy += 1
            print(f"  {znak} {nazwa}: w bazie {got}, oczekiwano {oczekiwane}")
    finally:
        db2.close()
    if rozjazdy:
        print(f"⛔ ROZJAZDY: {rozjazdy} — kopia zapasowa: {backup}")
        return 1
    print(f"\nZAPISANE i ZWERYFIKOWANE. Kopia zapasowa: {backup.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

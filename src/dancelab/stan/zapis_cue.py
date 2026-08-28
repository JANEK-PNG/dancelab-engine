"""Pady z ekranu → hot cue w Rekordboksie. Jedna droga dla obu skór.

Ten moduł nie liczy nic własnego i celowo nie ma własnej drogi do bazy:

* propozycje padów liczy `tui.cue_podglad.zbuduj_plan_cue`,
* plan do zapisu składa `tui.cue_zapis.zbuduj_plan_do_zapisu`,
* kolizje z Twoimi cue liczy `tui.cue_zapis.policz_kolizje`,
* **sam zapis** robi `ingestion.rekordbox_cue_writer.write_plan` — z odmową
  przy otwartym Rekordboksie, kopią zapasową, weryfikacją odczytem
  i automatycznym przywróceniem, gdy zapis się nie potwierdzi.

Tutaj siedzi wyłącznie KOLEJNOŚĆ tych kroków, wyjęta z `tui/app.py`, żeby
okno nie musiało jej powtarzać. Dwa stopnie zostają dwoma stopniami:
`przygotuj` liczy i pokazuje, `zapisz` dopiero rusza bazę.
"""

from __future__ import annotations

import pathlib
import time
from typing import Any

# Domyślnie: żywa baza Rekordboxa i katalog kopii, te same co w terminalu.
# Podmiana ścieżki istnieje dla testu, który pisze do KOPII master.db — nigdy
# po to, żeby program w locie wybierał sobie inną bazę.
from dancelab.ingestion.playlist_publish import BACKUP_DIR, PIONEER

BAZA_DOMYSLNA = PIONEER / "master.db"


def rekordbox_otwarty() -> bool:
    """Czy Rekordbox chodzi. Przy otwartym zapis jest zablokowany — jego
    własny bufor nadpisałby to, co zapiszemy."""
    from dancelab.ingestion.playlist_publish import rekordbox_running
    return bool(rekordbox_running())


def propozycje(kolejnosc: list[str], by_id: dict, wagi: Any):
    """CuePlan silnika dla zbudowanego setu — propozycje padów, nie zapis.

    Bez tego okno miałoby do zapisania tylko pady postawione ręcznie, więc
    jest to część drogi zapisu, a nie ozdoba."""
    from dancelab.ingestion.rekordbox_siatka import downbeaty_dla_sciezki
    from dancelab.tui.cue_podglad import zbuduj_plan_cue
    return zbuduj_plan_cue(list(kolejnosc), by_id, wagi,
                           downbeaty_dla=downbeaty_dla_sciezki)


def przygotuj(plan_cue, edycje: dict, by_id: dict, kolejnosc: list[str],
              *, baza: pathlib.Path | None = None) -> dict[str, Any]:
    """Stopień pierwszy: policz plan i kolizje na bazie, ale NIC nie zapisuj.

    Zwraca liczby, które DJ ma zobaczyć przed decyzją, oraz gotowy plan do
    stopnia drugiego. Utwory, których nie ma w kolekcji Rekordboksa, wracają
    imiennie — nigdy nie są dopasowywane na oko.
    """
    from dancelab.ingestion import cue_ledger
    from dancelab.ingestion.rekordbox_cue_writer import _open, read_existing_cues
    from dancelab.tui import cue_zapis as CZ

    sciezka = pathlib.Path(baza or BAZA_DOMYSLNA)
    content_ids = CZ.mapa_content_id(sciezka)
    plan, ids_setu, pominiete = CZ.zbuduj_plan_do_zapisu(
        plan_cue, edycje, by_id, list(kolejnosc), content_ids)

    db, tables = _open(sciezka)
    try:
        istniejace = read_existing_cues(db, tables)
    finally:
        db.close()

    wynik = CZ.policz_kolizje(plan, istniejace, cue_ledger.wczytaj())
    return {
        "plan": wynik["plan"],
        "ids_setu": ids_setu,
        "do_zapisu": wynik["do_zapisu"],
        "odswiezone": wynik["odswiezone"],
        "ustapilo_twoim": wynik["pominiete_kolizje"],
        "utworow": len(wynik["plan"].tracks),
        "spoza_kolekcji": pominiete,
    }


def zapisz(plan, *, nazwa: str = "okno DanceLab",
           baza: pathlib.Path | None = None,
           katalog_kopii: pathlib.Path | None = None) -> dict[str, Any]:
    """Stopień drugi: zapis przez sprawdzoną warstwę bezpieczeństwa.

    Po udanym zapisie pady trafiają do rejestru `cue_ledger` — dzięki temu
    następnym razem wiadomo, które cue w bazie są nasze i wolno je odświeżyć,
    a które postawił DJ i są nietykalne.
    """
    from dancelab.ingestion import cue_ledger
    from dancelab.ingestion.rekordbox_cue_writer import write_plan

    wynik = write_plan(
        plan,
        db_path=pathlib.Path(baza or BAZA_DOMYSLNA),
        backup_dir=pathlib.Path(katalog_kopii or BACKUP_DIR),
        timestamp=time.strftime("%Y%m%d_%H%M%S"),
        meta={"zrodlo": "okno DanceLab", "plan": nazwa},
        safe_swap=True)
    cue_ledger.zapamietaj(wynik.inserted,
                          znacznik=time.strftime("%Y-%m-%d %H:%M"))
    return {
        "zapisane": wynik.written,
        "usuniete": wynik.deleted,
        "kopia": str(wynik.backup_path),
    }

"""Write the catalog back out as a spreadsheet.

The spreadsheet stops being the source of truth and becomes a view, but it
stays the format the work is actually reviewed in. This exporter is also the
verification step: if a sheet comes back with fewer rows than went in, the
import lost something.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# sheet title -> (query, column headers)
ARKUSZE: dict[str, tuple[str, list[str]]] = {
    "Encje artysty": (
        "SELECT artysta_id, nazwa, ra_id, soundcloud, bandcamp, kraj,"
        " kraj_zamieszkania, wytwornie, obserwujacych_ra FROM artysta"
        " ORDER BY artysta_id",
        ["artysta_id", "nazwa kanoniczna", "ra_id", "SoundCloud", "Bandcamp",
         "kraj", "kraj zamieszkania", "wytwórnie", "obserwujących RA"],
    ),
    "Utwory kanoniczne": (
        "SELECT utwor_id, wykonawca, tytul, wydawca, wystapien, granych_przez,"
        " lata, zrodla, bpm, bpm_pewnosc, tonacja, tonacja_klasyczna,"
        " tonacja_pewnosc, energia, gestosc_groove, obecnosc_basu, dlugosc_s,"
        " analiza_wersja, analiza_data FROM utwor ORDER BY utwor_id",
        ["utwor_id", "wykonawca", "tytuł", "wydawca", "wystąpień",
         "granych przez", "lata", "źródła", "bpm", "bpm_pewnosc", "tonacja",
         "tonacja_klasyczna", "tonacja_pewnosc", "energia", "gestosc_groove",
         "obecnosc_basu", "dlugosc_s", "analiza_wersja", "analiza_data"],
    ),
    "Szwy": (
        "SELECT szew_id, artysta_id, ksywa, wydarzenie, data_tekst, poz_z,"
        " poz_do, utwor_wychodzacy, utwor_wchodzacy, utwor_z_id, utwor_do_id,"
        " czas_wejscia, czas_ms, zrodlo_czasu, zrodlo_pozycji, status_w_lejku,"
        " link_setu FROM szew ORDER BY szew_id",
        ["szew_id", "artysta_id", "ksywa", "wydarzenie", "data", "poz. z",
         "poz. do", "utwór wychodzący", "utwór wchodzący", "utwor_z_id",
         "utwor_do_id", "czas wejścia", "czas_ms", "źródło czasu",
         "źródło pozycji", "status w lejku", "link setu"],
    ),
    "Tracklisty": (
        "SELECT ksywa, setname, wydarzenie, data_tekst, pewnosc_polaczenia,"
        " pozycja, czas, rozpoznany, wykonawca_utworu, tytul_utworu, wydawca,"
        " zrodlo_pozycji, link_setu, utwor_id FROM pozycja_tracklisty"
        " ORDER BY id",
        ["ksywa", "set", "wydarzenie", "data", "pewność połączenia", "poz.",
         "czas", "rozpoznany", "wykonawca utworu", "tytuł utworu", "wydawca",
         "źródło pozycji", "link setu", "utwor_id (dopasowany)"],
    ),
    "Miksy": (
        "SELECT ksywa, tytul, wydarzenie, typ, scena, format, rola, czas,"
        " data_tekst, zrodlo, pewnosc, dlugosc_min, konto, kto_gral_obok,"
        " link, opis, youtube_id FROM miks ORDER BY miks_id",
        ["ksywa", "tytuł", "wydarzenie", "typ", "scena", "format", "rola",
         "czas", "data", "źródło", "pewność", "długość (min)",
         "konto (wrzucił)", "kto grał obok", "link", "opis od artysty",
         "youtube_id"],
    ),
    "Występy": (
        "SELECT ksywa, kiedy, data_tekst, wydarzenie, miejsce, miasto, kraj,"
        " link FROM wystep ORDER BY id",
        ["ksywa", "kiedy", "data", "wydarzenie", "miejsce", "miasto", "kraj",
         "link"],
    ),
    "Mapowanie": (
        "SELECT system_zrodlowy, id_zrodlowy, system_docelowy, id_docelowy,"
        " metoda, pewnosc FROM mapowanie ORDER BY system_zrodlowy, id_zrodlowy",
        ["system źródłowy", "id źródłowy", "system docelowy", "id docelowy",
         "metoda", "pewność"],
    ),
}


def run(conn: Any, target: Path) -> dict[str, int]:
    """Write every sheet. Returns rows written per sheet."""
    import openpyxl

    workbook = openpyxl.Workbook(write_only=True)
    written: dict[str, int] = {}
    for title, (sql, headers) in ARKUSZE.items():
        sheet = workbook.create_sheet(title)
        sheet.append(headers)
        count = 0
        with conn.cursor(name=f"eksport_{count}") as cur:
            # Server-side cursor: the tracklist sheet is 40k rows and there is
            # no reason to hold it all in memory twice.
            cur.itersize = 5000
            cur.execute(sql)
            for row in cur:
                sheet.append(list(row))
                count += 1
        written[title] = count

    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    return written

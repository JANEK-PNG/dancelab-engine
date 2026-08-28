"""Write the catalog back out as a spreadsheet.

The spreadsheet stops being the source of truth and becomes a view, but it
stays the format the work is actually reviewed in. This exporter is also the
verification step: if a sheet comes back with fewer rows than went in, the
import lost something.

All thirteen source sheets round-trip. One deliberate difference: Artyści
returns 2416 rows against 2423, because seven artists appear twice under
different casing ("Catz 'n Dogz" / "Catz 'N Dogz") with the data split across
the pair. The importer merges them field by field, so the export has fewer
rows and more information than the source.
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
    "Artyści": (
        "SELECT ksywa, soundcloud, apple_music, gatunek_apple, bandcamp,"
        " skad_bandcamp, gatunek_bandcamp, wytwornie_ra, kraj_ra,"
        " obserwujacych_ra, wystepow_w_ra, festiwal_2026, miksow_w_bazie,"
        " lata_w_garbiczu, uwagi, kandydaci FROM artysta_profil ORDER BY ksywa",
        ["ksywa sceniczna", "SoundCloud", "Apple Music", "gatunek wg Apple",
         "Bandcamp", "skąd (wg Bandcamp)", "gatunek wg Bandcamp",
         "wytwórnie (RA)", "kraj (RA)", "obserwujących (RA)", "występów w RA",
         "festiwal 2026", "miksów w bazie", "lata w Garbiczu", "uwagi",
         "kandydaci do rozstrzygnięcia"],
    ),
    "Utwory": (
        "SELECT ksywa, tytul, album, rok, link, zrodlo FROM dyskografia"
        " ORDER BY id",
        ["ksywa", "tytuł", "album", "rok", "link", "źródło"],
    ),
    "Programy": (
        "SELECT festiwal, ksywa, dzien, data_tekst, scena, charakter_sceny,"
        " start, koniec, rola, format FROM program ORDER BY id",
        ["festiwal", "ksywa", "dzień", "data", "scena", "charakter sceny",
         "start", "koniec", "rola", "format"],
    ),
    "Kanon RA": (
        "SELECT kategoria, miejsce, kolejnosc, ksywa, tytul, rok, profil_ra,"
        " soundcloud_id, autor_tekstu, uzasadnienie, artykul_ra FROM kanon_ra"
        " ORDER BY id",
        ["kategoria", "miejsce", "kolejność", "ksywa", "tytuł", "rok",
         "profil RA", "SoundCloud ID", "autor tekstu",
         "uzasadnienie redakcji", "artykuł RA"],
    ),
    "De School": (
        "SELECT data_tekst, dzien, cykl, ksywa, scena, typ, format, zrodlo,"
        " pewnosc, strona_archiwum, link FROM de_school ORDER BY id",
        ["data", "dzień", "cykl", "ksywa", "scena", "typ", "format", "źródło",
         "pewność", "strona archiwum", "link"],
    ),
    # Prose sheets. Without these the spreadsheet cannot become an export:
    # Metoda is the only text saying how the data was gathered.
    "Metoda": (
        "SELECT tresc FROM metoda ORDER BY wiersz",
        ["STAN NA DZIEŃ BUDOWY ARKUSZA"],
    ),
    "Legenda": (
        "SELECT wymiar, wartosc, kolor, co_znaczy FROM legenda ORDER BY wiersz",
        ["wymiar", "wartość", "kolor", "co znaczy"],
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

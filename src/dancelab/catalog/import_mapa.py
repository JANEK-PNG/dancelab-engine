"""Load the DJ map spreadsheet into the catalog.

The spreadsheet has been the project's source of truth for months, so the
importer is deliberately conservative: it never repairs a value, never guesses
an identifier, and keeps every date string it was given alongside the parsed
date. Anything it cannot parse stays visible as text rather than becoming NULL.

The import is idempotent by truncating the spreadsheet-derived tables first.
Tables holding our own measurements (analiza, wektor, ocena, sesja…) are left
untouched, as is the mapowanie glue, which ``dopasuj`` rebuilds separately.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

DEFAULT_XLSX = Path(
    "experiments_priv/2026-08-03_dj_mapa/mapa_djow_audioriver_garbicz.xlsx"
)

# Tables this importer owns end to end. Truncated before every run.
OWNED_TABLES = (
    "pozycja_tracklisty",
    "szew",
    "utwor",
    "artysta_profil",
    "dyskografia",
    "miks",
    "wystep",
    "program",
    "kanon_ra",
    "de_school",
    "artysta",
)

_YOUTUBE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


# --------------------------------------------------------------- converters


def _txt(value: Any) -> str | None:
    """Trim to text; empty and whitespace-only cells become NULL."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d-]", "", str(value))
    try:
        return int(digits)
    except ValueError:
        return None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _bool(value: Any) -> bool | None:
    """Parse the spreadsheet's several ways of writing yes and no."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"tak", "true", "1", "prawda", "y", "yes"}:
        return True
    if text in {"nie", "false", "0", "fałsz", "falsz", "n", "no"}:
        return False
    return None


def _date(value: Any) -> dt.date | None:
    """Parse a date, tolerating the formats the sources actually use.

    Partial dates (a bare year, or year-month) are common in scraped
    tracklists. They are not upgraded to a fake 1 January — they simply fail
    to parse and survive in the accompanying ``*_tekst`` column.
    """
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _youtube_id(link: str | None) -> str | None:
    if not link:
        return None
    found = _YOUTUBE.search(link)
    return found.group(1) if found else None


# ------------------------------------------------------------------ loading


def _rows(worksheet: Any) -> list[dict[str, Any]]:
    """Read a sheet as dicts keyed by header text."""
    iterator = worksheet.iter_rows(values_only=True)
    header = next(iterator, None)
    if header is None:
        return []
    names = [str(h).strip() if h is not None else f"_{i}" for i, h in enumerate(header)]
    out: list[dict[str, Any]] = []
    for row in iterator:
        if row is None or all(cell is None or cell == "" for cell in row):
            continue
        out.append(dict(zip(names, row, strict=False)))
    return out


def _copy(conn: Any, table: str, columns: list[str], rows: list[tuple[Any, ...]]) -> int:
    """Bulk-load with COPY; 40k-row sheets make row-by-row inserts painful."""
    if not rows:
        return 0
    cols = ", ".join(f'"{c}"' for c in columns)
    with conn.cursor() as cur:
        # Identifiers come from this module, never from the spreadsheet.
        with cur.copy(f'COPY "{table}" ({cols}) FROM STDIN') as copy:  # noqa: S608
            for row in rows:
                copy.write_row(row)
    return len(rows)


def run(conn: Any, xlsx: Path | None = None) -> dict[str, int]:
    """Import every sheet. Returns rows written per table."""
    import openpyxl

    path = Path(xlsx or DEFAULT_XLSX)
    if not path.exists():
        raise FileNotFoundError(f"nie znalazlem arkusza: {path}")

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = {ws.title: _rows(ws) for ws in workbook.worksheets}
    workbook.close()

    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE " + ", ".join(OWNED_TABLES) + " RESTART IDENTITY CASCADE"
        )

    written: dict[str, int] = {}

    # --- artysta (canonical) must land before anything referencing it -----
    rows = sheets.get("Encje artysty", [])
    written["artysta"] = _copy(
        conn,
        "artysta",
        [
            "artysta_id", "nazwa", "ra_id", "soundcloud", "bandcamp",
            "kraj", "kraj_zamieszkania", "wytwornie", "obserwujacych_ra",
        ],
        [
            (
                _txt(r.get("artysta_id")),
                _txt(r.get("nazwa kanoniczna")) or _txt(r.get("artysta_id")),
                _txt(r.get("ra_id")),
                _txt(r.get("SoundCloud")),
                _txt(r.get("Bandcamp")),
                _txt(r.get("kraj")),
                _txt(r.get("kraj zamieszkania")),
                _txt(r.get("wytwórnie")),
                _int(r.get("obserwujących RA")),
            )
            for r in rows
            if _txt(r.get("artysta_id"))
        ],
    )

    # --- utwor (canonical) -----------------------------------------------
    rows = sheets.get("Utwory kanoniczne", [])
    written["utwor"] = _copy(
        conn,
        "utwor",
        [
            "utwor_id", "wykonawca", "tytul", "wydawca", "wystapien",
            "granych_przez", "lata", "zrodla", "bpm", "bpm_pewnosc",
            "tonacja", "tonacja_klasyczna", "tonacja_pewnosc", "energia",
            "gestosc_groove", "obecnosc_basu", "dlugosc_s",
            "analiza_wersja", "analiza_data",
        ],
        [
            (
                _txt(r.get("utwor_id")),
                _txt(r.get("wykonawca")),
                _txt(r.get("tytuł")),
                _txt(r.get("wydawca")),
                _int(r.get("wystąpień")),
                _int(r.get("granych przez")),
                _txt(r.get("lata")),
                _txt(r.get("źródła")),
                _float(r.get("bpm")),
                _float(r.get("bpm_pewnosc")),
                _txt(r.get("tonacja")),
                _txt(r.get("tonacja_klasyczna")),
                _float(r.get("tonacja_pewnosc")),
                _float(r.get("energia")),
                _float(r.get("gestosc_groove")),
                _float(r.get("obecnosc_basu")),
                _float(r.get("dlugosc_s")),
                _txt(r.get("analiza_wersja")),
                _txt(r.get("analiza_data")),
            )
            for r in rows
            if _txt(r.get("utwor_id"))
        ],
    )

    # --- szew: references artysta and utwor ------------------------------
    known_artysta = _keys(conn, "SELECT artysta_id FROM artysta")
    known_utwor = _keys(conn, "SELECT utwor_id FROM utwor")
    rows = sheets.get("Szwy", [])
    szwy: list[tuple[Any, ...]] = []
    porzucone_fk = 0
    for r in rows:
        szew_id = _txt(r.get("szew_id"))
        if not szew_id:
            continue
        aid = _txt(r.get("artysta_id"))
        uz = _txt(r.get("utwor_z_id"))
        ud = _txt(r.get("utwor_do_id"))
        # A dangling identifier is dropped to NULL rather than rejecting the
        # seam: losing one link is better than losing the whole row, and the
        # count is reported so it never passes silently.
        if aid and aid not in known_artysta:
            aid, porzucone_fk = None, porzucone_fk + 1
        if uz and uz not in known_utwor:
            uz, porzucone_fk = None, porzucone_fk + 1
        if ud and ud not in known_utwor:
            ud, porzucone_fk = None, porzucone_fk + 1
        szwy.append(
            (
                szew_id, aid, _txt(r.get("ksywa")), _txt(r.get("wydarzenie")),
                _txt(r.get("data")), _date(r.get("data")),
                _int(r.get("poz. z")), _int(r.get("poz. do")),
                _txt(r.get("utwór wychodzący")), _txt(r.get("utwór wchodzący")),
                uz, ud,
                _txt(r.get("czas wejścia")), _int(r.get("czas_ms")),
                _txt(r.get("źródło czasu")), _txt(r.get("źródło pozycji")),
                _txt(r.get("status w lejku")), _txt(r.get("link setu")),
                _float(r.get("bpm_z")), _float(r.get("bpm_do")),
                _float(r.get("delta_bpm")), _float(r.get("delta_bpm_proc")),
                _txt(r.get("tonacja_z")), _txt(r.get("tonacja_do")),
                _txt(r.get("zgodnosc_harmoniczna")),
                _float(r.get("dlugosc_przejscia_s")), _txt(r.get("typ_przejscia")),
                _bool(r.get("bas_wstrzymany")),
                _float(r.get("energia_z")), _float(r.get("energia_do")),
                _float(r.get("delta_energii")),
                _txt(r.get("analiza_wersja")), _txt(r.get("analiza_data")),
                _bool(r.get("zweryfikowany_przez_czlowieka")),
                _bool(r.get("uzywalny_do_uczenia")),
            )
        )
    written["szew"] = _copy(
        conn, "szew",
        [
            "szew_id", "artysta_id", "ksywa", "wydarzenie", "data_tekst", "data",
            "poz_z", "poz_do", "utwor_wychodzacy", "utwor_wchodzacy",
            "utwor_z_id", "utwor_do_id", "czas_wejscia", "czas_ms",
            "zrodlo_czasu", "zrodlo_pozycji", "status_w_lejku", "link_setu",
            "bpm_z", "bpm_do", "delta_bpm", "delta_bpm_proc",
            "tonacja_z", "tonacja_do", "zgodnosc_harmoniczna",
            "dlugosc_przejscia_s", "typ_przejscia", "bas_wstrzymany",
            "energia_z", "energia_do", "delta_energii",
            "analiza_wersja", "analiza_data",
            "zweryfikowany_przez_czlowieka", "uzywalny_do_uczenia",
        ],
        szwy,
    )
    written["_szew_porzucone_fk"] = porzucone_fk

    # --- artysta_profil ---------------------------------------------------
    by_name = _map(conn, "SELECT lower(nazwa), artysta_id FROM artysta")
    rows = _scal_profile(sheets.get("Artyści", []))
    profile: list[tuple[Any, ...]] = []
    dopasowane_profile = 0
    for r in rows:
        ksywa = _txt(r.get("ksywa sceniczna"))
        if not ksywa:
            continue
        aid = by_name.get(ksywa.lower())
        dopasowane_profile += aid is not None
        profile.append(
            (
                ksywa, aid,
                _txt(r.get("SoundCloud")), _txt(r.get("Apple Music")),
                _txt(r.get("gatunek wg Apple")), _txt(r.get("Bandcamp")),
                _txt(r.get("skąd (wg Bandcamp)")), _txt(r.get("gatunek wg Bandcamp")),
                _txt(r.get("wytwórnie (RA)")), _txt(r.get("kraj (RA)")),
                _int(r.get("obserwujących (RA)")), _int(r.get("występów w RA")),
                _txt(r.get("festiwal 2026")), _int(r.get("miksów w bazie")),
                _txt(r.get("lata w Garbiczu")), _txt(r.get("uwagi")),
                _txt(r.get("kandydaci do rozstrzygnięcia")),
            )
        )
    written["artysta_profil"] = _copy(
        conn, "artysta_profil",
        [
            "ksywa", "artysta_id", "soundcloud", "apple_music", "gatunek_apple",
            "bandcamp", "skad_bandcamp", "gatunek_bandcamp", "wytwornie_ra",
            "kraj_ra", "obserwujacych_ra", "wystepow_w_ra", "festiwal_2026",
            "miksow_w_bazie", "lata_w_garbiczu", "uwagi", "kandydaci",
        ],
        profile,
    )
    written["_profil_dopasowany_do_encji"] = dopasowane_profile

    # --- remaining source sheets -----------------------------------------
    written["dyskografia"] = _copy(
        conn, "dyskografia",
        ["ksywa", "tytul", "album", "rok", "link", "zrodlo"],
        [
            (
                _txt(r.get("ksywa")), _txt(r.get("tytuł")), _txt(r.get("album")),
                _int(r.get("rok")), _txt(r.get("link")), _txt(r.get("źródło")),
            )
            for r in sheets.get("Utwory", [])
        ],
    )

    written["miks"] = _copy(
        conn, "miks",
        [
            "ksywa", "tytul", "wydarzenie", "typ", "scena", "format", "rola",
            "czas", "data_tekst", "data", "zrodlo", "pewnosc", "dlugosc_min",
            "konto", "kto_gral_obok", "link", "opis", "youtube_id",
        ],
        [
            (
                _txt(r.get("ksywa")), _txt(r.get("tytuł")), _txt(r.get("wydarzenie")),
                _txt(r.get("typ")), _txt(r.get("scena")), _txt(r.get("format")),
                _txt(r.get("rola")), _txt(r.get("czas")),
                _txt(r.get("data")), _date(r.get("data")),
                _txt(r.get("źródło")), _txt(r.get("pewność")),
                _float(r.get("długość (min)")), _txt(r.get("konto (wrzucił)")),
                _txt(r.get("kto grał obok")), _txt(r.get("link")),
                _txt(r.get("opis od artysty")), _youtube_id(_txt(r.get("link"))),
            )
            for r in sheets.get("Miksy", [])
        ],
    )

    written["wystep"] = _copy(
        conn, "wystep",
        ["ksywa", "kiedy", "data_tekst", "data", "wydarzenie", "miejsce",
         "miasto", "kraj", "link"],
        [
            (
                _txt(r.get("ksywa")), _txt(r.get("kiedy")),
                _txt(r.get("data")), _date(r.get("data")),
                _txt(r.get("wydarzenie")), _txt(r.get("miejsce")),
                _txt(r.get("miasto")), _txt(r.get("kraj")), _txt(r.get("link")),
            )
            for r in sheets.get("Występy", [])
        ],
    )

    written["pozycja_tracklisty"] = _copy(
        conn, "pozycja_tracklisty",
        [
            "ksywa", "setname", "wydarzenie", "data_tekst", "data",
            "pewnosc_polaczenia", "pozycja", "czas", "rozpoznany",
            "wykonawca_utworu", "tytul_utworu", "wydawca", "zrodlo_pozycji",
            "link_setu",
        ],
        [
            (
                _txt(r.get("ksywa")), _txt(r.get("set")), _txt(r.get("wydarzenie")),
                _txt(r.get("data")), _date(r.get("data")),
                _txt(r.get("pewność połączenia")), _int(r.get("poz.")),
                _txt(r.get("czas")), _txt(r.get("rozpoznany")),
                _txt(r.get("wykonawca utworu")), _txt(r.get("tytuł utworu")),
                _txt(r.get("wydawca")), _txt(r.get("źródło pozycji")),
                _txt(r.get("link setu")),
            )
            for r in sheets.get("Tracklisty", [])
        ],
    )

    written["program"] = _copy(
        conn, "program",
        ["festiwal", "ksywa", "dzien", "data_tekst", "data", "scena",
         "charakter_sceny", "start", "koniec", "rola", "format"],
        [
            (
                _txt(r.get("festiwal")), _txt(r.get("ksywa")), _txt(r.get("dzień")),
                _txt(r.get("data")), _date(r.get("data")),
                _txt(r.get("scena")), _txt(r.get("charakter sceny")),
                _txt(r.get("start")), _txt(r.get("koniec")),
                _txt(r.get("rola")), _txt(r.get("format")),
            )
            for r in sheets.get("Programy", [])
        ],
    )

    written["kanon_ra"] = _copy(
        conn, "kanon_ra",
        ["kategoria", "miejsce", "kolejnosc", "ksywa", "tytul", "rok",
         "profil_ra", "soundcloud_id", "autor_tekstu", "uzasadnienie",
         "artykul_ra"],
        [
            (
                _txt(r.get("kategoria")), _txt(r.get("miejsce")),
                _int(r.get("kolejność")), _txt(r.get("ksywa")),
                _txt(r.get("tytuł")), _int(r.get("rok")),
                _txt(r.get("profil RA")), _txt(r.get("SoundCloud ID")),
                _txt(r.get("autor tekstu")), _txt(r.get("uzasadnienie redakcji")),
                _txt(r.get("artykuł RA")),
            )
            for r in sheets.get("Kanon RA", [])
        ],
    )

    written["de_school"] = _copy(
        conn, "de_school",
        ["data_tekst", "data", "dzien", "cykl", "ksywa", "scena", "typ",
         "format", "zrodlo", "pewnosc", "strona_archiwum", "link"],
        [
            (
                _txt(r.get("data")), _date(r.get("data")), _txt(r.get("dzień")),
                _txt(r.get("cykl")), _txt(r.get("ksywa")), _txt(r.get("scena")),
                _txt(r.get("typ")), _txt(r.get("format")), _txt(r.get("źródło")),
                _txt(r.get("pewność")), _txt(r.get("strona archiwum")),
                _txt(r.get("link")),
            )
            for r in sheets.get("De School", [])
        ],
    )

    conn.commit()
    return written


def _keys(conn: Any, sql: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return {row[0] for row in cur.fetchall()}


def _map(conn: Any, sql: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return {row[0]: row[1] for row in cur.fetchall()}


def _scal_profile(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge artist rows that differ only in the casing of the stage name.

    The spreadsheet contains pairs like "Catz 'n Dogz" and "Catz 'N Dogz"
    where one row holds every link and country and the other is almost empty.
    Deduplicating by keeping whichever came first silently threw away the
    populated row, so instead the rows are merged field by field: the first
    non-empty value wins, and counters keep their maximum. The spelling comes
    from whichever row carries more data, since that is the one a human filled
    in on purpose.
    """
    liczniki = {"obserwujących (RA)", "występów w RA", "miksów w bazie"}
    grupy: dict[str, list[dict[str, Any]]] = {}
    kolejnosc: list[str] = []
    for row in rows:
        ksywa = _txt(row.get("ksywa sceniczna"))
        if not ksywa:
            continue
        key = ksywa.lower()
        if key not in grupy:
            grupy[key] = []
            kolejnosc.append(key)
        grupy[key].append(row)

    out: list[dict[str, Any]] = []
    for key in kolejnosc:
        grupa = grupy[key]
        if len(grupa) == 1:
            out.append(grupa[0])
            continue
        grupa = sorted(
            grupa,
            key=lambda r: sum(1 for v in r.values() if _txt(v) is not None),
            reverse=True,
        )
        scalony: dict[str, Any] = dict(grupa[0])
        for other in grupa[1:]:
            for column, value in other.items():
                if column in liczniki:
                    a, b = _int(scalony.get(column)), _int(value)
                    if b is not None and (a is None or b > a):
                        scalony[column] = b
                elif _txt(scalony.get(column)) is None and _txt(value) is not None:
                    scalony[column] = value
        out.append(scalony)
    return out

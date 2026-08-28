"""Import our own measurements: playlists, paper ratings, MIDI registries,
Rekordbox recordings.

These tables are small but carry the highest value per row — they are the only
place where a human judgement, a recorded performance and a machine score can
sit next to each other. Blank ratings are imported deliberately: the 158 pairs
exist as rows waiting for their number, so coverage can be reported honestly
as "0 of 158 filled" rather than as an empty table that looks like nothing was
ever planned.

``PRZYDZIAL_NIE_OTWIERAC.json`` is never read. It stays sealed until every
rating is in, and the importer must not be the thing that breaks that seal.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

OCENY_DIR = Path("experiments_priv/2026-08-17_ocena_papierowa")
REJESTRY_DIR = Path("experiments_priv/2026-08-24_rejestry_konsoli")
NAGRANIA_DIR = Path.home() / "Music/rekordbox/Recording"

SEALED = "PRZYDZIAL_NIE_OTWIERAC.json"

_STAMP = re.compile(r"rejestr_(\d{8})_(\d{6})_(.+)\.jsonl$")


def _sha256(path: Path, *, limit: int | None = None) -> str:
    """Checksum a file; ``limit`` caps the bytes read for very large audio."""
    digest = hashlib.sha256()
    read = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            read += len(chunk)
            if limit is not None and read >= limit:
                break
    return digest.hexdigest()


def _playlisty(conn: Any, directory: Path) -> dict[str, int]:
    source = directory / "playlisty_dane.json"
    if not source.exists():
        return {"playlista": 0, "pozycja_playlisty": 0}
    data = json.loads(source.read_text(encoding="utf-8"))

    listy = pozycje = 0
    with conn.cursor() as cur:
        cur.execute("TRUNCATE playlista, pozycja_playlisty RESTART IDENTITY CASCADE")
        for nazwa, tracks in data.items():
            cur.execute(
                "INSERT INTO playlista (nazwa, rodzaj, uwagi) VALUES (%s, %s, %s)"
                " RETURNING playlista_id",
                (nazwa, "ocena_papierowa", f"{len(tracks)} utworow"),
            )
            playlista_id = cur.fetchone()[0]
            listy += 1
            for index, track in enumerate(tracks, start=1):
                # track_id is only linked when the analysis actually exists;
                # the FK would otherwise reject the whole playlist.
                cur.execute(
                    "INSERT INTO pozycja_playlisty"
                    " (playlista_id, pozycja, wykonawca, tytul, track_id)"
                    " VALUES (%s, %s, %s, %s,"
                    "         (SELECT track_id FROM analiza WHERE track_id = %s))",
                    (
                        playlista_id,
                        index,
                        (track.get("artysta") or None),
                        track.get("tytul"),
                        track.get("track_id"),
                    ),
                )
                pozycje += 1
    conn.commit()
    return {"playlista": listy, "pozycja_playlisty": pozycje}


def _oceny(conn: Any, directory: Path) -> dict[str, int]:
    files = sorted(directory.glob("SESJA_*_transition_ratings.csv"))
    wpisane = puste = 0
    with conn.cursor() as cur:
        cur.execute("TRUNCATE ocena RESTART IDENTITY")
        for path in files:
            sesja = path.stem.split("_")[1]
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    raw = (row.get("dj_mixability_rating") or "").strip()
                    try:
                        rating = int(float(raw)) if raw else None
                    except ValueError:
                        rating = None
                    if rating is not None and not 1 <= rating <= 5:
                        rating = None
                    wpisane += rating is not None
                    puste += rating is None
                    engine = (row.get("engine_score") or "").strip()
                    blind = (row.get("blind") or "").strip().lower()
                    cur.execute(
                        "INSERT INTO ocena (pair_id, track_id_a, track_id_b,"
                        " engine_score, slepa, sesja_papier, ocena, komentarz,"
                        " oceniajacy)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        " ON CONFLICT (pair_id) DO NOTHING",
                        (
                            row.get("pair_id"),
                            row.get("track_id_a"),
                            row.get("track_id_b"),
                            float(engine) if engine else None,
                            blind == "true" if blind else None,
                            sesja,
                            rating,
                            (row.get("comment") or "").strip() or None,
                            "Janek",
                        ),
                    )
    conn.commit()
    return {"ocena": wpisane + puste, "_ocen_wpisanych": wpisane, "_ocen_pustych": puste}


def _rejestry(conn: Any, directory: Path) -> dict[str, int]:
    files = sorted(directory.glob("rejestr_*.jsonl"))
    sesje = rejestry = 0
    with conn.cursor() as cur:
        cur.execute("TRUNCATE sesja, rejestr, nagranie RESTART IDENTITY CASCADE")
        for path in files:
            stamp = _STAMP.search(path.name)
            data = nazwa = None
            if stamp:
                data = dt.datetime.strptime(stamp.group(1), "%Y%m%d").date()
                nazwa = stamp.group(3)

            zdarzen = 0
            pozycje_startowe = False
            pierwszy = ostatni = None
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("typ") == "stan_poczatkowy":
                        pozycje_startowe = True
                        continue
                    zdarzen += 1
                    czas = record.get("t")
                    if isinstance(czas, (int, float)):
                        if pierwszy is None:
                            pierwszy = czas
                        ostatni = czas

            dlugosc = (
                (ostatni - pierwszy)
                if pierwszy is not None and ostatni is not None
                else None
            )
            cur.execute(
                "INSERT INTO sesja (nazwa, data, sprzet, pozycje_startowe)"
                " VALUES (%s, %s, %s, %s) RETURNING sesja_id",
                (nazwa or path.stem, data, "DDJ-FLX4", pozycje_startowe),
            )
            sesja_id = cur.fetchone()[0]
            sesje += 1
            cur.execute(
                "INSERT INTO rejestr (sesja_id, sciezka, suma_kontrolna, zdarzen,"
                " dlugosc_s) VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (sciezka) DO NOTHING",
                (sesja_id, str(path), _sha256(path), zdarzen, dlugosc),
            )
            rejestry += 1
    conn.commit()
    return {"sesja": sesje, "rejestr": rejestry}


# Which recording belongs to which session — confirmed by Janek 28.08, not
# guessed. "Test 1" matches its registry by name, date and hour. The other two
# predate the recorder entirely: they are sets we have audio and cue points for
# but no hand movements, and they get a session of their own so the cue files
# stay reachable.
POWIAZANIA = {
    "Test 1/01 Test 1.wav": "test_1",
}
SESJE_BEZ_REJESTRU = {
    "Unknown Album/01 Premier.wav": ("Premier", "2026-02-25"),
    "Spring/01 Open Deck.wav": ("Open Deck", "2026-05-27"),
}


def _nagrania(conn: Any, directory: Path) -> dict[str, int]:
    """Index Rekordbox recordings and tie them to sessions where we know the tie.

    Only the header is checksummed: these are multi-gigabyte WAVs and a full
    hash would dominate the import.
    """
    if not directory.exists():
        return {"nagranie": 0}
    count = powiazane = bez_rejestru = 0
    with conn.cursor() as cur:
        for wav in sorted(directory.rglob("*.wav")):
            cue = wav.with_suffix(".cue")
            koncowka = f"{wav.parent.name}/{wav.name}"
            sesja_id = None

            if koncowka in POWIAZANIA:
                cur.execute("SELECT sesja_id FROM sesja WHERE nazwa = %s",
                            (POWIAZANIA[koncowka],))
                wiersz = cur.fetchone()
                if wiersz:
                    sesja_id = wiersz[0]
                    powiazane += 1
            elif koncowka in SESJE_BEZ_REJESTRU:
                nazwa, data = SESJE_BEZ_REJESTRU[koncowka]
                cur.execute(
                    "INSERT INTO sesja (nazwa, data, sprzet, pozycje_startowe,"
                    " uwagi) VALUES (%s, %s, %s, false, %s) RETURNING sesja_id",
                    (nazwa, data, "DDJ-FLX4",
                     "set sprzed rejestratora — jest audio i cue, brak ruchów rąk"),
                )
                sesja_id = cur.fetchone()[0]
                bez_rejestru += 1

            cur.execute(
                "INSERT INTO nagranie (sesja_id, sciezka_wav, sciezka_cue)"
                " VALUES (%s, %s, %s)",
                (sesja_id, str(wav), str(cue) if cue.exists() else None),
            )
            count += 1
    conn.commit()
    return {"nagranie": count, "_nagran_powiazanych": powiazane,
            "_sesji_bez_rejestru": bez_rejestru}


def run(
    conn: Any,
    *,
    oceny_dir: Path | None = None,
    rejestry_dir: Path | None = None,
    nagrania_dir: Path | None = None,
) -> dict[str, int]:
    """Import every measurement source. Returns rows written per table."""
    oceny_path = Path(oceny_dir or OCENY_DIR)
    result: dict[str, int] = {}
    result |= _playlisty(conn, oceny_path)
    result |= _oceny(conn, oceny_path)
    result |= _rejestry(conn, Path(rejestry_dir or REJESTRY_DIR))
    result |= _nagrania(conn, Path(nagrania_dir or NAGRANIA_DIR))
    return result

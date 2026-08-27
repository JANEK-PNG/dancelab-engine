"""Tests for the identity catalog.

The pure helpers are tested without a server so they run in ordinary CI. The
integration test needs PostgreSQL and creates its **own** database: it must
never touch the working catalog, because dropping the schema there would throw
away an import the user is relying on.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pytest

from dancelab.catalog import dopasuj, import_analiz, import_mapa

TEST_DB = "dancelab_test"


# ----------------------------------------------------------------- pure bits


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Four Tet - Baby (Original Mix)", "four tet baby"),
        ("Jamie xx feat. Oona Doherty - Falling", "jamie xx"),
        ("  Cliff  ", "cliff"),
        ("CATZ 'N DOGZ", "catz n dogz"),
        ("", ""),
        (None, ""),
    ],
)
def test_norm(raw, expected):
    assert dopasuj.norm(raw) == expected


def test_norm_matches_playlist_loader():
    """The normaliser must stay identical to the one measured on 7086 entries.

    A drift here would silently change every coverage number in the reports,
    so the two implementations are compared directly rather than trusted.
    """
    source = Path("experiments_priv/2026-08-17_playlisty_dancelab/wgraj_playlisty.py")
    if not source.exists():
        pytest.skip("brak skryptu playlist")
    namespace: dict = {}
    body = source.read_text(encoding="utf-8")
    start = body.index("def norm(")
    end = body.index("\ndef ", start + 1)
    exec("import re\nimport unicodedata as U\n" + body[start:end], namespace)  # noqa: S102
    original = namespace["norm"]
    for sample in [
        "Overmono - So U Kno",
        "Peggy Gou (feat. Lenny Kravitz) - I Believe [Extended]",
        "Åre & Ćma - Zażółć",
        "DJ Koze feat. Róisín Murphy - Illumination",
    ]:
        assert dopasuj.norm(sample) == original(sample)


def test_klucz_wymaga_obu_stron():
    """A join key with a missing artist or title must be empty, not partial."""
    assert dopasuj._klucz("Four Tet", "Baby")
    assert dopasuj._klucz("", "Baby") == ""
    assert dopasuj._klucz("Four Tet", None) == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), ("", None), ("tak", True), ("NIE", False), (True, True),
     ("cokolwiek", None)],
)
def test_bool(raw, expected):
    assert import_mapa._bool(raw) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-07-31", dt.date(2026, 7, 31)),
        ("31.07.2026", dt.date(2026, 7, 31)),
        (dt.datetime(2026, 7, 31, 22, 0), dt.date(2026, 7, 31)),
        # A bare year must NOT become 1 January: inventing a day would put a
        # false date into a table people read as fact.
        ("2026", None),
        ("kiedyś latem", None),
    ],
)
def test_date(raw, expected):
    assert import_mapa._date(raw) == expected


def test_youtube_id():
    assert import_mapa._youtube_id("https://www.youtube.com/watch?v=PMWXh8DCm8Q") == "PMWXh8DCm8Q"
    assert import_mapa._youtube_id("https://youtu.be/PMWXh8DCm8Q?t=30") == "PMWXh8DCm8Q"
    assert import_mapa._youtube_id("https://soundcloud.com/foo/bar") is None
    assert import_mapa._youtube_id(None) is None


def test_klasyfikacja_zrodla_domyslnie_restrykcyjna():
    """An unrecognised path must be filed as the local library.

    The 11.08 rule limits measurements to the DJ map. A default that guessed
    "corpus" would let unknown material leak into an argument, so the
    permissive answer requires an explicit corpus marker.
    """
    assert import_analiz._classify("/Volumes/X/DanceLabCorpus/a.wav") == "korpus"
    assert import_analiz._classify("/Users/jantrybus/Music/a.aiff") == "biblioteka_lokalna"
    assert import_analiz._classify("cokolwiek/innego.mp3") == "biblioteka_lokalna"
    assert import_analiz._classify(None) == "nieznane"


def test_scal_profile_wybiera_bogatszy_wiersz():
    """Case-variant duplicates merge instead of the first one winning."""
    rows = [
        {"ksywa sceniczna": "CATZ 'N DOGZ", "kraj (RA)": None, "miksów w bazie": 1},
        {"ksywa sceniczna": "Catz 'n Dogz", "kraj (RA)": "Poland",
         "miksów w bazie": 19, "Bandcamp": "https://x"},
    ]
    merged = import_mapa._scal_profile(rows)
    assert len(merged) == 1
    assert merged[0]["kraj (RA)"] == "Poland"
    assert merged[0]["Bandcamp"] == "https://x"
    assert merged[0]["miksów w bazie"] == 19  # counter keeps its maximum


def test_extract_header_reads_only_the_prefix(tmp_path: Path):
    """The header parser must not need the megabytes of frames behind it."""
    payload = {
        "schema_version": "1.0.0",
        "engine_version": "0.1.1",
        "track": {"track_id": "rb1", "title": "A {brace} in the title",
                  "bpm_estimate": 123.0},
        "beatgrid": list(range(50000)),
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    head = import_analiz._extract_header(path)
    assert head["track"]["track_id"] == "rb1"
    assert head["track"]["title"] == "A {brace} in the title"
    assert head["engine_version"] == "0.1.1"


# ---------------------------------------------------------------- integration


def _test_url() -> str | None:
    base = os.environ.get("DANCELAB_DB_URL")
    if not base:
        return None
    head, _, name = base.rpartition("/")
    if name == TEST_DB:
        return base
    return f"{head}/{TEST_DB}"


@pytest.fixture
def test_conn():
    """A connection to a throwaway database, never the working catalog."""
    psycopg = pytest.importorskip("psycopg")
    url = _test_url() or f"postgresql://dancelab:dancelab@127.0.0.1:5432/{TEST_DB}"
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin, admin.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
            cur.execute(f"CREATE DATABASE {TEST_DB}")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL niedostępny")

    from dancelab.catalog.db import connect

    with connect(url) as conn:
        yield conn


def test_schemat_i_idempotencja(test_conn):
    """Schema applies once, and re-importing twice leaves the same state."""
    from dancelab.catalog import schema
    from dancelab.catalog.db import table_counts

    assert schema.apply(test_conn) == [1, 2, 3]
    assert schema.apply(test_conn) == []
    assert schema.current_version(test_conn) == 3

    xlsx = Path(import_mapa.DEFAULT_XLSX)
    if not xlsx.exists():
        pytest.skip("brak arkusza mapy DJ-ów")

    first = import_mapa.run(test_conn, xlsx)
    counts_first = table_counts(test_conn)
    second = import_mapa.run(test_conn, xlsx)
    assert first == second
    assert table_counts(test_conn) == counts_first

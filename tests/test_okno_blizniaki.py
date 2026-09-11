"""The window's library list merges twins the way the terminal does.

Same track in several folders, or a file and its Apple Music stream: one row
with a copy count. Grouping is the terminal's (tui/duplikaty): artist+title
OR the Apple catalog id (stream path, ISRC bridge for files). Filters run
first, the full list and track_id lookups stay untouched.
"""

from __future__ import annotations

import pytest

from dancelab.gui.most import Most


def _w(tid, tytul, sciezka, wykonawca="X", grywalny=None):
    if grywalny is None:
        grywalny = not sciezka.startswith("apple-music:")
    return {"track_id": tid, "tytul": tytul, "wykonawca": wykonawca, "sciezka": sciezka,
            "bpm": 124.0, "grywalny": grywalny}


@pytest.fixture
def most(tmp_path, monkeypatch):
    from dancelab.tui import zrodlo as Z
    monkeypatch.setattr(Z, "zrodlo", lambda p: "apple" if str(p).startswith("apple") else "dysk")
    m = Most(katalog=str(tmp_path))
    m._most_isrc_mapa = {}
    monkeypatch.setattr(m, "biblioteka", lambda limit=400: {"utwory": [], "wszystkich": 0})
    monkeypatch.setattr(m, "ulubione", lambda: {"ulubione": []})
    monkeypatch.setattr(m, "filary", lambda: {"filary": []})
    return m


def ids(odp):
    return [(u["track_id"], u["kopii"]) for u in odp["utwory"]]


def test_same_title_in_folders_and_as_a_stream_is_one_row_the_file_wins(most):
    most._spis = [_w("s", "Pearl's Girl", "apple-music:tracks:9"),
                  _w("f1", "Pearl's Girl", "/m/a/pearl.aiff"),
                  _w("f2", "Pearl's Girl (Original Mix)", "/m/b/pearl.aiff"),
                  _w("o", "Other", "/m/o.aiff")]
    odp = most.szukaj()
    assert ids(odp) == [("f1", 3), ("o", 1)]
    assert (odp["znalezione"], odp["wszystkich"], odp["wpisow"], odp["scalono"]) == (2, 2, 4, 2)


def test_bridge_identity_merges_a_differently_titled_file_and_stream(most):
    most._spis = [_w("s", "Sex Life", "apple-music:tracks:42", wykonawca="Tracey"),
                  _w("f", "Sex Life (feat. Riko Dan)", "/m/sex.aiff", wykonawca="Riko Dan, Tracey")]
    assert [u for u, _ in ids(most.szukaj())] == ["s", "f"], "titles differ: two rows without the bridge"
    most._most_isrc_mapa = {"/m/sex.aiff": {"catalog_id": "42"}}
    most._spis = list(most._spis)                   # new list → groups recomputed
    assert ids(most.szukaj()) == [("f", 2)]


def test_a_favourite_or_pillar_copy_is_the_one_shown(most, monkeypatch):
    most._spis = [_w("f", "Track", "/m/t.aiff"), _w("s", "Track", "apple-music:tracks:1")]
    monkeypatch.setattr(most, "ulubione", lambda: {"ulubione": ["s"]})
    (u,) = most.szukaj()["utwory"]
    assert (u["track_id"], u["ulubiony"], u["kopii"]) == ("s", True, 2)


def test_filters_run_before_merging(most):
    most._spis = [_w("f", "Track", "/m/t.aiff"), _w("s", "Track", "apple-music:tracks:1")]
    assert ids(most.szukaj(sekcja="apple")) == [("s", 1)]
    assert ids(most.szukaj(sekcja="dysk")) == [("f", 1)]


def test_the_full_list_and_track_lookups_are_untouched(most):
    most._spis = [_w("f", "Track", "/m/t.aiff"), _w("s", "Track", "apple-music:tracks:1")]
    most.szukaj()
    assert [u["track_id"] for u in most._spis] == ["f", "s"]
    assert most._wpis_spisu("s")["track_id"] == "s"


def test_stems_of_different_tracks_stay_separate_rows(most):
    """Measured 11.09: `vocals.wav` of three different tracks merged by title alone."""
    most._spis = [dict(_w("a", "vocals", "/stems/bodhi/vocals.wav", wykonawca=""), dlugosc_sec=289.0),
                  dict(_w("b", "vocals", "/stems/airod/vocals.wav", wykonawca=""), dlugosc_sec=314.0),
                  dict(_w("c", "vocals", "/stems_smoke/airod/vocals.wav", wykonawca=""), dlugosc_sec=314.1)]
    assert ids(most.szukaj()) == [("a", 1), ("b", 2)]

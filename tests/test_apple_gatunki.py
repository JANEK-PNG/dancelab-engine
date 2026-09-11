"""Apple genres feed `style_label` last, never overwrite, and refuse umbrellas.

Why the umbrella rule exists: `_style_fit` scores a non-matching label 0.35
and a missing one 0.5, so stamping "Electronic" on a stream would rank it
below a track with no genre at all — with higher confidence. Measured on the
owner's library 2026-09-10: Electronic + Dance = 56 % of 10 286 songs.
"""

from __future__ import annotations

import json

from dancelab.ingestion.analysis_enrichment import (
    attach_apple_genres, attach_rekordbox_genres, load_apple_genre_map,
)


def _a(path, style=None, source=None):
    class T:
        source_path = path
        style_label = style
        style_label_source = source

    class A:
        track = T()
    return A()


MAPA = {"apple-music:tracks:1": "Techno", "apple-music:tracks:2": "Electronic",
        "apple-music:tracks:3": "Dance", "apple-music:tracks:4": "Afro House"}


def test_apple_uzupelnia_tylko_luki_i_znaczy_pochodzenie():
    a = _a("apple-music:tracks:1")
    b = _a("apple-music:tracks:4", style="Breaks")          # tag pliku — nietykalny
    c = _a("apple-music:tracks:9")                           # brak w bibliotece
    rep = attach_apple_genres([a, b, c], genre_map=MAPA)
    assert (a.track.style_label, a.track.style_label_source) == ("Techno", "apple")
    assert (b.track.style_label, b.track.style_label_source) == ("Breaks", "file_tag")
    assert c.track.style_label is None
    assert rep.attached == 1 and rep.missing == 1


def test_parasol_zostaje_brakiem_i_jest_nazwany_w_notce():
    a, b = _a("apple-music:tracks:2"), _a("apple-music:tracks:3")
    rep = attach_apple_genres([a, b], genre_map=MAPA)
    assert a.track.style_label is None and b.track.style_label is None
    assert rep.attached == 0 and rep.missing == 2
    assert any("parasol" in n for n in rep.notes)


def test_rekordbox_wygrywa_z_apple_i_znaczy_pochodzenie():
    a = _a("/m/x.mp3")
    attach_rekordbox_genres([a], genre_map={"/m/x.mp3": "UK Garage / Bassline"})
    attach_apple_genres([a], genre_map={"/m/x.mp3": "Techno"})
    assert a.track.style_label == "UK Garage / Bassline"
    assert a.track.style_label_source == "rekordbox"


def test_mapa_z_biblioteki_bierze_pierwszy_gatunek_po_id_katalogu(tmp_path):
    lib = {"songs": [
        {"id": "l1", "attributes": {"playParams": {"catalogId": "77"}, "genreNames": ["Garage", "Dance"]}},
        {"id": "l2", "attributes": {"genreNames": ["Rock"]}},                       # upload bez id
        {"id": "l3", "attributes": {"playParams": {"catalogId": "78"}}},           # bez gatunku
    ]}
    p = tmp_path / "apple_library.json"
    p.write_text(json.dumps(lib))
    mapa, note = load_apple_genre_map(p)
    assert mapa == {"apple-music:tracks:77": "Garage"}
    assert "1 utworów" in note


def test_brak_biblioteki_to_notka_nie_wyjatek(tmp_path):
    mapa, note = load_apple_genre_map(tmp_path / "nie_ma.json")
    assert mapa == {} and "apple_music_biblioteka.py" in note

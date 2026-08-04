"""Struktura utworu z Rekordboxa — słowniki, granice, i odmowa przy niepewności.

Największy brak silnika (03.08: 1881 segmentów, wszystkie bez etykiety) zamknięty
nie modelem, tylko odczytem analizy, którą Rekordbox już policzył. Te testy
pilnują, że nie zaczniemy przy okazji zgadywać.
"""

from __future__ import annotations

import pathlib

import pytest

from dancelab.ingestion.rekordbox_phrases import (
    BANKS,
    CLUB,
    SHARE,
    SONG,
    Phrase,
    PhraseAnalysis,
    read_phrases,
)


def _p(i, kind, label, a, b):
    return Phrase(index=i, kind=kind, label=label, start_beat=a * 4,
                  start_sec=float(a), end_beat=b * 4, end_sec=float(b),
                  has_fill=False, fill_start_beat=None)


def test_slowniki_odczytane_ze_zrzutow_janka():
    """Mapowanie ma pochodzić z porównania z ekranem, nie z domysłu.
    Gdyby ktoś je kiedyś 'poprawił', ten test ma zapiszczeć."""
    assert CLUB[1] == "INTRO" and CLUB[2] == "UP" and CLUB[3] == "DOWN"
    assert CLUB[5] == "CHORUS" and CLUB[6] == "OUTRO"
    assert SONG[1] == "INTRO" and SONG[8] == "BRIDGE" and SONG[9] == "CHORUS"
    assert SONG[10] == "OUTRO" and SONG[2] == "VERSE1"


def test_mood_3_nie_dostaje_etykiet():
    """Sister i Nature Boy (mood=3) mają słownik piosenkowy, ale INNĄ numerację
    niż mood=2. Zgadnięcie byłoby liczbą wyglądającą na zmierzoną (ADR-005)."""
    assert 3 not in BANKS, "mood 3 nie jest potwierdzony — nie wolno go mapować"


def test_znajduje_fraze_po_czasie_i_etykiecie():
    an = PhraseAnalysis(mood=1, bank=0, end_beat=400, phrases=[
        _p(1, 1, "INTRO", 0, 10), _p(2, 2, "UP", 10, 30),
        _p(3, 5, "CHORUS", 30, 60), _p(4, 6, "OUTRO", 60, 90)])
    assert an.at(5.0).label == "INTRO"
    assert an.at(45.0).label == "CHORUS"
    assert an.at(1000.0) is None, "poza utworem = nie wiem"
    assert an.intro.start_sec == 0.0
    assert an.outro.start_sec == 60.0
    assert [p.label for p in an.of_label("UP", "CHORUS")] == ["UP", "CHORUS"]


def test_brak_outro_to_none_a_nie_ostatnia_fraza():
    """Nie każdy utwór ma outro. Podstawienie ostatniej frazy byłoby zmyśleniem."""
    an = PhraseAnalysis(mood=1, bank=0, end_beat=200, phrases=[
        _p(1, 1, "INTRO", 0, 10), _p(2, 2, "UP", 10, 40)])
    assert an.outro is None


def test_brak_pliku_to_powod_nie_wyjatek():
    an, why = read_phrases(pathlib.Path("/nie/ma/takiego/ANLZ0000.EXT"))
    assert an is None and "brak pliku" in why


@pytest.mark.skipif(not SHARE.exists(), reason="brak analizy Rekordboxa na tej maszynie")
def test_na_prawdziwym_pliku_daje_sekundy_i_etykiety():
    exts = sorted(SHARE.rglob("ANLZ*.EXT"))
    if not exts:
        pytest.skip("brak plików ANLZ")
    for f in exts[:25]:
        an, why = read_phrases(f, f.with_suffix(".DAT"))
        if an is None or an.mood not in BANKS or not an.phrases:
            continue
        assert an.phrases[0].start_beat == 1, "pierwsza fraza zaczyna się na bicie 1"
        assert any(p.label for p in an.phrases), "żadna fraza nie dostała etykiety"
        assert any(p.start_sec is not None for p in an.phrases), "brak przeliczenia na sekundy"
        assert an.source == "rekordbox_phrase", "źródło musi być opisane jako cudze"
        return
    pytest.skip("w próbce nie było utworu z potwierdzonym słownikiem")

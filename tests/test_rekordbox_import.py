"""Import analiz Rekordboxa dla utworów BEZ pliku na dysku.

Zmierzone 09.08: 1571 z 1880 pozycji kolekcji Janka to strumienie Apple Music
bez pliku, więc silnik pracował na 256 utworach zamiast ~1900. Rekordbox ma
dla nich komplet — te testy pilnują, żeby import go przenosił WIERNIE i żeby
nigdzie nie udawał, że mamy audio.
"""

import pathlib

import pytest

from dancelab.core.models import BeatGrid, FeatureFrame, SegmentType
from dancelab.ingestion import rekordbox_import as RI


def test_typ_frazy_z_energii_a_nie_z_nazw_pioneera():
    """Nazewnictwa faz Pioneera NIE zgadujemy — typ nadaje nasza reguła na
    zmierzonej energii, a przy braku rozstrzygnięcia mówimy `unknown`."""
    assert RI._typ_frazy(0.5, 0.5, True, False) is SegmentType.intro
    assert RI._typ_frazy(0.5, 0.5, False, True) is SegmentType.outro
    assert RI._typ_frazy(0.9, 0.5, False, False) is SegmentType.groove
    assert RI._typ_frazy(0.2, 0.5, False, False) is SegmentType.breakdown
    assert RI._typ_frazy(0.45, 0.5, False, False) is SegmentType.unknown, \
        "strefa niepewna ma zostać nienazwana"
    assert RI._typ_frazy(0.5, 0.0, False, False) is SegmentType.unknown, \
        "bez energii nie ma podstaw do nazwania sekcji"


def test_segmenty_biora_granice_z_fraz_i_typ_z_energii(monkeypatch, tmp_path):
    """Granice są Pioneera (numery bitów), typy nasze."""
    class _Wpis:
        def __init__(self, beat):
            self.beat = beat

    class _Tag:
        def __init__(self, wpisy):
            self.content = type("C", (), {"entries": wpisy})()

    class _Plik:
        def __init__(self, wpisy):
            self._t = [_Tag(wpisy)]

        def getall_tags(self, nazwa):
            return self._t if nazwa == "PSSI" else []

    wpisy = [_Wpis(1), _Wpis(17), _Wpis(33)]     # bity 1, 17, 33
    monkeypatch.setattr(RI, "_nfc", RI._nfc)     # bez zmian, dla czytelności
    import pyrekordbox.anlz as anlz
    monkeypatch.setattr(anlz.AnlzFile, "parse_file",
                        staticmethod(lambda *_a, **_k: _Plik(wpisy)))

    plik = tmp_path / "ANLZ0000.EXT"
    plik.write_bytes(b"x")
    siatka = BeatGrid(bpm=120.0, reliable=True,
                      beat_times_sec=[i * 0.5 for i in range(64)])
    klatki = [FeatureFrame(track_id="t", timestamp_sec=float(s),
                           rms=0.2 if s < 8 else 0.9) for s in range(20)]

    segmenty = RI.segmenty_z_anlz(plik, siatka, "t", 20.0, klatki)
    assert [round(s.start_sec, 2) for s in segmenty] == [0.0, 8.0, 16.0]
    assert segmenty[0].segment_type is SegmentType.intro
    assert segmenty[-1].segment_type is SegmentType.outro


def test_wysokosc_slupka_to_dolne_piec_bitow(monkeypatch, tmp_path):
    """Bajt fali pakuje wysokość (5 bitów) i barwę (3 bity) — bierzemy
    wysokość. Bez maski energia utworu wyszłaby z barwy, nie z głośności."""
    class _Tag:
        content = type("C", (), {"entries": [0xFF, 0xE0, 0x1F]})()

    class _Plik:
        def getall_tags(self, nazwa):
            return [_Tag()] if nazwa == "PWV3" else []

    import pyrekordbox.anlz as anlz
    monkeypatch.setattr(anlz.AnlzFile, "parse_file",
                        staticmethod(lambda *_a, **_k: _Plik()))
    plik = tmp_path / "ANLZ0000.EXT"
    plik.write_bytes(b"x")

    klatki = RI.klatki_z_anlz(plik, "t", 1.0)
    assert len(klatki) == 1
    # 0xFF→31, 0xE0→0, 0x1F→31  ⇒ średnia (31+0+31)/3 / 31
    assert klatki[0].rms == pytest.approx((31 + 0 + 31) / 3 / 31, abs=1e-4)


def test_utwor_bez_pliku_zostaje_w_puli_ale_nie_da_sie_go_zagrac():
    """Dwie strony tej samej decyzji: strumień ma prawo być w puli (ma tempo,
    siatkę, energię i sekcje), ale odsłuch musi odmówić z powodem."""
    import asyncio

    from dancelab.core.models import AnalysisResult, Track
    from dancelab.tui.app import DanceLabTUI

    strumien = AnalysisResult(
        engine_version=RI.WERSJA,
        track=Track(track_id="rb1", title="Ze strumienia",
                    source_path="apple-music:tracks:123", duration_sec=200.0,
                    bpm_estimate=128.0))
    plikowy = AnalysisResult(
        engine_version="0.1.1",
        track=Track(track_id="f1", title="Z dysku",
                    source_path="/m/a.wav", duration_sec=200.0,
                    bpm_estimate=128.0))

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._bez_pliku(strumien.track), "strumień = odmowa odsłuchu"
            assert app._bez_pliku(plikowy.track) is None, \
                "utwór z dysku gra normalnie"
            powod = app._bez_pliku(strumien.track)
            assert "Rekordboks" in powod, "powód ma mówić, GDZIE to zagrać"

    asyncio.run(go())


@pytest.mark.skipif(not (pathlib.Path.home() / "Library/Pioneer/rekordbox"
                         / "master.db").exists(),
                    reason="brak lokalnej bazy Rekordboxa")
def test_import_na_zywej_kolekcji_daje_komplet():
    """Na prawdziwej bazie: każdy zaimportowany utwór ma tempo, siatkę
    z FAZĄ TAKTU i energię — inaczej nie ma po co go wstawiać do puli."""
    analizy, _ = RI.importuj(limit=12)
    assert analizy, "kolekcja bez utworów do zaimportowania"
    for a in analizy:
        assert a.engine_version == RI.WERSJA, "źródło ma być jawne"
        assert a.track.bpm_estimate and a.track.bpm_estimate > 0
        assert a.beatgrid and a.beatgrid.beat_times_sec
        assert a.beatgrid.downbeat_phase_verified, \
            "Pioneer numeruje bity w takcie — faza taktu jest znana"
        assert a.features, "bez energii utwór nie wejdzie w łuk setu"

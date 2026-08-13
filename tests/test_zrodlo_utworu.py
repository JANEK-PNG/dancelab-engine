"""Skąd bierze się utwór — Apple Music, dysk, czy nie ma go wcale."""

from dancelab.tui.zrodlo import APPLE, BRAK, DYSK, ikona, opis, zrodlo


def test_apple_music_poznajemy_po_sciezce_nie_po_tym_ze_pliku_brak():
    assert zrodlo("apple-music:tracks:1576510482") == APPLE
    assert opis("apple-music:tracks:1") == "Apple Music"


def test_plik_ktory_istnieje_to_dysk(tmp_path):
    p = tmp_path / "utwor.wav"
    p.write_bytes(b"RIFF")
    assert zrodlo(str(p)) == DYSK
    assert ikona(str(p)) == "▣"


def test_odpiety_dysk_to_NIE_jest_apple_music():
    # 65 utworów w bibliotece Janka leży na /Volumes/ANTYWIRUS. Gdy dysk jest
    # odpięty, pliku nie ma — ale to wciąż jego pliki, nie streaming. Mylenie
    # tych dwóch rzeczy to fałszywa informacja pokazana przed setem.
    assert zrodlo("/Volumes/ANTYWIRUS/kurs dj/01 - Call Me Babe.flac") == BRAK
    assert opis("/Volumes/ANTYWIRUS/x.flac") == "Niedostępne"


def test_brak_sciezki_to_brak_a_nie_wyjatek():
    assert zrodlo(None) == BRAK
    assert zrodlo("") == BRAK


def test_ikony_sa_jednokolumnowe():
    # emoji w wielu terminalach zajmuje dwie kolumny i rozjeżdża tabelę
    for tekst in ("apple-music:tracks:1", "/nie/ma/pliku.wav"):
        assert len(ikona(tekst)) == 1

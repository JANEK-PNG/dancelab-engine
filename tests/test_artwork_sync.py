"""Synchronizacja okładek — dopasowanie, osadzanie, raport.

Reguły: okładka wchodzi TYLKO przy pewnym dopasowaniu (niejednoznaczność =
pominięcie z imiennym powodem), zapis weryfikowany odczytem, mtime pliku
zachowany, raport dzieli losy plików na kategorie. Sieć i pliki przez
atrapy tam, gdzie się da; osadzanie na PRAWDZIWYM pliku tymczasowym.
"""

from __future__ import annotations

import io
import json
import os
import wave

import dancelab.ingestion.artwork_sync as sync
from dancelab.ingestion.artwork_sync import (osadz_okladke, szukaj_okladki,
                                             synchronizuj)


def _itunes(wyniki):
    return lambda url: json.dumps({"results": wyniki}).encode() \
        if "itunes.apple.com" in url else b"OBRAZEK"


def test_szukaj_pewne_dopasowanie_i_wysoka_rozdzielczosc():
    http = _itunes([{"artistName": "Bicep", "trackName": "Glue",
                     "artworkUrl100": "https://x/100x100bb.jpg"}])
    url, powod = szukaj_okladki("Bicep", "Glue (Original Mix)", http=http)
    assert url == "https://x/600x600bb.jpg" and powod == "dopasowane"


def test_szukaj_niejednoznaczne_pomija_z_powodem():
    http = _itunes([{"artistName": "Ktos Inny", "trackName": "Glue",
                     "artworkUrl100": "https://x/100x100bb.jpg"}])
    url, powod = szukaj_okladki("Bicep", "Glue", http=http)
    assert url is None and "niejednoznaczne" in powod
    url, powod = szukaj_okladki("Bicep", "Glue", http=_itunes([]))
    assert url is None and "nie znaleziono" in powod


def test_osadzanie_weryfikacja_i_mtime(tmp_path):
    """Prawdziwy WAV: okładka wchodzi w ID3, odczyt ją widzi, mtime bez zmian."""
    from PIL import Image
    plik = tmp_path / "utwor.wav"
    with wave.open(str(plik), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), (9, 9, 200)).save(buf, format="JPEG")
    mtime_przed = os.stat(plik).st_mtime_ns

    blad = osadz_okladke(str(plik), buf.getvalue())
    assert blad is None
    from dancelab.tui.okladki import _bajty_okladki
    assert _bajty_okladki(str(plik)), "weryfikacja odczytem widzi okładkę"
    assert os.stat(plik).st_mtime_ns == mtime_przed, "mtime zachowany"


def test_synchronizuj_raportuje_kategorie(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "RAPORT", tmp_path / "raport.json")

    class _T:
        def __init__(self, path, artist, title):
            self.source_path = path
            self.artist = artist
            self.title = title

    class _A:
        def __init__(self, *a):
            self.track = _T(*a)
    analizy = [_A("/m/ma.mp3", "Ma", "Okladke"),
               _A("/m/trafiony.mp3", "Bicep", "Glue"),
               _A("/m/mglisty.mp3", "Bicep", "Glue")]
    monkeypatch.setattr("dancelab.tui.okladki._bajty_okladki",
                        lambda p: b"jest" if "ma" in p else None)
    wywolania = {"n": 0}

    def http(url):
        if "itunes" in url:
            wywolania["n"] += 1
            if wywolania["n"] == 1:
                return json.dumps({"results": [
                    {"artistName": "Bicep", "trackName": "Glue",
                     "artworkUrl100": "https://x/100x100bb.jpg"}]}).encode()
            return json.dumps({"results": [
                {"artistName": "Obcy", "trackName": "Cos"}]}).encode()
        return b"OBRAZEK"
    osadzone = []
    raport = synchronizuj(analizy, http=http,
                          osadz=lambda p, o: osadzone.append((p, o)) and None,
                          przerwa_sek=0)
    assert raport["z_okladka_juz"] == 1
    assert raport["osadzone"] == ["/m/trafiony.mp3"]
    assert osadzone == [("/m/trafiony.mp3", b"OBRAZEK")]
    assert len(raport["niejednoznaczne"]) == 1
    assert (tmp_path / "raport.json").exists()

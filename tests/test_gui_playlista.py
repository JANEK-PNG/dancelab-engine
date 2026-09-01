"""Playlista z okna do Rekordboxa — dwa stopnie i uczciwe liczby.

Okno wysyła set tą samą funkcją co terminal (`publish_playlist`), więc testy
nie sprawdzają dopasowywania utworów — ma własne testy. Sprawdzają to, co
jest NOWE: że stopień pierwszy naprawdę nic nie zapisuje, że liczby, które DJ
potwierdza, dotyczą tego setu i tej nazwy, oraz że wysłanie zostawia ślad
w dzienniku decyzji.
"""

import json

import pytest

from dancelab.gui.most import Most
from dancelab.ingestion.playlist_publish import PublishReport
from dancelab.stan import dziennik, playlista


class _Track:
    def __init__(self, tid: str, sciezka: str | None) -> None:
        self.track_id = tid
        self.source_path = sciezka
        self.title = f"Utwór {tid}"
        self.artist = "Test"
        self.bpm_estimate = 128.0
        self.key_estimate = "8A"
        self.key_detection_source = None
        self.duration_sec = 300.0


class _Analiza:
    def __init__(self, tid: str, sciezka: str | None) -> None:
        self.track = _Track(tid, sciezka)


@pytest.fixture()
def most(tmp_path, monkeypatch):
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path / "werdykty")
    monkeypatch.setattr(playlista, "rekordbox_otwarty", lambda: False)
    m = Most(katalog=str(tmp_path / "analizy"))
    m._analizy = {"t1": _Analiza("t1", "/muzyka/t1.aiff"),
                  "t2": _Analiza("t2", "/muzyka/t2.aiff"),
                  "t3": _Analiza("t3", None)}      # strumień bez pliku
    m._kolejnosc = ["t1", "t2"]
    m._parametry_budowy = {"minuty": 90, "dj": None}
    return m


def _raport(**kw):
    dane = {"ok": True, "playlist_name": "P", "requested": 2, "matched": 2,
            "written": 0, "backup_path": None, "notes": []}
    dane.update(kw)
    return PublishReport(**dane)


def _zdarzenia(tmp_path):
    plik = tmp_path / "werdykty" / dziennik.PLIK_ZDARZEN
    if not plik.exists():
        return []
    return [json.loads(l) for l in plik.read_text().splitlines()]


def test_podglad_nie_zapisuje_i_liczy_dopasowania(most, monkeypatch):
    wolania = []

    def fake(paths, *, name, dry_run=False, **kw):
        wolania.append({"paths": list(paths), "name": name, "dry_run": dry_run})
        return _raport(playlist_name=name, matched=2,
                       notes=["POMINIĘTY (brak/niejednoznaczny): t9.aiff"])

    monkeypatch.setattr("dancelab.ingestion.playlist_publish.publish_playlist",
                        fake)
    odp = most.podglad_playlisty()
    assert "blad" not in odp
    assert wolania[0]["dry_run"] is True          # stopień pierwszy tylko czyta
    assert wolania[0]["paths"] == ["/muzyka/t1.aiff", "/muzyka/t2.aiff"]
    assert odp["dopasowane"] == 2 and odp["zapisane"] == 0
    assert odp["notki"] == ["POMINIĘTY (brak/niejednoznaczny): t9.aiff"]
    # nazwa domyślna niesie parametry budowy, żeby dziesięć playlist
    # „DanceLab" dało się od siebie odróżnić
    assert odp["nazwa"] == "DanceLab okno · 90 min"


def test_utwor_bez_pliku_wraca_imiennie(most, monkeypatch):
    most._kolejnosc = ["t1", "t3"]
    monkeypatch.setattr("dancelab.ingestion.playlist_publish.publish_playlist",
                        lambda paths, **kw: _raport(requested=len(paths),
                                                    matched=len(paths)))
    odp = most.podglad_playlisty()
    assert odp["bez_sciezki"] == ["t3"]           # strumień, nie plik


def test_wyslanie_bez_podgladu_odmawia(most):
    assert "blad" in most.wyslij_playliste()


def test_zmiana_setu_po_podgladzie_uniewaznia_liczby(most, monkeypatch):
    monkeypatch.setattr("dancelab.ingestion.playlist_publish.publish_playlist",
                        lambda paths, **kw: _raport())
    most.podglad_playlisty()
    assert most.zapis_stan()["playlista_policzona"] is True

    most.wytnij(1)                                 # set się zmienił
    assert most._playlista_gotowa is None
    assert "blad" in most.wyslij_playliste()

    # Druga droga do tego samego: kolejność zmieniona z pominięciem edycji
    # (np. wczytaniem planu). Wtedy stan pierwszego stopnia jeszcze stoi,
    # więc to porównanie jest ostatnią bramką przed zapisem.
    most._kolejnosc = ["t1", "t2"]
    most.podglad_playlisty()
    most._kolejnosc = ["t2", "t1"]
    odp = most.wyslij_playliste()
    assert "policz jeszcze raz" in odp["blad"]
    assert most._playlista_gotowa is None


def test_zmiana_nazwy_po_podgladzie_uniewaznia_liczby(most, monkeypatch):
    monkeypatch.setattr("dancelab.ingestion.playlist_publish.publish_playlist",
                        lambda paths, **kw: _raport())
    most.podglad_playlisty("Piątek")
    odp = most.wyslij_playliste("Sobota")
    assert "policz jeszcze raz" in odp["blad"]


def test_wyslanie_zostawia_werdykt_i_zdarzenie(most, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dancelab.ingestion.playlist_publish.publish_playlist",
        lambda paths, *, name, dry_run=False, **kw: _raport(
            playlist_name=name, matched=2,
            written=0 if dry_run else 2,
            backup_path=None if dry_run else "/kopie/master.PRE.db"))

    most.podglad_playlisty("Piątek")
    odp = most.wyslij_playliste("Piątek")
    assert "blad" not in odp
    assert odp["zapisane"] == 2 and odp["kopia"].endswith(".db")
    assert most._playlista_gotowa is None          # zużyty stopień pierwszy

    werdykt = json.loads(open(odp["werdykt"]).read())
    assert werdykt["powod"] == "playlista"
    assert [u["track_id"] for u in werdykt["kolejnosc"]] == ["t1", "t2"]
    zd = _zdarzenia(tmp_path)[-1]
    assert zd["typ"] == "playlista" and zd["zapisane"] == 2


def test_nieudany_zapis_nie_udaje_sukcesu(most, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dancelab.ingestion.playlist_publish.publish_playlist",
        lambda paths, *, name, dry_run=False, **kw: _raport(
            playlist_name=name, ok=dry_run,
            notes=[] if dry_run else ["Rekordbox działa — zamknij go"]))

    most.podglad_playlisty()
    odp = most.wyslij_playliste()
    assert odp["ok"] is False
    assert "Rekordbox działa" in odp["blad"]
    assert "werdykt" not in odp                    # nie ma czego świętować
    assert _zdarzenia(tmp_path)[-1]["typ"] == "playlista_nieudana"


def test_otwarty_rekordbox_blokuje_oba_stopnie(most, monkeypatch):
    monkeypatch.setattr(playlista, "rekordbox_otwarty", lambda: True)
    assert "otwarty" in most.podglad_playlisty()["blad"]


def test_set_bez_plikow_odmawia_zamiast_wysylac_pustke(most, monkeypatch):
    most._kolejnosc = ["t3"]                       # sam strumień
    odp = most.podglad_playlisty()
    assert "żaden utwór" in odp["blad"]

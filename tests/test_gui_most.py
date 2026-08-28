"""Most GUI — cienka warstwa, ale bez testów była całkiem niepokryta.

Zewnętrzny przegląd 28.08 wskazał to wprost. Testy pilnują trzech rzeczy, na
których stoi bezpieczeństwo okna: most nigdy nie rzuca wyjątkiem do
JavaScriptu, edycje przeżywają zamknięcie okna, a stan Rekordboxa decyduje o
prawie do zapisu.
"""

from __future__ import annotations

import json

import pytest

from dancelab.gui.most import Most


@pytest.fixture
def most(tmp_path, monkeypatch):
    """Most piszący do katalogu testowego, nie do prawdziwych planów."""
    m = Most(katalog=str(tmp_path / "processed"))
    monkeypatch.setattr(type(m), "PLIK_EDYCJI", str(tmp_path / "edycje.json"))
    return m


def test_blad_zamiast_wyjatku(most):
    """Wyjątek w moście zamienia się w JS w nieczytelną odrzuconą obietnicę.

    Każda metoda ma zwrócić słownik z kluczem 'blad', który widok potrafi
    pokazać — ADR-005: każde „nie wiem" ma swój piksel.
    """
    odp = most.przebieg_utworu("czego-nie-ma")
    assert "blad" in odp
    assert isinstance(odp["blad"], str) and odp["blad"]
    json.dumps(odp)                       # musi przejść przez most do JS


def test_brak_katalogu_analiz_mowi_co_zrobic(most):
    odp = most.biblioteka()
    assert "blad" in odp
    assert "podpowiedz" in odp, "komunikat bez wyjścia jest bezużyteczny"


def test_pady_dzialaja_bez_planu_setu(most):
    """Ustawianie cue w pojedynczym utworze to sensowne użycie, nie błąd."""
    assert most.pady("t1")["pady"] == {}
    most.postaw_pad("t1", "A", 60_000)
    pady = most.pady("t1")["pady"]
    assert pady["A"]["position_ms"] == 60_000


def test_cofniecie_wraca_do_poprzedniego_stanu(most):
    most.postaw_pad("t1", "A", 60_000)
    most.postaw_pad("t1", "B", 90_000)
    most.zdejmij_pad("t1", "A")
    assert set(most.pady("t1")["pady"]) == {"B"}
    odp = most.cofnij("t1")
    assert odp["cofnieto"] is True
    assert set(odp["pady"]) == {"A", "B"}


def test_edycje_przezywaja_zamkniecie_okna(most, tmp_path, monkeypatch):
    """Warunek postawiony w przeglądzie: bez tego GUI nie może pisać do bazy.

    Zapis do master.db z ulotnej pamięci jednego okna byłby zapisem, którego
    terminal nie widział i nie mógł zrecenzować.
    """
    most.postaw_pad("t9", "A", 12_345)
    most.postaw_pad("t9", "C", 67_890)
    zapis = most.zapisz_edycje()
    assert zapis["padow"] == 2

    nowy = Most(katalog=str(tmp_path / "processed"))
    monkeypatch.setattr(type(nowy), "PLIK_EDYCJI", most.PLIK_EDYCJI)
    assert nowy.pady("t9")["pady"] == {}, "nowa instancja zaczyna pusta"
    assert nowy.wczytaj_edycje()["wczytano"] == 2
    pady = nowy.pady("t9")["pady"]
    assert pady["A"]["position_ms"] == 12_345
    assert pady["C"]["position_ms"] == 67_890


def test_historia_cofania_nie_wraca_z_dysku(most, tmp_path, monkeypatch):
    """Cofanie dotyczy bieżącej pracy — cofanie wczorajszych ruchów myliłoby."""
    most.postaw_pad("t1", "A", 1000)
    most.zapisz_edycje()
    nowy = Most(katalog=str(tmp_path / "processed"))
    monkeypatch.setattr(type(nowy), "PLIK_EDYCJI", most.PLIK_EDYCJI)
    nowy.wczytaj_edycje()
    assert nowy.cofnij("t1")["cofnieto"] is False


def test_stan_rekordboxa_rozstrzyga_o_zapisie(most, monkeypatch):
    """Otwarty Rekordbox musi blokować zapis i podawać powód, nie milczeć."""
    import dancelab.ingestion.rekordbox_cue_writer as w

    monkeypatch.setattr(w, "is_rekordbox_running", lambda: True)
    s = most.stan_rekordboxa()
    assert s["otwarty"] is True
    assert s["zapis_dozwolony"] is False
    assert "Rekordbox" in s["powod"]

    monkeypatch.setattr(w, "is_rekordbox_running", lambda: False)
    assert most.stan_rekordboxa()["zapis_dozwolony"] is True


def test_kolizje_odmawiaja_gdy_nie_ma_z_czym_porownac(most):
    """Brak utworu w bibliotece Rekordboxa to nie 'zero kolizji' — to brak
    podstawy do wyroku, i musi być nazwany."""
    most.postaw_pad("t1", "A", 1000)
    odp = most.kolizje("t1")
    assert odp["kolizje"] == []
    assert "uwaga" in odp or "blad" in odp, "cisza sugerowałaby, że jest czysto"


# --------------------------------------------------------------- zapis cue

def test_zapis_bez_setu_odmawia(most, monkeypatch):
    """Bez setu nie ma czego zapisywać — i most mówi to zamiast próbować."""
    from dancelab.stan import zapis_cue
    monkeypatch.setattr(zapis_cue, "rekordbox_otwarty", lambda: False)
    odp = most.przygotuj_zapis_cue()
    assert "zbuduj set" in odp["blad"]


def test_zapis_przy_otwartym_rekordboksie_odmawia(most, monkeypatch):
    """Otwarty Rekordbox nadpisze naszą zmianę własnym buforem, więc zapis
    jest zablokowany — tak samo jak w terminalu."""
    from dancelab.stan import zapis_cue
    monkeypatch.setattr(zapis_cue, "rekordbox_otwarty", lambda: True)
    most._kolejnosc = ["t1"]
    odp = most.przygotuj_zapis_cue()
    assert "Rekordbox" in odp["blad"]


def test_wyslanie_bez_policzenia_odmawia(most, monkeypatch):
    """Dwa stopnie zostają dwoma stopniami: potwierdza się liczby, które się
    zobaczyło, więc bez stopnia pierwszego nie ma zapisu."""
    from dancelab.stan import zapis_cue
    monkeypatch.setattr(zapis_cue, "rekordbox_otwarty", lambda: False)
    odp = most.zapisz_cue()
    assert "policz" in odp["blad"]


def test_edycja_pada_uniewaznia_policzony_plan(most, monkeypatch):
    """Inaczej potwierdzenie zapisałoby stan sprzed edycji — dokładnie ten
    błąd, przed którym TUI broni się kasowaniem planu przy każdej zmianie."""
    from dancelab.stan import zapis_cue
    monkeypatch.setattr(zapis_cue, "rekordbox_otwarty", lambda: False)
    most._zapis_gotowy = object()
    most.postaw_pad("t1", "A", 1000)
    assert most._zapis_gotowy is None
    assert "policz" in most.zapisz_cue()["blad"]

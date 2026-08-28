"""Plan setu wspólny dla obu skór.

Warunek postawiony przez zewnętrzny przegląd 28.08: zanim okno dostanie prawo
pisać do master.db, plan postawiony w oknie musi dać się odczytać w terminalu.
Bez tego byłby to zapis, którego nikt nie zrecenzował.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from dancelab.stan import plan as SP
from dancelab.tui import plan_store


@dataclass
class Slad:
    track_id: str
    source_path: str


@dataclass
class Analiza:
    track: Slad
    features: list = field(default_factory=list)


def pula(*pary) -> dict:
    return {tid: Analiza(track=Slad(track_id=tid, source_path=sciezka))
            for tid, sciezka in pary}


@pytest.fixture
def katalog(tmp_path, monkeypatch):
    """Plany w katalogu testowym — nigdy w prawdziwych planach Janka."""
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    monkeypatch.setattr(SP, "WSKAZNIK", tmp_path / "biezacy.json")
    return tmp_path


def test_plan_z_okna_odczytany_droga_terminala(katalog):
    """To jest ten warunek. Zapis przez `stan.plan` (droga okna), odczyt przez
    `plan_store` (droga terminala, klawisz `o`) — ta sama kolejność."""
    by_id = pula(("t1", "/m/a.aiff"), ("t2", "/m/b.aiff"), ("t3", "/m/c.aiff"))
    sciezka = SP.zapisz(["t2", "t1", "t3"], by_id,
                        nazwa="z okna", parametry={"minutes": 90})

    # dokładnie to, co robi TUI przy wczytywaniu planu
    rec = plan_store.read_plan(sciezka)
    kolejnosc, notki = plan_store.match_order(rec, by_id)
    assert kolejnosc == ["t2", "t1", "t3"]
    assert notki == []


def test_wskaznik_biezacego_dziala_w_obie_strony(katalog):
    by_id = pula(("t1", "/m/a.aiff"), ("t2", "/m/b.aiff"))
    assert SP.sciezka_biezacego() is None

    SP.zapisz(["t1", "t2"], by_id, nazwa="pierwszy", parametry={})
    wynik = SP.wczytaj(by_id)
    assert wynik["kolejnosc"] == ["t1", "t2"]
    assert wynik["nazwa"] == "pierwszy"

    # drugi zapis przejmuje wskaźnik — „bieżący" to zawsze ostatni
    SP.zapisz(["t2"], by_id, nazwa="drugi", parametry={})
    assert SP.wczytaj(by_id)["nazwa"] == "drugi"


def test_utwor_znikniety_z_puli_jest_POMIJANY_z_notka(katalog):
    """Nigdy nie podmieniamy zamiennika po cichu — to zachowanie z plan_store
    i musi przetrwać opakowanie."""
    pelna = pula(("t1", "/m/a.aiff"), ("t2", "/m/b.aiff"))
    SP.zapisz(["t1", "t2"], pelna, nazwa="x", parametry={})

    uboga = pula(("t1", "/m/a.aiff"))
    wynik = SP.wczytaj(uboga)
    assert wynik["kolejnosc"] == ["t1"]
    assert any("BRAK W PULI" in n for n in wynik["notki"])
    assert wynik["zapisanych"] == 2, "musi być widać, ilu utworów brakuje"


def test_przeniesiony_plik_ratowany_po_sciezce(katalog):
    """track_id to hash ścieżki, więc po przenosinach id się zmienia —
    dopasowanie po ścieżce jest jedynym ratunkiem i musi działać przez adapter."""
    stara = pula(("stare_id", "/m/a.aiff"))
    SP.zapisz(["stare_id"], stara, nazwa="x", parametry={})

    nowa = pula(("nowe_id", "/m/a.aiff"))     # ta sama ścieżka, inne id
    wynik = SP.wczytaj(nowa)
    assert wynik["kolejnosc"] == ["nowe_id"]
    assert any("po ścieżce" in n for n in wynik["notki"])


def test_brak_planu_mowi_co_zrobic(katalog):
    wynik = SP.wczytaj({})
    assert wynik["kolejnosc"] == []
    assert "zbuduj set" in wynik["powod"]


def test_znikniety_plik_planu_nie_wybucha(katalog):
    by_id = pula(("t1", "/m/a.aiff"))
    sciezka = SP.zapisz(["t1"], by_id, nazwa="x", parametry={})
    sciezka.unlink()
    wynik = SP.wczytaj(by_id)
    assert wynik["kolejnosc"] == []
    assert "zniknął" in wynik["powod"]


def test_lista_zaznacza_biezacy(katalog):
    by_id = pula(("t1", "/m/a.aiff"))
    SP.zapisz(["t1"], by_id, nazwa="stary", parametry={})
    import time
    time.sleep(1.05)                      # nazwa pliku ma rozdzielczość sekundy
    SP.zapisz(["t1"], by_id, nazwa="nowy", parametry={})
    wpisy = SP.lista()
    biezace = [w for w in wpisy if w["biezacy"]]
    assert len(biezace) == 1
    assert biezace[0]["nazwa"] == "nowy"

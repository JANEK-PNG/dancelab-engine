"""Dziennik decyzji okna (Q14): edycje padów i werdykt zapisu.

Trzy rzeczy, których pilnują te testy:

1. każda edycja pada zostawia zdarzenie z kontekstem propozycji silnika —
   o ile DJ tę propozycję OGLĄDAŁ; edycja w ciemno pól kontekstu nie dostaje;
2. pad silnika w utworze, którego ekran nigdy nie narysował, przeszedł
   DOMYŚLNIE — werdykt nie ma prawa nazwać go zaakceptowanym;
3. awaria zapisu dziennika nie wywraca edycji — pad staje, ostrzeżenie wraca
   do widoku.
"""

import json

import pytest

from dancelab.decision.cue_export_models import CuePlan, PlannedCue, TrackCuePlan
from dancelab.gui.most import Most
from dancelab.stan import dziennik


def _plan_dwoch_utworow() -> CuePlan:
    """Silnik proponuje: utwór t1 pad A (10 s), utwór t2 pad A (20 s)."""
    return CuePlan(tracks=[
        TrackCuePlan(content_id="t1", track_title="Pierwszy", cues=[
            PlannedCue(content_id="t1", position_ms=10_000, kind=1,
                       pad_label="A", cue_type="mix_in")]),
        TrackCuePlan(content_id="t2", track_title="Drugi", cues=[
            PlannedCue(content_id="t2", position_ms=20_000, kind=1,
                       pad_label="A", cue_type="mix_in")]),
    ])


@pytest.fixture()
def most(tmp_path, monkeypatch):
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path / "werdykty")
    m = Most(katalog=str(tmp_path / "analizy"))
    m._plan_cue = _plan_dwoch_utworow()
    m._kolejnosc = ["t1", "t2"]
    return m


def _zdarzenia(tmp_path):
    plik = tmp_path / "werdykty" / dziennik.PLIK_ZDARZEN
    if not plik.exists():
        return []
    return [json.loads(l) for l in plik.read_text().splitlines()]


def test_edycje_padow_niosa_kontekst_propozycji(most, tmp_path):
    # DJ otwiera ekran utworu t1 → widzi pady → dopiero teraz edytuje.
    most.pady("t1")

    # Ręczny pad na wolnej literze: silnik dla B nie proponował nic i to jest
    # FAKT (silnik_ms=None), nie brak danych.
    odp = most.postaw_pad("t1", "B", 5_000)
    assert "blad" not in odp

    # Przesunięcie pada silnikowego A o 4 uderzenia przy 120 BPM = +2 s.
    odp = most.przesun_pad("t1", "A", 4, 120.0)
    assert "blad" not in odp
    assert odp["pady"]["A"]["position_ms"] == 12_000

    # Zdjęcie pada silnikowego = odrzucenie propozycji.
    odp = most.zdejmij_pad("t1", "A")
    assert "blad" not in odp

    zd = _zdarzenia(tmp_path)
    assert [z["typ"] for z in zd] == \
        ["cue_postaw", "cue_przesuniecie", "cue_zdjecie"]
    assert zd[0]["silnik_ms"] is None                  # ręczny, wolna litera
    assert zd[1]["silnik_ms"] == 10_000                # propozycja, którą ruszył
    assert zd[1]["position_ms"] == 12_000
    assert zd[2]["silnik_ms"] == 10_000                # propozycja, którą zdjął


def test_edycja_w_ciemno_bez_pol_kontekstu(most, tmp_path):
    # Ekran t2 nigdy nie narysowany — edycja nie dostaje porównania,
    # którego DJ nie widział.
    odp = most.postaw_pad("t2", "B", 7_000)
    assert "blad" not in odp
    zd = _zdarzenia(tmp_path)
    assert zd[0]["typ"] == "cue_postaw"
    assert "silnik_ms" not in zd[0]


def test_nieogladane_pady_przechodza_domyslnie(most):
    most.pady("t1")                                    # t2 nigdy nie pokazany
    utwory, miara = most._klasyfikuj_pady()

    t1 = next(u for u in utwory if u["track_id"] == "t1")
    t2 = next(u for u in utwory if u["track_id"] == "t2")
    assert t1["propozycje_widziane"] is True
    assert t2["propozycje_widziane"] is False
    assert t2["pady"]["A"]["los"] == "z_silnika"
    assert miara["z_silnika"] == 2
    assert miara["przeszlo_domyslnie"] == 1            # tylko pad z t2
    assert miara["utwory_z_widzianymi"] == 1


def test_klasyfikacja_losow_padow(most):
    most.pady("t1")
    most.pady("t2")
    most.przesun_pad("t1", "A", 4, 120.0)              # nadpisany
    most.postaw_pad("t1", "B", 5_000)                  # reczny
    most.zdejmij_pad("t2", "A")                        # zdjety

    utwory, miara = most._klasyfikuj_pady()
    t1 = next(u for u in utwory if u["track_id"] == "t1")
    t2 = next(u for u in utwory if u["track_id"] == "t2")
    assert t1["pady"]["A"] == {"los": "nadpisany", "silnik_ms": 10_000,
                               "position_ms": 12_000}
    assert t1["pady"]["B"]["los"] == "reczny"
    assert t2["pady"]["A"] == {"los": "zdjety", "silnik_ms": 20_000}
    assert miara == {"z_silnika": 0, "nadpisane": 1, "reczne": 1, "zdjete": 1,
                     "przeszlo_domyslnie": 0, "utwory_z_widzianymi": 2}


def test_werdykt_przezywa_niezapisywalne_wagi(most, tmp_path):
    class Dziwne:                                      # ani model, ani dict
        pass

    most._wagi_budowy = Dziwne()
    rec = most._werdykt_zapisu("test", {"zapisane": 0})
    plik, blad = dziennik.zapisz_werdykt(rec)
    assert blad is None
    dane = json.loads((tmp_path / "werdykty" / plik.split("/")[-1]).read_text())
    assert dane["miara"]["z_silnika"] == 2


def test_awaria_dziennika_nie_blokuje_edycji(most, tmp_path, monkeypatch):
    # KATALOG wskazuje na PLIK → mkdir się wywróci → edycja ma przejść,
    # a ostrzeżenie wrócić do widoku.
    zapora = tmp_path / "zapora"
    zapora.write_text("")
    monkeypatch.setattr(dziennik, "KATALOG", zapora / "w")
    most.pady("t1")
    odp = most.postaw_pad("t1", "B", 5_000)
    assert "blad" not in odp
    assert odp["pady"]["B"]["position_ms"] == 5_000
    assert "dziennik nie zapisał" in odp.get("dziennik", "")

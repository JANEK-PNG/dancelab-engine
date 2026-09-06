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
    return [json.loads(line) for line in plik.read_text().splitlines()]


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
                     "przeszlo_domyslnie": 0, "utwory_z_widzianymi": 2,
                     "edycje_sprzed_planu": 0}


def test_werdykt_przezywa_niezapisywalne_wagi(most, tmp_path):
    class Dziwne:                                      # ani model, ani dict
        pass

    most._wagi_budowy = Dziwne()
    rec = most._werdykt_zapisu("test", {"zapisane": 0})
    plik, blad = dziennik.zapisz_werdykt(rec, skora="gui")
    assert blad is None
    dane = json.loads((tmp_path / "werdykty" / plik.split("/")[-1]).read_text())
    assert dane["miara"]["z_silnika"] == 2


def test_cofniecie_loguje_co_naprawde_wrocilo(most, tmp_path):
    # Historia edycji jest wspólna: pad postawiony na t2, cofnięcie zrobione
    # z ekranu t1 — zdarzenie ma nieść klucz t2, nie utwór z ekranu.
    most.pady("t2")
    most.postaw_pad("t2", "B", 7_000)
    odp = most.cofnij("t1")
    assert odp["cofnieto"] is True
    zd = _zdarzenia(tmp_path)
    assert zd[-1]["typ"] == "cue_cofniecie"
    assert zd[-1]["zmienione"] == ["t2|B"]
    assert "track_id" not in zd[-1]


def test_edycje_sprzed_planu_nie_licza_sie_jako_reakcja(most):
    # Nadpisanie pada A na t1 istniało już w chwili budowy planu — werdykt
    # nie ma prawa policzyć go jako odpowiedzi na propozycję tego planu.
    most.pady("t1")
    most.przesun_pad("t1", "A", 4, 120.0)
    # migawka WARTOŚCI, nie samych kluczy — patrz `Most._migawka_edycji`
    most._edycje_sprzed_planu = most._migawka_edycji()
    utwory, miara = most._klasyfikuj_pady()
    t1 = next(u for u in utwory if u["track_id"] == "t1")
    assert t1["pady"]["A"]["los"] == "nadpisany"
    assert t1["pady"]["A"]["sprzed_planu"] is True
    assert miara["edycje_sprzed_planu"] == 1


def test_poprawka_PO_zobaczeniu_planu_liczy_sie_jako_reakcja(most):
    """Zgrubny pad → budowa → poprawka po obejrzeniu propozycji.

    To jest normalny tryb pracy, a nie przypadek dziwny. Do 02.09 znacznik
    „sprzed planu" wisiał na samym KLUCZU, a `cue_edycje.przesun` nadpisuje
    wpis pod tym samym kluczem — więc reakcja na propozycję wchodziła do
    dziennika opisana jako „to nie była reakcja". Dokładne odwrócenie tego,
    co ten znacznik ma znaczyć, w danych zbieranych tylko do przodu.
    """
    most.pady("t1")
    most.postaw_pad("t1", "A", 5_000)          # przed budową
    most._edycje_sprzed_planu = most._migawka_edycji()

    most.przesun_pad("t1", "A", 4, 120.0)      # PO obejrzeniu propozycji
    utwory, miara = most._klasyfikuj_pady()
    t1 = next(u for u in utwory if u["track_id"] == "t1")
    assert "sprzed_planu" not in t1["pady"]["A"]
    assert miara["edycje_sprzed_planu"] == 0

    # cofnięcie do stanu sprzed planu przywraca znacznik — wartość znowu ta sama
    most.cofnij("t1")
    _, miara_po = most._klasyfikuj_pady()
    assert miara_po["edycje_sprzed_planu"] == 1


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


def test_zapis_cue_konczy_sie_werdyktem_na_dysku(tmp_path, monkeypatch):
    """Pełna droga okna na KOPII master.db: podgląd → zapis → werdykt.

    Testuje sam szew, którego testy jednostkowe nie widzą: że `zapisz_cue`
    naprawdę odkłada `gui_werdykt_*.json` i wskazuje go w odpowiedzi.
    """
    from pathlib import Path
    import shutil

    pytest.importorskip("pyrekordbox")
    zywa = Path.home() / "Library/Pioneer/rekordbox/master.db"
    if not zywa.exists():
        pytest.skip("brak lokalnej master.db do skopiowania")

    import pyrekordbox.db6.database as _db
    from dancelab.ingestion import cue_ledger, rekordbox_cue_writer as W
    from dancelab.stan import zapis_cue

    monkeypatch.setattr(_db, "get_rekordbox_pid", lambda *a, **k: 0)
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    monkeypatch.setattr(cue_ledger, "SCIEZKA", tmp_path / "rejestr.json")
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path / "werdykty")
    kopia = tmp_path / "master.db"
    shutil.copy2(zywa, kopia)
    monkeypatch.setattr(zapis_cue, "BAZA_DOMYSLNA", kopia)
    monkeypatch.setattr(zapis_cue, "BACKUP_DIR", tmp_path / "kopie")
    monkeypatch.setattr(zapis_cue, "rekordbox_otwarty", lambda: False)

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(kopia))
    try:
        wiersz = db.session.query(tables.DjmdContent).filter(
            tables.DjmdContent.FolderPath != None).first()  # noqa: E711
        sciezka = str(wiersz.FolderPath)
    finally:
        db.close()

    class _T:
        track_id, source_path, title, artist = "t1", sciezka, "Testowy", "Test"

    class _A:
        track = _T()

    m = Most(katalog=str(tmp_path / "analizy"))
    m._plan_cue = CuePlan(tracks=[TrackCuePlan(content_id="t1", cues=[
        PlannedCue(content_id="t1", position_ms=61_500, kind=1,
                   pad_label="A", cue_type="mix_in")])])
    m._kolejnosc = ["t1"]
    m._analizy = {"t1": _A()}
    m.pady("t1")

    podglad = m.przygotuj_zapis_cue()
    assert "blad" not in podglad, podglad
    wynik = m.zapisz_cue(nazwa="test dziennika")
    assert "blad" not in wynik, wynik
    assert wynik["zapisane"] >= 1

    werdykt = json.loads(Path(wynik["werdykt"]).read_text())
    assert werdykt["powod"] == "zapis_cue"
    assert werdykt["liczby_podgladu"]["do_zapisu"] == podglad["do_zapisu"]
    t1 = next(u for u in werdykt["utwory"] if u["track_id"] == "t1")
    assert t1["propozycje_widziane"] is True
    assert t1["pady"]["A"]["los"] == "z_silnika"
    zd = _zdarzenia(tmp_path)
    assert zd[-1]["typ"] == "zapis_cue"
    assert zd[-1]["werdykt"] == wynik["werdykt"]

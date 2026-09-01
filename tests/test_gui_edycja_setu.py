"""Edycja setu w oknie: podmiana, dopisanie, cięcie, przesunięcie.

Okno dostało to, co terminal ma od 05.08. Testy pilnują trzech rzeczy, na
których ta funkcja stoi:

1. kandydaci liczą się TYM SAMYM, czym powstał set (wagi, łuk, planer, okno
   tempa, kotwica) — sugestia z innym gustem niż set byłaby cichym kłamstwem;
2. każda zmiana kolejności trafia do dziennika decyzji z rangą kandydata —
   to jest sygnał, dla którego Q14 w ogóle włączono;
3. po zmianie kolejności policzony plan zapisu przestaje obowiązywać, a
   propozycje padów są przeliczane, zanim DJ zobaczy liczby do potwierdzenia.
"""

import json

import pytest

from dancelab.decision.cue_export_models import CuePlan, PlannedCue, TrackCuePlan
from dancelab.gui.most import Most
from dancelab.stan import dziennik


class _Track:
    def __init__(self, tid: str, bpm: float) -> None:
        self.track_id = tid
        self.bpm_estimate = bpm
        self.key_estimate = "8A"
        self.key_detection_source = None
        self.title = f"Utwór {tid}"
        self.artist = "Test"
        self.duration_sec = 300.0
        self.source_path = f"/muzyka/{tid}.aiff"
        self.sound_embedding = None


class _Analiza:
    def __init__(self, tid: str, bpm: float = 128.0) -> None:
        self.track = _Track(tid, bpm)
        self.features = []


@pytest.fixture()
def most(tmp_path, monkeypatch):
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path / "werdykty")
    m = Most(katalog=str(tmp_path / "analizy"))
    m._analizy = {t: _Analiza(t) for t in ("t1", "t2", "t3", "k1", "k2")}
    m._kolejnosc = ["t1", "t2", "t3"]
    m._ctx_edycji = {"wagi": object(), "luk": "off", "planer": "smart",
                     "bpm_min": None, "bpm_max": None,
                     "kotwica_centroid": None, "filary": ["t2"]}
    return m


def _zdarzenia(tmp_path):
    plik = tmp_path / "werdykty" / dziennik.PLIK_ZDARZEN
    if not plik.exists():
        return []
    return [json.loads(l) for l in plik.read_text().splitlines()]


def test_kandydaci_ocenia_ta_sama_miara_co_budowa(most, monkeypatch):
    """Wagi, łuk, planer i okno tempa idą do sugestii wprost z budowy."""
    zapamietane = {}

    def fake(by_id, order, index, **kw):
        zapamietane.update(kw, index=index, order=list(order))
        from dancelab.decision.slot_suggest import SlotSuggestion
        return [SlotSuggestion("k1", 0.91, "wejście 0,90 · wyjście 0,92"),
                SlotSuggestion("k2", 0.70, "wejście 0,70 · wyjście 0,70")]

    import dancelab.decision.slot_suggest as SS
    monkeypatch.setattr(SS, "suggest_for_slot", fake)
    most._ctx_edycji["bpm_min"] = 124.0
    most._ctx_edycji["bpm_max"] = 130.0
    kotwica = [0.1, 0.2]
    most._ctx_edycji["kotwica_centroid"] = kotwica

    odp = most.kandydaci(1, "smart", "podmiana")
    assert "blad" not in odp
    assert [k["track_id"] for k in odp["kandydaci"]] == ["k1", "k2"]
    assert [k["ranga"] for k in odp["kandydaci"]] == [1, 2]
    assert odp["kandydaci"][0]["why"].startswith("wejście")
    assert zapamietane["index"] == 1
    assert zapamietane["weights"] is most._ctx_edycji["wagi"]
    assert zapamietane["arc"] == "off"
    assert zapamietane["planner_mode"] == "smart"
    assert zapamietane["bpm_min"] == 124.0 and zapamietane["bpm_max"] == 130.0
    assert zapamietane["anchor"] == kotwica


def test_tryb_bpm_nie_niesie_kotwicy(most, monkeypatch):
    """Tryb nazywa dokładnie to, co ocenia — bez cichej kotwicy z budowy."""
    zapamietane = {}
    import dancelab.decision.slot_suggest as SS
    monkeypatch.setattr(SS, "suggest_for_slot",
                        lambda *a, **kw: zapamietane.update(kw) or [])
    most._ctx_edycji["kotwica_centroid"] = [0.5]
    most.kandydaci(0, "bpm", "podmiana")
    assert zapamietane["planner_mode"] == "bpm"
    assert zapamietane["anchor"] is None


def test_podmiana_loguje_range_kandydata(most, tmp_path, monkeypatch):
    import dancelab.decision.slot_suggest as SS
    from dancelab.decision.slot_suggest import SlotSuggestion
    monkeypatch.setattr(SS, "suggest_for_slot", lambda *a, **kw: [
        SlotSuggestion("k1", 0.91, "why"), SlotSuggestion("k2", 0.70, "why")])

    most.kandydaci(1, "smart", "podmiana")
    odp = most.podmien(1, "k2")
    assert "blad" not in odp
    assert most._kolejnosc == ["t1", "k2", "t3"]
    assert [u["track_id"] for u in odp["utwory"]] == ["t1", "k2", "t3"]

    zd = _zdarzenia(tmp_path)[-1]
    assert zd["typ"] == "podmiana" and zd["pozycja"] == 2
    assert zd["out"].endswith("t2.aiff") and zd["in"].endswith("k2.aiff")
    # ranga 2 = DJ minął pierwszą propozycję; to jest cały sens tego pola
    assert zd["zrodlo"] == "panel_silnika" and zd["ranga"] == 2
    assert zd["kandydatow"] == 2 and zd["tryb"] == "smart"


def test_wybor_bez_panelu_jest_wlasny_a_nie_zgadniety(most, tmp_path):
    odp = most.podmien(0, "k1")
    assert "blad" not in odp
    zd = _zdarzenia(tmp_path)[-1]
    assert zd["zrodlo"] == "reka_dj"
    assert "ranga" not in zd


def test_dopisanie_wstawia_za_pozycja(most, tmp_path):
    odp = most.dopisz_utwor(0, "k1")
    assert "blad" not in odp
    assert most._kolejnosc == ["t1", "k1", "t2", "t3"]
    assert _zdarzenia(tmp_path)[-1]["pozycja"] == 2


def test_ciecie_filaru_mowi_o_tym_wprost(most, tmp_path):
    odp = most.wytnij(1)                       # t2 jest filarem
    assert "blad" not in odp
    assert most._kolejnosc == ["t1", "t3"]
    assert "FILAR" in odp["uwaga"]
    zd = _zdarzenia(tmp_path)[-1]
    assert zd["typ"] == "ciecie" and zd["filar"] is True


def test_przesuniecie_na_brzegu_to_nie_blad(most):
    odp = most.przesun_utwor(0, -1)
    assert "blad" not in odp
    assert "brzeg setu" in odp["uwaga"]
    assert most._kolejnosc == ["t1", "t2", "t3"]

    odp = most.przesun_utwor(0, 1)
    assert most._kolejnosc == ["t2", "t1", "t3"]
    assert odp["na"] == 1


def test_odmowy_nie_ruszaja_setu(most):
    assert "blad" in most.podmien(9, "k1")
    assert "blad" in most.podmien(0, "nieznany")
    assert "blad" in most.podmien(0, "t2")          # już w secie
    assert "blad" in most.kandydaci(9)
    assert most._kolejnosc == ["t1", "t2", "t3"]

    pusty = Most(katalog="x")
    assert "blad" in pusty.kandydaci(0)             # bez setu nie ma szczelin
    pusty._kolejnosc = ["t1"]
    assert "wag budowy" in pusty.kandydaci(0)["blad"]   # plan z pliku


def test_edycja_uniewaznia_policzony_zapis_i_przelicza_pady(most, monkeypatch):
    """Liczby, które DJ potwierdza, muszą dotyczyć setu PO edycji."""
    most._plan_cue = CuePlan(tracks=[TrackCuePlan(content_id="t2", cues=[
        PlannedCue(content_id="t2", position_ms=1000, kind=1, pad_label="A")])])
    most._zapis_gotowy = "stary plan"

    most.podmien(1, "k1")
    assert most._zapis_gotowy is None
    assert most._plan_cue_nieaktualny is True

    from dancelab.stan import zapis_cue
    swiezy = CuePlan(tracks=[TrackCuePlan(content_id="k1", cues=[
        PlannedCue(content_id="k1", position_ms=2000, kind=1, pad_label="A")])])
    wolania = []
    monkeypatch.setattr(zapis_cue, "propozycje",
                        lambda kol, by_id, wagi: wolania.append(list(kol)) or swiezy)
    monkeypatch.setattr(zapis_cue, "rekordbox_otwarty", lambda: False)
    monkeypatch.setattr(zapis_cue, "przygotuj",
                        lambda *a, **kw: {"plan": "nowy", "do_zapisu": 1,
                                          "odswiezone": 0, "ustapilo_twoim": 0,
                                          "utworow": 1, "spoza_kolekcji": []})

    odp = most.przygotuj_zapis_cue()
    assert "blad" not in odp
    assert wolania == [["t1", "k1", "t3"]]          # przeliczone na NOWYM secie
    assert most._plan_cue is swiezy
    assert most._plan_cue_nieaktualny is False
    assert most._werdykt_zapisu("x", {})["plan_cue_przeliczony_po_edycji"] is True

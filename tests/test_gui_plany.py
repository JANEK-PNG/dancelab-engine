"""Faza 2, grupa 1 (02.09): plan pod nazwą i kosz planów w oknie.

Terminal ma Ctrl+S i X od 04.08; okno zapisywało plan wyłącznie automatem
po budowie i nie pamiętało ani planu silnika po wczytaniu, ani edycji —
plik zapisany po podmianach nie miał więc z czego wziąć historii.
"""

import json

from dancelab.gui.most import Most
from dancelab.stan import plan as SP
from dancelab.tui import plan_store


class _T:
    def __init__(self, tid):
        self.track_id, self.source_path, self.title, self.artist = tid, f"/m/{tid}.aiff", tid, "X"
        self.bpm_estimate, self.key_estimate, self.duration_sec = 128.0, "8A", 300.0
        self.key_detection_source = self.key_confidence = self.style_label = None
        self.sound_embedding = None


class _A:
    def __init__(self, tid):
        self.track, self.features = _T(tid), []


def _most(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path / "plany")
    monkeypatch.setattr(SP, "WSKAZNIK", tmp_path / "plany" / "biezacy.json")
    m = Most(katalog=str(tmp_path))
    m._analizy = {t: _A(t) for t in ("a", "b", "c")}
    m._kolejnosc = ["a", "b", "c"]
    m._plan_silnika = ["a", "b", "c"]
    m._parametry_budowy = {"minuty": 30}
    return m


def test_zapis_planu_niesie_plan_silnika_i_edycje(tmp_path, monkeypatch):
    m = _most(tmp_path, monkeypatch)
    odp = m.wytnij(1)
    assert "blad" not in odp
    assert [e["typ"] for e in m._edycje_setu] == ["ciecie"]

    odp = m.zapisz_plan("piątek klub")
    assert "blad" not in odp, odp
    rec = json.loads(open(odp["zapisano"], encoding="utf-8").read())
    assert rec["nazwa"] == "piątek klub"
    assert [w["track_id"] for w in rec["kolejnosc"]] == ["a", "c"]
    assert rec["plan_silnika"] == ["a", "b", "c"]
    assert [e["typ"] for e in rec["edycje"]] == ["ciecie"]
    assert odp["edycji"] == 1 and odp["utworow"] == 2


def test_zapis_planu_bez_setu_odmawia(tmp_path, monkeypatch):
    m = _most(tmp_path, monkeypatch)
    m._kolejnosc = []
    assert "nie ma czego zapisać" in m.zapisz_plan("x")["blad"]


def test_usuniecie_planu_jest_miekkie_i_zdejmuje_wskaznik(tmp_path, monkeypatch):
    m = _most(tmp_path, monkeypatch)
    sciezka = m.zapisz_plan("do kosza")["zapisano"]
    assert SP.sciezka_biezacego() is not None          # zapis oznacza bieżący

    odp = m.usun_plan(sciezka)
    assert "blad" not in odp, odp
    assert "kosz" in odp["kosz"] and (tmp_path / "plany" / "kosz").is_dir()
    assert not (tmp_path / "plany" / sciezka.split("/")[-1]).exists()
    assert SP.sciezka_biezacego(musi_istniec=False) is None   # wskaźnik poszedł z planem
    assert odp["plany"] == []


def test_wczytany_plan_wnosi_swoja_historie(tmp_path, monkeypatch):
    m = _most(tmp_path, monkeypatch)
    m._edycje_setu = [{"typ": "przesuniecie"}]
    m.zapisz_plan("z historią")
    m2 = _most(tmp_path, monkeypatch)
    m2._kolejnosc, m2._plan_silnika, m2._edycje_setu = [], [], []
    monkeypatch.setattr(m2, "_pula", lambda: list(m2._analizy.values()))
    wynik = m2._wczytaj_plan_teraz(SP.lista()[0]["path"])
    assert "blad" not in wynik, wynik
    assert m2._plan_silnika == ["a", "b", "c"]
    assert [e["typ"] for e in m2._edycje_setu] == ["przesuniecie"]

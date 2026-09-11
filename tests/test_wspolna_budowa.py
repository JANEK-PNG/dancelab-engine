"""Krok 7 scalania skór (02.09): jeden budowniczy setu.

Terminal miał własne 200 linii (`_build_plan`), okno — `stan.budowa.zbuduj`.
Różniły się nie tylko kosmetyką: tryb Folder, kotwica z ♥, przerywanie
i odcisk świeżości istniały tylko w terminalu, więc okno nie karmiło
historii świeżości wcale, a karta „★ moje ulubione" na ścianie DJ-ów była
w oknie ślepą uliczką. Te testy pilnują, że terminal przekłada formularz
na `Parametry` bez straty i że to, co było tylko jego, jest teraz wspólne.
"""

import threading

from dancelab.gui.most import Most
from dancelab.stan import budowa
from dancelab.tui.app import DanceLabTUI


class _T:
    def __init__(self, tid, bpm=128.0):
        self.track_id, self.source_path, self.bpm_estimate = tid, f"/m/{tid}.aiff", bpm
        self.key_estimate, self.title, self.artist = "8A", tid, "X"
        self.duration_sec, self.style_label, self.sound_embedding = 300.0, None, None
        self.key_detection_source = self.key_confidence = None


class _A:
    def __init__(self, tid, bpm=128.0):
        self.track, self.features = _T(tid, bpm), []


class _Plan:
    def __init__(self, order):
        self.track_order, self.warnings, self.mean_transition_score = list(order), [], 0.5


def _stub_app(pula, formularz):
    app = DanceLabTUI.__new__(DanceLabTUI)
    app._params = lambda: dict(formularz)
    app.call_from_thread = lambda f, *a, **k: f(*a, **k)
    app.query_one = lambda *a, **k: type("S", (), {"update": staticmethod(lambda *x: None)})()
    app.processed_dir = "/nieistotny"
    app._user_state = {}
    app._stop = threading.Event()
    app._library_analyses = lambda: (list(pula), ["higiena: 0"])
    return app


FORMULARZ = dict(pool="library", folder="", novelty="balanced", seed=42,
                 minutes=45.0, bpm_min=124.0, bpm_max=134.0, styles=["Tech House"],
                 dj=None, contour=True, arc="build", tempo="staircase", planner="smart")


def test_terminal_przeklada_caly_formularz_na_parametry(monkeypatch):
    """Każde pole `_params` ma trafić w swoje pole `Parametry` — zgubione
    pole to set zbudowany inaczej, niż DJ ustawił."""
    zebrane = {}

    def zbuduj(par, **kw):
        zebrane["par"], zebrane["kw"] = par, kw
        return {"plan": _Plan(["a", "b"]), "kolejnosc": ["a", "b"], "by_id": {},
                "wagi": "W", "notki": ["n1"], "kotwica": None,
                "kotwica_centroid": [0.1], "filary": ["a"], "odcisk": "ODCISK",
                "tryb_filarow": None, "filary_zgloszone": 0, "filary_stan": "brak"}
    monkeypatch.setattr(budowa, "zbuduj", zbuduj)

    app = _stub_app([_A("a"), _A("b")], FORMULARZ)
    app._user_state = {"tryb_filarow": "rama"}
    plan, by_id, notki = app._build_plan()

    par = zebrane["par"]
    assert (par.minuty, par.bpm_min, par.bpm_max) == (45.0, 124.0, 134.0)
    assert par.style == ["Tech House"] and par.kontur is True
    assert (par.luk, par.tempo, par.planer) == ("build", "staircase", "smart")
    assert (par.nowosc, par.ziarno, par.zrodlo_puli) == ("balanced", 42, "library")
    assert par.tryb_filarow == "rama"
    kw = zebrane["kw"]
    # metoda związana powstaje na nowo przy każdym odczycie — porównujemy właściciela
    assert kw["przerwij"].__self__ is app._stop        # anulowanie z terminala
    assert kw["stan_uzytkownika"] is app._user_state   # filary i ♥ z tego samego stanu
    assert len(kw["analizy"]) == 2                     # pula z Biblioteki, nie drugi odczyt
    assert app._ctx["odcisk"] == "ODCISK" and app._ctx["anchor"] == [0.1]
    assert app._ctx["filary"] == ["a"] and app._ctx["weights"] == "W"
    assert notki == ["higiena: 0", "n1"]              # higiena puli + notki budowy


def test_tryb_folder_nie_czyta_biblioteki(monkeypatch):
    zebrane = {}
    monkeypatch.setattr(budowa, "zbuduj", lambda par, **kw: zebrane.update(par=par, kw=kw) or {
        "plan": _Plan([]), "by_id": {}, "wagi": None, "notki": [], "kotwica_centroid": None,
        "filary": [], "odcisk": None})
    app = _stub_app([_A("a")], {**FORMULARZ, "pool": "folder", "folder": "/muzyka"})
    app._library_analyses = lambda: (_ for _ in ()).throw(AssertionError("Biblioteka czytana w trybie Folder"))
    app._build_plan()
    assert zebrane["par"].zrodlo_puli == "folder" and zebrane["par"].folder == "/muzyka"
    assert zebrane["kw"]["analizy"] is None


def test_zbuduj_zwraca_odcisk_i_szanuje_przerwanie(monkeypatch):
    from dancelab.decision import set_builder
    monkeypatch.setattr(set_builder, "build_set", lambda analizy, wagi, **kw: _Plan(
        [a.track.track_id for a in analizy][:kw["target_track_count"]]))
    monkeypatch.setattr(budowa, "dokarm", lambda analizy, **k: [])
    pula = [_A(f"t{i}", 124.0 + i) for i in range(8)]
    par = budowa.Parametry(minuty=20.0, nowosc="balanced", ziarno=7)

    wynik = budowa.zbuduj(par, analizy=list(pula), stan_uzytkownika={})
    assert wynik["odcisk"] is not None
    assert wynik["odcisk"].seed == 7
    assert any("świeżość: balanced" in n for n in wynik["notki"])

    import pytest
    with pytest.raises(budowa.OdmowaBudowy, match="anulowane"):
        budowa.zbuduj(par, analizy=list(pula), przerwij=lambda: True)


def test_kotwica_z_ulubionych_jest_wspolna(monkeypatch):
    """Okno pokazywało kartę „★ moje ulubione", a `zbuduj` odpowiadało
    „kotwica niedostępna" — bo tylko terminal umiał policzyć ją z ♥."""
    from dancelab.decision import anchors
    widziane = {}

    class _Kot:
        name, n_tracks, centroid, contour = anchors.MOJE_ULUBIONE, 2, [0.5], None
    monkeypatch.setattr(anchors, "kotwica_z_utworow",
                        lambda analizy, nazwa=anchors.MOJE_ULUBIONE:
                        widziane.update(ids=[a.track.track_id for a in analizy]) or _Kot())
    pula = [_A("a"), _A("b"), _A("c")]
    stan = {"ulubione_utwory": [{"track_id": "a", "path": "/m/a.aiff"},
                                {"track_id": "c", "path": "/m/c.aiff"}]}
    kot, notki = budowa._kotwica(anchors.MOJE_ULUBIONE, pula, stan)
    assert kot is not None and widziane["ids"] == ["a", "c"]
    assert any("z Twoich ulubionych: 2" in n for n in notki)


def test_okno_karmi_historie_swiezosci_raz_przy_uzyciu(monkeypatch, tmp_path):
    """Ta sama reguła co S/W w terminalu: odcisk idzie do historii przy
    pierwszym UŻYCIU setu, nie przy każdej budowie i nie dwa razy."""
    from dancelab.decision import history
    dopisane = []
    monkeypatch.setattr(history, "HistoryStore",
                        lambda p: type("H", (), {"append": staticmethod(dopisane.append)})())
    m = Most(katalog=str(tmp_path))
    assert m._utrwal_odcisk("test") is None            # bez budowy nie ma odcisku
    m._ctx_edycji = {"odcisk": "ODCISK"}
    assert "dopisany" in m._utrwal_odcisk("zapisane cue")
    assert m._utrwal_odcisk("wysłana playlista") is None
    assert dopisane == ["ODCISK"]

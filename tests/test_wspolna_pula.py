"""Krok 6 scalania skór (02.09): jedna pula, jedno dokarmianie, jeden odczyt planu.

Znalezisko z tego kroku: okno wczytywało plan na SUROWEJ puli (bez tonacji
z Rekordboxa i wektorów), o ile wcześniej nie zbudowało setu — bo dokarmiał
dopiero `zbuduj`. Terminal dokarmiał przy każdym wczytaniu. Ten sam plan,
dwie różne pule, zależnie od skóry i kolejności kliknięć.
"""

import json

from dancelab.gui.most import Most
from dancelab.stan import budowa, plan as SP
from dancelab.tui import plan_store


class _T:
    def __init__(self, tid):
        self.track_id, self.source_path = tid, f"/m/{tid}.aiff"
        self.bpm_estimate, self.key_estimate, self.title, self.artist = 128.0, "8A", tid, "X"
        self.duration_sec, self.style_label, self.sound_embedding = 300.0, None, None
        self.key_detection_source, self.key_confidence = None, None


class _A:
    def __init__(self, tid):
        self.track, self.features = _T(tid), []


def _atrapa_dokarmiania(monkeypatch):
    """Podmienia cztery `attach_*` znacznikiem — liczy, ile razy i na czym."""
    from dancelab.ingestion import analysis_enrichment as AE
    from dancelab.ingestion.analysis_enrichment import EnrichmentReport
    wywolania = []

    def zrob(nazwa):
        def f(analizy, *a, **k):
            analizy = list(analizy)
            wywolania.append((nazwa, len(analizy)))
            for x in analizy:
                setattr(x, f"dokarmione_{nazwa}", True)
            return EnrichmentReport(attached=len(analizy), missing=0)
        return f
    for n in ("attach_sound_embeddings", "attach_rekordbox_genres",
              "attach_rekordbox_keys", "attach_rekordbox_meta", "attach_apple_identity",
              "attach_apple_genres"):
        monkeypatch.setattr(AE, n, zrob(n))
    return wywolania


def test_dokarm_wola_cztery_zrodla_i_nazywa_liczby(monkeypatch):
    wyw = _atrapa_dokarmiania(monkeypatch)
    pula = [_A("a"), _A("b")]
    notki = budowa.dokarm(pula)
    assert [n for n, _ in wyw] == ["attach_sound_embeddings", "attach_rekordbox_genres",
                                   "attach_rekordbox_keys", "attach_rekordbox_meta",
                                   "attach_apple_identity", "attach_apple_genres"]
    assert any("wektory 2/2" in n and "tonacje RB 2/2" in n for n in notki)
    assert budowa.dokarmianie_padlo(notki) is None


def test_dokarm_bez_wektorow_i_awaria_wraca_jako_notka(monkeypatch):
    wyw = _atrapa_dokarmiania(monkeypatch)
    budowa.dokarm([_A("a")], wektory=False)
    assert "attach_sound_embeddings" not in [n for n, _ in wyw]

    from dancelab.ingestion import analysis_enrichment as AE
    def pada(*a, **k):
        raise RuntimeError("master.db zamknięta")
    monkeypatch.setattr(AE, "attach_rekordbox_keys", pada)
    notki = budowa.dokarm([_A("a")])
    assert budowa.dokarmianie_padlo(notki) == "dokarmianie nie wyszło: master.db zamknięta"


def test_okno_wczytuje_plan_na_dokarmionej_puli(monkeypatch, tmp_path):
    """Przed 02.09: `Most._pula()` nie dokarmiało — plan przed budową szedł surowo."""
    wyw = _atrapa_dokarmiania(monkeypatch)
    pula = [_A("a"), _A("b"), _A("c")]
    monkeypatch.setattr(budowa, "pula", lambda katalog: (list(pula), []))
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    monkeypatch.setattr(SP, "WSKAZNIK", tmp_path / "biezacy.json")
    plik = tmp_path / "plan_x.json"
    plik.write_text(json.dumps({"nazwa": "x", "kolejnosc": [
        {"track_id": "a", "path": "/m/a.aiff"}, {"track_id": "c", "path": "/m/c.aiff"}],
        "parametry": {}, "plan_silnika": ["a", "c"], "edycje": []}))

    m = Most(katalog=str(tmp_path))
    wynik = m._wczytaj_plan_teraz(str(plik))
    assert wynik["kolejnosc"] == ["a", "c"]
    assert wynik["plan_silnika"] == ["a", "c"] and wynik["edycje"] == []
    assert all(getattr(a, "dokarmione_attach_rekordbox_keys", False) for a in pula)
    # raz, nie przy każdym wczytaniu
    assert len(wyw) == 6
    m._wczytaj_plan_teraz(str(plik))
    assert len(wyw) == 6


def test_terminal_wczytuje_plan_ta_sama_droga(monkeypatch, tmp_path):
    """`_load_plan_worker` idzie przez `stan.plan.wczytaj` — jeden odczyt
    i jedno dopasowanie do puli dla obu skór."""
    from dancelab.tui.app import DanceLabTUI

    wyw = _atrapa_dokarmiania(monkeypatch)
    pula = [_A("a"), _A("b")]
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    plik = tmp_path / "plan_y.json"
    plik.write_text(json.dumps({"nazwa": "y", "kolejnosc": [
        {"track_id": "b", "path": "/m/b.aiff"}], "parametry": {},
        "plan_silnika": ["b"], "edycje": [{"typ": "ciecie"}]}))

    app = DanceLabTUI.__new__(DanceLabTUI)
    app._ctx = None
    app._library_analyses = lambda: (list(pula), [])
    notki = []
    app._note = lambda t: notki.append(t)
    app.call_from_thread = lambda f, *a, **k: f(*a, **k)
    app.query_one = lambda *a, **k: type("S", (), {"update": staticmethod(lambda *x: None)})()
    zaladowane = {}
    app._after_plan_load = lambda rec, order, notes: zaladowane.update(
        rec=rec, order=order, notes=notes)

    app._load_plan_worker.__wrapped__(app, str(plik)) if hasattr(
        app._load_plan_worker, "__wrapped__") else app._load_plan_worker(str(plik))

    assert zaladowane["order"] == ["b"]
    assert zaladowane["rec"]["edycje"] == [{"typ": "ciecie"}]
    assert zaladowane["rec"]["plan_silnika"] == ["b"]
    assert [n for n, _ in wyw][0] == "attach_sound_embeddings"     # plan: z wektorami


def test_niedokarmiona_pula_nie_trafia_do_cache_okna(monkeypatch, tmp_path):
    """Bramka „dokarmianie padło → odmowa budowy" musi działać także przy
    DRUGIEJ budowie. Wcześniej notki puli żyły w `_budowa`, który każda
    budowa podmienia, a pula siedziała w cache — pierwsza budowa odmawiała,
    druga szła po cichu na surowej puli."""
    pula = [_A("a"), _A("b")]
    monkeypatch.setattr(budowa, "pula", lambda katalog: (list(pula), ["higiena: 0"]))
    proby = []

    def dokarm(analizy, **k):
        proby.append(1)
        return ["dokarmianie nie wyszło: master.db zamknięta"] if len(proby) == 1 else ["dokarmianie: ok"]
    monkeypatch.setattr(budowa, "dokarm", dokarm)

    m = Most(katalog=str(tmp_path))
    m._pula()
    assert budowa.dokarmianie_padlo(m._notki_puli)          # pierwsze wejście: awaria
    assert m._analizy_pula is None                          # …i NIE w cache
    m._pula()
    assert len(proby) == 2                                  # drugie wejście dokarmia od nowa
    assert m._analizy_pula is not None and budowa.dokarmianie_padlo(m._notki_puli) is None
    m._pula()
    assert len(proby) == 2                                  # zdrowa pula zostaje w cache

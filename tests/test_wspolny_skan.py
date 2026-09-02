"""Faza 2, grupa 3a (02.09): jedna analiza folderu dla trybu Folder i skanu.

Terminal miał sekwencję „znajdź → bramkarz → analizuj" przepisaną dwa razy
(budowa i onboarding); okno nie miało jej wcale. Teraz jest jedna funkcja
z odmowami zamiast pustych wyników.
"""

import threading
import time

import pytest

from dancelab.gui.most import Most
from dancelab.stan import budowa


def _atrapy(monkeypatch, pliki, odrzucone=(), porazki=()):
    from dancelab.workflows import smart_playlist as SP
    from dancelab.ingestion import bramkarz as B
    from dancelab.core import config as C
    monkeypatch.setattr(SP, "discover_audio_files", lambda folder, **k: list(pliki))
    monkeypatch.setattr(B, "przesiej", lambda p, run_fn=None: (
        [x for x in p if x not in dict(odrzucone)], list(odrzucone)))
    monkeypatch.setattr(C, "load_config", lambda *a, **k: object())
    wywolania = {}

    def analyze_files(files, cfg, *, processed_dir=None, stage_progress=None, should_stop=None, **k):
        wywolania.update(files=list(files), processed_dir=processed_dir)
        for f in files:
            stage_progress(f, "quick")
        return [f"analiza:{f}" for f in files], list(porazki)
    monkeypatch.setattr(SP, "analyze_files", analyze_files)
    return wywolania


def test_przeanalizuj_folder_odmawia_gdy_nie_ma_czego(monkeypatch):
    _atrapy(monkeypatch, [])
    with pytest.raises(budowa.OdmowaBudowy, match="brak plików audio"):
        budowa.przeanalizuj_folder("/muzyka", "/proc")
    _atrapy(monkeypatch, ["/muzyka/a.wav"], odrzucone=[("/muzyka/a.wav", "52 min")])
    with pytest.raises(budowa.OdmowaBudowy, match="bramkarz odrzucił wszystko"):
        budowa.przeanalizuj_folder("/muzyka", "/proc")
    with pytest.raises(budowa.OdmowaBudowy, match="podaj ścieżkę"):
        budowa.przeanalizuj_folder("  ", "/proc")


def test_przeanalizuj_folder_liczy_i_raportuje(monkeypatch):
    wyw = _atrapy(monkeypatch, ["/m/a.aiff", "/m/b.aiff", "/m/zly.aiff"],
                  odrzucone=[("/m/zly.aiff", "stem")])
    etapy = []
    analizy, notki = budowa.przeanalizuj_folder("/m", "/proc", mow=etapy.append)
    assert analizy == ["analiza:/m/a.aiff", "analiza:/m/b.aiff"]
    assert wyw["processed_dir"] == "/proc"
    assert any("BRAMKARZ odrzucił: zly.aiff" in n for n in notki)
    assert notki[-1] == "przeanalizowane: 2 z 2 plików"
    assert etapy[0] == "Analiza 2 plików…" and "quick: a.aiff" in etapy


def test_okno_skanuje_w_tle_i_uniewaznia_pule(monkeypatch, tmp_path):
    _atrapy(monkeypatch, ["/m/a.aiff"])
    m = Most(katalog=str(tmp_path))
    m._spis, m._analizy_pula, m._notki_puli = [{"track_id": "x"}], ["stara"], ["n"]
    assert "podaj ścieżkę" in m.skanuj_folder("")["blad"]
    assert m.skanuj_folder("/m") == {"ruszylo": True}
    for _ in range(50):
        if m.postep_skanu()["stan"] != "trwa":
            break
        time.sleep(0.02)
    st = m.postep_skanu()
    assert st["stan"] == "gotowe" and st["przeanalizowane"] == 1, st
    assert (m._spis, m._analizy_pula, m._notki_puli) == ([], None, [])


def test_okno_skan_odmowa_wraca_z_powodem(monkeypatch, tmp_path):
    _atrapy(monkeypatch, [])
    m = Most(katalog=str(tmp_path))
    m.skanuj_folder("/pusto")
    for _ in range(50):
        if m.postep_skanu()["stan"] != "trwa":
            break
        time.sleep(0.02)
    st = m.postep_skanu()
    assert st["stan"] == "odmowa" and "brak plików audio" in st["blad"]


def test_terminal_skanuje_ta_sama_funkcja(monkeypatch):
    from dancelab.tui.app import DanceLabTUI
    _atrapy(monkeypatch, ["/m/a.aiff"])
    app = DanceLabTUI.__new__(DanceLabTUI)
    app.processed_dir = "/proc"
    app._stop = threading.Event()
    notki = []
    app._note = lambda t: notki.append(t)
    app.notify = lambda *a, **k: None
    app.call_from_thread = lambda f, *a, **k: f(*a, **k)
    app.query_one = lambda sel, *a: type("W", (), {"value": "/m", "update": staticmethod(lambda *x: None)})()
    app._library_analyses = lambda: (["a"], ["higiena"])
    ustawione = []
    app._set_library = ustawione.append
    app._lib_analyze_worker.__wrapped__(app) if hasattr(app._lib_analyze_worker, "__wrapped__") else app._lib_analyze_worker()
    assert ustawione == [["a"]]
    assert any("przeanalizowane: 1 z 1" in n for n in notki)

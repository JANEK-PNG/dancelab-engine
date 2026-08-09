"""Edytor cue etap 2 — warstwa edycji padów + klawisze w zakładce.

Model: propozycje silnika niezmienne, edycje DJ-a jako nakładka; ślad
silnika (silnik_ms) nie znika po przesunięciu — uczciwość „o ile się
różnimy". Z cofa po kroku. Klawisze: litera=pad, strzałki=uderzenia,
X=zdejmij (wszystko tylko w zakładce Eksport/Cue, zero zapisu).
"""

import asyncio

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.tui import cue_edycje, cue_podglad
from dancelab.tui.cue_podglad import zbuduj_plan_cue


def _analysis(track_id, *, title=""):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title,
                    source_path=f"/m/{track_id}.wav", duration_sec=360.0),
        beatgrid=BeatGrid(bpm=120.0, reliable=True),
        segments=[],
    )


def _okna_atrapa(analysis, weights):
    if analysis.track.track_id == "A":
        return [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9,
                                 window_type=WindowType.mix_out)]
    return [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9,
                             window_type=WindowType.mix_in)]


def _plan(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A", title="Alfa"),
             "B": _analysis("B", title="Beta")}
    return zbuduj_plan_cue(["A", "B"], by_id, weights=None), by_id


def test_przesun_liczy_uderzenia_i_pamieta_silnik(monkeypatch):
    plan, _ = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    przed = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    assert przed["zrodlo"] == "silnik" and przed["position_ms"] == 300000
    nowa = cue_edycje.przesun(ed, "A", "B", -8, 120.0,
                              przed["silnik_ms"], przed["position_ms"])
    assert nowa == 300000 - 8 * 500, "8 uderzeń przy 120 BPM = 4 s"
    po = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    assert po["zrodlo"] == "reka"
    assert po["silnik_ms"] == 300000, "ślad silnika nie znika"


def test_cofnij_wraca_po_kroku(monkeypatch):
    plan, _ = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    p = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    cue_edycje.przesun(ed, "A", "B", +1, 120.0, p["silnik_ms"],
                       p["position_ms"])
    cue_edycje.zdejmij(ed, "A", "B")
    assert "B" not in cue_edycje.efektywne_pady(plan, ed, "A")
    assert cue_edycje.cofnij(ed)
    assert cue_edycje.efektywne_pady(plan, ed, "A")["B"]["zrodlo"] == "reka"
    assert cue_edycje.cofnij(ed)
    assert cue_edycje.efektywne_pady(plan, ed, "A")["B"]["zrodlo"] == "silnik"
    assert not cue_edycje.cofnij(ed), "pusta historia mówi False"


def test_postaw_reczny_pad_i_zdejmij(monkeypatch):
    plan, _ = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    cue_edycje.postaw(ed, "A", "C", 123500)
    p = cue_edycje.efektywne_pady(plan, ed, "A")["C"]
    assert p["zrodlo"] == "reka" and p["silnik_ms"] is None
    cue_edycje.zdejmij(ed, "A", "C")
    assert "C" not in cue_edycje.efektywne_pady(plan, ed, "A")


def test_klawisze_w_zakladce_edytuja_pady(tmp_path, monkeypatch):
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            self_tabs = app.query_one("#tabs", TabbedContent)
            self_tabs.active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            assert app._cue_track == "A"

            await pilot.press("b")          # litera = wybór istniejącego pada
            assert app._cue_wybor == "B"

            await pilot.press("left")       # ±1 uderzenie po siatce
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 300000 - 500 and p["zrodlo"] == "reka"

            await pilot.press("d")          # brak pada D → nowy ręczny
            assert app._cue_wybor == "D"
            assert "D" in cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")

            await pilot.press("x")          # zdejmij wybrany
            assert "D" not in cue_edycje.efektywne_pady(
                plan, app._cue_edycje, "A")

            await pilot.press("z")          # cofnij zdjęcie
            assert "D" in cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")

    asyncio.run(go())


def test_p_gra_od_wybranego_pada_bez_dzwieku_w_testach(tmp_path, monkeypatch):
    """Etap 3 (skarga Janka 09.08: „nie mam pojęcia jak podsłuchać od A"):
    P z wybranym padem gra TEN utwór od pozycji pada; drugi raz stop.
    W testach odtwarzacz jest atrapą — dźwięk nigdy nie startuje sam."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)
    zagrane = []

    class Atrapa:
        def gra(self):
            return False

        sciezka = None

        def graj_od(self, path, bpm, sekunda):
            zagrane.append((path, sekunda))
            return None

        def graj_od_zera(self, path, bpm):
            zagrane.append((path, 0.0))
            return None

        def stop(self):
            return False

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()

            await pilot.press("b")          # pad B (wyjście @ 300 s)
            await pilot.press("p")
            assert zagrane == [("/m/A.wav", 300.0)], \
                "P gra utwór A od pozycji pada B"

    asyncio.run(go())


def test_cue_nazwa_nie_dubluje_artysty(monkeypatch):
    from dancelab.tui.app import DanceLabTUI

    plan, by_id = _plan(monkeypatch)
    by_id["A"].track.artist = "O'Flynn"
    by_id["A"].track.title = "O'Flynn - Sekete (ft. Swordman Kit)"
    app = DanceLabTUI.__new__(DanceLabTUI)
    app._ctx = {"by_id": by_id}
    assert app._cue_nazwa("A") == "O'Flynn – Sekete (ft. Swordman Kit)"


def test_znajdz_narzedzie_zna_gniazda_homebrew(tmp_path, monkeypatch):
    """Regresja 09.08: apka z ikony dostaje goły PATH launchd — ffplay
    z Homebrew musi się znaleźć mimo braku w PATH."""
    import dancelab.tui.odtwarzacz as odt

    monkeypatch.setattr(odt.shutil, "which", lambda n: None)
    narzedzie = tmp_path / "ffplay"
    narzedzie.write_text("#!/bin/sh\n")
    assert odt._znajdz("ffplay", katalogi=(str(tmp_path),)) == str(narzedzie)
    assert odt._znajdz("czegos_nie_ma", katalogi=(str(tmp_path),)) is None


def test_os_czasu_ma_glowice_w_miejscu_odtwarzania():
    """Oś czasu w pasku (decyzja Janka 09.08): energia utworu + głowica
    w miejscu odtwarzania + zegar; bez analizy NIC nie rysujemy."""
    from dancelab.core.models import FeatureFrame
    from dancelab.tui.pasek import os_z_glowica

    a = _analysis("A")            # duration_sec = 360
    a.features = [FeatureFrame(track_id="A", timestamp_sec=float(t),
                               rms=0.2 + (t % 60) / 100.0)
                  for t in range(0, 360, 5)]
    poczatek = os_z_glowica(a, 0.0, 40)
    srodek = os_z_glowica(a, 180.0, 40)
    assert poczatek.plain.index("▮") == 0, "na starcie głowica z lewej"
    assert srodek.plain.index("▮") == 20, "w połowie utworu — w połowie osi"
    assert "3:00 / 6:00" in srodek.plain, "zegar teraz/całość"
    assert os_z_glowica(None, 10.0, 40) is None, "bez analizy: brak rysunku"
    assert os_z_glowica(a, 10.0, 4) is None, "za wąsko: brak rysunku"


def test_karta_pokazuje_wszystkie_osiem_padow(tmp_path, monkeypatch):
    """Tabelka jak w Rekordboksie (życzenie Janka 09.08): sloty A–H są
    WIDOCZNE zawsze — puste mówią, że można tam postawić pad."""
    from textual.widgets import DataTable, Static, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            karta = str(app.query_one("#cue-card", Static).render())
            for litera in "ABCDEFGH":
                assert f"\n {litera}" in karta or f"\n▶{litera}" in karta \
                    or f"  {litera}" in karta, f"slot {litera} musi być widoczny"
            assert karta.count("pusty") == 7, "jeden pad zajęty, siedem wolnych"
            assert "naciśnij C, żeby postawić pad" in karta

    asyncio.run(go())

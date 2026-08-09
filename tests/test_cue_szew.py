"""Szew przeniesiony do Eksport/Cue (decyzja Janka 09.08).

Sedno przeniesienia: w Secie porównanie pary pokazywało szew z PROPOZYCJI
silnika, a na CDJ-e i tak jedzie to, co DJ ma na padach. Odsłuch mieszka
więc tam, gdzie stoją pady — i renderuje się DOKŁADNIE z ich pozycji.

Dźwięk w testach nie startuje nigdy: odtwarzacz i render są atrapami.
"""

import asyncio

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.tui import cue_edycje, cue_podglad, seam_preview
from dancelab.tui.cue_podglad import zbuduj_plan_cue


def _analysis(track_id, *, title=""):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title,
                    source_path=f"/m/{track_id}.wav", duration_sec=360.0,
                    bpm_estimate=120.0),
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


class _Atrapa:
    """Odtwarzacz-atrapa: zapisuje, co miałoby zagrać. Cisza."""

    sciezka = None

    def __init__(self):
        self.zagrane = []

    def gra(self):
        return False

    def graj_od(self, path, bpm, sekunda):
        self.zagrane.append((path, sekunda))
        return None

    def graj_od_zera(self, path, bpm):
        self.zagrane.append((path, 0.0))
        return None

    def stop(self):
        return False

    def pozycja(self):
        return 0.0

    def skonczyl_sie(self):
        return None

    def przelacz(self, path, bpm):
        self.zagrane.append((path, 0.0))
        return "start", None

    def opis(self):
        return ""


def test_szew_bierze_pozycje_z_padow_a_nie_z_propozycji(tmp_path,
                                                       monkeypatch):
    """Sedno: przesunięty pad zmienia SŁYSZANY szew. Gdyby render brał
    okna silnika, cue zostałoby na 300 s mimo przesunięcia."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)
    wywolania = []
    wav = tmp_path / "szew.wav"
    wav.write_bytes(b"")

    def render_atrapa(analysis_a, analysis_b, *, cue_a_sec, cue_b_sec):
        wywolania.append((analysis_a.track.track_id,
                          analysis_b.track.track_id, cue_a_sec, cue_b_sec))
        return {"output": wav, "cue_a_sec": cue_a_sec, "cue_b_sec": cue_b_sec,
                "bpm": 120.0, "rate_b": 1.0, "beats": 32,
                "rozumowanie": [], "zrodlo": "pady DJ-a"}

    monkeypatch.setattr(seam_preview, "zbuduj_szew_z_padow", render_atrapa)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = _Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()

            await pilot.press("b")            # pad wyjścia (300 s)
            await pilot.press("shift+left")   # −8 TAKTÓW = −32 uderzenia
            await pilot.press("s")            # S jak SZEW
            for _ in range(50):
                await pilot.pause(0.05)
                if wywolania:
                    break

            assert wywolania, "S ma zszyć parę z padów"
            tid_a, tid_b, cue_a, cue_b = wywolania[0]
            assert (tid_a, tid_b) == ("A", "B")
            assert cue_a == 284.0, "wyjście z PRZESUNIĘTEGO pada, nie z okna"
            assert cue_b == 30.0, "wejście z pada następnego utworu"
            assert app._odtwarzacz.zagrane == [(str(wav), 0.0)]

    asyncio.run(go())


def test_c_zostaje_padem_c(tmp_path, monkeypatch):
    """Litery A–H należą do padów CDJ i nic im ich nie odbiera —
    dlatego szew siedzi pod S, nie pod C."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = _Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()

            await pilot.press("c")
            assert app._cue_wybor == "C", "C stawia/wybiera pad C"
            assert "C" in cue_edycje.efektywne_pady(
                plan, app._cue_edycje, "A")

    asyncio.run(go())


def test_ostatni_utwor_odmawia_imiennie(tmp_path, monkeypatch):
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = _Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            tabela = app.query_one("#cue-table", DataTable)
            tabela.focus()
            tabela.move_cursor(row=1)
            app._cue_track = "B"
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()
            notki = " ".join(str(x) for x in app.query_one("#warnings").lines)
            assert "ostatni utwór nie ma następnika" in notki
            assert app._odtwarzacz.zagrane == [], "odmowa = cisza"

    asyncio.run(go())


def test_set_juz_nie_gra_szwu(tmp_path, monkeypatch):
    """W Secie zostaje sam FAKT o szwie: P gra zaznaczony UTWÓR nawet przy
    otwartym pasku porównania. Regresja odwrotna do starego zachowania."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            odt = _Atrapa()
            app._odtwarzacz = odt
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            tabela = app.query_one("#set", DataTable)
            tabela.add_columns("poz", "utwór")
            tabela.add_row("1", "Alfa")
            tabela.add_row("2", "Beta")
            tabela.focus()
            tabela.move_cursor(row=0)
            app._compare_idx = 0
            app.query_one("#compare").add_class("open")
            await pilot.pause()

            await pilot.press("p")
            for _ in range(20):
                await pilot.pause(0.05)
                if odt.zagrane:
                    break
            assert odt.zagrane == [("/m/A.wav", 0.0)], \
                "P w Secie gra UTWÓR — szwu słucha się w Eksport/Cue"

    asyncio.run(go())


def test_render_z_padow_dostaje_dokladnie_te_sekundy(tmp_path, monkeypatch):
    """Warstwa czysta: pozycje padów lądują w rendererze bez korekt."""
    import dancelab.preview.transition_simulation as ts

    by_id = {"A": _analysis("A"), "B": _analysis("B")}
    for tid, a in by_id.items():
        plik = tmp_path / f"{tid}.wav"
        plik.write_bytes(b"RIFF")
        a.track.source_path = str(plik)
    widziane = {}

    def render(**kw):
        widziane.update(kw)
        kw["output_path"].write_bytes(b"")

    monkeypatch.setattr(ts, "render_transition_preview", render)
    monkeypatch.setattr(seam_preview, "CACHE_DIR", tmp_path / "cache")

    info = seam_preview.zbuduj_szew_z_padow(
        by_id["A"], by_id["B"], cue_a_sec=296.0, cue_b_sec=30.0)

    assert widziane["cue_a_sec"] == 296.0
    assert widziane["cue_b_sec"] == 30.0
    assert widziane["bpm_master"] == 120.0
    assert info["beats"] == widziane["duration_beats"] > 0
    assert (tmp_path / "cache") in info["output"].parents

"""Odsłuch podąża za kursorem DJ-a — ale nie startuje tego samego pliku dwa razy.

Zmierzony błąd (14.08): na dwuutworowym secie automatyczne przejście
uruchamiało TRZY procesy odtwarzacza zamiast dwóch. Mechanizm:

  koniec A → `_nastepny` puszcza B i przesuwa kursor
           → ruch kursora uzbraja zegar podążania (0,12 s)
           → po 0,12 s B akurat nie gra → B startuje OD ZERA drugi raz.

W uchu DJ-a to zacięcie na każdej automatycznej zmianie utworu. Warunek
„już gra" był za słaby: liczy się to, czy plik jest W ODTWARZACZU, a nie
czy akurat leci.

Dźwięk w testach nie startuje nigdy: proces odtwarzacza jest atrapą.
"""

import asyncio
import subprocess

import dancelab.tui.odtwarzacz as odt
from dancelab.tui.app import DanceLabTUI


def _pula(*tids):
    class _T:
        def __init__(self, tid):
            self.track_id = tid
            self.source_path = f"/m/{tid}.mp3"
            self.duration_sec = 300.0
            self.bpm_estimate = 130.0
            self.key_estimate = "8A"
            self.key_confidence = 0.9
            self.style_label = "test"
            self.sound_embedding = None

    class _A:
        def __init__(self, tid):
            self.track = _T(tid)
            self.features = []

    return {tid: _A(tid) for tid in tids}


class _FakeProc:
    def __init__(self, cmd):
        self.cmd = cmd
        self.zakonczony = False

    def poll(self):
        return 0 if self.zakonczony else None

    def terminate(self):
        self.zakonczony = True


def _atrapa_procesow(monkeypatch):
    monkeypatch.setattr(odt, "FFPLAY", "/fake/ffplay")
    monkeypatch.setattr(odt, "AFPLAY", "/fake/afplay")
    started = []
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda cmd: started.append(_FakeProc(cmd)) or started[-1])
    return started


async def _set_dwoch(app, pilot, by_id):
    from textual.widgets import DataTable, TabbedContent
    app.query_one("#tabs", TabbedContent).active = "tab-set"
    await pilot.pause()
    app._ctx = dict(by_id=by_id, weights=None, arc="build", planner="smart",
                    bpm_min=None, bpm_max=None, anchor=None, params={})
    app._order = ["A", "B"]
    app._render_order(by_id)
    await pilot.pause()
    tabela = app.query_one("#set", DataTable)
    tabela.move_cursor(row=0)
    tabela.focus()
    return tabela


def test_kursor_na_utworze_ktory_jest_w_odtwarzaczu_nie_startuje_go_znowu(
        tmp_path, monkeypatch):
    """Sedno regresji: gdy plik spod kursora siedzi już w odtwarzaczu,
    zegar podążania MILCZY — nawet jeśli utwór właśnie się skończył."""
    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    started = _atrapa_procesow(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            by_id = _pula("A", "B")
            await _set_dwoch(app, pilot, by_id)
            await pilot.press("space")            # gra A
            await pilot.pause()
            assert len(started) == 1

            started[0].zakonczony = True          # A skończył się SAM
            app._tick_player()                    # → gra B, kursor na B
            await pilot.pause()
            assert len(started) == 2

            # kluczowy moment: B kończy się w oknie debounce'u (0,12 s)
            started[1].zakonczony = True
            await pilot.pause(0.3)                # zegar podążania zdążył
            assert len(started) == 2, \
                "utwór z odtwarzacza nie ma prawa ruszyć drugi raz"

    asyncio.run(go())


def test_ruch_kursora_dj_a_przelacza_odsluch(tmp_path, monkeypatch):
    """Druga strona tej samej monety: podążanie za kursorem MA działać,
    gdy DJ sam przesunie zaznaczenie na inny utwór."""
    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    started = _atrapa_procesow(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            by_id = _pula("A", "B")
            tabela = await _set_dwoch(app, pilot, by_id)
            await pilot.press("space")            # gra A
            await pilot.pause()
            assert started[0].cmd[-1] == "/m/A.mp3"

            tabela.move_cursor(row=1)             # DJ przesuwa kursor na B
            for _ in range(30):
                await pilot.pause(0.05)
                if len(started) > 1:
                    break
            assert len(started) == 2, "kursor na nowym utworze = ten utwór gra"
            assert started[1].cmd[-1] == "/m/B.mp3"

    asyncio.run(go())

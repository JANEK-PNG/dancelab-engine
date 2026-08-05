"""TUI (Ekran 1) i produktowy zapis playlist — granice bezpieczeństwa.

Nie testujemy tu Textuala; testujemy NASZE reguły: parser okna tempa mówi
dlaczego odmawia, zapis odmawia przy otwartym Rekordboksie zanim czegokolwiek
dotknie, a aplikacja wstaje i ma wszystkie pola formularza.
"""

from __future__ import annotations

import asyncio

import dancelab.ingestion.playlist_publish as publish_mod
from dancelab.ingestion.playlist_publish import publish_playlist
from dancelab.tui.app import (
    DanceLabTUI, _format_track_info, _mode_params, _parse_bpm)


def test_karta_info_nazywa_zrodla_i_mowi_czego_nie_wie():
    class _T:
        bpm_estimate = 131.5
        key_estimate = "8A"
        key_confidence = 0.83
        style_label = "UK Garage"
        duration_sec = 245.0
        sound_embedding = [0.1]
        source_path = "/m/x/a [remix].mp3"

    rb = {"bpm": 132.0, "comment": "bangier", "matched_by": "path",
          "playlists": ["DanceLab/piatek", "ulubione"]}
    txt = _format_track_info(_T(), rb, None)
    assert "SILNIK" in txt and "131.5" in txt and "8A" in txt
    assert "/m/x/a [remix].mp3" in txt                      # lokalizacja na dysku
    assert "BPM wg Rekordboxa: 132.0" in txt                # źródło nazwane
    assert "DanceLab/piatek" in txt and "ulubione" in txt   # playlisty z master.db
    assert "bangier" in txt

    assert "nie ma w kolekcji" in _format_track_info(_T(), None, None)
    assert "master.db nieodczytany: pad" in \
        _format_track_info(_T(), None, "master.db nieodczytany: pad")


def test_tryby_sugestii_mapuja_na_tryby_silnika():
    """bpm/harmonic = oficjalne tryby plannera, bez kotwicy; smart = kontekst
    budowy Z kotwicą — panel nie może mieć innego gustu niż budowa."""
    ctx = {"planner": "smart", "anchor": [0.1, 0.2]}
    assert _mode_params("bpm", ctx) == ("bpm", None)
    assert _mode_params("harmonic", ctx) == ("harmonic", None)
    assert _mode_params("smart", ctx) == ("smart", [0.1, 0.2])


def test_parse_bpm_poprawne_i_puste():
    assert _parse_bpm("128-140") == (128.0, 140.0, None)
    assert _parse_bpm(" 130 - 135 ") == (130.0, 135.0, None)
    assert _parse_bpm("") == (None, None, None)


def test_parse_bpm_odmawia_z_powodem():
    for zle in ("140", "abc-def", "140-130"):
        lo, hi, err = _parse_bpm(zle)
        assert lo is None and hi is None and err, zle


def test_zapis_odmawia_przy_otwartym_rekordboksie(monkeypatch):
    """Odmowa PRZED dotknięciem bazy — bez backupu, bez połączenia."""
    monkeypatch.setattr(publish_mod, "rekordbox_running", lambda: True)
    report = publish_playlist(["/x/a.mp3"], name="test")
    assert not report.ok and report.written == 0 and report.backup_path is None
    assert any("zamknij" in n.lower() for n in report.notes)


def test_tui_wstaje_i_ma_formularz():
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            for wid in ("#pool", "#minutes", "#bpm", "#styles", "#dj",
                        "#contour", "#arc", "#tempo", "#planner", "#set",
                        "#warnings", "#status"):
                assert app.query_one(wid) is not None, wid
            await pilot.pause()
            # pasek statusu mówi o stanie Rekordboxa — kanał uczciwości
            status = str(app.query_one("#status").render())
            assert "Rekordbox" in status
    asyncio.run(go())


def test_tui_edycje_bez_setu_odmawiaja_z_powodem():
    """X/A/S/V/Z przed budową = odmowa z powodem, nie traceback."""
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            for key in ("x", "a", "s", "v", "z", "i"):
                await pilot.press(key)
                await pilot.pause()
            lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
            assert lines.count("najpierw zbuduj") >= 6
    asyncio.run(go())


def _fake_pool(*tids):
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


def test_tui_ciecie_i_przesuniecie_loguja_werdykty(tmp_path, monkeypatch):
    """X wycina, Shift+↑ przesuwa; oba ruchy lądują w dzienniku werdyktów."""
    import dancelab.tui.app as app_mod
    monkeypatch.setattr(app_mod, "WERDYKTY_DIR", tmp_path)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            by_id = _fake_pool("A", "B", "C")
            app._ctx = dict(by_id=by_id, weights=None, arc="build",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None, params={})
            app._order = ["A", "B", "C"]
            app._engine_order = ["A", "B", "C"]
            app._render_order(by_id)
            await pilot.pause()
            from textual.widgets import DataTable
            table = app.query_one("#set", DataTable)
            table.move_cursor(row=1)
            table.focus()
            await pilot.press("x")            # wycina B
            await pilot.pause()
            assert app._order == ["A", "C"]
            await pilot.press("shift+up")     # C przed A
            await pilot.pause()
            assert app._order == ["C", "A"]
            await pilot.press("v")            # świadomy werdykt
            await pilot.pause()
            assert len(app._edits) == 2

            # notki schowane domyślnie, L pokazuje; poświata pomalowała sąsiada
            from textual.widgets import Log
            log = app.query_one("#warnings", Log)
            assert not log.has_class("open")
            await pilot.press("l")
            await pilot.pause()
            assert log.has_class("open")
            from textual.coordinate import Coordinate
            from rich.text import Text
            bpm_cell = table.get_cell_at(Coordinate(0, 1))
            assert isinstance(bpm_cell, Text)    # BPM na podkładce tła
            assert "on #" in str(bpm_cell.style)
    asyncio.run(go())

    log = (tmp_path / "tui_edycje.jsonl").read_text().splitlines()
    assert len(log) == 2 and '"ciecie"' in log[0] and '"przesuniecie"' in log[1]
    werdykty = list(tmp_path.glob("tui_werdykt_*.json"))
    assert len(werdykty) == 1
    tekst = werdykty[0].read_text()
    assert '"plan_silnika"' in tekst and '"stan_dja"' in tekst


def test_tui_budowa_bez_kotwicy_nie_pada_na_noselection():
    """Regres 05.08: puste „Graj jak…" dawało obiekt NoSelection zamiast None
    i budowa padała na ODMOWIE zanim doszła do puli. Prawidłowa odmowa przy
    pustej puli to „pusta pula", nigdy NoSelection."""
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            await pilot.press("b")
            for _ in range(40):
                await pilot.pause(0.1)
                lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
                if "ODMOWA" in lines:
                    break
            assert "NoSelection" not in lines
            assert "pusta pula" in lines
    asyncio.run(go())


def test_tui_odmowa_budowy_pokazuje_powod():
    """Pusta pula = ODMOWA z powodem w panelu ostrzeżeń, nie traceback."""
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            await pilot.press("b")
            for _ in range(40):                    # worker w wątku — czekamy krótko
                await pilot.pause(0.1)
                lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
                if "ODMOWA" in lines:
                    break
            assert "ODMOWA" in lines
    asyncio.run(go())


def test_p_odtwarza_i_zatrzymuje_bez_prawdziwego_dzwieku(tmp_path, monkeypatch):
    """P renderuje szew i startuje odtwarzacz; drugie P zatrzymuje; ostatni
    utwór odmawia. Dźwięk i render podmienione atrapami — weryfikacja NIGDY
    nie gra audio (twarda zasada projektu)."""
    import subprocess

    class _FakeProc:
        def __init__(self, cmd):
            self.cmd = cmd
            self.killed = False

        def poll(self):
            return 1 if self.killed else None

        def terminate(self):
            self.killed = True

    started = []
    monkeypatch.setattr(subprocess, "Popen",
                        lambda cmd: started.append(_FakeProc(cmd)) or started[-1])
    import dancelab.tui.seam_preview as sp
    wav = tmp_path / "szew.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(sp, "zbuduj_szew", lambda a, b, w: {
        "output": wav, "beats": 64, "bpm": 130.0, "rozumowanie": []})

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            by_id = _fake_pool("A", "B")
            app._ctx = dict(by_id=by_id, weights=None, arc="build",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None, params={})
            app._order = ["A", "B"]
            app._render_order(by_id)
            await pilot.pause()
            table = app.query_one("#set", DataTable)
            table.move_cursor(row=0)
            table.focus()
            await pilot.press("p")
            for _ in range(50):
                await pilot.pause(0.1)
                if app._player is not None:
                    break
            assert started and "afplay" in started[0].cmd[0]
            assert str(wav) in started[0].cmd[1]
            await pilot.press("p")            # drugie P zatrzymuje
            await pilot.pause()
            assert started[0].killed
            table.move_cursor(row=1)          # ostatni utwór — odmowa
            await pilot.pause()
            await pilot.press("p")
            await pilot.pause()
            assert len(started) == 1, "nie wystartował drugi odtwarzacz"
            lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
            assert "ostatni utwór nie ma następnika" in lines
    asyncio.run(go())

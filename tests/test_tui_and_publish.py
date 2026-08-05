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
            assert isinstance(bpm_cell, Text)    # BPM wyróżniony boldem
            assert "bold" in str(bpm_cell.style)  # bold, nie tło — oba motywy
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


def test_p_kontekstowe_pauza_skoki_i_szew(tmp_path, monkeypatch):
    """Nowy odtwarzacz (ffplay): P gra utwór / pauzuje / wznawia; →/← skacze
    ±8 uderzeń wg tempa TYLKO gdy gra; przy otwartym pasku szwu P gra
    przejście. Dźwięk = atrapy — weryfikacja NIGDY nie gra audio."""
    import subprocess
    import dancelab.tui.odtwarzacz as odt
    monkeypatch.setattr(odt, "FFPLAY", "/fake/ffplay")

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
    monkeypatch.setattr(sp, "zbuduj_szew", lambda a, b, w, **kw: {
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
            table.move_cursor(row=1)
            table.focus()

            # → bez grania NIE startuje odtwarzacza (strzałka zostaje tabeli)
            await pilot.press("right")
            await pilot.pause()
            assert started == []

            await pilot.press("p")            # P = alias spacji
            await pilot.pause()
            assert started[0].cmd[0] == "/fake/ffplay"
            assert started[0].cmd[-1] == "/m/B.mp3"
            assert float(started[0].cmd[started[0].cmd.index("-ss") + 1]) == 0.0

            await pilot.press("right")        # skok +8 uderzeń @130 ≈ 3,69 s
            await pilot.pause()
            assert started[0].killed
            ss = float(started[1].cmd[started[1].cmd.index("-ss") + 1])
            assert 3.3 < ss < 4.3, f"skok o 8 uderzen, dostalem {ss}"

            await pilot.press("p")            # pauza
            await pilot.pause()
            assert started[1].killed
            await pilot.press("p")            # wznowienie od miejsca
            await pilot.pause()
            ss2 = float(started[2].cmd[started[2].cmd.index("-ss") + 1])
            assert ss2 >= ss and started[2].cmd[-1] == "/m/B.mp3"

            # pasek szwu otwarty → P gra PRZEJŚCIE
            await pilot.press("p")            # pauza utworu
            await pilot.pause()
            app._compare_idx = 0
            app.query_one("#compare").add_class("open")
            await pilot.press("p")
            for _ in range(50):
                await pilot.pause(0.1)
                if len(started) > 3:
                    break
            assert started[3].cmd[-1] == str(wav), "P przy pasku szwu = szew"
    asyncio.run(go())


def test_gdy_gra_strzalka_przelacza_jak_next_song(tmp_path, monkeypatch):
    """Wzorzec Quick Look / next-song: gdy coś GRA, ↓ przełącza odtwarzanie
    na nowo zaznaczony utwór (stary proces ubity — zero nakładki);
    przy pauzie strzałki tylko chodzą po liście."""
    import subprocess
    import dancelab.tui.odtwarzacz as odt
    monkeypatch.setattr(odt, "FFPLAY", "/fake/ffplay")

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

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            by_id = _fake_pool("A", "B", "C")
            app._ctx = dict(by_id=by_id, weights=None, arc="build",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None, params={})
            app._order = ["A", "B", "C"]
            app._render_order(by_id)
            await pilot.pause()
            table = app.query_one("#set", DataTable)
            table.move_cursor(row=0)
            table.focus()

            await pilot.press("space")        # spacja = graj (standard)
            await pilot.pause()
            assert started and started[0].cmd[-1] == "/m/A.mp3"

            await pilot.press("down")         # gra → ↓ = next song
            for _ in range(30):
                await pilot.pause(0.1)
                if len(started) > 1:
                    break
            assert started[0].killed, "zero nakładki"
            assert started[1].cmd[-1] == "/m/B.mp3"

            await pilot.press("space")        # pauza
            await pilot.pause()
            assert started[1].killed
            await pilot.press("down")         # pauza → ↓ tylko zaznacza
            await pilot.pause(0.5)
            assert len(started) == 2, "przy pauzie strzałka NIE gra"
    asyncio.run(go())

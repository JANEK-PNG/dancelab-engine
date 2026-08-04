"""TUI (Ekran 1) i produktowy zapis playlist — granice bezpieczeństwa.

Nie testujemy tu Textuala; testujemy NASZE reguły: parser okna tempa mówi
dlaczego odmawia, zapis odmawia przy otwartym Rekordboksie zanim czegokolwiek
dotknie, a aplikacja wstaje i ma wszystkie pola formularza.
"""

from __future__ import annotations

import asyncio

import dancelab.ingestion.playlist_publish as publish_mod
from dancelab.ingestion.playlist_publish import publish_playlist
from dancelab.tui.app import DanceLabTUI, _parse_bpm


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
            for key in ("x", "a", "s", "v", "z"):
                await pilot.press(key)
                await pilot.pause()
            lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
            assert lines.count("najpierw zbuduj") >= 5
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
    asyncio.run(go())

    log = (tmp_path / "tui_edycje.jsonl").read_text().splitlines()
    assert len(log) == 2 and '"ciecie"' in log[0] and '"przesuniecie"' in log[1]
    werdykty = list(tmp_path.glob("tui_werdykt_*.json"))
    assert len(werdykty) == 1
    tekst = werdykty[0].read_text()
    assert '"plan_silnika"' in tekst and '"stan_dja"' in tekst


def test_tui_odmowa_budowy_pokazuje_powod():
    """Pusta pula = ODMOWA z powodem w panelu ostrzeżeń, nie traceback."""
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            await pilot.press("b")
            for _ in range(40):                    # worker w wątku — czekamy krótko
                await pilot.pause(0.1)
                lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
                if "ODMOWA" in lines:
                    break
            assert "ODMOWA" in lines
    asyncio.run(go())

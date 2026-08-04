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

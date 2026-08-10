"""Budowa z kotwicą „★ moje ulubione" — CAŁA ścieżka w aplikacji.

Dwa razy 09.08 wywaliłem budowę zmianą w tej ścieżce (`ui` i `notes` — obie
zmienne nie istniały w tym miejscu), a testy tego nie łapały, bo żaden nie
przechodził jej w TUI. Ten test przechodzi.
"""

import asyncio

from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track


def _pula(katalog, ile: int = 14) -> list[str]:
    from dancelab.storage.repositories import FileAnalysisRepository

    repo = FileAnalysisRepository(katalog)
    ids = []
    for i in range(ile):
        tid = f"t{i:02d}"
        a = AnalysisResult(
            engine_version="test",
            track=Track(track_id=tid, source_path=f"itest:track:{i}",
                        title=f"Utwór {i}", bpm_estimate=128.0,
                        key_estimate="8A", duration_sec=300.0,
                        sound_embedding=[1.0, i * 0.01, 0.5]),
            beatgrid=BeatGrid(bpm=128.0, reliable=True),
            features=[FeatureFrame(track_id=tid, timestamp_sec=float(s),
                                   rms=0.5) for s in range(0, 300, 30)])
        repo.save(a)
        ids.append(tid)
    return ids


def test_kotwica_z_ulubionych_buduje_set(tmp_path):
    from textual.widgets import Input, Select, TabbedContent

    from dancelab.decision.anchors import MOJE_ULUBIONE
    from dancelab.tui import user_store
    from dancelab.tui.app import DanceLabTUI

    pula = tmp_path / "pula"
    pula.mkdir()
    ids = _pula(pula)
    stan = user_store.load_state(str(pula))
    stan["ulubione_utwory"] = [{"track_id": t, "path": f"itest:track:{i}"}
                               for i, t in enumerate(ids[:4])]
    user_store.save_state(stan, str(pula))

    async def go():
        app = DanceLabTUI(processed_dir=str(pula))
        async with app.run_test(size=(120, 38)) as pilot:
            for _ in range(200):
                if app._lib:
                    break
                await asyncio.sleep(0.05)
            assert app._lib, "pula testowa się nie wczytała"

            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            app.query_one("#dj", Select).value = MOJE_ULUBIONE
            app.query_one("#minutes", Input).value = "20"
            await pilot.pause()

            app.action_build()
            for _ in range(400):
                await asyncio.sleep(0.05)
                if app._order:
                    break
            assert app._order, "budowa z własną kotwicą nie dała setu"
            notki = " ".join(str(x) for x in app.query_one("#warnings").lines)
            assert "kotwica z Twoich ulubionych" in notki, \
                "DJ ma wiedzieć, z czego policzyliśmy kotwicę"

    asyncio.run(go())

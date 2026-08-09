"""Zrzuty ekranu do instrukcji → docs/zrzuty/*.svg.

Powtarzalność zamiast ręcznych zrzutów: instrukcja pokazywała przełącznik
podpisany „artwork" długo po tym, jak w programie nazwano go „okładki".
Zrzut, który kłamie, jest gorszy niż jego brak.

Użycie (wczytuje NAJNOWSZY zapisany plan, żeby zakładki miały treść):
    .venv/bin/python scripts/zrzuty_dokumentacji.py

Zakładka Eksport / Cue jest zrzucana w stanie „Rekordbox zamknięty" —
to stan, w którym DJ faktycznie wysyła cue. Sprawdzanie procesu jest na
czas zrzutu wyłączone; nic nie jest zapisywane do żadnej bazy.
"""

from __future__ import annotations

import asyncio
import pathlib

KORZEN = pathlib.Path(__file__).resolve().parent.parent
ZRZUTY = KORZEN / "docs" / "zrzuty"
ROZMIAR = (120, 38)


async def _czekaj(warunek, sekund: float, opis: str) -> None:
    for _ in range(int(sekund * 10)):
        if warunek():
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(opis)


async def go() -> None:
    from textual.widgets import Static, TabbedContent

    import dancelab.ingestion.playlist_publish as PP
    from dancelab.tui.app import PROCESSED_DEFAULT, DanceLabTUI
    from dancelab.tui.plan_store import match_order, read_plan

    ZRZUTY.mkdir(parents=True, exist_ok=True)
    PP.rekordbox_running = lambda: False   # zrzut stanu roboczego, zero zapisu

    app = DanceLabTUI(processed_dir=str(PROCESSED_DEFAULT))
    async with app.run_test(size=ROZMIAR) as pilot:
        await _czekaj(lambda: app._lib, 180, "biblioteka nie wstała")
        await pilot.pause()
        app.save_screenshot(str(ZRZUTY / "biblioteka.svg"))
        print("biblioteka.svg")

        plany = sorted((KORZEN / "data/exports/tui_plany").glob("*.json"))
        if not plany:
            print("brak zapisanych planów — Set i Cue pominięte")
            return
        rec = read_plan(str(plany[-1]))
        ctx = await asyncio.to_thread(app._pool_ctx_for, rec.get("parametry", {}))
        app._ctx = ctx
        order, notes = match_order(rec, ctx["by_id"])
        app._after_plan_load(rec, order, notes)
        await pilot.pause()

        app.query_one("#tabs", TabbedContent).active = "tab-set"
        await pilot.pause()
        app.save_screenshot(str(ZRZUTY / "set.svg"))
        print("set.svg")

        app.query_one("#tabs", TabbedContent).active = "tab-export"
        await pilot.pause()
        await _czekaj(
            lambda: "Pady bieżącego setu" in str(
                app.query_one("#cue-head", Static).render()),
            300, "podgląd cue się nie policzył")
        app._refresh_status()
        await pilot.pause()
        app.save_screenshot(str(ZRZUTY / "cue.svg"))
        print("cue.svg")


if __name__ == "__main__":
    asyncio.run(go())

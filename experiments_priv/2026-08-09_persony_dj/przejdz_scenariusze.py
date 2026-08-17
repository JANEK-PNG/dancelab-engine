"""Osobna instancja aplikacji dla każdej persony + jej scenariusz.

Testujemy APLIKACJĘ, nie gust: interesuje nas, co program ROBI i CO MÓWI,
gdy dostanie bibliotekę o innym kształcie. Każda persona dostaje własny
katalog puli, więc instancje niczego o sobie nie wiedzą.

Zapisuje przebieg do WYNIKI.md obok tego pliku.

Użycie:
    .venv/bin/python experiments_priv/2026-08-09_persony_dj/przejdz_scenariusze.py [persona ...]
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
KATALOG = pathlib.Path(__file__).resolve().parent
PULE = KATALOG / "pule"

# persona → (kotwica, gatunek w briefie, minuty)
SCENARIUSZE = {
    # marta: mała pula, leftfield — sprawdzamy rozluźnianie sit
    "marta":  ("Ben UFO", "", 40),
    # bartek: wesela, ogromna rozpiętość tempa i gatunki spoza taksonomii
    "bartek": ("Peggy Gou", "", 60),
    # kuba: techno; JEGO kotwica (Amelie Lens) NIE MA wpisu w księdze 284 DJ-ów
    "kuba":   ("Amelie Lens", "Techno (Peak Time / Driving)", 120),
    # zosia: pierwszy rok — bez kotwicy, bez gatunku, długi set
    "zosia":  ("", "", 120),
}


async def przejdz(nazwa: str, raport: list[str]) -> None:
    from textual.widgets import Input, Select, Static, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    kot, gat, minuty = SCENARIUSZE[nazwa]
    pula = PULE / nazwa
    raport.append(f"\n## {nazwa}\n")
    raport.append(f"pula: `{pula.name}` · brief: {minuty} min"
                  + (f" · gatunek: {gat}" if gat else " · bez gatunku")
                  + (f" · kotwica: {kot}" if kot else " · bez kotwicy") + "\n")

    app = DanceLabTUI(processed_dir=str(pula))
    async with app.run_test(size=(120, 38)) as pilot:
        for _ in range(1200):
            if app._lib:
                break
            await asyncio.sleep(0.1)
        raport.append(f"- Biblioteka wczytana: **{len(app._lib)} utworów**")

        app.query_one("#tabs", TabbedContent).active = "tab-set"
        await pilot.pause()
        app.query_one("#minutes", Input).value = str(minuty)
        if gat:
            app.query_one("#styles", Input).value = gat
        if kot:
            wybor = app.query_one("#dj", Select)
            dostepne = [w for _e, w in (wybor._options or [])]
            if kot in dostepne:
                wybor.value = kot
                raport.append(f"- kotwica `{kot}`: **jest w księgi kotwic**")
            else:
                raport.append(f"- kotwica `{kot}`: **NIE MA jej w księdze** "
                              f"({len(dostepne)} dostępnych) — persona nie "
                              f"może jej wybrać")
        await pilot.pause()

        app.action_build()
        for _ in range(2400):
            await asyncio.sleep(0.1)
            if app._order:
                break
        if not app._order:
            raport.append("- **BUDOWA NIE DAŁA SETU**")
        else:
            by = app._ctx["by_id"]
            raport.append(f"- zbudowany set: **{len(app._order)} utworów**")
            wiersze = ["", "| # | BPM | ton | utwór |", "|---|---|---|---|"]
            for i, tid in enumerate(app._order[:6], 1):
                t = by[tid].track
                nazwa_u = ((t.artist + " – ") if t.artist else "") + (t.title or "?")
                wiersze.append(f"| {i} | {t.bpm_estimate or 0:.1f} | "
                               f"{t.key_estimate or '?'} | {nazwa_u[:44]} |")
            raport.extend(wiersze)

        # odsłuch pierwszego utworu — co program powie
        if app._order:
            from textual.widgets import DataTable
            tab = app.query_one("#set", DataTable)
            tab.focus(); tab.move_cursor(row=0)
            await pilot.press("p")
            await pilot.pause()

        notki = [str(x) for x in app.query_one("#warnings").lines]
        raport.append("\n**Co program powiedział:**\n")
        for n in notki[-14:]:
            raport.append(f"- {n.strip()[:150]}")
        app.query_one("#status", Static)


async def main() -> int:
    kogo = sys.argv[1:] or list(SCENARIUSZE)
    raport = ["# Persony — przebieg scenariuszy", "",
              "Każda persona = osobna instancja aplikacji na własnej puli.", ""]
    for nazwa in kogo:
        print(f"→ {nazwa}", flush=True)
        try:
            await przejdz(nazwa, raport)
        except Exception as exc:  # noqa: BLE001 — awaria to też wynik testu
            raport.append(f"\n## {nazwa}\n\n- **APLIKACJA SIĘ WYWALIŁA**: "
                          f"`{type(exc).__name__}: {exc}`")
            print(f"   wywrotka: {type(exc).__name__}: {exc}", flush=True)
    (KATALOG / "WYNIKI.md").write_text("\n".join(raport) + "\n")
    print(f"\nzapisane: {KATALOG / 'WYNIKI.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

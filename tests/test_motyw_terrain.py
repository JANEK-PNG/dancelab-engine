"""Motyw TERRAIN w TUI (decyzja Janka 12.08: kolory z makiet GUI).

Przybite, żeby żaden refaktor nie cofnął po cichu palety do monokai:
volt na primary, grafit w tle, talie A/B w accent/secondary.
"""

from __future__ import annotations

import asyncio

from dancelab.tui.app import DanceLabTUI


def test_tui_wstaje_w_palecie_terrain():
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            assert app.theme == "dancelab-terrain"
            motyw = app.available_themes["dancelab-terrain"]
            assert str(motyw.primary).lower() == "#d6f549"      # volt
            assert str(motyw.background).lower() == "#171614"   # grafit
            assert str(motyw.accent).lower() == "#e0a458"       # talia A
            assert str(motyw.secondary).lower() == "#6db3c9"    # talia B
            assert motyw.dark
    asyncio.run(go())

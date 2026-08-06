"""`dancelab tui` — wykrywanie grafiki terminala musi zajść PRZED Textual.

textual-image wybiera protokół (TGP/Sixel/półbloki) raz, przy imporcie,
odpytując terminal i czekając na odpowiedź na stdin. Gdy Textual już działa,
jego czytnik stdin zjada odpowiedź i wykrywanie zawsze pada — Ghostty
dostawał wtedy mozaikę zamiast ostrych okładek (zrzut Janka, 08.08).
Ten test pilnuje, żeby import textual_image nie wrócił do leniwego.
"""

import sys

from typer.testing import CliRunner

from dancelab.cli.analyze import app

runner = CliRunner()


def test_tui_imports_textual_image_before_app_starts(monkeypatch):
    kolejnosc = []

    class AtrapaTUI:
        def __init__(self, processed_dir):
            pass

        def run(self):
            kolejnosc.append("textual_image.renderable" in sys.modules)

    import dancelab.tui.app as tui_app
    monkeypatch.setattr(tui_app, "DanceLabTUI", AtrapaTUI)
    monkeypatch.delitem(sys.modules, "textual_image.renderable", raising=False)
    monkeypatch.delitem(sys.modules, "textual_image", raising=False)

    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 0, result.output
    assert kolejnosc == [True], (
        "textual_image.renderable ma być zaimportowany zanim ruszy aplikacja"
    )


def test_ostry_renderer_rozpoznaje_po_module_nie_po_nazwie(monkeypatch):
    """Każda klasa textual-image nazywa się dosłownie `Image` — aliasy
    TGPImage/SixelImage istnieją tylko w imporcie. Warunek po __name__
    nigdy nie był prawdziwy (druga przyczyna mozaiki w Ghostty)."""
    import textual_image.renderable as tir
    from textual_image.renderable.halfcell import Image as Polbloki
    from textual_image.renderable.sixel import Image as Sixel
    from textual_image.renderable.tgp import Image as TGP

    from dancelab.tui.okladki import _ostry_renderer

    monkeypatch.setattr(tir, "Image", TGP)
    assert _ostry_renderer() is TGP, "TGP (Ghostty/kitty) ma dawać ostrą klasę"
    monkeypatch.setattr(tir, "Image", Sixel)
    assert _ostry_renderer() is Sixel, "Sixel (iTerm2/WezTerm) też jest ostry"
    monkeypatch.setattr(tir, "Image", Polbloki)
    assert _ostry_renderer() is None, "półbloki = zostajemy przy naszej mozaice"


def test_przelacznik_artwork_scala_galerie_i_synchronizacje(tmp_path, monkeypatch):
    """Decyzja Janka (08.08): zamiast przycisku mały toggle — ON pokazuje
    okładki w liście I dociąga brakujące; OFF tylko chowa (zero kasowania,
    zero dociągania). K jest klawiszowym wejściem tej samej dźwigni."""
    import asyncio

    import dancelab.tui.user_store as store
    from textual.widgets import Switch

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")
    wywolania = []
    monkeypatch.setattr(DanceLabTUI, "_artwork_worker",
                        lambda self: wywolania.append("sync"))

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            przelacznik = app.query_one("#lib-artwork", Switch)
            przelacznik.value = True
            await pilot.pause()
            assert app._user_state["okladki_w_liscie"] is True
            assert wywolania == ["sync"], "ON = galeria + dociąganie braków"
            przelacznik.value = False
            await pilot.pause()
            assert app._user_state["okladki_w_liscie"] is False
            assert app._artwork_przerwij.is_set(), "OFF przerywa dociąganie"
            assert wywolania == ["sync"], "OFF niczego nie dociąga i nie kasuje"

    asyncio.run(go())


def test_kursor_nie_kasuje_okladek_w_liscie():
    """Obrazek TGP koduje SIEBIE w kolorze pisma (kolor znaku = id obrazka
    dla terminala). Domyślny kursor DataTable nadpisuje kolor wiersza →
    okładka pod kursorem znikała (zrzut Janka, 08.08). Priorytet
    'renderable' oddaje kolor treści."""
    import asyncio

    from textual.widgets import DataTable

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test():
            tabela = app.query_one("#lib-table", DataTable)
            assert tabela.cursor_foreground_priority == "renderable"

    asyncio.run(go())

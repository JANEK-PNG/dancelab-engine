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

"""Gatunki wg taksonomii Beatportu (decyzja Janka 09.08).

Nazwa gatunku jest CAŁOŚCIĄ: „140 / Deep Dubstep / Grime" to jeden gatunek,
nie trzy. Wcześniejsza propozycja rozbijania po ukośniku wymyślałaby byty
(„140" nie jest gatunkiem) — te testy pilnują, że tego nie robimy, i że tag
spoza taksonomii nie znika ani nie jest naciągany na najbliższy.
"""

import asyncio

from dancelab.tui import gatunki as G


class _T:
    def __init__(self, tag):
        self.style_label = tag
        self.source_path = "/m/x.mp3"


class _A:
    def __init__(self, tag):
        self.track = _T(tag)


PULA = [_A("Tech House"), _A("Tech House"), _A("tech house"),
        _A("140 / Deep Dubstep / Grime"), _A("UK Garage / Bassline"),
        _A("Hip-Hop"), _A("Loop Samples"), _A("https://djsoundtop.com"),
        _A(None)]


def test_nazwa_gatunku_jest_caloscia():
    assert G.kanoniczny("140 / Deep Dubstep / Grime") == \
        "140 / Deep Dubstep / Grime"
    assert G.kanoniczny("140") is None, "człon nazwy NIE jest gatunkiem"
    assert G.kanoniczny("Grime") is None
    assert G.kanoniczny("  tech   house ") == "Tech House", "luz w zapisie"


def test_grupowanie_po_sekcjach_beatportu_i_liczby():
    grupy = dict(G.policz(PULA))
    assert grupy["Electronic"][0] == ("Tech House", 3), "najliczniejszy pierwszy"
    assert ("140 / Deep Dubstep / Grime", 1) in grupy["Electronic"]
    assert grupy["Open Format"] == [("Hip-Hop", 1)]


def test_tag_spoza_taksonomii_nie_znika_i_nie_jest_naciagany():
    grupy = dict(G.policz(PULA))
    poza = dict(grupy[G.POZA])
    assert poza["Loop Samples"] == 1
    assert "https://djsoundtop.com" in poza


def test_pokrycie_mowi_ile_masz_i_ile_bez_tagu():
    mam, wszystkich, bez = G.pokrycie(PULA)
    assert mam == 4 and wszystkich == 46 and bez == 1


def test_przelacz_dodaje_i_zdejmuje_po_przecinkach():
    p = G.przelacz("", "Tech House")
    assert p == "Tech House"
    p = G.przelacz(p, "140 / Deep Dubstep / Grime")
    assert p == "Tech House, 140 / Deep Dubstep / Grime", \
        "ukośnik NALEŻY do nazwy — rozdziela tylko przecinek"
    assert G.przelacz(p, "Tech House") == "140 / Deep Dubstep / Grime"


def test_enter_dodaje_gatunki_a_ctrl_g_tylko_zamyka():
    """Życzenie Janka 09.08: „wybór gatunku powinien być akceptowany
    enterem, a nie Ctrl+G; Ctrl+G dopiero zamyka. Można dodać więcej niż
    jeden gatunek". Enter zostawia listę otwartą — inaczej wybranie dwóch
    gatunków wymagałoby dwóch otwarć panelu."""
    from textual.widgets import Input, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            app._lib = list(PULA)
            await pilot.pause()
            app.action_gatunki()
            await pilot.pause()
            lst = app.query_one("#suggest-list")
            assert lst.get_option_at_index(0).id.startswith("__"), \
                "pierwszy wiersz to nagłówek sekcji"

            lst.highlighted = 1                  # najliczniejszy gatunek
            await pilot.press("enter")
            await pilot.pause()
            pole = app.query_one("#styles", Input)
            assert pole.value == "Tech House"
            assert app.query_one("#suggest").has_class("open"), \
                "lista ZOSTAJE otwarta — gatunków wybiera się kilka"
            assert "✓" in lst.get_option_at_index(1).prompt, \
                "wybrany gatunek jest oznaczony na liście"

            lst.highlighted = 2                  # drugi gatunek
            await pilot.press("enter")
            await pilot.pause()
            assert pole.value.count(",") == 1, "dwa gatunki naraz"

            lst.highlighted = 1                  # Enter drugi raz = zdejmij
            await pilot.press("enter")
            await pilot.pause()
            assert "Tech House" not in pole.value

            app.action_gatunki()                 # Ctrl+G TYLKO zamyka
            await pilot.pause()
            assert not app.query_one("#suggest").has_class("open")
            assert app.query_one("#styles", Input).value == pole.value, \
                "zamknięcie panelu niczego nie dopisuje"

    asyncio.run(go())


def test_enter_na_naglowku_sekcji_nic_nie_robi():
    from textual.widgets import Input, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            app._lib = list(PULA)
            await pilot.pause()
            app.action_gatunki()
            await pilot.pause()
            app.query_one("#suggest-list").highlighted = 0   # „— Electronic —"
            await pilot.press("enter")
            await pilot.pause()
            assert app.query_one("#styles", Input).value == ""

    asyncio.run(go())

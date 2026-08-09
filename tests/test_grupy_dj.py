"""Grupy brzmieniowe DJ-ów w „Graj jak…" (decyzja Janka 09.08).

Grupujemy po ZMIERZONYM centroidzie brzmienia, bo dwa oczywiste pomysły
padły na danych: gatunek (pole puste w 100% profili) i miejsce/event
(w tytułach miksów siedzi tylko źródło naszego scrapingu). Etykieta grupy
to jej najbardziej typowi członkowie — żadnych wymyślonych nazw gatunków.
"""

import asyncio

from dancelab.tui import grupy_dj as G


def _ksiazka(n_na_grupe=6):
    """Trzy wyraźnie różne rodziny brzmienia (wektory 3D wystarczą)."""
    djs = {}
    for i in range(n_na_grupe):
        djs[f"techno{i}"] = {"centroid": [1.0, 0.02 * i, 0.0],
                             "n_tracks": 50 + i, "cos_median": 0.65}
        djs[f"disco{i}"] = {"centroid": [0.0, 1.0, 0.02 * i],
                            "n_tracks": 40 + i, "cos_median": 0.84}
        djs[f"bass{i}"] = {"centroid": [0.0, 0.02 * i, 1.0],
                           "n_tracks": 30 + i, "cos_median": 0.75}
    return djs


def test_grupy_zbieraja_pokrewne_brzmienie():
    grupy = G.grupuj(_ksiazka(), k=3)
    assert len(grupy) == 3
    rodziny = [{n.rstrip("012345") for n, _, _ in czlonkowie}
               for _, czlonkowie in grupy]
    assert {"techno"} in rodziny and {"disco"} in rodziny \
        and {"bass"} in rodziny, "każda grupa to jedna rodzina"


def test_etykieta_to_najbardziej_typowi_czlonkowie():
    grupy = G.grupuj(_ksiazka(), k=3)
    for etykieta, czlonkowie in grupy:
        assert etykieta.startswith("brzmi jak: ")
        pierwszy = czlonkowie[0][0]
        assert pierwszy in etykieta, "nagłówek nazywa najbardziej typowego"


def test_podzial_jest_powtarzalny():
    a = G.grupuj(_ksiazka(), k=3)
    b = G.grupuj(_ksiazka(), k=3)
    assert [e for e, _ in a] == [e for e, _ in b], "ustalone ziarno"


def test_za_malo_djow_to_jedna_grupa_a_nie_zmyslony_podzial():
    mala = {"a": {"centroid": [1.0, 0.0], "n_tracks": 5, "cos_median": 0.7}}
    grupy = G.grupuj(mala, k=8)
    assert len(grupy) == 1 and grupy[0][0].startswith("wszyscy")


def test_opis_pokazuje_skok_i_nazywa_odwage():
    assert "odważny" in G.opis("Ben UFO", 64, 0.637)
    assert "gładki" in G.opis("Eats Everything", 74, 0.815)
    assert G.opis("X", 10, None) == "X  (10 wekt.)", "brak pomiaru = brak słowa"


def test_ctrl_d_pokazuje_rodziny_i_wybiera_kotwice(monkeypatch):
    from textual.widgets import Select, TabbedContent

    import dancelab.decision.anchors as anchors
    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr(anchors, "load_anchor_book",
                        lambda *a, **k: {"djs": _ksiazka()})

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            app.query_one("#dj", Select).set_options(
                [(n, n) for n in sorted(_ksiazka())])
            app.action_grupy_dj()
            await pilot.pause()
            assert app._panel_mode == "dj"
            lst = app.query_one("#suggest-list")
            assert lst.get_option_at_index(0).id.startswith("__"), \
                "pierwszy wiersz to nagłówek rodziny"
            lst.highlighted = 1
            wybrany = lst.get_option_at_index(1).id
            app.action_grupy_dj()                 # drugie Ctrl+D = wybór
            await pilot.pause()
            assert app.query_one("#dj", Select).value == wybrany

    asyncio.run(go())

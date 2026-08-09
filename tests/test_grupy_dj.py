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


def test_ctrl_d_otwiera_i_zamyka_liste_rodzin(monkeypatch):
    """Ctrl+D tylko OTWIERA i ZAMYKA (życzenie Janka 09.08). Wyboru
    dokonuje Enter — patrz test niżej."""
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
            app.action_grupy_dj()
            await pilot.pause()
            assert app._panel_mode == "dj"
            lst = app.query_one("#suggest-list")
            assert lst.get_option_at_index(0).id.startswith("__"), \
                "pierwszy wiersz to nagłówek rodziny"
            naglowki = sum(1 for i in range(lst.option_count)
                           if lst.get_option_at_index(i).id.startswith("__"))
            assert naglowki >= 2, "DJ-e pogrupowani w rodziny brzmieniowe"

            app.action_grupy_dj()                 # drugie Ctrl+D = ZAMKNIJ
            await pilot.pause()
            assert not app.query_one("#suggest").has_class("open")
            from textual.widgets._select import NoSelection
            assert isinstance(app.query_one("#dj", Select).value,
                              NoSelection), \
                "zamknięcie panelu nie ustawia kotwicy"

    asyncio.run(go())


def test_enter_wybiera_kotwice_i_zamyka(monkeypatch):
    """Ten sam Enter co przy gatunkach. Kotwica jest JEDNA, więc Enter ją
    ustawia i zamyka listę."""
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
            lst = app.query_one("#suggest-list")
            i = next(n for n in range(lst.option_count)
                     if not lst.get_option_at_index(n).id.startswith("__"))
            wybrany = lst.get_option_at_index(i).id
            lst.highlighted = i
            await pilot.press("enter")
            await pilot.pause()

            assert app.query_one("#dj", Select).value == wybrany
            assert not app.query_one("#suggest").has_class("open"), \
                "kotwica jest jedna — po wyborze lista się zamyka"

    asyncio.run(go())


def test_klasa_tui_nie_ma_zdublowanych_metod():
    """Regresja 09.08: druga metoda `on_option_list_option_selected` w tej
    samej klasie po cichu KASOWAŁA pierwszą — Enter w panelu nie działał,
    a Python nawet nie mruknął. Test pilnuje, żeby to się nie powtórzyło."""
    import ast
    import collections
    import pathlib as _p

    import dancelab.tui.app as A

    drzewo = ast.parse(_p.Path(A.__file__).read_text())
    klasy = [n for n in drzewo.body if isinstance(n, ast.ClassDef)]
    for klasa in klasy:
        nazwy = [f.name for f in klasa.body
                 if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
        dubel = [n for n, ile in collections.Counter(nazwy).items() if ile > 1]
        assert not dubel, f"{klasa.name}: zdublowane metody {dubel}"

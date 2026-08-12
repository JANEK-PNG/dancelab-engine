"""Kolekcja DJ-ów (decyzja Janka 12.08, przeniesiona ze ściany kart do TUI).

Trzy przybite zasady:
1. kolekcja to RĘCZNY wybór, kolejność = kolejność zbierania;
2. DJ-e z kolekcji mają PIERWSZEŃSTWO w polu „Brzmi jak…" i niosą ✓;
3. K w panelu „Brzmi jak…" zbiera/wypuszcza bez zamykania listy,
   a separatory i „★ moje ulubione" odmawiają grzecznie.
"""

from __future__ import annotations

import asyncio

from dancelab.tui import user_store as U
from dancelab.tui.app import DanceLabTUI, _opcje_kotwic


def _stan():
    return {k: (list(v) if isinstance(v, list) else v)
            for k, v in U._EMPTY.items()}


def test_przelaczanie_i_kolejnosc_zbierania():
    state = _stan()
    assert U.przelacz_kolekcje_dj(state, "Ben UFO")
    assert U.przelacz_kolekcje_dj(state, "Ayesha")
    assert U.kolekcja_djow(state) == ["Ben UFO", "Ayesha"]
    assert not U.przelacz_kolekcje_dj(state, "Ben UFO")   # wypuszczony
    assert U.kolekcja_djow(state) == ["Ayesha"]
    assert U.w_kolekcji(state, "Ayesha")


def test_kolekcja_przezywa_zapis_i_odczyt(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "STATE_PATH", tmp_path / "stan.json")
    state = _stan()
    U.przelacz_kolekcje_dj(state, "Ayesha")
    U.save_state(state)
    assert U.kolekcja_djow(U.load_state()) == ["Ayesha"]


def test_opcje_kotwic_kolekcja_przed_reszta_z_checkmarkiem():
    wpisy = [("Amelie", 40, 0.8), ("Ayesha", 39, 0.7), ("Ben UFO", 28, 0.6)]
    opcje = _opcje_kotwic(wpisy, ["Ben UFO", "Ayesha"])
    assert [v for _e, v in opcje] == ["Ben UFO", "Ayesha", "Amelie"]
    assert opcje[0][0].startswith("✓ ") and opcje[1][0].startswith("✓ ")
    assert not opcje[2][0].startswith("✓")


def test_pusta_kolekcja_nie_zmienia_porzadku():
    wpisy = [("A", 1, 0.5), ("B", 2, 0.6)]
    opcje = _opcje_kotwic(wpisy, [])
    assert [v for _e, v in opcje] == ["A", "B"]
    assert all(not e.startswith("✓") for e, _v in opcje)


def _ksiega_atrapa():
    # mało nazwisk → grupuj() zwraca jedną grupę „wszyscy DJ-e" (bez klastrów)
    return {"djs": {
        "Ayesha": {"centroid": [1, 0], "n_tracks": 39, "cos_median": 0.7},
        "Ben UFO": {"centroid": [0, 1], "n_tracks": 28, "cos_median": 0.8},
        "Tim Reaper": {"centroid": [1, 1], "n_tracks": 177, "cos_median": 0.75},
    }}


def test_k_w_panelu_zbiera_dj_a_pole_dostaje_pierwszenstwo(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "STATE_PATH", tmp_path / "stan.json")
    import dancelab.decision.anchors as A
    monkeypatch.setattr(A, "load_anchor_book", lambda *a, **k: _ksiega_atrapa())
    monkeypatch.setattr(A, "list_anchors", lambda *a, **k: [
        ("Ayesha", 39, 0.7), ("Ben UFO", 28, 0.8), ("Tim Reaper", 177, 0.75)])

    async def go():
        from textual.widgets import OptionList, Select
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.action_grupy_dj()
            await pilot.pause()
            lst = app.query_one("#suggest-list", OptionList)
            # najedź na konkretnego DJ-a (id bez „__" i bez ulubionych)
            cel = next(i for i in range(lst.option_count)
                       if (lst.get_option_at_index(i).id or "") == "Ben UFO")
            lst.highlighted = cel
            lst.focus()
            await pilot.press("k")
            await pilot.pause()
            assert U.kolekcja_djow(app._user_state) == ["Ben UFO"]
            # panel został otwarty i ma sekcję kolekcji z ✓
            teksty = [str(lst.get_option_at_index(i).prompt)
                      for i in range(lst.option_count)]
            assert any("twoja kolekcja (1)" in t for t in teksty)
            assert any(t.strip().startswith("✓ Ben UFO") for t in teksty)
            # pole „Brzmi jak…" przestawione: Ben UFO zaraz po ulubionych
            pole = app.query_one("#dj", Select)
            pary = list(pole._options or [])
            wartosci = [v for _e, v in pary]
            po_ulub = wartosci.index("★ moje ulubione") + 1
            assert wartosci[po_ulub] == "Ben UFO", "kolekcja tuż po ★ ulubionych"
            assert pary[po_ulub][0].startswith("✓ ")
            # K na separatorze odmawia grzecznie, stan bez zmian
            lst.highlighted = 0
            await pilot.press("k")
            await pilot.pause()
            assert U.kolekcja_djow(app._user_state) == ["Ben UFO"]
    asyncio.run(go())


def test_zakladka_dje_lista_karta_kolekcja_i_kotwica(tmp_path, monkeypatch):
    """Osobna zakładka DJ-e (Janek 12.08): lista z kolekcją na górze,
    karta podświetlonego DJ-a z pomiarów księgi, K zbiera, Enter ustawia
    kotwicę „Brzmi jak…" bez wychodzenia z zakładki."""
    monkeypatch.setattr(U, "STATE_PATH", tmp_path / "stan.json")
    import dancelab.decision.anchors as A
    monkeypatch.setattr(A, "load_anchor_book", lambda *a, **k: _ksiega_atrapa())
    monkeypatch.setattr(A, "list_anchors", lambda *a, **k: [
        ("Ayesha", 39, 0.7), ("Ben UFO", 28, 0.8), ("Tim Reaper", 177, 0.75)])

    async def go():
        from textual.widgets import OptionList, Select, Static, TabbedContent
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-dj"
            await pilot.pause()
            lst = app.query_one("#dj-lista", OptionList)
            assert lst.option_count > 3, "lista DJ-ów wypełniona z księgi"
            cel = next(i for i in range(lst.option_count)
                       if (lst.get_option_at_index(i).id or "") == "Ayesha")
            lst.highlighted = cel
            await pilot.pause()
            karta = str(app.query_one("#dj-karta", Static).content)
            assert "Ayesha" in karta and "39" in karta, "karta z pomiarów"
            assert "poza kolekcją" in karta
            lst.focus()
            await pilot.press("k")                 # zbierz do kolekcji
            await pilot.pause()
            assert U.kolekcja_djow(app._user_state) == ["Ayesha"]
            karta = str(app.query_one("#dj-karta", Static).content)
            assert "w kolekcji" in karta
            teksty = [str(lst.get_option_at_index(i).prompt)
                      for i in range(lst.option_count)]
            assert any("twoja kolekcja (1)" in t for t in teksty)
            # Enter = kotwica w polu „Brzmi jak…"
            cel = next(i for i in range(lst.option_count)
                       if (lst.get_option_at_index(i).id or "") == "Ayesha")
            lst.highlighted = cel
            await pilot.press("enter")
            await pilot.pause()
            assert app.query_one("#dj", Select).value == "Ayesha"
            assert app.query_one("#tabs", TabbedContent).active == "tab-dj", \
                "Enter nie wyrzuca z zakładki"
    asyncio.run(go())

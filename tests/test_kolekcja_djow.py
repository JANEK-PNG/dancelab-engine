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


def test_sciana_kart_kolekcja_kotwica_i_strzalki(tmp_path, monkeypatch):
    """Ściana kart jak w GUI (Janek 13.08): karty zamiast listy, K zbiera
    (karta odzyskuje kolor), Enter ustawia kotwicę bez wychodzenia,
    strzałki chodzą po kafelkach."""
    monkeypatch.setattr(U, "STATE_PATH", tmp_path / "stan.json")
    import dancelab.decision.anchors as A
    monkeypatch.setattr(A, "load_anchor_book", lambda *a, **k: _ksiega_atrapa())
    monkeypatch.setattr(A, "list_anchors", lambda *a, **k: [
        ("Ayesha", 39, 0.7), ("Ben UFO", 28, 0.8), ("Tim Reaper", 177, 0.75)])
    from dancelab.tui import dj_profile as P
    monkeypatch.setattr(P, "PROFIL_PATH", tmp_path / "brak.json")

    async def go():
        from textual.widgets import Select, TabbedContent
        from dancelab.tui.app import KartaDJ
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-dj"
            await pilot.pause()
            karty = app.query(KartaDJ).nodes
            assert len(karty) == 3, "trzy karty na ścianie, nie lista"
            assert app.focused in karty, "wejście = fokus na karcie"
            pierwsza = app.focused
            assert pierwsza.has_class("szara"), "poza kolekcją = przygaszona"
            await pilot.press("k")
            await pilot.pause()
            assert U.kolekcja_djow(app._user_state) == [pierwsza.dj]
            karty2 = app.query(KartaDJ).nodes
            nowa = next(k for k in karty2 if k.dj == pierwsza.dj)
            assert not nowa.has_class("szara"), "w kolekcji = pełny kolor"
            assert karty2[0].dj == pierwsza.dj, "kolekcja na przód ściany"
            await pilot.press("right")
            await pilot.pause()
            druga = app.focused
            assert isinstance(druga, KartaDJ) and druga.dj != pierwsza.dj
            await pilot.press("enter")
            await pilot.pause()
            assert app.query_one("#dj", Select).value == druga.dj
            assert app.query_one("#tabs", TabbedContent).active == "tab-dj"
    asyncio.run(go())

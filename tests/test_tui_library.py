"""Zakładka Biblioteka (TUI 2.0, krok a) — filtry, zakładki, uczciwa energia.

Reguły: filtr znaczy dokładnie to, co mówi (podciąg nazwa/gatunek, dokładna
tonacja, domknięte okno BPM — utwór bez tempa przy oknie odpada); Ctrl+Tab
krąży po zakładkach w stałej kolejności; energia jest RELATYWNA w obrębie
biblioteki, a brak ramek RMS to „—", nigdy zmyślona wartość.
"""

from __future__ import annotations

import asyncio

import pytest

from dancelab.tui.app import (
    DanceLabTUI, _TAB_ORDER, _filary_for_build, filter_library)


class _T:
    def __init__(self, tid, name, bpm, key, genre):
        self.track_id = tid
        self.source_path = f"/m/{name}.mp3"
        self.bpm_estimate = bpm
        self.key_estimate = key
        self.key_confidence = 0.9
        self.style_label = genre
        self.duration_sec = 300.0
        self.sound_embedding = None


class _A:
    def __init__(self, *args):
        self.track = _T(*args)
        self.features = []


LIB = [
    _A("a", "Mercy System - Steppers", 132.0, "4A", "breaks"),
    _A("b", "Detlef - Lil Bunny", 130.0, "2A", "Tech House"),
    _A("c", "Hodge - Wiggler", 135.0, "1A", "UK Bass"),
    _A("d", "Bez Tempa", None, None, None),
    _A("e", "Overmono - So U Kno", 131.0, "5A", "breaks"),
]


def test_filtr_szuka_w_nazwie_i_gatunku_bez_wielkosci_liter():
    assert [a.track.track_id for a in filter_library(LIB, search="mercy")] == ["a"]
    assert [a.track.track_id for a in filter_library(LIB, search="uk bass")] == ["c"]
    assert len(filter_library(LIB, search="")) == 5


def test_filtr_tonacji_dokladny():
    assert [a.track.track_id for a in filter_library(LIB, key="2a")] == ["b"]
    assert filter_library(LIB, key="9B") == []


def test_okno_bpm_domkniete_a_brak_tempa_odpada():
    got = [a.track.track_id for a in filter_library(LIB, bpm_lo=130, bpm_hi=132)]
    assert got == ["a", "b", "e"], "135 poza oknem, brak tempa też poza oknem"


def test_filtry_skladaja_sie():
    got = filter_library(LIB, search="e", bpm_lo=129, bpm_hi=133, key="2A")
    assert [a.track.track_id for a in got] == ["b"]


def _state(*filary):
    return {"filary": [{"track_id": t, "path": f"/m/{t}.mp3"} for t in filary]}


def _by_id():
    return {a.track.track_id: a for a in LIB}


def test_filary_przechodza_do_budowy_z_notka():
    ids, notes = _filary_for_build(_state("a", "b", "e"), _by_id(), None, None, 10)
    assert ids == ["a", "b", "e"]
    assert any("filary w budowie: 3" in n for n in notes)


def test_mniej_niz_trzy_filary_odmawia():
    """Reguła Janka 05.08: filary to 3-10. Minimum egzekwuje budowa."""
    with pytest.raises(ValueError, match="minimum 3"):
        _filary_for_build(_state("a", "b"), _by_id(), None, None, 10)


def test_filar_poza_oknem_tempa_pominiety_imiennie():
    ids, notes = _filary_for_build(_state("a", "b", "e", "c"),
                                   _by_id(), 129, 133, 10)
    assert ids == ["a", "b", "e"], "c ma 135 — poza oknem"
    assert any("poza oknem tempa" in n and "Hodge" in n for n in notes)


def test_filar_spoza_puli_pominiety_imiennie():
    ids, notes = _filary_for_build(_state("nie_ma"), _by_id(), None, None, 10)
    assert ids == []
    assert any("nieobecny w puli" in n and "nie_ma" in n for n in notes)


def test_wiecej_filarow_niz_miejsc_odmawia_z_liczbami():
    with pytest.raises(ValueError, match=r"filarów \(3\).*miejsc w secie \(2\)"):
        _filary_for_build(_state("a", "b", "e"), _by_id(), None, None, 2)


def test_zakladki_istnieja_i_ctrl_tab_krazy():
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
            tc = app.query_one("#tabs", TabbedContent)
            assert tc.active == "tab-lib"          # wizja: Biblioteka pierwsza
            for wid in ("#lib-search", "#lib-key", "#lib-bpm", "#lib-table",
                        "#lib-folder", "#lib-analyze", "#lib-side-list",
                        "#lib-build", "#export-stub"):
                assert app.query_one(wid) is not None, wid
            app.action_next_tab()
            await pilot.pause()
            assert tc.active == "tab-set"
            app.action_next_tab()
            await pilot.pause()
            assert tc.active == "tab-export"
            app.action_next_tab()
            await pilot.pause()
            assert tc.active == "tab-lib"          # pełne kółko
            app.action_prev_tab()
            await pilot.pause()
            assert tc.active == "tab-export"
    asyncio.run(go())


def test_u_i_f_pinuja_z_biblioteki(tmp_path, monkeypatch):
    """U pinuje ulubiony, F filar; znaczniki w tabeli, licznik w pasku."""
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Static
            app._set_library(list(LIB))
            await pilot.pause()
            table = app.query_one("#lib-table", DataTable)
            table.move_cursor(row=0)
            table.focus()
            await pilot.press("u")
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            assert len(app._user_state["ulubione_utwory"]) == 1
            assert len(app._user_state["filary"]) == 1
            from textual.coordinate import Coordinate
            assert str(table.get_cell_at(Coordinate(0, 0))) == "♥"
            assert str(table.get_cell_at(Coordinate(0, 1))) == "F"
            count_line = str(app.query_one("#lib-count", Static).render())
            assert "filary: 1 (min 3, max 10)" in count_line
            assert "F=filar" in count_line          # legenda widoczna na ekranie
            await pilot.press("f")            # drugi raz zdejmuje
            await pilot.pause()
            assert app._user_state["filary"] == []
    asyncio.run(go())
    assert (tmp_path / "stan.json").exists()   # stan przeżywa zamknięcie


def test_biblioteka_renderuje_i_filtruje_na_zywo():
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Input, Static
            app._set_library(list(LIB))
            await pilot.pause()
            table = app.query_one("#lib-table", DataTable)
            assert table.row_count == 5
            assert "5 z 5" in str(app.query_one("#lib-count", Static).render())
            app.query_one("#lib-search", Input).value = "mercy"
            await pilot.pause()
            assert table.row_count == 1
            assert "1 z 5" in str(app.query_one("#lib-count", Static).render())
            # zły filtr BPM = powód w liczniku, nie traceback
            app.query_one("#lib-search", Input).value = ""
            app.query_one("#lib-bpm", Input).value = "140-130"
            await pilot.pause()
            assert "puste okno" in str(app.query_one("#lib-count", Static).render())
    asyncio.run(go())


def test_g_wstawia_szkic_filarow_bez_budowy(tmp_path, monkeypatch):
    """G z <3 filarami odmawia; z 3 przenosi do Set jako SZKIC (bez budowy —
    brief zostaje w grze), filary w tabeli oznaczone ⚑ i złotem."""
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Static, TabbedContent
            tc = app.query_one("#tabs", TabbedContent)
            app._set_library(list(LIB))
            await pilot.pause()
            app._user_state["filary"] = [
                {"track_id": "a", "path": "/m/a.mp3"},
                {"track_id": "b", "path": "/m/b.mp3"}]
            app.action_build_from_filary()
            await pilot.pause()
            assert tc.active == "tab-lib", "2 filary = odmowa, zostajemy"
            app._user_state["filary"].append(
                {"track_id": "e", "path": "/m/e.mp3"})
            app.action_build_from_filary()
            await pilot.pause()
            assert tc.active == "tab-set"
            assert sorted(app._order) == ["a", "b", "e"], "szkic = same filary"
            assert app._engine_order == [], "NIC nie zbudowano — brief czeka"
            assert "SZKIC" in str(app.query_one("#progress", Static).render())
            from textual.coordinate import Coordinate
            from rich.text import Text
            table = app.query_one("#set", DataTable)
            cell = table.get_cell_at(Coordinate(0, 0))
            assert isinstance(cell, Text) and str(cell).startswith("⚑")
    asyncio.run(go())


def test_sortowanie_klikiem_w_naglowek():
    """Cykl Janka: liczby ↓→↑→kasacja, teksty A-Z→Z-A→kasacja;
    braki ZAWSZE na końcu; wykonawca i tytuł to osobne kolumny."""
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable
            from textual.coordinate import Coordinate
            app._set_library(list(LIB))
            await pilot.pause()
            table = app.query_one("#lib-table", DataTable)

            app._cycle_sort(2)                  # 1. klik BPM = ↓ rosnąco
            assert app._lib_sort == (2, False)
            app._render_library()
            await pilot.pause()
            assert "Detlef" in str(table.get_cell_at(Coordinate(0, 8)))
            assert "Bez Tempa" in str(
                table.get_cell_at(Coordinate(4, 9))), "brak tempa na końcu"
            klucz_bpm = app._lib_col_keys[2]
            assert "↓" in str(table.columns[klucz_bpm].label)
            app._cycle_sort(2)                  # 2. klik = ↑ malejąco
            assert app._lib_sort == (2, True)
            app._render_library()
            await pilot.pause()
            assert "Hodge" in str(table.get_cell_at(Coordinate(0, 8)))
            assert "↑" in str(table.columns[klucz_bpm].label)
            app._cycle_sort(2)                  # 3. klik kasuje, strzałka znika
            assert app._lib_sort is None
            app._render_library()
            await pilot.pause()
            assert "↓" not in str(table.columns[klucz_bpm].label)
            assert "↑" not in str(table.columns[klucz_bpm].label)

            app._cycle_sort(9)                  # tytuł: 1. klik A-Z
            assert app._lib_sort == (9, False)
            app._render_library()
            await pilot.pause()
            assert "Bez Tempa" in str(table.get_cell_at(Coordinate(0, 9)))
            app._cycle_sort(9)
            assert app._lib_sort == (9, True)   # Z-A
            app._cycle_sort(9)
            assert app._lib_sort is None

            # wykonawca sparsowany z nazwy pliku "Artysta - Tytuł"
            app._render_library()
            await pilot.pause()
            from dancelab.tui.app import _wykonawca_tytul
            assert _wykonawca_tytul(LIB[0].track) == ("Mercy System",
                                                      "Steppers")
    asyncio.run(go())


def test_sekcje_po_lewej_filtruja_widok(tmp_path, monkeypatch):
    """Sekcja ♥/⚑ zawęża tabelę do przypiętych; nazwa sekcji w liczniku."""
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Static
            app._set_library(list(LIB))
            await pilot.pause()
            app._user_state["ulubione_utwory"] = [
                {"track_id": "b", "path": "/m/b.mp3"}]
            app._user_state["filary"] = [
                {"track_id": "a", "path": "/m/a.mp3"},
                {"track_id": "e", "path": "/m/e.mp3"}]
            table = app.query_one("#lib-table", DataTable)
            app._set_lib_section("fav")
            await pilot.pause()
            assert table.row_count == 1
            assert "♥ Ulubione: 1 z 5" in str(
                app.query_one("#lib-count", Static).render())
            app._set_lib_section("filary")
            await pilot.pause()
            assert table.row_count == 2
            app._set_lib_section("all")
            await pilot.pause()
            assert table.row_count == 5
    asyncio.run(go())


def test_po_polsku_tlumaczy_znane_i_przepuszcza_nieznane():
    from dancelab.tui.po_polsku import po_polsku
    assert po_polsku(
        "removed 2 duplicate audio file(s) (same bytes): x→y, a→b"
    ) == "duplikaty (te same bajty) usunięte z puli: 2 — x→y, a→b"
    assert po_polsku(
        "BPM range applied (125.0-145.0); 50 out-of-range track(s) left out"
    ).startswith("okno tempa 125.0-145.0 — poza oknem zostało: 50")
    assert po_polsku(
        "artist diversity relaxed - repeated artist(s): bicep, bodhi"
    ) == "różnorodność artystów poluzowana — powtórzeni: bicep, bodhi"
    assert po_polsku("pinned_track_ids reference unknown tracks: abc123"
                     ) == "filar wskazuje utwór spoza puli: abc123"
    # nieznany komunikat przechodzi bez zmian — żadnego zgadywania
    assert po_polsku("some brand new warning") == "some brand new warning"
    assert po_polsku("higiena puli: odrzucone 17") == "higiena puli: odrzucone 17"


def test_rozstaw_filary_rownomiernie_i_rosnaco_po_tempie():
    """Metafora Janka: filary podpierają CAŁĄ konstrukcję — równomierne
    pozycje, kolejność rosnąco po BPM (schodki tempa), nigdy zbite na ogonie."""
    from dancelab.tui.app import _rozstaw_filary
    by_id = _by_id()
    # a=132, b=130, e=131 → kolejność pozycji: b(130), e(131), a(132)
    out = _rozstaw_filary(["a", "b", "e"], by_id, 12)
    assert out == {2: "b", 6: "e", 10: "a"}
    # 6 filarów w 18 slotach — rozrzut po całości, nie 13-18
    szesc = {t: 120 + i for i, t in enumerate("pqrstu")}

    class _FA:
        def __init__(self, bpm):
            self.track = type("T", (), {"bpm_estimate": float(bpm)})()
    duzy = {t: _FA(b) for t, b in szesc.items()}
    pozycje = sorted(_rozstaw_filary(list(szesc), duzy, 18))
    assert pozycje == [2, 5, 8, 11, 14, 17]


def test_rozstaw_filary_ciasny_set_bez_kolizji():
    """k bliskie n: pozycje ściśle rosnące, wszystkie w zakresie."""
    from dancelab.tui.app import _rozstaw_filary

    class _FA:
        def __init__(self, bpm):
            self.track = type("T", (), {"bpm_estimate": float(bpm)})()
    by_id = {t: _FA(120 + i) for i, t in enumerate("abcde")}
    out = _rozstaw_filary(list("abcde"), by_id, 5)
    assert sorted(out) == [1, 2, 3, 4, 5]
    out = _rozstaw_filary(list("abcd"), by_id, 5)
    poz = sorted(out)
    assert len(poz) == 4 and poz[0] >= 1 and poz[-1] <= 5
    assert all(x < y for x, y in zip(poz, poz[1:]))


def test_rozstaw_rama_brzegi_i_srodek():
    """Rama: najwolniejszy filar OTWIERA set, najszybszy ZAMYKA, środek równo."""
    from dancelab.tui.app import _rozstaw_filary
    by_id = _by_id()   # a=132, b=130, e=131
    out = _rozstaw_filary(["a", "b", "e"], by_id, 12, tryb="rama")
    assert out[1] == "b" and out[12] == "a"
    assert out[6] == "e"                       # środek równomiernie


def test_wstaw_podpory_w_najslabsze_przesla():
    """Konstrukcja zmierzona, filar wchodzi w najsłabsze przęsło, przydział
    filar→przęsło po najlepszym mostku."""
    from dancelab.tui.app import _wstaw_podpory
    core = ["A", "B", "C", "D"]
    scores = {("A", "B"): 0.9, ("B", "C"): 0.2, ("C", "D"): 0.5,
              # mostki: P świetny w B→C, Q lepszy w C→D
              ("B", "P"): 0.9, ("P", "C"): 0.9, ("B", "Q"): 0.3,
              ("Q", "C"): 0.3, ("C", "P"): 0.4, ("P", "D"): 0.4,
              ("C", "Q"): 0.8, ("Q", "D"): 0.8}
    final, notes = _wstaw_podpory(core, ["P", "Q"],
                                  lambda a, b: scores.get((a, b), 0.5))
    assert final == ["A", "B", "P", "C", "Q", "D"]
    assert any("#2→#3" in n for n in notes)    # najsłabsze przęsło nazwane

    import pytest as _pytest
    with _pytest.raises(ValueError, match="za mało przęseł"):
        _wstaw_podpory(["A", "B"], ["P", "Q"], lambda a, b: 0.5)


def test_f_w_secie_otwiera_tryby_a_wybor_sie_zapisuje(tmp_path, monkeypatch):
    """Podwójne F w zakładce Set = panel trybów (wzorzec dwóch naciśnięć);
    wybór trwa w stanie użytkownika."""
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import OptionList, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            assert app._panel_mode == "pillar_mode"
            lst = app.query_one("#suggest-list", OptionList)
            lst.highlighted = 0                # Podpory
            await pilot.press("f")
            await pilot.pause()
            assert app._user_state["tryb_filarow"] == "podpory"
            assert app._panel_mode is None     # panel zamknięty po wyborze
    asyncio.run(go())
    import json
    assert json.loads((tmp_path / "stan.json").read_text())[
        "tryb_filarow"] == "podpory"


def test_wyciecie_filaru_zdejmuje_pin(tmp_path, monkeypatch):
    """Decyzja Janka: X na filarze tnie z setu I odpina w Bibliotece."""
    import dancelab.tui.app as app_mod
    import dancelab.tui.user_store as store
    monkeypatch.setattr(app_mod, "WERDYKTY_DIR", tmp_path)
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            by_id = {a.track.track_id: a for a in LIB}
            app._ctx = dict(by_id=by_id, weights=None, arc="build",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None, params={}, filary=["b"])
            app._user_state["filary"] = [{"track_id": "b", "path": "/m/b.mp3"}]
            app._order = ["a", "b", "c"]
            app._engine_order = ["a", "b", "c"]
            app._render_order(by_id)
            await pilot.pause()
            table = app.query_one("#set", DataTable)
            table.move_cursor(row=1)           # filar b
            table.focus()
            await pilot.press("x")
            await pilot.pause()
            assert app._order == ["a", "c"]
            assert app._user_state["filary"] == [], "pin zdjęty razem z cięciem"
            assert app._edits[-1]["filar"] is True
    asyncio.run(go())

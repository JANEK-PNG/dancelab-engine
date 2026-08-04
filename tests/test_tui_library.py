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


def test_g_wysyla_filary_do_set_buildera(tmp_path, monkeypatch):
    """G z <3 filarami odmawia i zostaje w Bibliotece; z 3 przenosi do Set
    i odpala budowę."""
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
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
            assert tc.active == "tab-set", "3 filary = jedziemy budować"
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

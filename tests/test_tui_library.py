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
]


def test_filtr_szuka_w_nazwie_i_gatunku_bez_wielkosci_liter():
    assert [a.track.track_id for a in filter_library(LIB, search="mercy")] == ["a"]
    assert [a.track.track_id for a in filter_library(LIB, search="uk bass")] == ["c"]
    assert len(filter_library(LIB, search="")) == 4


def test_filtr_tonacji_dokladny():
    assert [a.track.track_id for a in filter_library(LIB, key="2a")] == ["b"]
    assert filter_library(LIB, key="9B") == []


def test_okno_bpm_domkniete_a_brak_tempa_odpada():
    got = [a.track.track_id for a in filter_library(LIB, bpm_lo=130, bpm_hi=132)]
    assert got == ["a", "b"], "135 poza oknem, brak tempa też poza oknem"


def test_filtry_skladaja_sie():
    got = filter_library(LIB, search="e", bpm_lo=129, bpm_hi=133, key="2A")
    assert [a.track.track_id for a in got] == ["b"]


def _state(*filary):
    return {"filary": [{"track_id": t, "path": f"/m/{t}.mp3"} for t in filary]}


def _by_id():
    return {a.track.track_id: a for a in LIB}


def test_filary_przechodza_do_budowy_z_notka():
    ids, notes = _filary_for_build(_state("a", "b"), _by_id(), None, None, 10)
    assert ids == ["a", "b"]
    assert any("filary w budowie: 2" in n for n in notes)


def test_filar_poza_oknem_tempa_pominiety_imiennie():
    ids, notes = _filary_for_build(_state("a", "c"), _by_id(), 129, 133, 10)
    assert ids == ["a"], "c ma 135 — poza oknem"
    assert any("poza oknem tempa" in n and "Hodge" in n for n in notes)


def test_filar_spoza_puli_pominiety_imiennie():
    ids, notes = _filary_for_build(_state("nie_ma"), _by_id(), None, None, 10)
    assert ids == []
    assert any("nieobecny w puli" in n and "nie_ma" in n for n in notes)


def test_wiecej_filarow_niz_miejsc_odmawia_z_liczbami():
    with pytest.raises(ValueError, match=r"filarów \(3\).*miejsc w secie \(2\)"):
        _filary_for_build(_state("a", "b", "c"), _by_id(), None, None, 2)


def test_zakladki_istnieja_i_ctrl_tab_krazy():
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import TabbedContent
            tc = app.query_one("#tabs", TabbedContent)
            assert tc.active == "tab-lib"          # wizja: Biblioteka pierwsza
            for wid in ("#lib-search", "#lib-key", "#lib-bpm", "#lib-table",
                        "#lib-folder", "#lib-analyze", "#export-stub"):
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
            assert "filary: 1/10" in str(
                app.query_one("#lib-count", Static).render())
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
            assert table.row_count == 4
            assert "4 z 4" in str(app.query_one("#lib-count", Static).render())
            app.query_one("#lib-search", Input).value = "mercy"
            await pilot.pause()
            assert table.row_count == 1
            assert "1 z 4" in str(app.query_one("#lib-count", Static).render())
            # zły filtr BPM = powód w liczniku, nie traceback
            app.query_one("#lib-search", Input).value = ""
            app.query_one("#lib-bpm", Input).value = "140-130"
            await pilot.pause()
            assert "puste okno" in str(app.query_one("#lib-count", Static).render())
    asyncio.run(go())

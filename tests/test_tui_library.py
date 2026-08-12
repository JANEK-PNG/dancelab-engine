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
    """Stan w NOWYM kształcie: filary żyją w aktywnej playliście (11.08)."""
    return {"filary": [], "aktywna_playlista": 0, "playlisty": [{
        "nazwa": "Test", "kotwica": None,
        "filary": [{"track_id": t, "path": f"/m/{t}.mp3", "rola": ""}
                   for t in filary]}]}


def _playlista_testowa(app, *filary):
    import dancelab.tui.user_store as store
    store.nowa_playlista(app._user_state, "Test")
    app._user_state["playlisty"][-1]["filary"] = [
        {"track_id": t, "path": f"/m/{t}.mp3", "rola": ""} for t in filary]


def _by_id():
    return {a.track.track_id: a for a in LIB}


def test_filary_przechodza_do_budowy_z_notka():
    ids, notes, _rola = _filary_for_build(_state("a", "b", "e"), _by_id(), None, None, 10)
    assert ids == ["a", "b", "e"]
    assert any("filary w budowie: 3" in n for n in notes)


def test_mniej_niz_trzy_filary_odmawia():
    """Reguła Janka 05.08: filary to 3-10. Minimum egzekwuje budowa."""
    with pytest.raises(ValueError, match="minimum 3"):
        _filary_for_build(_state("a", "b"), _by_id(), None, None, 10)


def test_filar_poza_oknem_tempa_pominiety_imiennie():
    ids, notes, _rola = _filary_for_build(_state("a", "b", "e", "c"),
                                   _by_id(), 129, 133, 10)
    assert ids == ["a", "b", "e"], "c ma 135 — poza oknem"
    assert any("poza oknem tempa" in n and "Hodge" in n for n in notes)


def test_filar_spoza_puli_pominiety_imiennie():
    ids, notes, _rola = _filary_for_build(_state("nie_ma"), _by_id(), None, None, 10)
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
                        "#lib-build", "#cue-table"):
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
            import dancelab.tui.user_store as store2
            _playlista_testowa(app)           # F wymaga aktywnej playlisty
            app._render_side_list()
            await pilot.press("f")            # otwiera wybór ROLI (11.08)
            await pilot.pause()
            assert app._panel_mode == "rola_filaru"
            await pilot.press("enter")        # pierwsza rola = otwarcie
            await pilot.pause()
            assert len(app._user_state["ulubione_utwory"]) == 1
            wpisy = store2.filary_wpisy(app._user_state)
            assert len(wpisy) == 1 and wpisy[0]["rola"] == "otwarcie"
            from textual.coordinate import Coordinate
            assert str(table.get_cell_at(Coordinate(0, 1))) == "♥"
            assert str(table.get_cell_at(Coordinate(0, 2))) == "F·O"
            count_line = str(app.query_one("#lib-count", Static).render())
            assert "filary: 1 (min 3, max 10)" in count_line
            assert "F=filar" in count_line          # legenda widoczna na ekranie
            app._filar_kandydat = (wpisy[0]["track_id"], wpisy[0]["path"])
            app._apply_rola_filaru("__zdejmij")
            await pilot.pause()
            assert store2.filary_wpisy(app._user_state) == []
    asyncio.run(go())
    # stan przeżywa zamknięcie — i należy do TEJ biblioteki, nie do programu
    # (od 09.08 plik jest osobny dla każdej puli; wcześniej filary jednego
    # użytkownika wyciekały do wszystkich bibliotek)
    assert store.sciezka_stanu("/nieistniejacy/katalog").exists()


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
            _playlista_testowa(app, "a", "b")
            app.action_build_from_filary()
            await pilot.pause()
            assert tc.active == "tab-lib", "2 filary = odmowa, zostajemy"
            app._user_state["playlisty"][-1]["filary"].append(
                {"track_id": "e", "path": "/m/e.mp3", "rola": ""})
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

            app._cycle_sort(3)                  # 1. klik BPM = ↓ rosnąco
            assert app._lib_sort == (3, False)
            app._render_library()
            await pilot.pause()
            assert "Detlef" in str(table.get_cell_at(Coordinate(0, 10)))
            assert "Bez Tempa" in str(
                table.get_cell_at(Coordinate(4, 11))), "brak tempa na końcu"
            klucz_bpm = app._lib_col_keys[3]
            assert "↓" in str(table.columns[klucz_bpm].label)
            app._cycle_sort(3)                  # 2. klik = ↑ malejąco
            assert app._lib_sort == (3, True)
            app._render_library()
            await pilot.pause()
            assert "Hodge" in str(table.get_cell_at(Coordinate(0, 10)))
            assert "↑" in str(table.columns[klucz_bpm].label)
            app._cycle_sort(3)                  # 3. klik kasuje, strzałka znika
            assert app._lib_sort is None
            app._render_library()
            await pilot.pause()
            assert "↓" not in str(table.columns[klucz_bpm].label)
            assert "↑" not in str(table.columns[klucz_bpm].label)

            app._cycle_sort(11)                 # tytuł: 1. klik A-Z
            assert app._lib_sort == (11, False)
            app._render_library()
            await pilot.pause()
            assert "Bez Tempa" in str(table.get_cell_at(Coordinate(0, 11)))
            app._cycle_sort(11)
            assert app._lib_sort == (11, True)  # Z-A
            app._cycle_sort(11)
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
            _playlista_testowa(app, "a", "e")
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
    assert json.loads(store.sciezka_stanu("/nieistniejacy/katalog").read_text())[
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
            _playlista_testowa(app, "b")
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
            import dancelab.tui.user_store as store3
            assert store3.filary_wpisy(app._user_state) == [], \
                "pin zdjęty razem z cięciem"
            assert app._edits[-1]["filar"] is True
    asyncio.run(go())


def test_c_otwiera_pasek_szwu_i_zamyka(tmp_path, monkeypatch):
    """C otwiera pasek szwu w duchu CURVE — same FAKTY o szwie i wskazanie,
    gdzie się go słucha (Eksport/Cue, z padów DJ-a). Drugie C chowa; ostatni
    utwór odmawia. Plan z atrapy — bez audio."""
    import dancelab.tui.seam_preview as sp
    monkeypatch.setattr(sp, "zaplanuj_szew", lambda a, b, w, **kw: {
        "cue_a_sec": 200.0, "cue_b_sec": 10.0, "beats": 64, "bpm": 130.0,
        "rate_b": 1.0, "rozumowanie": ["stabilny szew"]})

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Static, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            by_id = {a.track.track_id: a for a in LIB[:2]}
            app._ctx = dict(by_id=by_id, weights=None, arc="build",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None, params={})
            app._order = ["a", "b"]
            app._render_order(by_id)
            await pilot.pause()
            table = app.query_one("#set", DataTable)
            table.move_cursor(row=0)
            table.focus()
            await pilot.press("c")
            for _ in range(50):
                await pilot.pause(0.1)
                if app.query_one("#compare").has_class("open"):
                    break
            assert app.query_one("#compare").has_class("open")
            tytul = str(app.query_one("#cmp-title", Static).render())
            assert "SZEW #1 ⇄ #2" in tytul and "Mercy System" in tytul
            info = str(app.query_one("#cmp-info", Static).render())
            assert "64 uderzeń" in info
            assert "Eksport/Cue" in info, \
                "pasek ma mówić, GDZIE się szwu słucha"
            await pilot.press("c")            # drugie C chowa
            await pilot.pause()
            assert not app.query_one("#compare").has_class("open")
            table.move_cursor(row=1)          # ostatni — odmowa
            await pilot.pause()
            await pilot.press("c")
            await pilot.pause()
            lines = " ".join(str(l) for l in app.query_one("#warnings").lines)
            assert "ostatni utwór nie ma następnika" in lines
    asyncio.run(go())




def test_s_pyta_o_nazwe_a_o_pokazuje_bogaty_opis_i_x_usuwa(tmp_path,
                                                           monkeypatch):
    """Odpowiedź na „jak znajdziemy plan wśród 100": S pyta o nazwę,
    lista O niesie nazwę+utwory+BPM+kotwicę+datę, X usuwa MIĘKKO do kosza."""
    import dancelab.tui.plan_store as ps
    monkeypatch.setattr(ps, "PLANS_DIR", tmp_path)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import Input, OptionList, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            by_id = {a.track.track_id: a for a in LIB[:2]}
            app._ctx = dict(by_id=by_id, weights=None, arc="build",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None,
                            params={"bpm_min": 128.0, "bpm_max": 136.0,
                                    "dj": "Ben UFO"})
            app._order = ["a", "b"]
            app._engine_order = ["a", "b"]
            await pilot.press("s")
            await pilot.pause()
            from dancelab.tui.app import NazwaPlanuScreen
            assert isinstance(app.screen, NazwaPlanuScreen), "S pyta o nazwę"
            pole = app.screen.query_one("#plan-name", Input)
            pole.value = "piątek u Bartka"
            await pilot.press("enter")
            await pilot.pause()
            plany = ps.list_plans()
            assert plany[0]["nazwa"] == "piątek u Bartka"
            assert plany[0]["bpm"] == "128-136" and plany[0]["dj"] == "Ben UFO"

            await pilot.press("o")           # lista z bogatym opisem
            await pilot.pause()
            lst = app.query_one("#suggest-list", OptionList)
            opis = str(lst.get_option_at_index(0).prompt)
            assert "piątek u Bartka" in opis and "128-136" in opis \
                and "Ben UFO" in opis

            await pilot.press("x")           # miękkie usunięcie
            await pilot.pause()
            assert ps.list_plans() == []
            assert (tmp_path / "kosz").exists()
            assert len(list((tmp_path / "kosz").glob("plan_*.json"))) == 1
    asyncio.run(go())


def test_brief_swiezosc_i_seed(tmp_path, monkeypatch):
    """Domyślnie deterministycznie (seed None); tryb świeży losuje seed,
    gdy pola nie wypełniono; ręczny seed przechodzi; śmieciowy odmawia."""
    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import Input, Select, TabbedContent
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            p = app._params()
            assert p["novelty"] == "deterministic" and p["seed"] is None

            app.query_one("#novelty", Select).value = "fresh"
            p = app._params()
            assert p["novelty"] == "fresh"
            assert isinstance(p["seed"], int), "losowy seed przy pustym polu"

            app.query_one("#seed", Input).value = "4821"
            assert app._params()["seed"] == 4821

            app.query_one("#seed", Input).value = "abc"
            import pytest as _pytest
            with _pytest.raises(ValueError, match="seed to liczba"):
                app._params()
    asyncio.run(go())


def test_historia_setow_odcisk_i_odczyt(tmp_path, monkeypatch):
    """Odcisk zbudowanego setu ląduje w historii i wraca przez recent()."""
    import dancelab.tui.app as app_mod
    monkeypatch.setattr(app_mod, "HISTORIA_SETOW", tmp_path / "historia.jsonl")
    from dancelab.decision.history import (HistoryStore, context_hash,
                                           fingerprint_plan)
    odcisk = fingerprint_plan(["a", "b", "c"],
                              ctx_hash=context_hash(bpm_min=128.0),
                              seed=7, novelty_mode="fresh", pinned_ids=["b"])
    HistoryStore(app_mod.HISTORIA_SETOW).append(odcisk)
    wrocilo = HistoryStore(app_mod.HISTORIA_SETOW).recent()
    assert len(wrocilo) == 1
    assert wrocilo[0].track_ids_ordered == ["a", "b", "c"]
    assert wrocilo[0].pinned_ids == ["b"] and wrocilo[0].seed == 7


def test_lufs_parser_cache_i_bramkarz(tmp_path, monkeypatch):
    """LUFS: parser podsumowania ebur128 + trwały cache z kluczem
    path|size|mtime; bramkarz: zdrowy przechodzi, chory z imiennym powodem,
    brak ffprobe NIE blokuje."""
    import dancelab.ingestion.loudness as ld
    from dancelab.ingestion.bramkarz import przesiej, sprawdz_plik

    assert ld.wyluskaj_lufs("...\n    I:   -8.7 LUFS\n...") == -8.7
    assert ld.wyluskaj_lufs("zadnego podsumowania") is None

    monkeypatch.setattr(ld, "CACHE", tmp_path / "lufs.json")
    plik = tmp_path / "a.wav"
    plik.write_bytes(b"RIFFdane")
    mapa = ld.zmierz_brakujace([str(plik)],
                               run_fn=lambda p: "I: -9.9 LUFS")
    assert mapa[str(plik)] == -9.9
    # drugi przebieg NIE woła ffmpeg (cache) — run_fn wybucha, gdyby wołał
    mapa2 = ld.zmierz_brakujace([str(plik)],
                                run_fn=lambda p: 1 / 0)
    assert mapa2[str(plik)] == -9.9
    # podmiana pliku uniewaznia wpis
    plik.write_bytes(b"RIFFinne dane dluzsze")
    mapa3 = ld.zmierz_brakujace([str(plik)],
                                run_fn=lambda p: "I: -5.0 LUFS")
    assert mapa3[str(plik)] == -5.0

    def fake_probe(path):
        if "chory" in path:
            return 1, "", "moov atom not found"
        if "pusty" in path:
            return 0, '{"streams": []}', ""
        return 0, '{"streams": [{"codec_name": "pcm_s16le"}]}', ""
    assert sprawdz_plik("/m/ok.wav", run_fn=fake_probe) is None
    assert "uszkodzony" in sprawdz_plik("/m/chory.wav", run_fn=fake_probe)
    assert "brak strumienia audio" in sprawdz_plik("/m/pusty.wav",
                                                   run_fn=fake_probe)
    zdrowe, odrzucone = przesiej(["/m/ok.wav", "/m/chory.wav"],
                                 run_fn=fake_probe)
    assert zdrowe == ["/m/ok.wav"] and len(odrzucone) == 1

    def brak_ffprobe(path):
        raise FileNotFoundError
    assert sprawdz_plik("/m/ok.wav", run_fn=brak_ffprobe) is None


def test_zdjecie_filtra_nie_ubija_granego_utworu(tmp_path, monkeypatch):
    """Regres z życia 06.08: szukajka → play → wyczyszczenie filtra grało
    pierwszy utwór z listy. Teraz: render NIE jest nawigacją, a kursor
    odnajduje grany utwór na pełnej liście."""
    import subprocess
    import dancelab.tui.odtwarzacz as odt
    monkeypatch.setattr(odt, "FFPLAY", "/fake/ffplay")
    monkeypatch.setattr(odt, "AFPLAY", "/fake/afplay")

    class _FakeProc:
        def __init__(self, cmd):
            self.cmd = cmd
            self.killed = False

        def poll(self):
            return 1 if self.killed else None

        def terminate(self):
            self.killed = True

    started = []
    monkeypatch.setattr(subprocess, "Popen",
                        lambda cmd: started.append(_FakeProc(cmd)) or started[-1])

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Input
            app._set_library(list(LIB))
            await pilot.pause()
            app.query_one("#lib-search", Input).value = "hodge"
            await pilot.pause(0.3)
            table = app.query_one("#lib-table", DataTable)
            assert table.row_count == 1
            table.move_cursor(row=0)
            table.focus()
            await pilot.press("space")        # gra Hodge z przefiltrowanej
            await pilot.pause()
            assert started[-1].cmd[-1].endswith("Hodge - Wiggler.mp3")

            app.query_one("#lib-search", Input).value = ""   # zdejmij filtr
            await pilot.pause(0.5)
            assert table.row_count == 5
            assert not started[0].killed, "grany utwór przeżył zdjęcie filtra"
            assert len(started) == 1, "nic nowego nie wystartowało"
            wiersz = table.cursor_row
            from dancelab.tui.app import _wykonawca_tytul
            assert _wykonawca_tytul(
                app._lib_view[wiersz].track)[0] == "Hodge", \
                "kursor odnalazł grany utwór na pełnej liście"
    asyncio.run(go())


def test_mozaika_okladki_renderuje_i_brak_jest_none(tmp_path, monkeypatch):
    """Okładka z tagów → mozaika o zadanych wymiarach; plik bez okładki →
    None (rysujemy pustkę, nie zmyślony obrazek)."""
    import dancelab.tui.okladki as ok
    from PIL import Image
    import io
    obraz = Image.new("RGB", (100, 100), (200, 40, 40))
    buf = io.BytesIO()
    obraz.save(buf, format="PNG")
    monkeypatch.setattr(ok, "_bajty_okladki",
                        lambda path: buf.getvalue() if "ma" in path else None)
    ok.mozaika.cache_clear()
    moz = ok.mozaika("/m/ma_okladke.mp3", 12, 6)
    assert moz is not None
    from rich.console import Console
    wyjscie = Console(width=40, record=True)
    wyjscie.print(moz)
    linie = wyjscie.export_text().splitlines()
    assert len(linie) == 6, "wysokość w komórkach zgodna z zamówieniem"
    assert ok.mozaika("/m/bez.mp3", 12, 6) is None


def test_k_przelacza_okladki_w_liscie(tmp_path, monkeypatch):
    """K: galeria z okładkami (wiersze ×3, mozaika w 1. kolumnie) ↔ widok
    kompaktowy; stan trwały."""
    import dancelab.tui.okladki as ok
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), (10, 200, 90)).save(buf, format="PNG")
    monkeypatch.setattr(ok, "_bajty_okladki",
                        lambda path: buf.getvalue() if "Hodge" in path else None)
    ok.mozaika.cache_clear()
    # K odpala też dociąganie okładek (jedna dźwignia) — w teście bez sieci
    monkeypatch.setattr(DanceLabTUI, "_artwork_worker", lambda self: None)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.coordinate import Coordinate
            from textual.widgets import DataTable
            from rich_pixels import Pixels
            app._set_library(list(LIB))
            await pilot.pause()
            table = app.query_one("#lib-table", DataTable)
            assert str(table.get_cell_at(Coordinate(0, 0))) == "", \
                "kompaktowo: kolumna okładek pusta"
            table.focus()
            await pilot.press("k")
            await pilot.pause()
            assert app._user_state["okladki_w_liscie"] is True
            wiersz_hodge = next(
                i for i, a in enumerate(app._lib_view)
                if "Hodge" in a.track.source_path)
            assert isinstance(
                table.get_cell_at(Coordinate(wiersz_hodge, 0)), Pixels), \
                "galeria: mozaika w kolumnie okładek"
            await pilot.press("k")
            await pilot.pause()
            assert app._user_state["okladki_w_liscie"] is False
    asyncio.run(go())


def test_pool_ctx_for_dziala_bez_wczesniejszej_budowy(monkeypatch):
    """Regresja 08.08: O (wczytaj plan) bez wcześniejszej budowy wołało
    _pool_ctx_for, a tam brakowało importu attach_rekordbox_meta —
    worker połykał NameError jako notkę i plan nigdy nie wchodził."""
    import asyncio as aio

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test():
            monkeypatch.setattr(app, "_library_analyses",
                                lambda: (list(LIB), []))
            ctx = await aio.to_thread(app._pool_ctx_for, {})
            assert ctx["by_id"], "pula z biblioteki dopięta pod plan"
            assert "weights" in ctx
    asyncio.run(go())


def test_odmowa_filarow_wymienia_winowajcow_z_tempem():
    """Skarga Janka 09.08: „mimo że dodałem 4 filary" — odmowa mówiła ILE
    zostało, nie KTÓRE wypadły. Ma nieść nazwiska, tempa i okno."""
    with pytest.raises(ValueError) as exc:
        _filary_for_build(_state("a", "b", "c", "e"), _by_id(), 130, 131, 10)
    tekst = str(exc.value)
    assert "wypadły" in tekst
    assert "Mercy System - Steppers (132" in tekst, "nazwisko + tempo"
    assert "130–131" in tekst, "okno tempa w radzie"


def test_buduj_set_zawsze_widoczny_bez_skrolowania():
    """Skarga Janka 09.08: „Buduj set powinien być fixed na dole, bo teraz
    trzeba zeskrolować, żeby się pojawił". Guzik dokowany do dołu kolumny
    briefu; pola przewijają się pod nim. Test mierzy GEOMETRIĘ."""
    from textual.widgets import Button, TabbedContent

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test(size=(120, 30)) as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            guzik = app.query_one("#go", Button)
            kolumna = app.query_one("#form")
            wyniki = app.query_one("#results")
            dol_guzika = guzik.region.y + guzik.region.height
            dol_kolumny = kolumna.region.y + kolumna.region.height
            assert abs(dol_guzika - dol_kolumny) <= 1, \
                "guzik przy dolnej krawędzi, nie na końcu przewijania"
            assert wyniki.region.x > kolumna.region.x, \
                "kolumna wyników nadal OBOK briefu, nie pod nim"
    asyncio.run(go())


def test_nowa_playlista_wraca_do_biblioteki_a_budowa_zapisuje(
        tmp_path, monkeypatch):
    """Decyzje Janka 12.08: Enter po nazwie → OD RAZU Biblioteka (F przypina
    filary do playlisty), a każda udana budowa zapisuje utwory DO aktywnej
    playlisty (ostatnia budowa wygrywa)."""
    import dancelab.tui.user_store as store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            from textual.widgets import DataTable, Input
            app._lib = LIB
            app._set_lib_section("pl-new")          # ＋ nowa playlista
            await pilot.pause()
            pole = app.screen.query_one("#plan-name", Input)
            pole.value = "Środa testowa"
            pole.focus()
            await pilot.press("enter")
            await pilot.pause()
            pl = store.aktywna_playlista(app._user_state)
            assert pl is not None and pl["nazwa"] == "Środa testowa"
            assert app._lib_section == "all", "po nazwie wracamy do Biblioteki"
            assert app.focused is app.query_one("#lib-table", DataTable), \
                "fokus na tabeli Biblioteki — od razu można zaznaczać F"

            class _Plan:
                track_order = ["a", "b", "e"]
                mean_transition_score = 0.5
                warnings = []

            app._ctx = dict(by_id=_by_id(), weights=None, arc="off",
                            planner="smart", bpm_min=None, bpm_max=None,
                            anchor=None, params={}, filary=[])
            app._show_plan(_Plan(), _by_id(), [])
            await pilot.pause()
            zapisane = [e["track_id"]
                        for e in store.utwory_playlisty(app._user_state)]
            assert zapisane == ["a", "b", "e"], "budowa zapisała set W playliście"
    asyncio.run(go())

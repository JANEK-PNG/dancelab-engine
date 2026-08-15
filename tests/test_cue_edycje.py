"""Edytor cue etap 2 — warstwa edycji padów + klawisze w zakładce.

Model: propozycje silnika niezmienne, edycje DJ-a jako nakładka; ślad
silnika (silnik_ms) nie znika po przesunięciu — uczciwość „o ile się
różnimy". Z cofa po kroku. Klawisze: litera=pad, strzałki=uderzenia,
X=zdejmij (wszystko tylko w zakładce Eksport/Cue, zero zapisu).
"""

import asyncio

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.tui import cue_edycje, cue_podglad
from dancelab.tui.cue_podglad import zbuduj_plan_cue


def _analysis(track_id, *, title=""):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title,
                    source_path=f"/m/{track_id}.wav", duration_sec=360.0),
        beatgrid=BeatGrid(bpm=120.0, reliable=True),
        segments=[],
    )


def _okna_atrapa(analysis, weights):
    if analysis.track.track_id == "A":
        return [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9,
                                 window_type=WindowType.mix_out)]
    return [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9,
                             window_type=WindowType.mix_in)]


def _plan(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A", title="Alfa"),
             "B": _analysis("B", title="Beta")}
    return zbuduj_plan_cue(["A", "B"], by_id, weights=None), by_id


def test_przesun_liczy_uderzenia_i_pamieta_silnik(monkeypatch):
    plan, _ = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    przed = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    assert przed["zrodlo"] == "silnik" and przed["position_ms"] == 300000
    nowa = cue_edycje.przesun(ed, "A", "B", -8, 120.0,
                              przed["silnik_ms"], przed["position_ms"])
    assert nowa == 300000 - 8 * 500, "8 uderzeń przy 120 BPM = 4 s"
    po = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    assert po["zrodlo"] == "reka"
    assert po["silnik_ms"] == 300000, "ślad silnika nie znika"


def test_cofnij_wraca_po_kroku(monkeypatch):
    plan, _ = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    p = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    cue_edycje.przesun(ed, "A", "B", +1, 120.0, p["silnik_ms"],
                       p["position_ms"])
    cue_edycje.zdejmij(ed, "A", "B")
    assert "B" not in cue_edycje.efektywne_pady(plan, ed, "A")
    assert cue_edycje.cofnij(ed)
    assert cue_edycje.efektywne_pady(plan, ed, "A")["B"]["zrodlo"] == "reka"
    assert cue_edycje.cofnij(ed)
    assert cue_edycje.efektywne_pady(plan, ed, "A")["B"]["zrodlo"] == "silnik"
    assert not cue_edycje.cofnij(ed), "pusta historia mówi False"


def test_postaw_reczny_pad_i_zdejmij(monkeypatch):
    plan, _ = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    cue_edycje.postaw(ed, "A", "C", 123500)
    p = cue_edycje.efektywne_pady(plan, ed, "A")["C"]
    assert p["zrodlo"] == "reka" and p["silnik_ms"] is None
    cue_edycje.zdejmij(ed, "A", "C")
    assert "C" not in cue_edycje.efektywne_pady(plan, ed, "A")


def test_klawisze_w_zakladce_edytuja_pady(tmp_path, monkeypatch):
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            self_tabs = app.query_one("#tabs", TabbedContent)
            self_tabs.active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            assert app._cue_track == "A"

            await pilot.press("b")          # litera = wybór istniejącego pada
            assert app._cue_wybor == "B"

            # ←/→ przesuwa o TAKT (4 uderzenia), bo hot cue stoi na
            # „jedynce" — ruch o jeden bit tylko by z niej zsuwał
            await pilot.press("left")
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 300000 - 2000, "jeden takt @120 = 2 s"
            assert p["zrodlo"] == "reka"

            await pilot.press("d")          # brak pada D → nowy ręczny
            assert app._cue_wybor == "D"
            assert "D" in cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")

            await pilot.press("x")          # zdejmij wybrany
            assert "D" not in cue_edycje.efektywne_pady(
                plan, app._cue_edycje, "A")

            await pilot.press("z")          # cofnij zdjęcie
            assert "D" in cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")

    asyncio.run(go())


def test_p_gra_od_wybranego_pada_bez_dzwieku_w_testach(tmp_path, monkeypatch):
    """Etap 3 (skarga Janka 09.08: „nie mam pojęcia jak podsłuchać od A"):
    P z wybranym padem gra TEN utwór od pozycji pada; drugi raz stop.
    W testach odtwarzacz jest atrapą — dźwięk nigdy nie startuje sam."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR",
                        tmp_path / "werdykty")
    plan, by_id = _plan(monkeypatch)
    zagrane = []

    class Atrapa:
        def gra(self):
            return False

        sciezka = None

        def graj_od(self, path, bpm, sekunda):
            zagrane.append((path, sekunda))
            return None

        def graj_od_zera(self, path, bpm):
            zagrane.append((path, 0.0))
            return None

        def stop(self):
            return False

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()

            await pilot.press("b")          # pad B (wyjście @ 300 s)
            await pilot.press("p")
            assert zagrane == [("/m/A.wav", 300.0)], \
                "P gra utwór A od pozycji pada B"

    asyncio.run(go())


def test_cue_nazwa_nie_dubluje_artysty(monkeypatch):
    from dancelab.tui.app import DanceLabTUI

    plan, by_id = _plan(monkeypatch)
    by_id["A"].track.artist = "O'Flynn"
    by_id["A"].track.title = "O'Flynn - Sekete (ft. Swordman Kit)"
    app = DanceLabTUI.__new__(DanceLabTUI)
    app._ctx = {"by_id": by_id}
    assert app._cue_nazwa("A") == "O'Flynn – Sekete (ft. Swordman Kit)"


def test_znajdz_narzedzie_zna_gniazda_homebrew(tmp_path, monkeypatch):
    """Regresja 09.08: apka z ikony dostaje goły PATH launchd — ffplay
    z Homebrew musi się znaleźć mimo braku w PATH."""
    import dancelab.tui.odtwarzacz as odt

    monkeypatch.setattr(odt.shutil, "which", lambda n: None)
    narzedzie = tmp_path / "ffplay"
    narzedzie.write_text("#!/bin/sh\n")
    assert odt._znajdz("ffplay", katalogi=(str(tmp_path),)) == str(narzedzie)
    assert odt._znajdz("czegos_nie_ma", katalogi=(str(tmp_path),)) is None


def test_os_czasu_ma_glowice_w_miejscu_odtwarzania():
    """Oś czasu w pasku (decyzja Janka 09.08): energia utworu + głowica
    w miejscu odtwarzania + zegar; bez analizy NIC nie rysujemy."""
    from dancelab.core.models import FeatureFrame
    from dancelab.tui.pasek import os_z_glowica

    a = _analysis("A")            # duration_sec = 360
    a.features = [FeatureFrame(track_id="A", timestamp_sec=float(t),
                               rms=0.2 + (t % 60) / 100.0)
                  for t in range(0, 360, 5)]
    poczatek = os_z_glowica(a, 0.0, 40)
    srodek = os_z_glowica(a, 180.0, 40)
    assert poczatek.plain.index("▮") == 0, "na starcie głowica z lewej"
    assert srodek.plain.index("▮") == 20, "w połowie utworu — w połowie osi"
    assert "3:00 / 6:00" in srodek.plain, "zegar teraz/całość"
    assert os_z_glowica(None, 10.0, 40) is None, "bez analizy: brak rysunku"
    assert os_z_glowica(a, 10.0, 4) is None, "za wąsko: brak rysunku"


def test_karta_pokazuje_wszystkie_osiem_padow(tmp_path, monkeypatch):
    """Tabelka jak w Rekordboksie (życzenie Janka 09.08): sloty A–H są
    WIDOCZNE zawsze — puste mówią, że można tam postawić pad."""
    from textual.widgets import DataTable, Static, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            tab = str(app.query_one("#cue-pady", Static).render())
            wiersze = tab.splitlines()
            assert wiersze[0] == "HOT CUE", "kolumna po prawej, jak w RB"
            # siatka 2×4 jak pady na CDJ-u (życzenie Janka 09.08)
            assert all(f"{litera} " in wiersze[1] for litera in "ABCD")
            assert all(f"{litera} " in wiersze[2] for litera in "EFGH")
            assert tab.count("—") == 7, "jeden pad zajęty, siedem wolnych"
            os_lewa = str(app.query_one("#cue-os", Static).render())
            assert "energia" in os_lewa and "czas" in os_lewa, \
                "oś utworu została po lewej stronie"

    asyncio.run(go())


def test_druga_litera_przenosi_pad_pod_glowice(tmp_path, monkeypatch):
    """Skarga Janka 09.08: „jak przestawić hot cue w czasie, bo to
    nieintuicyjne". Strzałki zostają do precyzji, ale duży skok robi się
    tak jak na sprzęcie: graj → dojedź → ta sama litera drugi raz."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)

    class Atrapa:
        sciezka = "/m/A.wav"

        def gra(self):
            return True

        def pozycja(self):
            return 100.0        # 1:40

        def skonczyl_sie(self):
            return None

        def stop(self):
            return False

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()

            await pilot.press("b")             # wybór (pad B @ 300 s)
            assert app._cue_wybor == "B"
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 300_000, "pierwsze naciśnięcie nie rusza"

            await pilot.press("b")             # drugie = przenieś pod głowicę
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 100_000, "pad ląduje na 1:40"
            assert p["zrodlo"] == "reka"
            assert p["silnik_ms"] == 300_000, "ślad silnika zostaje"

            await pilot.press("z")             # cofnięcie działa
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 300_000

    asyncio.run(go())


def test_przenoszenie_odmawia_gdy_odtwarzacz_stoi_gdzie_indziej(tmp_path,
                                                               monkeypatch):
    """Bez odtwarzacza na TYM utworze „przenieś tu" nie ma sensu — odmowa
    z powodem, nie ciche przeniesienie w przypadkowe miejsce."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            await pilot.press("b")
            await pilot.press("b")
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 300_000, "nic nie ruszone"
            notki = " ".join(str(x) for x in app.query_one("#warnings").lines)
            assert "najpierw P" in notki

    asyncio.run(go())


def test_parsowanie_czasu_i_kwantyzacja():
    """Ręczne wpisanie czasu (życzenie Janka 09.08): rozumiemy zapis
    minutowy i sekundowy, przecinek jak kropka; wpisana wartość jest
    dociągana do siatki — jak quantize w Rekordboksie."""
    from dancelab.core.models import BeatGrid
    from dancelab.tui.cue_edycje import czas_po_kwantyzacji, parsuj_czas

    assert parsuj_czas("2:31") == 151.0
    assert parsuj_czas("2:31,5") == 151.5, "przecinek działa jak kropka"
    assert parsuj_czas(" 151 ") == 151.0
    assert parsuj_czas("bzdura") is None and parsuj_czas("") is None

    # siatka co 0,5 s (120 BPM), faza taktu NIEzweryfikowana → snap do bitu
    grid = BeatGrid(bpm=120.0, beat_times_sec=[i * 0.5 for i in range(400)],
                    quality_score=0.9)
    czas, powod = czas_po_kwantyzacji(grid, 151.2)
    assert czas == 151.0 and "bitu" in powod
    czas, powod = czas_po_kwantyzacji(grid, 151.0)
    assert czas == 151.0 and powod == "trafione w siatkę"


def test_t_wpisuje_czas_pada_i_dociaga(tmp_path, monkeypatch):
    from textual.widgets import DataTable, TabbedContent

    from dancelab.core.models import BeatGrid
    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)
    by_id["A"].beatgrid = BeatGrid(
        bpm=120.0, beat_times_sec=[i * 0.5 for i in range(800)],
        quality_score=0.9)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            await pilot.press("b")               # wybór pada B (300 s)
            await pilot.press("t")               # edycja W KRATCE pada
            await pilot.pause()
            assert app._cue_czas_bufor is not None, "tryb edycji w kratce"
            for _ in range(8):                   # kasujemy podpowiedziany czas
                await pilot.press("backspace")
            for znak in ("2", "colon", "3", "1", "comma", "2"):
                await pilot.press(znak)          # piszemy wprost w kratce
            assert app._cue_czas_bufor == "2:31,2"
            await pilot.press("enter")
            await pilot.pause()
            assert app._cue_czas_bufor is None, "po Enterze wychodzimy z trybu"
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 151_000, \
                "2:31,2 dociągnięte do bitu na 2:31,0"

    asyncio.run(go())


def test_esc_zamyka_pole_czasu_bez_zmiany(tmp_path, monkeypatch):
    """Pole czasu przy padach (weto Janka na okienko): Esc chowa je
    i oddaje fokus liście, nie ruszając pada."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            await pilot.press("b")
            await pilot.press("t")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app._cue_czas_bufor is None, "Esc wychodzi z edycji"
            assert app.focused.id == "cue-table", "fokus zostaje na liście"
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 300_000, "pad nietknięty"

    asyncio.run(go())


def test_gotowe_czasy_fraz_do_wyboru_strzalkami(tmp_path, monkeypatch):
    """„Dropdown z gotowymi timingami fraz" (życzenie Janka 09.08):
    propozycje to POCZĄTKI SEKCJI utworu + czas silnika — zmierzone,
    nie wymyślone; ↑↓ wstawia je do kratki."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.core.models import Segment, SegmentType
    from dancelab.tui.app import DanceLabTUI
    from dancelab.tui.cue_podglad import propozycje_czasu

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)
    by_id["A"].segments = [
        Segment(segment_id="s1", track_id="A", start_sec=0.0, end_sec=30.0,
                segment_type=SegmentType.intro),
        Segment(segment_id="s2", track_id="A", start_sec=124.0, end_sec=180.0,
                segment_type=SegmentType.breakdown),
    ]

    prop = propozycje_czasu(by_id["A"], silnik_ms=300_000)
    assert ("INTRO", 0.0) in prop and ("BREAK", 124.0) in prop
    assert ("silnik", 300.0) in prop, "propozycja silnika też na liście"

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            await pilot.press("b")
            await pilot.press("t")
            await pilot.pause()
            await pilot.press("down")            # wybór kolejnej frazy
            assert app._cue_czas_bufor == "2:04.0", "BREAK wskoczył do kratki"
            await pilot.press("enter")
            await pilot.pause()
            p = cue_edycje.efektywne_pady(plan, app._cue_edycje, "A")["B"]
            assert p["position_ms"] == 124_000

    asyncio.run(go())


def test_lista_fraz_przewija_sie_i_mowi_ile_zostalo(tmp_path, monkeypatch):
    """Skarga Janka 09.08: „lista powinna się skrolować, bo w oryginale
    jest więcej fraz niż w wyborze". Dane wracają w CAŁOŚCI, przewija się
    widok, a licznik i strzałki mówią, ile jest poza kadrem."""
    from textual.widgets import DataTable, Static, TabbedContent

    from dancelab.core.models import Segment, SegmentType
    from dancelab.tui.app import DanceLabTUI
    from dancelab.tui.cue_podglad import propozycje_czasu

    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    plan, by_id = _plan(monkeypatch)
    by_id["A"].segments = [
        Segment(segment_id=f"s{i}", track_id="A", start_sec=i * 25.0,
                end_sec=(i + 1) * 25.0,
                segment_type=SegmentType.groove if i % 2 else
                SegmentType.breakdown)
        for i in range(12)
    ]
    assert len(propozycje_czasu(by_id["A"], 300_000)) == 13, \
        "wszystkie frazy + silnik, bez cichego obcinania"

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app._cue_plan = plan
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._render_cue_lista()
            app.query_one("#cue-table", DataTable).focus()
            await pilot.pause()
            await pilot.press("b")
            await pilot.press("t")
            await pilot.pause()
            widok = str(app.query_one("#cue-pady", Static).render())
            assert "1/13" in widok, "licznik pozycji na liście"
            assert "niżej" in widok, "widać, że coś jest poza kadrem"
            for _ in range(8):
                await pilot.press("down")
            widok = str(app.query_one("#cue-pady", Static).render())
            assert "9/13" in widok and "wyżej" in widok, "widok przewinięty"

    asyncio.run(go())


def test_cue_ladują_na_poczatku_taktu(monkeypatch):
    """Życzenie Janka 09.08: hot cue stoi tam, gdzie Rekordbox rysuje czerwoną
    linię taktu — 68.1, nie 68.2. Dotyczy WSZYSTKICH dróg: propozycji silnika,
    ręcznie wpisanego czasu i gotowych czasów fraz."""
    from dancelab.core.models import BeatGrid
    from dancelab.tui.cue_edycje import czas_po_kwantyzacji

    # takty co 2 s (120 BPM, 4/4) — dokładnie tak, jak liczy je Rekordbox
    takty = [round(i * 2.0, 3) for i in range(200)]
    siatka = BeatGrid(bpm=120.0, reliable=True,
                      beat_times_sec=[i * 0.5 for i in range(800)],
                      downbeat_phase_verified=True)

    czas, powod = czas_po_kwantyzacji(siatka, 136.7, takty)
    assert czas == 136.0, "najbliższy TAKT, nie najbliższy bit"
    assert "taktu 69" in powod, f"powód ma nazwać takt: {powod}"

    czas, powod = czas_po_kwantyzacji(siatka, 137.4, takty)
    assert czas == 138.0, "w drugą stronę też do najbliższego taktu"


def test_bez_siatki_rekordboxa_mowimy_ze_nie_znamy_taktu():
    """Bez fazy taktu nie wiemy, który bit jest jedynką — przyciągamy do bitu
    i mówimy o tym wprost, zamiast zgadywać takt."""
    from dancelab.core.models import BeatGrid
    from dancelab.tui.cue_edycje import czas_po_kwantyzacji

    siatka = BeatGrid(bpm=120.0, reliable=True,
                      beat_times_sec=[i * 0.5 for i in range(800)],
                      downbeat_phase_verified=False)
    czas, powod = czas_po_kwantyzacji(siatka, 136.7, downbeaty=None)
    assert czas == 136.5, "najbliższy bit"
    assert "który bit jest jedynką" in powod


def test_propozycje_fraz_startuja_na_takcie():
    """„Jak mamy te automatyczne ustawianie cue to fraz, to ma się zaczynać
    na początku taktu" — Janek 09.08."""
    from dancelab.core.models import AnalysisResult, Segment, SegmentType, Track
    from dancelab.tui.cue_podglad import propozycje_czasu

    analiza = AnalysisResult(
        engine_version="test",
        track=Track(track_id="A", source_path="/m/a.wav", duration_sec=300.0),
        segments=[
            Segment(segment_id="s1", track_id="A", start_sec=30.3,
                    end_sec=60.0, segment_type=SegmentType.intro),
            Segment(segment_id="s2", track_id="A", start_sec=60.9,
                    end_sec=90.0, segment_type=SegmentType.drop),
        ])
    takty = [round(i * 2.0, 3) for i in range(200)]
    punkty = propozycje_czasu(analiza, silnik_ms=None, downbeaty=takty)
    assert [sek for _n, sek in punkty] == [30.0, 60.0], \
        "każda fraza dociągnięta do początku taktu"

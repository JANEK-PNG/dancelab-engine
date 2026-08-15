"""S w zakładce Set gra szew z propozycji silnika — i nie ubija aplikacji.

Commit 3a23d1a (13.08) wprowadził S w Secie i przełączał zakładkę na
`"tab-cue"`. Zakładki o takim identyfikatorze nie ma (`_TAB_ORDER` to
lib/dj/set/export), więc Textual rzucał `ValueError: No Tab with id
'--content-tab-tab-cue'` i program padał — na klawiszu, który instrukcja
użytkownika każe nacisnąć. Commit nie miał testu; ten test jest tym testem.

Sedno: w Secie nie ma jeszcze padów DJ-a, więc szew MUSI powstać z okien
przejść (propozycja silnika), a nie z planu cue, którego może w ogóle nie
być, jeśli DJ nie zajrzał do Eksportu.

Dźwięk w testach nie startuje nigdy: odtwarzacz i render są atrapami.
"""

import asyncio

from dancelab.core.models import AnalysisResult, BeatGrid, Track
from dancelab.tui import seam_preview


def _analysis(track_id, sciezka, *, title=""):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title, source_path=str(sciezka),
                    duration_sec=360.0, bpm_estimate=120.0),
        beatgrid=BeatGrid(bpm=120.0, reliable=True), segments=[])


class _Atrapa:
    """Odtwarzacz-atrapa: zapisuje, co miałoby zagrać. Cisza."""

    sciezka = None

    def __init__(self):
        self.zagrane = []

    def gra(self):
        return False

    def graj_od_zera(self, path, bpm):
        self.zagrane.append((path, bpm))
        return None

    def graj_od(self, path, bpm, sekunda):
        self.zagrane.append((path, sekunda))
        return None

    def stop(self):
        return False

    def pozycja(self):
        return 0.0

    def skonczyl_sie(self):
        return None

    def opis(self):
        return ""


def _srodowisko(tmp_path, monkeypatch):
    """Dwa utwory z realnie istniejącymi plikami + atrapa renderu."""
    monkeypatch.setattr("dancelab.tui.app.WERDYKTY_DIR", tmp_path / "w")
    pliki = {}
    for tid in ("A", "B"):
        p = tmp_path / f"{tid}.wav"
        p.write_bytes(b"RIFF")
        pliki[tid] = p
    by_id = {"A": _analysis("A", pliki["A"], title="Alfa"),
             "B": _analysis("B", pliki["B"], title="Beta")}
    wywolania = []
    wav = tmp_path / "szew.wav"
    wav.write_bytes(b"RIFF")

    def render_atrapa(a, b, weights, **kw):
        wywolania.append((a.track.track_id, b.track.track_id))
        return {"output": wav, "cue_a_sec": 300.0, "cue_b_sec": 30.0,
                "bpm": 120.0, "rate_b": 1.0, "beats": 32, "rozumowanie": []}

    monkeypatch.setattr(seam_preview, "zbuduj_szew", render_atrapa)
    return by_id, wywolania, wav


def test_s_w_secie_gra_szew_i_nie_przelacza_zakladki(tmp_path, monkeypatch):
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    by_id, wywolania, wav = _srodowisko(tmp_path, monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = _Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            # celowo BEZ planu cue: DJ nie zaglądał do Eksportu
            app._cue_plan = None
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            app.query_one("#set", DataTable).focus()
            await pilot.pause()

            await pilot.press("s")
            for _ in range(60):
                await pilot.pause(0.05)
                if app._odtwarzacz.zagrane:
                    break

            assert wywolania == [("A", "B")], \
                "S ma zszyć parę pod kursorem z propozycji silnika"
            assert app._odtwarzacz.zagrane == [(str(wav), 120.0)]
            assert app.query_one("#tabs", TabbedContent).active == "tab-set", \
                "S nie ma wyrzucać DJ-a z zakładki, w której stoi"

    asyncio.run(go())


def test_s_na_ostatnim_utworze_mowi_dlaczego_nie_gra(tmp_path, monkeypatch):
    """Ostatni utwór nie ma następnika — to stan, nie awaria."""
    from textual.widgets import DataTable, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    by_id, wywolania, _ = _srodowisko(tmp_path, monkeypatch)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._odtwarzacz = _Atrapa()
            app._ctx = {"by_id": by_id, "weights": None}
            app._order = ["A", "B"]
            app.query_one("#tabs", TabbedContent).active = "tab-set"
            await pilot.pause()
            app._render_order(by_id)              # realne wiersze setu
            t = app.query_one("#set", DataTable)
            t.focus()
            await pilot.pause()
            t.move_cursor(row=1)                  # ostatni utwór setu
            await pilot.pause()
            assert t.cursor_row == 1

            await pilot.press("s")
            await pilot.pause(0.1)

            assert not wywolania, "na ostatnim utworze nie ma czego zszywać"
            assert app._odtwarzacz.zagrane == []
            assert app.query_one("#tabs", TabbedContent).active == "tab-set"

    asyncio.run(go())

"""Podgląd cue w zakładce Eksport/Cue (etap 1) — czysta warstwa + UI.

Etap 1 niczego nie zapisuje: liczy propozycje padów dla BIEŻĄCEJ kolejności
setu (po edycjach) i uczciwie mówi, co jest pewne, a co wymaga odsłuchu.
"""

import asyncio

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.decision.cue_export_models import CuePlan
from dancelab.tui import cue_podglad
from dancelab.tui.cue_podglad import wiersze_podgladu, zbuduj_plan_cue


def _analysis(track_id, *, title="", key=None, reliable=True):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title, key_estimate=key,
                    source_path=f"/m/{track_id}.wav"),
        beatgrid=BeatGrid(bpm=120.0, reliable=reliable),
        segments=[],
    )


def _okna_atrapa(analysis, weights):
    if analysis.track.track_id == "A":
        return [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9,
                                 window_type=WindowType.mix_out)]
    return [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9,
                             window_type=WindowType.mix_in)]


def test_plan_dla_pary_stawia_wyjscie_na_A_i_wejscie_na_B(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A", key="8A"), "B": _analysis("B", key="9A")}
    plan = zbuduj_plan_cue(["A", "B"], by_id, weights=None)
    typy = {(t.content_id, c.cue_type)
            for t in plan.tracks for c in t.cues}
    assert ("A", "mix_out") in typy and ("B", "mix_in") in typy


def test_utwor_bez_analizy_wraca_imiennie_a_reszta_zyje(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A"), "B": _analysis("B")}
    plan = zbuduj_plan_cue(["A", "duch", "B"], by_id, weights=None)
    assert any("duch" in w for w in plan.warnings)
    assert plan.tracks, "obecne utwory dalej dostają propozycje"


def test_wiersze_podgladu_format_i_uczciwosc(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A", title="Alfa"),
             "B": _analysis("B", title="Beta", reliable=False)}
    plan = zbuduj_plan_cue(["A", "B"], by_id, weights=None)
    wiersze = wiersze_podgladu(plan, ["A", "B"], {"A": "Alfa", "B": "Beta"})
    assert wiersze, "para z oknami daje wiersze"
    w_a = next(w for w in wiersze if w[1] == "Alfa")
    assert w_a[3] == "5:00.0", "pozycja w mm:ss z okna mix-out"
    w_b = next(w for w in wiersze if w[1] == "Beta")
    assert w_b[5] == "POSŁUCHAJ", \
        "niewiarygodna siatka po stronie B = cue bez ✓ (uczciwość)"


def test_zakladka_bez_setu_mowi_co_zrobic():
    from textual.widgets import Static

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app._cue_podglad_worker()
            await pilot.pause()
            for _ in range(20):
                tekst = str(app.query_one("#cue-head", Static).render())
                if "Brak setu" in tekst:
                    break
                await asyncio.sleep(0.05)
            assert "zbuduj go w zakładce Set" in tekst

    asyncio.run(go())


def test_zakladka_z_setem_liczy_podglad_i_deklaruje_brak_zapisu():
    from textual.widgets import Static

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test():
            app._ctx = {"by_id": {"A": _analysis("A", title="Alfa"),
                                  "B": _analysis("B", title="Beta")},
                        "weights": None}
            app._order = ["A", "B"]
            app._cue_podglad_worker()
            tekst = ""
            for _ in range(40):
                tekst = str(app.query_one("#cue-head", Static).render())
                if "zapisuję" in tekst or "nie wyszedł" in tekst:
                    break
                await asyncio.sleep(0.05)
            assert "nic nie zapisuję" in tekst, tekst

    asyncio.run(go())


def test_podglad_niczego_nie_zapisuje():
    """Etap 1: moduł podglądu nie może nawet importować warstwy zapisu."""
    import dancelab.tui.cue_podglad as m
    zrodlo = open(m.__file__).read()
    assert "rekordbox_cue_writer" not in zrodlo
    assert "write_plan" not in zrodlo


def test_cue_plan_typ_zwracany(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A"), "B": _analysis("B")}
    assert isinstance(zbuduj_plan_cue(["A", "B"], by_id, weights=None), CuePlan)


def test_plan_cue_przyciagany_do_taktow_rekordboxa(monkeypatch):
    """Skarga Janka 09.08: cue mijały czerwone linie taktów. Powód: plan
    powstawał na NASZEJ siatce. Teraz każde cue jedzie na najbliższy takt
    Rekordboxa — a utwór bez jego siatki zostaje nietknięty, bez udawania."""
    from dancelab.tui.cue_podglad import zbuduj_plan_cue

    monkeypatch.setattr(cue_podglad, "_okna", _okna_atrapa)
    by_id = {"A": _analysis("A"), "B": _analysis("B")}
    plan_bez = zbuduj_plan_cue(["A", "B"], by_id, weights=None)
    takty = {by_id["A"].track.source_path:
             [round(i * 2.0, 3) for i in range(400)]}
    plan = zbuduj_plan_cue(["A", "B"], by_id, weights=None,
                           downbeaty_dla=lambda p: takty.get(p, []))

    poz = {(t.content_id, c.pad_label): c.position_ms
           for t in plan.tracks for c in t.cues}
    for (tid, _pad), ms in poz.items():
        if tid == "A":
            assert ms % 2000 == 0, f"cue utworu A poza taktem: {ms} ms"
    b_przed = {(t.content_id, c.pad_label): c.position_ms
               for t in plan_bez.tracks for c in t.cues}
    for klucz, ms in poz.items():
        if klucz[0] == "B":
            assert ms == b_przed[klucz], \
                "bez siatki Rekordboxa nie ruszamy pozycji"

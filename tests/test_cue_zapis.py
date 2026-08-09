"""Etap 4: pady z ekranu → hot cue w Rekordboksie (warstwa przygotowania).

Testy NIE dotykają bazy: sprawdzają scalenie (silnik + Twoje edycje),
tłumaczenie tożsamości (nasz track_id → ContentID Rekordboksa po ścieżce)
oraz politykę kolizji — nasz pad ZAWSZE ustępuje padowi, który DJ ustawił
sam. Sam zapis robi sprawdzona warstwa `rekordbox_cue_writer` (odmowa przy
otwartym RB, backup, weryfikacja, auto-przywrócenie) — tu jej nie dublujemy.
"""

import asyncio

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.tui import cue_edycje, cue_podglad, cue_zapis
from dancelab.tui.cue_podglad import zbuduj_plan_cue


def _analysis(tid):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=tid, title=tid, source_path=f"/m/{tid}.wav",
                    duration_sec=360.0),
        beatgrid=BeatGrid(bpm=120.0, reliable=True), segments=[])


def _okna(analysis, weights):
    if analysis.track.track_id == "A":
        return [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9,
                                 window_type=WindowType.mix_out)]
    return [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9,
                             window_type=WindowType.mix_in)]


def _plan(monkeypatch):
    monkeypatch.setattr(cue_podglad, "_okna", _okna)
    by_id = {"A": _analysis("A"), "B": _analysis("B")}
    return zbuduj_plan_cue(["A", "B"], by_id, weights=None), by_id


CONTENT = {"/m/A.wav": "111", "/m/B.wav": "222"}


def test_zapisujemy_to_co_widac_na_ekranie(monkeypatch):
    """Pozycja pada bierze się z ekranu: propozycja silnika ALBO Twoje
    przesunięcie; pad postawiony ręcznie też jedzie."""
    plan, by_id = _plan(monkeypatch)
    ed = cue_edycje.nowe()
    p = cue_edycje.efektywne_pady(plan, ed, "A")["B"]
    cue_edycje.przesun(ed, "A", "B", -8, 120.0, p["silnik_ms"],
                       p["position_ms"])
    cue_edycje.postaw(ed, "A", "C", 90_000)

    do_zapisu, ids, pominiete = cue_zapis.zbuduj_plan_do_zapisu(
        plan, ed, by_id, ["A", "B"], CONTENT)
    a = next(t for t in do_zapisu.tracks if t.content_id == "111")
    pady = {c.pad_label: c.position_ms for c in a.cues}
    assert pady["B"] == 300_000 - 8 * 500, "przesunięcie DJ-a, nie propozycja"
    assert pady["C"] == 90_000, "pad ręczny też jedzie"
    assert ids == ["111", "222"] and pominiete == []


def test_utwor_spoza_kolekcji_pomijany_imiennie(monkeypatch):
    plan, by_id = _plan(monkeypatch)
    do_zapisu, ids, pominiete = cue_zapis.zbuduj_plan_do_zapisu(
        plan, cue_edycje.nowe(), by_id, ["A", "B"], {"/m/A.wav": "111"})
    assert ids == ["111"]
    assert pominiete == ["B"], "brak w kolekcji = imienny powód, nie zgadywanie"
    assert all(t.content_id == "111" for t in do_zapisu.tracks)


def test_nasz_pad_ustepuje_padowi_dja(monkeypatch):
    """Polityka kolizji: cue DJ-a jest nietykalne."""
    from dancelab.decision.cue_conflict import ExistingCue

    plan, by_id = _plan(monkeypatch)
    do_zapisu, _ids, _p = cue_zapis.zbuduj_plan_do_zapisu(
        plan, cue_edycje.nowe(), by_id, ["A", "B"], CONTENT)
    przed = sum(len(t.cues) for t in do_zapisu.tracks)
    istniejace = {"111": [ExistingCue(pad_index=2, position_ms=12_345,
                                      comment="moje wyjście")]}
    wynik = cue_zapis.policz_kolizje(do_zapisu, istniejace)
    assert wynik["do_zapisu"] == przed - 1
    assert wynik["pominiete_kolizje"] == 1
    zapisane = {(t.content_id, c.pad_label)
                for t in wynik["plan"].tracks for c in t.cues}
    assert ("111", "B") not in zapisane, "pad B należy do DJ-a — nie ruszamy"


def test_w_w_eksporcie_nie_pisze_playlisty_i_odmawia_bez_setu():
    """W w zakładce Eksport dotyczy CUE, nie playlisty; bez setu odmawia
    z powodem, a nie po cichu."""
    from textual.widgets import TabbedContent

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            wolane = []
            app._write_worker = lambda: wolane.append("playlista")
            app.action_write()
            await pilot.pause()
            assert wolane == [], "W w Eksporcie NIE publikuje playlisty"
            notki = " ".join(str(x) for x in app.query_one("#warnings").lines)
            assert "najpierw zbuduj set" in notki

    asyncio.run(go())


def test_cta_w_prawym_dolnym_rogu_pod_odtwarzaczem():
    """Układ jak w Bibliotece (życzenie Janka 09.08): guziki wysyłki
    w prawym dolnym rogu, POD paskiem odtwarzacza. Regresja: gdy oba
    dokowały się osobno do dolnej krawędzi, pasek PRZYKRYWAŁ guziki."""
    from textual.widgets import Button, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test(size=(120, 30)) as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            guzik = app.query_one("#cue-write", Button)
            pasek = next(w for w in app.query(".pb-box") if w.region.height)
            assert guzik.region.y >= pasek.region.y + pasek.region.height, \
                "CTA pod paskiem, nie pod nim schowane"
            ekran = app.query_one("#cue-dol").region
            assert guzik.region.x > ekran.width // 2, "CTA po prawej stronie"

    asyncio.run(go())


def test_odswiezamy_SWOJE_pady_a_cudze_zostaja(monkeypatch, tmp_path):
    """Sedno awarii z 09.08 („nie widzę cue w Rekordboksie"): nasz własny pad
    z poprzedniej wysyłki blokował nas jak cudzy, więc przesunięcie pada
    nigdy nie docierało do bazy. Teraz: NASZ pad (UUID w rejestrze) jest
    odświeżany, pad DJ-a dalej nietykalny."""
    from dancelab.decision.cue_conflict import ExistingCue

    plan, by_id = _plan(monkeypatch)
    do_zapisu, _ids, _p = cue_zapis.zbuduj_plan_do_zapisu(
        plan, cue_edycje.nowe(), by_id, ["A", "B"], CONTENT)

    rejestr = {"nasz-uuid": {"content_id": "111", "kind": 2,
                             "position_ms": 111_000, "zapisane": "wczoraj"}}
    istniejace = {
        # pad B utworu 111 = NASZ poprzedni zapis (UUID w rejestrze)
        "111": [ExistingCue(pad_index=2, position_ms=111_000,
                            comment="MIX OUT → next", uuid="nasz-uuid")],
        # pad A utworu 222 = cue DJ-a, UUID nieznany
        "222": [ExistingCue(pad_index=1, position_ms=30_000,
                            comment="moje wejście", uuid="obcy-uuid")],
    }
    wynik = cue_zapis.policz_kolizje(do_zapisu, istniejace, rejestr)
    pady = {(t.content_id, c.pad_label): c
            for t in wynik["plan"].tracks for c in t.cues}

    assert ("111", "B") in pady, "nasz własny pad ma zostać ODŚWIEŻONY"
    assert pady[("111", "B")].replace_existing is True, \
        "odświeżenie wymaga jawnego pozwolenia na usunięcie starego wiersza"
    assert wynik["odswiezone"] == 1
    assert ("222", "A") not in pady, "pad DJ-a zostaje nietknięty"


def test_bez_uuid_w_rejestrze_pad_uchodzi_za_cudzy(monkeypatch):
    """Zawodzimy w stronę bezpieczną: cue zapisane przez nas PRZED powstaniem
    rejestru (albo z pustym UUID) jest traktowane jak cudze."""
    from dancelab.decision.cue_conflict import ExistingCue

    plan, by_id = _plan(monkeypatch)
    do_zapisu, _ids, _p = cue_zapis.zbuduj_plan_do_zapisu(
        plan, cue_edycje.nowe(), by_id, ["A", "B"], CONTENT)
    istniejace = {"111": [ExistingCue(pad_index=2, position_ms=111_000,
                                      comment="MIX OUT → next", uuid="")]}
    wynik = cue_zapis.policz_kolizje(do_zapisu, istniejace, rejestr={})
    pady = {(t.content_id, c.pad_label) for t in wynik["plan"].tracks
            for c in t.cues}
    assert ("111", "B") not in pady
    assert wynik["odswiezone"] == 0


def test_rejestr_zapisuje_i_wybacza_uszkodzenie(tmp_path):
    from dancelab.ingestion import cue_ledger

    plik = tmp_path / "rejestr.json"
    ile = cue_ledger.zapamietaj(
        [{"uuid": "u1", "content_id": "111", "kind": 2, "position_ms": 5000},
         {"uuid": "", "content_id": "111", "kind": 3, "position_ms": 6000}],
        znacznik="2026-08-09 21:00", sciezka=plik)
    assert ile == 1, "wpis bez UUID-a jest bezużyteczny — nie zapisujemy go"
    assert cue_ledger.wczytaj(plik)["u1"]["content_id"] == "111"

    plik.write_text("{to nie jest json")
    assert cue_ledger.wczytaj(plik) == {}, \
        "uszkodzony rejestr = zero uprawnień, nie wywrotka"


def test_guzik_mowi_dlaczego_nie_da_sie_wyslac():
    """Skarga Janka 09.08: klika i „nie widzi cue w Rekordboksie". Przy
    otwartym Rekordboksie zapis jest niemożliwy — przycisk MA to mówić
    i być nieklikalny, zamiast wyglądać normalnie i milczeć."""
    from textual.widgets import Button, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    async def go(rb_otwarty: bool) -> Button:
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test(size=(120, 30)) as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._odswiez_guzik_cue(rb_otwarty)
            await pilot.pause()
            return app.query_one("#cue-write", Button)

    g = asyncio.run(go(True))
    assert g.disabled is True
    assert "Zamknij Rekordbox" in str(g.label)

    g = asyncio.run(go(False))
    assert g.disabled is False and "Wyślij cue" in str(g.label)


def test_guzik_po_pierwszym_nacisnieciu_prosi_o_potwierdzenie(monkeypatch):
    """Drugie pół awarii: pierwsze naciśnięcie tylko LICZY, a przycisk
    wyglądał tak samo — klik wyglądał jak brak reakcji."""
    from textual.widgets import Button, TabbedContent

    from dancelab.tui.app import DanceLabTUI

    plan, by_id = _plan(monkeypatch)
    do_zapisu, ids, _p = cue_zapis.zbuduj_plan_do_zapisu(
        plan, cue_edycje.nowe(), by_id, ["A", "B"], CONTENT)

    async def go():
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test(size=(120, 30)) as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-export"
            await pilot.pause()
            app._cue_zapis_gotowy = (do_zapisu, ids)
            app._odswiez_guzik_cue(False)
            await pilot.pause()
            g = app.query_one("#cue-write", Button)
            ile = sum(len(t.cues) for t in do_zapisu.tracks)
            assert "POTWIERDŹ" in str(g.label) and str(ile) in str(g.label)
            assert g.disabled is False

    asyncio.run(go())

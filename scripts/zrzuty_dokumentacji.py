"""Zrzuty ekranu do instrukcji → docs/zrzuty/*.svg — KAŻDY stan osobno.

Powtarzalność zamiast ręcznych zrzutów: instrukcja pokazywała przełącznik
podpisany „artwork" długo po tym, jak w programie nazwano go „okładki".
Zrzut, który kłamie, jest gorszy niż jego brak.

Żądanie Janka z 09.08: „każda opcja musi być opatrzona screenem, musi być
pokazane każde menu, podmenu, opcje wybierania". Skrypt przechodzi więc
aplikację zakładka po zakładce i otwiera każdy panel po kolei.

Użycie (wczytuje NAJNOWSZY zapisany plan, żeby zakładki miały treść):
    .venv/bin/python scripts/zrzuty_dokumentacji.py [nazwa ...]

Zasady, których skrypt pilnuje:
* NIC nie jest zapisywane — zapis ulubionych i filarów jest podmieniony
  na pustą funkcję, więc Twoja biblioteka wychodzi z tego nietknięta;
* ŻADEN zrzut nie uruchamia dźwięku (twarda zasada projektu), dlatego
  odsłuch utworu i szwu nie ma własnego zrzutu;
* stany zależne od Rekordboksa (przycisk wysyłki) są ustawiane przez
  podmianę SPRAWDZANIA procesu, nigdy przez zamykanie cudzego programu.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

KORZEN = pathlib.Path(__file__).resolve().parent.parent
ZRZUTY = KORZEN / "docs" / "zrzuty"
ROZMIAR = (120, 38)


async def _czekaj(warunek, sekund: float, opis: str) -> None:
    for _ in range(int(sekund * 10)):
        if warunek():
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(opis)


class Sesja:
    """Jedno uruchomienie aplikacji + zapisywanie kolejnych stanów."""

    def __init__(self, app, pilot, tylko: set[str] | None):
        self.app, self.pilot, self.tylko = app, pilot, tylko
        self.zrobione: list[str] = []

    def chce(self, nazwa: str) -> bool:
        return not self.tylko or nazwa in self.tylko

    async def zrzut(self, nazwa: str) -> None:
        await self.pilot.pause()
        self.app.save_screenshot(str(ZRZUTY / f"{nazwa}.svg"))
        self.zrobione.append(nazwa)
        print(f"  {nazwa}.svg")

    async def zakladka(self, ident: str) -> None:
        from textual.widgets import TabbedContent

        self.app.query_one("#tabs", TabbedContent).active = ident
        await self.pilot.pause()

    async def zamknij_panel(self) -> None:
        from textual.widgets import DataTable

        self.app._close_panel()
        self.app.query_one("#set", DataTable).focus()
        await self.pilot.pause()


# ----------------------------------------------------------------- Biblioteka

async def biblioteka(s: Sesja) -> None:
    from textual.widgets import DataTable, Input

    print("Biblioteka")
    await s.zakladka("tab-lib")
    tabela = s.app.query_one("#lib-table", DataTable)
    tabela.focus()
    if s.chce("lib_widok"):
        await s.zrzut("lib_widok")

    if s.chce("lib_szukanie"):
        s.app.query_one("#lib-search", Input).value = "bicep"
        s.app.query_one("#lib-bpm", Input).value = "128-140"
        await s.pilot.pause()
        s.app._render_library()
        await s.zrzut("lib_szukanie")
        s.app.query_one("#lib-search", Input).value = ""
        s.app.query_one("#lib-bpm", Input).value = ""
        s.app._render_library()
        await s.pilot.pause()

    if s.chce("lib_oznaczenia"):
        tabela.focus()
        tabela.move_cursor(row=0)
        await s.pilot.press("u")            # ♥
        tabela.move_cursor(row=1)
        await s.pilot.press("f")            # ⚑
        await s.zrzut("lib_oznaczenia")
        tabela.move_cursor(row=0)
        await s.pilot.press("u")            # cofnij oznaczenia
        tabela.move_cursor(row=1)
        await s.pilot.press("f")
        await s.pilot.pause()

    if s.chce("lib_okladki"):
        tabela.focus()
        await s.pilot.press("k")
        await s.pilot.pause()
        await asyncio.sleep(2.0)            # miniatury dociągają się chwilę
        await s.zrzut("lib_okladki")
        await s.pilot.press("k")
        await s.pilot.pause()

    if s.chce("lib_sortowanie"):
        tabela.focus()
        s.app._lib_sort = (2, False)        # kolumna BPM, rosnąco
        s.app._render_library()
        await s.zrzut("lib_sortowanie")
        s.app._lib_sort = None
        s.app._render_library()
        await s.pilot.pause()

    if s.chce("lib_analizuj"):
        pole = s.app.query_one("#lib-folder", Input)
        pole.value = "/Users/ja/Music/nowe utwory"
        await s.zrzut("lib_analizuj")
        pole.value = ""
        await s.pilot.pause()

    if s.chce("lib_notki"):
        tabela.focus()
        await s.pilot.press("l")
        await s.zrzut("lib_notki")
        await s.pilot.press("l")
        await s.pilot.pause()


# ------------------------------------------------------------------------ Set

async def set_pusty(s: Sesja) -> None:
    print("Set — przed budową")
    await s.zakladka("tab-set")
    if s.chce("set_brief"):
        await s.zrzut("set_brief")

    if s.chce("set_gatunki"):
        s.app.action_gatunki()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      30, "panel gatunków się nie otworzył")
        await s.zrzut("set_gatunki")
        await s.zamknij_panel()

    if s.chce("set_djs"):
        s.app.action_grupy_dj()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      60, "panel DJ-ów się nie otworzył")
        await s.zrzut("set_djs")
        await s.zamknij_panel()

    if s.chce("set_filary_tryb"):
        s.app.action_toggle_filar()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      30, "panel trybu filarów się nie otworzył")
        await s.zrzut("set_filary_tryb")
        await s.zamknij_panel()


async def set_zbudowany(s: Sesja) -> None:
    from textual.widgets import DataTable

    print("Set — z wczytanym planem")
    await s.zakladka("tab-set")
    tabela = s.app.query_one("#set", DataTable)
    tabela.focus()
    tabela.move_cursor(row=0)
    await s.pilot.pause()
    if s.chce("set_lista"):
        await s.zrzut("set_lista")

    if s.chce("set_podmiana"):
        s.app.action_replace()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      180, "panel podmiany się nie policzył")
        await s.zrzut("set_podmiana")
        await s.zamknij_panel()

    if s.chce("set_dopisz"):
        tabela.focus()
        tabela.move_cursor(row=0)
        s.app.action_add()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      180, "panel dopisania się nie policzył")
        await s.zrzut("set_dopisz")
        await s.zamknij_panel()

    if s.chce("set_szew"):
        tabela.focus()
        tabela.move_cursor(row=0)
        s.app.action_compare_pair()
        await _czekaj(lambda: s.app.query_one("#compare").has_class("open"),
                      120, "pasek szwu się nie otworzył")
        await s.zrzut("set_szew")
        s.app.query_one("#compare").remove_class("open")
        await s.pilot.pause()

    if s.chce("set_info"):
        tabela.focus()
        s.app.action_track_info()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      120, "karta utworu się nie otworzyła")
        await s.zrzut("set_info")
        await s.zamknij_panel()

    if s.chce("set_plany"):
        tabela.focus()
        s.app.action_load_plan()
        await _czekaj(lambda: s.app.query_one("#suggest").has_class("open"),
                      60, "lista planów się nie otworzyła")
        await s.zrzut("set_plany")
        await s.zamknij_panel()

    if s.chce("set_nazwa_planu"):
        tabela.focus()
        s.app.action_save_plan()
        await _czekaj(
            lambda: s.app.screen is not s.app.screen_stack[0], 30,
            "okno nazwy planu się nie otworzyło")
        await s.zrzut("set_nazwa_planu")
        await s.pilot.press("escape")       # NIE zapisujemy planu
        await s.pilot.pause()


# --------------------------------------------------------------- Eksport/Cue

async def eksport_cue(s: Sesja) -> None:
    from textual.widgets import DataTable, Static

    print("Eksport / Cue")
    await s.zakladka("tab-export")
    await _czekaj(
        lambda: "Pady bieżącego setu" in str(
            s.app.query_one("#cue-head", Static).render()),
        300, "podgląd cue się nie policzył")
    tabela = s.app.query_one("#cue-table", DataTable)
    tabela.focus()
    s.app._refresh_status()
    if s.chce("cue_widok"):
        await s.zrzut("cue_widok")

    litera = next((p.lower() for p in "ABCDEFGH"
                   if p in s.app._cue_pady_teraz()), None)
    if litera and s.chce("cue_pad"):
        await s.pilot.press(litera)
        await s.zrzut("cue_pad")

    if litera and s.chce("cue_czas"):
        await s.pilot.press("t")
        await _czekaj(lambda: s.app._cue_czas_bufor is not None, 30,
                      "edycja czasu się nie włączyła")
        await s.pilot.press("down")
        await s.zrzut("cue_czas")
        await s.pilot.press("escape")
        await s.pilot.pause()

    if litera and s.chce("cue_przesuniety"):
        await s.pilot.press(litera)
        await s.pilot.press("shift+left")   # −8 uderzeń
        await s.zrzut("cue_przesuniety")
        await s.pilot.press("z")            # cofnij — plan zostaje czysty
        await s.pilot.pause()

    if s.chce("cue_potwierdz"):
        s.app._cue_przygotuj_zapis()
        await _czekaj(lambda: s.app._cue_zapis_gotowy is not None, 300,
                      "plan zapisu cue się nie policzył")
        s.app._refresh_status()
        await s.zrzut("cue_potwierdz")

    if s.chce("cue_rb_otwarty"):
        # CAŁY ekran musi pokazywać ten sam stan: sam przycisk przestawiony
        # przy pasku statusu mówiącym „Rekordbox zamknięty" byłby zrzutem,
        # który kłamie. Podmieniamy więc SPRAWDZANIE procesu na czas zrzutu.
        import dancelab.ingestion.playlist_publish as PP

        PP.rekordbox_running = lambda: True
        s.app._refresh_status()
        await s.zrzut("cue_rb_otwarty")
        PP.rekordbox_running = lambda: False
        s.app._refresh_status()
        await s.pilot.pause()


# ---------------------------------------------------------------------- bieg

async def go(tylko: set[str] | None) -> None:
    import dancelab.ingestion.playlist_publish as PP
    import dancelab.tui.user_store as US
    from dancelab.tui.app import PROCESSED_DEFAULT, DanceLabTUI
    from dancelab.tui.plan_store import match_order, read_plan

    ZRZUTY.mkdir(parents=True, exist_ok=True)
    PP.rekordbox_running = lambda: False       # stan roboczy, zero zapisu
    US.save_state = lambda *a, **k: None       # biblioteka Janka nietknięta

    app = DanceLabTUI(processed_dir=str(PROCESSED_DEFAULT))
    async with app.run_test(size=ROZMIAR) as pilot:
        s = Sesja(app, pilot, tylko)
        await _czekaj(lambda: app._lib, 300, "biblioteka nie wstała")
        await biblioteka(s)
        await set_pusty(s)

        plany = sorted((KORZEN / "data/exports/tui_plany").glob("*.json"))
        if not plany:
            print("brak zapisanych planów — Set z planem i Cue pominięte")
            return
        rec = read_plan(str(plany[-1]))
        ctx = await asyncio.to_thread(app._pool_ctx_for, rec.get("parametry", {}))
        app._ctx = ctx
        order, notes = match_order(rec, ctx["by_id"])
        app._after_plan_load(rec, order, notes)
        await pilot.pause()

        await set_zbudowany(s)
        await eksport_cue(s)
        print(f"\nzrzutów: {len(s.zrobione)}")


if __name__ == "__main__":
    asyncio.run(go(set(sys.argv[1:]) or None))

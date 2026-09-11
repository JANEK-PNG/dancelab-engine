"""The full desktop app path, driven: DesktopMost, editor lock, the Apple login hook.

    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/aplikacja_pelna.py

Builds the window exactly as ``dancelab gui`` does (``gui/okno.uruchom``):
``DesktopMost`` (desktop library profiles), ``editor_lock``, the same
``create_window`` arguments and closing hooks, and ``wlacz_okienka()``. The
only addition is ``evaluate_js`` so a script can drive it: pick one Apple
Music stream from the library the desktop layer actually loaded, set volume
0.3, press play (``graj('')``) for 3 seconds, jump 8 beats forward with the
same handler as the → button, read the cover, press again to pause. Sound:
about 3 s at 0.3, the level Janek agreed to for these checks. Writes
wynik_aplikacja.json (gitignored) and prints it.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))

PLAY_S = 3
SAMPLE = ("JSON.stringify({gra: stan.gra, opis: document.querySelector('#opis-gry').textContent,"
          " guzik_wylaczony: document.querySelector('#btn-graj').disabled,"
          " czas: document.querySelector('#czas-gry').textContent,"
          " okladka: (() => { const i = document.querySelector('#okladka-gry');"
          " return i && !i.hidden ? (i.getAttribute('src') || '').slice(0, 40) : null; })()})")


def main() -> None:
    """Open the app the way `dancelab gui` does, play a stream briefly, pause, close."""
    import webview

    from dancelab.gui import okno as okno_mod
    from dancelab.gui.apple_logowanie import wlacz_okienka
    from dancelab.gui.desktop import DesktopMost
    from dancelab.storage.editor_lock import editor_lock

    wynik: dict[str, object] = {}
    with editor_lock():
        most = DesktopMost()
        wynik["katalog"] = pathlib.Path(most._katalog).name
        win = webview.create_window(
            okno_mod.TYTUL, url=(okno_mod.STATYCZNE / "index.html").as_uri(), js_api=most,
            width=1440, height=900, min_size=(1040, 640), background_color="#0e1013")
        most._window = win
        win.events.closing += most._on_closing
        win.events.closed += most.zamknij
        wynik["hak_logowania"] = wlacz_okienka()

        def poll(expr: str, timeout: float) -> object:
            end = time.time() + timeout
            while time.time() < end:
                try:
                    v = win.evaluate_js(expr)
                except Exception:  # noqa: BLE001
                    v = None
                if v not in (None, "", False, "null"):
                    return v
                time.sleep(0.5)
            return None

        def run() -> None:
            start = time.time()
            try:
                ready = poll("typeof stan !== 'undefined' && !!window.appleGra"
                             " && Array.isArray(stan.spis) && stan.spis.length > 0", 150)
                wynik["strona_gotowa_s"] = round(time.time() - start, 1) if ready else None
                if not ready:
                    return
                tid = win.evaluate_js("(stan.spis.find(u => u.apple) || {}).track_id || null")
                wynik["strumien_w_bibliotece_desktop"] = bool(tid)
                wynik["wierszy"] = win.evaluate_js("stan.spis.length")
                if not tid:
                    return
                win.evaluate_js(f"wybierzUtwor({json.dumps(tid)})")
                time.sleep(2)
                wynik["przed"] = json.loads(win.evaluate_js(SAMPLE))
                win.evaluate_js("window.__INIT__ = null; appleGra.init().then("
                                "m => { m.volume = 0.3; window.__INIT__ = 'ok'; },"
                                " e => { window.__INIT__ = 'err: ' + e.message; })")
                wynik["init"] = poll("window.__INIT__", 40)
                if wynik["init"] != "ok":
                    return
                win.evaluate_js("graj('')")
                probki = []
                for _ in range(PLAY_S):
                    time.sleep(1)
                    probki.append(json.loads(win.evaluate_js(SAMPLE)))
                wynik["gra"] = probki
                win.evaluate_js("skok(8)")                      # the → button's handler
                time.sleep(0.8)
                wynik["po_skoku_8"] = json.loads(win.evaluate_js(SAMPLE))
                win.evaluate_js("graj('')")                     # same button: pause
                time.sleep(1.5)
                wynik["po_pauzie"] = json.loads(win.evaluate_js(SAMPLE))
            finally:
                try:
                    win.evaluate_js("window.appleGra && appleGra.porzuc()")
                except Exception:  # noqa: BLE001
                    pass
                wynik["czas_calkowity_s"] = round(time.time() - start, 1)
                most._allow_close = True
                win.destroy()

        webview.start(run)
    text = json.dumps(wynik, ensure_ascii=False, indent=1)
    (TU / "wynik_aplikacja.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

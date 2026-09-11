"""Check the wired-in stream playback in the REAL window page with the REAL bridge.

    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/okno_prawdziwe.py

Loads src/dancelab/gui/statyczne/index.html in pywebview with ``Most`` as
js_api — the same page and bridge the DanceLab window uses — opens one Apple
Music stream on the track screen, and drives the page's own ``graj('')`` the
way the play button does: once to play (volume set to 0.3 first), once more
to pause. About 5 seconds of sound, asked for by Janek on 2026-09-10. Tokens
travel through js_api only; nothing is served over HTTP. Prints samples of
the page's own player state and writes them to wynik_okno.json (gitignored).
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.gui.most import Most  # noqa: E402

PAGE = ROOT / "src/dancelab/gui/statyczne/index.html"
PROCESSED = ROOT / Most.KATALOG_ANALIZ
WANTED = "apple-music:tracks:1687954211"      # Jinjé — A Ship Full of Ghosts
PLAY_S = 3
HARD_CAP_S = 180


def stream_track_id() -> str:
    """Track id of the wanted stream, else of the first stream in the catalog."""
    first = None
    for f in sorted(PROCESSED.glob("*.json")):
        t = json.loads(f.read_text()).get("track") or {}
        sp = t.get("source_path") or ""
        if sp == WANTED:
            return t["track_id"]
        if first is None and sp.startswith("apple-music:tracks:"):
            first = t["track_id"]
    if first is None:
        sys.exit("brak strumienia w katalogu analiz")
    return first


SAMPLE = ("JSON.stringify({gra: stan.gra, opis: document.querySelector('#opis-gry').textContent,"
          " guzik_wylaczony: document.querySelector('#btn-graj').disabled,"
          " czas: document.querySelector('#czas-gry').textContent})")


def main() -> None:
    """Open the real page, play one stream for a few seconds, pause, close."""
    import webview

    tid = stream_track_id()
    most = Most()
    win = webview.create_window("DanceLab — próba odsłuchu Apple Music", url=PAGE.as_uri(),
                                js_api=most, width=1280, height=800)
    win.events.closed += most.zamknij
    wynik: dict[str, object] = {"track_id": tid}

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
                         " && Array.isArray(stan.spis) && stan.spis.length > 0", 120)
            wynik["strona_gotowa_s"] = round(time.time() - start, 1) if ready else None
            if not ready:
                return
            win.evaluate_js(f"wybierzUtwor({json.dumps(tid)})")
            time.sleep(2)
            wynik["przed"] = json.loads(win.evaluate_js(SAMPLE))
            win.evaluate_js("window.__INIT__ = null; appleGra.init().then("
                            "m => { m.volume = 0.3; window.__INIT__ = 'ok'; },"
                            " e => { window.__INIT__ = 'err: ' + e.message; })")
            wynik["init"] = poll("window.__INIT__", 30)
            if wynik["init"] != "ok":
                return
            win.evaluate_js("graj('')")                       # the play button's handler
            probki = []
            for _ in range(PLAY_S):
                time.sleep(1)
                probki.append(json.loads(win.evaluate_js(SAMPLE)))
            wynik["gra"] = probki
            win.evaluate_js("graj('')")                       # same button again: pause
            time.sleep(1.5)
            wynik["po_pauzie"] = json.loads(win.evaluate_js(SAMPLE))
        finally:
            try:
                win.evaluate_js("window.appleGra && appleGra.porzuc()")
            except Exception:  # noqa: BLE001
                pass
            wynik["czas_calkowity_s"] = round(time.time() - start, 1)
            win.destroy()

    webview.start(run)
    text = json.dumps(wynik, ensure_ascii=False, indent=1)
    (TU / "wynik_okno.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

"""Drive the real window: ⌘⇧B opens the report dialog, save writes a ticket with a screenshot.

    .venv/bin/python experiments_priv/2026-09-11_zgloszenia/proba_okna.py

Same construction as `dancelab gui` (DesktopMost, editor lock, report script
loaded by index.html). Tickets go to a scratch folder via $DANCELAB_ZGLOSZENIA
so the owner's ~/.dancelab/zgloszenia stays clean. No sound. Checks that the
shortcut does not also start a set build (plain "B" builds a set in app.js).
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    """Open the window, file one report through the UI, print what landed on disk."""
    cel = pathlib.Path(tempfile.mkdtemp(prefix="dl-zgloszenia-"))
    os.environ["DANCELAB_ZGLOSZENIA"] = str(cel)
    import webview

    from dancelab.gui import okno as okno_mod
    from dancelab.gui.apple_logowanie import wlacz_okienka
    from dancelab.gui.desktop import DesktopMost
    from dancelab.storage.editor_lock import editor_lock

    wynik: dict[str, object] = {"katalog": str(cel)}
    with editor_lock():
        most = DesktopMost()
        win = webview.create_window(
            okno_mod.TYTUL, url=(okno_mod.STATYCZNE / "index.html").as_uri(), js_api=most,
            width=1440, height=900, min_size=(1040, 640), background_color="#0e1013")
        most._window = win
        win.events.closing += most._on_closing
        win.events.closed += most.zamknij
        wlacz_okienka()

        def poll(expr: str, timeout: float) -> object:
            end = time.time() + timeout
            while time.time() < end:
                try:
                    v = win.evaluate_js(expr)
                except Exception:  # noqa: BLE001
                    v = None
                if v not in (None, "", False, "null"):
                    return v
                time.sleep(0.4)
            return None

        def run() -> None:
            try:
                wynik["strona"] = bool(poll("!!window.zgloszenie && typeof stan !== 'undefined'"
                                            " && Array.isArray(stan.spis) && stan.spis.length > 0", 120))
                wynik["przycisk_w_pasku"] = win.evaluate_js("!!document.querySelector('.stan .btn-zglos')")
                budowa_przed = json.dumps(most.postep_budowy())
                win.evaluate_js("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'B', metaKey: true,"
                                " shiftKey: true, bubbles: true, cancelable: true}))")
                wynik["okienko_po_skrocie"] = bool(poll("!!document.querySelector('.zgl-okno')", 15))
                time.sleep(0.5)
                wynik["skrot_nie_zbudowal_setu"] = json.dumps(most.postep_budowy()) == budowa_przed
                wynik["info_w_okienku"] = win.evaluate_js("document.querySelector('.zgl-info').textContent")
                win.evaluate_js("document.querySelector('.zgl-okno [data-zgl=\"zapisz\"]').click()")
                time.sleep(0.8)
                wynik["pusty_opis_odmowa"] = win.evaluate_js("document.querySelector('.zgl-blad').textContent")
                win.evaluate_js("document.querySelector('#zgl-opis').value = 'próba z okna: zgłoszenie z automatu';"
                                "document.querySelector('#zgl-waga').value = 'drobny';"
                                "document.querySelector('.zgl-okno [data-zgl=\"zapisz\"]').click()")
                wynik["toast"] = poll("document.querySelector('.zgl-toast')?.textContent || null", 15)
                wynik["okienko_zamkniete"] = not win.evaluate_js("!!document.querySelector('.zgl-okno')")
            finally:
                most._allow_close = True
                win.destroy()

        webview.start(run)
    foldery = sorted(cel.glob("DL-*"))
    wynik["folderow"] = len(foldery)
    if foldery:
        f = foldery[-1]
        wynik["pliki"] = sorted(p.name for p in f.iterdir())
        wynik["png_bajtow"] = (f / "zrzut.png").stat().st_size if (f / "zrzut.png").exists() else 0
        d = json.loads((f / "zgloszenie.json").read_text())
        wynik["json"] = {k: d.get(k) for k in ("opis", "waga", "commit", "system")}
        wynik["okno_ekran"] = (d.get("okno") or {}).get("ekran")
        wynik["srodowisko_zrzut"] = (d.get("srodowisko") or {}).get("zrzut")
    print(json.dumps(wynik, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

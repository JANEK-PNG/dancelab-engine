"""Screenshot of the DanceLab window's web content, for bug reports.

WKWebView renders its own snapshot (`takeSnapshotWithConfiguration:`), so no
Screen Recording permission is needed and only the app's page is captured —
never another window or the desktop. AppKit must be driven from the main
thread, so the call is posted there with `AppHelper.callAfter` (the same way
pywebview itself evaluates JavaScript) and this thread waits for the result.
Called from a js_api worker thread; from the main thread it refuses instead
of deadlocking.
"""

from __future__ import annotations

import threading
from typing import Any


def zrzut_png(window: Any, timeout: float = 5.0) -> tuple[bytes | None, str | None]:
    """(PNG bytes, None) or (None, reason). Never raises."""
    if window is None:
        return None, "okno nie jest otwarte"
    if threading.current_thread() is threading.main_thread():
        return None, "zrzut wołany z wątku głównego — pominięty, żeby okno nie zamarzło"
    try:
        import AppKit
        from PyObjCTools import AppHelper
        from webview.platforms import cocoa
    except Exception as exc:                           # noqa: BLE001
        return None, f"zrzut niedostępny poza macOS ({type(exc).__name__})"
    widok = cocoa.BrowserView.instances.get(getattr(window, "uid", None))
    if widok is None:
        return None, "okno nie jest otwarte"

    gotowe = threading.Event()
    wynik: dict[str, Any] = {}

    def po_zrzucie(obraz, blad):
        try:
            if obraz is None:
                wynik["blad"] = f"WebKit nie oddał obrazu ({blad})"
                return
            rep = AppKit.NSBitmapImageRep.imageRepWithData_(obraz.TIFFRepresentation())
            png = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
            wynik["png"] = bytes(png)
        except Exception as exc:                       # noqa: BLE001
            wynik["blad"] = f"zamiana zrzutu na PNG nie wyszła ({type(exc).__name__})"
        finally:
            gotowe.set()

    def zrob():
        try:
            widok.webview.takeSnapshotWithConfiguration_completionHandler_(None, po_zrzucie)
        except Exception as exc:                       # noqa: BLE001
            wynik["blad"] = f"zrzut nie ruszył ({type(exc).__name__})"
            gotowe.set()

    AppHelper.callAfter(zrob)
    if not gotowe.wait(timeout):
        return None, f"zrzut nie przyszedł w {timeout:.0f} s"
    return wynik.get("png"), wynik.get("blad")

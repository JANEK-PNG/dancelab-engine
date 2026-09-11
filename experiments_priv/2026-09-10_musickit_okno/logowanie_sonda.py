"""Probe: can Apple's MusicKit login popup open INSIDE a pywebview window?

    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/logowanie_sonda.py okno
    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/logowanie_sonda.py apple

Why: pywebview's Cocoa UI delegate returns nil from
``webView:createWebViewWithConfiguration:forNavigationAction:windowFeatures:``
for script-opened windows, so ``window.open`` gives ``null`` and
``MusicKit.authorize()`` hangs (measured 2026-09-10). This probe replaces
that delegate method at runtime with one that builds a WKWebView from the
configuration WebKit hands over (that keeps ``window.opener``, which the
Apple login page posts the token back through) inside a new NSWindow, and
closes the NSWindow on ``webViewDidClose:``.

Kill criteria, written before the first run:
* ``okno`` — ``window.open('https://example.com')`` still returns null, or no
  second window appears → the patch does not take; fall back to the Safari
  flow started from the window.
* ``apple`` — the popup opens but ``isAuthorized`` stays false after Janek
  logs in (5 min cap) → the opener link is broken; same fallback.

No sound: nothing plays. No token is printed or written; only its length.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))

OKNA: list = []          # keep popup windows alive (PyObjC would free them)


def patch_pywebview() -> None:
    """Give pywebview's UI delegate a real window.open.

    Try 1 assigned plain functions onto pywebview's delegate class and the
    process died with SIGSEGV on first show (exit 139): the selectors lost
    their ObjC signatures. A PyObjC SUBCLASS inherits the signature of the
    method it overrides, so the delegate class is swapped for a subclass.
    """
    import AppKit
    import Foundation
    import WebKit
    from webview.platforms import cocoa

    base = cocoa.BrowserView.BrowserDelegate

    class DanceLabPopupDelegate(base):
        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                self, webview, config, action, features):
            rect = Foundation.NSMakeRect(240, 160, 520, 700)
            style = (AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
                     | AppKit.NSWindowStyleMaskResizable)
            win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect, style, AppKit.NSBackingStoreBuffered, False)
            win.setReleasedWhenClosed_(False)
            wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(rect, config)
            wv.setUIDelegate_(self)
            win.setContentView_(wv)
            win.setTitle_("Apple — logowanie")
            win.makeKeyAndOrderFront_(None)
            OKNA.append((win, wv))
            return wv

        def webViewDidClose_(self, webview):
            for win, wv in list(OKNA):
                if wv == webview:
                    win.orderOut_(None)
                    OKNA.remove((win, wv))

    cocoa.BrowserView.BrowserDelegate = DanceLabPopupDelegate


OKNO_JS = r"""
window.__WYNIK__ = null;
(async () => {
  const w = {};
  const r = window.open('https://example.com', 'sonda', 'width=500,height=600');
  w.window_open = r ? 'window' : 'null';
  await new Promise(res => setTimeout(res, 3000));
  try { w.popup_closed = r ? r.closed : null; } catch (e) { w.popup_closed = 'err'; }
  try { if (r) r.close(); } catch (e) {}
  window.__WYNIK__ = w;
})();
"""

APPLE_JS = r"""
window.__WYNIK__ = null;
(async () => {
  const w = {};
  try {
    await new Promise(res => (window.pywebview && window.pywebview.api) ? res()
      : window.addEventListener('pywebviewready', res, {once: true}));
    const t = await window.pywebview.api.tokeny();
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
      s.onload = res; s.onerror = () => rej(new Error('musickit.js did not load'));
      document.head.appendChild(s);
    });
    if (!window.MusicKit || !MusicKit.configure) {
      await new Promise(res => document.addEventListener('musickitloaded', res, {once: true}));
    }
    const m = await MusicKit.configure({developerToken: t.dev,
      app: {name: 'DanceLab', build: '1'}, storefrontId: 'pl'});
    w.before = m.isAuthorized;
    const tok = await Promise.race([m.authorize(),
      new Promise(res => setTimeout(() => res(null), 300000))]);
    w.isAuthorized = m.isAuthorized;
    w.token_len = tok ? String(tok).length : 0;
    w.token_matches_instance = !!tok && tok === m.musicUserToken;
  } catch (e) { w.error = String(e && (e.message || e.name) || e); }
  window.__WYNIK__ = w;
})();
"""


class Api:
    """Only the developer token crosses js_api here; the probe never saves a user token."""

    def tokeny(self) -> dict:
        from dancelab.ingestion.apple_music_api import developer_token, load_config
        cfg = load_config()
        return {"dev": developer_token(pathlib.Path(cfg["klucz"]), cfg["key_id"],
                                       cfg["team_id"], 3600)}


def main() -> None:
    """Run one stage, print the result, close everything."""
    import webview

    stage = (sys.argv[1:] or ["okno"])[0]
    patch_pywebview()
    js = OKNO_JS if stage == "okno" else APPLE_JS
    page = TU / f"logowanie_{stage}.html"
    page.write_text(f"<!doctype html><meta charset='utf-8'><body style='font:14px system-ui;"
                    f"background:#0e1013;color:#ccc;padding:1rem'>sonda logowania: {stage}"
                    f"<script>{js}</script>", encoding="utf-8")
    win = webview.create_window(f"DanceLab sonda logowania · {stage}", url=page.as_uri(),
                                js_api=Api(), width=520, height=200)
    wynik: dict = {"stage": stage}
    cap = 30 if stage == "okno" else 330

    def run() -> None:
        end = time.time() + cap
        while time.time() < end:
            try:
                raw = win.evaluate_js("JSON.stringify(window.__WYNIK__ || null)")
            except Exception:  # noqa: BLE001
                raw = None
            if raw and raw != "null":
                wynik.update(json.loads(raw))
                break
            time.sleep(1)
        else:
            wynik["timeout_s"] = cap
        wynik["okna_popup_otwarte"] = len(OKNA)
        for w_, _ in list(OKNA):
            w_.orderOut_(None)
        win.destroy()

    webview.start(run)
    page.unlink(missing_ok=True)
    text = json.dumps(wynik, ensure_ascii=False, indent=1)
    (TU / f"wynik_logowanie_{stage}.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

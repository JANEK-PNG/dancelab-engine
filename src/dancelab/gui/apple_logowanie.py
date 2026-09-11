"""Apple's MusicKit login window inside the DanceLab app.

pywebview's Cocoa UI delegate answers
``webView:createWebViewWithConfiguration:forNavigationAction:windowFeatures:``
with ``nil`` for script-opened windows, so ``window.open`` returns ``null``
and ``MusicKit.authorize()`` never shows Apple's sign-in page (measured
2026-09-10). :func:`wlacz_okienka` swaps pywebview's delegate class for a
subclass that builds a WKWebView from the configuration WebKit hands over —
that keeps ``window.opener``, through which Apple's page returns the token —
inside a new NSWindow, and hides it when the page calls ``window.close()``.

Scope is deliberately narrow:

* only script-opened windows pointing at ``*.apple.com`` get a window; links
  the DJ clicks keep pywebview's behaviour (external browser), anything else
  still gets ``nil``;
* a subclass, not assigned functions — assigning plain functions onto the
  existing class lost the ObjC signatures and crashed the process on first
  show (SIGSEGV, exit 139, probe 2026-09-11).

Verified in the probe: ``window.open`` returns a live window and its
``close()`` closes it. The Apple sign-in itself needs the DJ's Apple ID and
has not been exercised by a machine.
"""

from __future__ import annotations

_OKNA: list = []            # (NSWindow, WKWebView) pairs kept alive while open
_WLACZONE = False


def _host_apple(action) -> bool:
    try:
        host = str(action.request().URL().host() or "").lower()
    except Exception:                                  # noqa: BLE001
        return False
    return host == "apple.com" or host.endswith(".apple.com")


def wlacz_okienka() -> bool:
    """Let MusicKit open Apple's login window. True when the patch is in place."""
    global _WLACZONE
    if _WLACZONE:
        return True
    try:
        import AppKit
        import Foundation
        import objc
        import WebKit
        from webview.platforms import cocoa
    except Exception:                                  # noqa: BLE001
        return False                                   # not macOS / no pywebview

    base = cocoa.BrowserView.BrowserDelegate
    link_activated = getattr(WebKit, "WKNavigationTypeLinkActivated", 0)

    class DanceLabAppleLoginDelegate(base):
        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                self, webview, config, action, features):
            if action.navigationType() == link_activated or not _host_apple(action):
                return objc.super(DanceLabAppleLoginDelegate, self) \
                    .webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                        webview, config, action, features)
            rect = Foundation.NSMakeRect(260, 140, 520, 720)
            style = (AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
                     | AppKit.NSWindowStyleMaskResizable)
            win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect, style, AppKit.NSBackingStoreBuffered, False)
            win.setReleasedWhenClosed_(False)
            wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(rect, config)
            wv.setUIDelegate_(self)
            win.setContentView_(wv)
            win.setTitle_("Apple Music — logowanie")
            win.makeKeyAndOrderFront_(None)
            _OKNA.append((win, wv))
            return wv

        def webViewDidClose_(self, webview):
            for win, wv in list(_OKNA):
                if wv == webview:
                    win.orderOut_(None)
                    _OKNA.remove((win, wv))

    cocoa.BrowserView.BrowserDelegate = DanceLabAppleLoginDelegate
    _WLACZONE = True
    return True

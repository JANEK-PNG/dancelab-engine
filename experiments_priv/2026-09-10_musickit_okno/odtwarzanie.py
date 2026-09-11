"""Login inside the window and a real, short playback — Janek asked for both (2026-09-10).

    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/odtwarzanie.py

Two pywebview windows on file:// (the origin the real window uses):

* ``popup`` — plain ``MusicKit.authorize()``. pywebview's Cocoa backend
  returns nil for script-opened windows, so this measures whether Apple's
  login popup can appear at all. Never plays anything.
* ``hash`` — hands MusicKit the user token Janek already granted (stored in
  ~/.dancelab/musickit/user_token) through the URL hash MusicKit parses on
  configure (``_processLocationHash``: base64 JSON with ``musicUserToken``).
  Then ONE track plays at volume 0.3 for about 5 seconds and is stopped;
  the Python side destroys the window after a hard cap regardless.

Tokens never touch the disk here and never reach stdout or wynik_odtwarzanie.json.
"""

from __future__ import annotations

import json
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.ingestion.apple_music_api import (  # noqa: E402
    developer_token, load_config, read_user_token,
)

PORT = 8690
SONG = "1687954211"          # Jinjé — A Ship Full of Ghosts, in Janek's library, 7:14
PLAY_S = 5
HARD_CAP_S = 60

COMMON = r"""
async function tokens() {
  const r = await fetch('http://127.0.0.1:%PORT%/tokens');
  return r.json();
}
async function loadMusicKit() {
  await new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
    s.onload = res; s.onerror = () => rej(new Error('musickit.js did not load'));
    document.head.appendChild(s);
  });
  if (!window.MusicKit || !MusicKit.configure) {
    await new Promise(res => document.addEventListener('musickitloaded', res, {once: true}));
  }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const within = (p, ms, what) => Promise.race([p, sleep(ms).then(() => {
  throw new Error(what + ' did not finish in ' + ms / 1000 + ' s'); })]);
window.__KROK__ = 'start';
"""

POPUP_JS = COMMON + r"""
window.__WYNIK__ = null;
(async () => {
  const w = {origin: location.protocol};
  try {
    const t = await tokens();
    await loadMusicKit();
    const m = await MusicKit.configure({developerToken: t.dev,
      app: {name: 'DanceLab', build: '1'}, storefrontId: 'pl'});
    const opened = [];
    const orig = window.open;
    window.open = function (...a) { const r = orig.apply(window, a); opened.push(r ? 'window' : 'null'); return r; };
    const res = await Promise.race([
      m.authorize().then(v => 'resolved:' + (v ? 'token' : 'empty'), e => 'rejected:' + String(e && (e.message || e.name) || e)),
      sleep(12000).then(() => 'timeout 12 s')]);
    w.authorize = res;
    w.window_open = opened;
    w.isAuthorized = m.isAuthorized;
    w.href_still_file = location.protocol === 'file:';
  } catch (e) { w.error = String(e && e.message || e); }
  window.__WYNIK__ = w;
})();
"""

HASH_JS = COMMON + r"""
window.__WYNIK__ = null;
(async () => {
  const w = {origin: location.protocol};
  window.__W__ = w;
  let m = null;
  try {
    const t = await tokens();
    const packed = btoa(JSON.stringify({itre: '0', musicUserToken: t.user, cid: ''}));
    history.replaceState(null, '', location.pathname + '#' + packed);
    await loadMusicKit();
    // No storefrontId: MusicKit's assertUserStorefront() throws CONTENT_EQUIVALENT
    // when the configured storefront differs from the authorized user's (try 1).
    window.__KROK__ = 'configure';
    m = await within(MusicKit.configure({developerToken: t.dev,
      app: {name: 'DanceLab', build: '1'}}), 15000, 'configure');
    history.replaceState(null, '', location.pathname);        // token out of the URL again
    w.isAuthorized = m.isAuthorized;
    w.storefront_config = m.storefrontId;
    w.storefront_user = m.storekit ? m.storekit.storefrontCountryCode : null;
    if (w.storefront_user && w.storefront_user !== m.storefrontId) {
      try { m.storefrontId = w.storefront_user; w.storefront_aligned = m.storefrontId; }
      catch (e) { w.storefront_align_error = String(e); }
    }
    w.previewOnly_before = m.previewOnly;
    if (!m.isAuthorized) { w.playback = 'skipped: not authorized'; window.__WYNIK__ = w; return; }
    m.volume = 0.3;
    window.__KROK__ = 'setQueue';
    await within(m.setQueue({song: '%SONG%', startPlaying: false}), 15000, 'setQueue');
    window.__KROK__ = 'play';
    w.queued = m.nowPlayingItem ? {id: m.nowPlayingItem.id,
      duration_ms: m.nowPlayingItem.attributes && m.nowPlayingItem.attributes.durationInMillis,
      preview: !!(m.nowPlayingItem.isPreview || m.nowPlayingItem.previewURL && m.previewOnly)} : null;
    const samples = [];
    const started = Date.now();
    try { await Promise.race([m.play(), sleep(8000).then(() => { throw new Error('play() did not resolve in 8 s'); })]); }
    catch (e) { w.play_error = String(e && (e.message || e.name) || e); }
    while (Date.now() - started < %PLAY_MS%) {
      samples.push({t_ms: Date.now() - started, state: m.playbackState,
                    pos_s: Math.round((m.currentPlaybackTime || 0) * 10) / 10,
                    dur_s: Math.round(m.currentPlaybackDuration || 0)});
      await sleep(1000);
    }
    w.samples = samples;
    window.__KROK__ = 'stop';
    w.previewOnly_after = m.previewOnly;
  } catch (e) { w.error = String(e && e.message || e); }
  finally {
    if (m) { try { await m.stop(); } catch (e) { w.stop_error = String(e); }
             try { m.volume = 0; } catch (e) {}
             w.state_after_stop = m.playbackState; w.pos_after_stop = m.currentPlaybackTime; }
  }
  window.__WYNIK__ = w;
})();
"""

PAGE = """<!doctype html><meta charset="utf-8"><title>DanceLab · Apple Music</title>
<body style="font:14px system-ui;background:#0e1013;color:#ccc;padding:1rem">%LABEL%
<script>%JS%</script>"""


def main() -> None:
    """Serve tokens on localhost, open both windows, collect, stop, close."""
    import webview

    cfg = load_config()
    user = read_user_token()
    if not user:
        sys.exit("brak tokenu użytkownika — najpierw scripts/apple_music_biblioteka.py autoryzuj")
    dev = developer_token(pathlib.Path(cfg["klucz"]), cfg["key_id"], cfg["team_id"], 3600)
    payload = json.dumps({"dev": dev, "user": user}).encode("utf-8")

    pages = {
        "popup": PAGE.replace("%LABEL%", "logowanie przez wyskakujące okno — bez dźwięku")
                     .replace("%JS%", POPUP_JS),
        "hash": PAGE.replace("%LABEL%", f"token przez adres + {PLAY_S} s odtwarzania, głośność 0,3")
                    .replace("%JS%", HASH_JS.replace("%SONG%", SONG)
                             .replace("%PLAY_MS%", str(PLAY_S * 1000))),
    }
    files = {}
    for name, html in pages.items():
        f = TU / f"strona_{name}.html"                   # no token inside
        f.write_text(html.replace("%PORT%", str(PORT)), encoding="utf-8")
        files[name] = f

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            body = payload if self.path == "/tokens" else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    only = set(sys.argv[1:]) or set(files)
    windows = {name: webview.create_window(f"DanceLab sonda {name}", url=f.as_uri(),
                                           width=480, height=160)
               for name, f in files.items() if name in only}
    wynik: dict[str, object] = {}

    def collect() -> None:
        deadline = time.time() + HARD_CAP_S
        while time.time() < deadline and len(wynik) < len(windows):
            for name, win in windows.items():
                if name in wynik:
                    continue
                try:
                    raw = win.evaluate_js("JSON.stringify(window.__WYNIK__ || null)")
                except Exception as exc:  # noqa: BLE001
                    raw = None
                    wynik.setdefault("_errors", []).append(f"{name}: {type(exc).__name__}")
                if raw and raw != "null":
                    wynik[name] = json.loads(raw)
            time.sleep(1)
        for name, win in windows.items():
            if name in wynik:
                continue
            try:
                krok = win.evaluate_js("window.__KROK__ || null")
                part = win.evaluate_js("JSON.stringify(window.__W__ || null)")
                win.evaluate_js("try { MusicKit.getInstance().stop(); } catch (e) {}")
            except Exception as exc:  # noqa: BLE001
                krok, part = f"evaluate_js: {type(exc).__name__}", None
            wynik[name] = {"timeout_s": HARD_CAP_S, "krok": krok,
                           "czesciowy": json.loads(part) if part and part != "null" else None}
        for win in windows.values():          # destroying the view also silences it
            win.destroy()

    webview.start(collect)
    srv.shutdown()
    for f in files.values():
        f.unlink(missing_ok=True)
    text = json.dumps(wynik, ensure_ascii=False, indent=1)
    assert dev not in text and user not in text
    (TU / "wynik_odtwarzanie.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

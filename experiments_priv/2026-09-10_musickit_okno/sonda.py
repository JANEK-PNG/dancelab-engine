"""Probe: can the DanceLab window (pywebview / WKWebView) play full Apple Music streams?

    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/sonda.py

NO SOUND, by construction: nothing here calls play, sets a queue or loads a
song. Two small windows open for a few seconds — one on http://localhost, one
on file:// (the origin the real window uses, gui/okno.py) — each reads the
FairPlay/EME capability and MusicKit's own flags, then both close.

The developer token (1 h) never touches the disk: the localhost page gets it
inlined from memory, the file:// page fetches it from the same local server.
Prints JSON without tokens and writes it to wynik.json beside this script.
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

from dancelab.ingestion.apple_music_api import developer_token, load_config  # noqa: E402

PORT = 8689

PROBE_JS = r"""
window.__WYNIK__ = null;
(async () => {
  const w = {origin: location.origin || location.protocol, ua: navigator.userAgent};
  w.eme_api = typeof navigator.requestMediaKeySystemAccess;
  w.media_keys = typeof window.MediaKeys;
  w.webkit_media_keys = typeof window.WebKitMediaKeys;
  try {
    w.fps1 = window.WebKitMediaKeys ? WebKitMediaKeys.isTypeSupported('com.apple.fps.1_0', 'video/mp4') : null;
    w.fps2 = window.WebKitMediaKeys ? WebKitMediaKeys.isTypeSupported('com.apple.fps.2_0', 'video/mp4') : null;
  } catch (e) { w.fps_err = String(e); }
  try {
    const cfg = [{initDataTypes: ['sinf', 'skd'],
                  audioCapabilities: [{contentType: 'audio/mp4;codecs="mp4a.40.2"'}],
                  videoCapabilities: [{contentType: 'video/mp4;codecs="avc1.42E01E"'}]}];
    const acc = await navigator.requestMediaKeySystemAccess('com.apple.fps', cfg);
    w.eme_fps = 'ok:' + acc.keySystem;
  } catch (e) { w.eme_fps = 'err:' + (e && e.name) + ':' + (e && e.message); }
  try {
    let token = window.__DEV__;
    if (!token) {
      const r = await fetch('http://127.0.0.1:%PORT%/token');
      token = await r.text();
    }
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
      s.onload = res; s.onerror = () => rej(new Error('musickit.js did not load'));
      document.head.appendChild(s);
    });
    if (!window.MusicKit || !MusicKit.configure) {
      await new Promise(res => document.addEventListener('musickitloaded', res, {once: true}));
    }
    const m = await MusicKit.configure({developerToken: token,
      app: {name: 'DanceLab', build: '1'}, storefrontId: 'pl'});
    w.musickit = 'configured';
    w.version = MusicKit.version || null;
    w.isAuthorized = m.isAuthorized;
    w.previewOnly = m.previewOnly;
    const flags = {};
    for (const k of ['supportsDrm', 'hasMediaKeySupport']) {
      for (const o of [m, m._mediaItemPlayback, m.player, MusicKit]) {
        if (o && typeof o[k] === 'function') { try { flags[k] = o[k](); } catch (e) { flags[k] = 'err'; } }
      }
    }
    w.flags = flags;
  } catch (e) { w.musickit = 'err:' + String(e && e.message || e); }
  window.__WYNIK__ = w;
})();
"""

PAGE = """<!doctype html><meta charset="utf-8"><title>sonda</title>
<body style="font:14px system-ui;background:#0e1013;color:#ccc;padding:1rem">sonda MusicKit — bez dźwięku
<script>%DEV%%PROBE%</script>"""


def main() -> None:
    """Serve the probe, open two windows, collect their answers, close everything."""
    import webview

    cfg = load_config()
    token = developer_token(pathlib.Path(cfg["klucz"]), cfg["key_id"], cfg["team_id"], 3600)
    probe = PROBE_JS.replace("%PORT%", str(PORT))
    http_page = PAGE.replace("%DEV%", "window.__DEV__=" + json.dumps(token) + ";").replace(
        "%PROBE%", probe)
    file_page = PAGE.replace("%DEV%", "").replace("%PROBE%", probe)
    file_path = TU / "sonda_plik.html"          # no token inside — fetched at runtime
    file_path.write_text(file_page, encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:  # keep the token out of any log
            return

        def do_GET(self) -> None:  # noqa: N802
            body = (token if self.path == "/token" else http_page).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8" if self.path == "/token"
                             else "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    windows = {
        "localhost": webview.create_window("sonda localhost", url=f"http://localhost:{PORT}/",
                                           width=360, height=120),
        "file": webview.create_window("sonda file", url=file_path.as_uri(),
                                      width=360, height=120),
    }
    wynik: dict[str, object] = {}

    def collect() -> None:
        deadline = time.time() + 45
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
        for name in windows:
            wynik.setdefault(name, "brak odpowiedzi w 45 s")
        for win in windows.values():
            win.destroy()

    webview.start(collect)
    srv.shutdown()
    file_path.unlink(missing_ok=True)
    text = json.dumps(wynik, ensure_ascii=False, indent=1)
    assert token not in text
    (TU / "wynik.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

"""Read the owner's Apple Music library through the Apple Music API.

Two steps, both local:

    .venv/bin/python scripts/apple_music_biblioteka.py autoryzuj
        Serves one page on 127.0.0.1 that loads MusicKit JS, asks Apple for a
        Music User Token in the browser, and stores it in
        ~/.dancelab/musickit/user_token (mode 0600). The developer token used
        by the page lives one hour.

    .venv/bin/python scripts/apple_music_biblioteka.py biblioteka
        Downloads storefront, library songs and playlists (with tracks) to
        data/reports/apple_library.json (gitignored) and prints the join with
        rekordbox's stream ids — the number that says whether this unlocks
        genres for the streams.

Configuration: ~/.dancelab/musickit/konfig.json with keys ``klucz`` (path to
the .p8 file — outside the repo, outside the Desktop), ``key_id`` and
``team_id``. The .p8 is read by openssl only; nothing here prints a token.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dancelab.ingestion.apple_music_api import (  # noqa: E402
    AppleMusicClient, developer_token, fetch_library, summarize,
)

DIR = pathlib.Path.home() / ".dancelab" / "musickit"
CONFIG = DIR / "konfig.json"
USER_TOKEN = DIR / "user_token"
OUTPUT = ROOT / "data/reports/apple_library.json"
PORT = 8688

PAGE = """<!doctype html><meta charset="utf-8"><title>DanceLab · Apple Music</title>
<body style="font:16px system-ui;padding:2rem;max-width:36rem">
<h1>Autoryzacja Apple Music</h1>
<p>Kliknij, zaloguj się w oknie Apple, wróć tutaj.</p>
<button id="b" disabled>Autoryzuj</button> <p id="s">ładuję MusicKit…</p>
<script src="https://js-cdn.music.apple.com/musickit/v3/musickit.js" async></script>
<script>
document.addEventListener('musickitloaded', async () => {
  try {
    await MusicKit.configure({developerToken: '%TOKEN%', app: {name: 'DanceLab', build: '1'},
      storefrontId: 'pl'});
  } catch (e) { document.getElementById('s').textContent = 'MusicKit: ' + e; return; }
  const b = document.getElementById('b'); b.disabled = false;
  document.getElementById('s').textContent = 'gotowe do autoryzacji';
  b.onclick = async () => {
    try {
      const t = await MusicKit.getInstance().authorize();
      const r = await fetch('/token', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: t})});
      document.body.textContent = r.ok ? 'Zapisane. Wróć do terminala.' : 'Zapis nie powiódł się.';
    } catch (e) { document.getElementById('s').textContent = 'autoryzacja: ' + e; }
  };
});
</script>"""


def load_config() -> dict[str, str]:
    """Read the MusicKit configuration or explain what is missing."""
    if not CONFIG.exists():
        sys.exit(f"brak {CONFIG} — potrzebne pola: klucz (ścieżka .p8), key_id, team_id")
    cfg = json.loads(CONFIG.read_text())
    missing = [k for k in ("klucz", "key_id", "team_id") if not cfg.get(k)]
    if missing:
        sys.exit(f"w {CONFIG} brakuje: {', '.join(missing)}")
    return cfg


def mint(cfg: dict[str, str], ttl_s: int) -> str:
    try:
        return developer_token(pathlib.Path(cfg["klucz"]), cfg["key_id"], cfg["team_id"], ttl_s)
    except (ValueError, RuntimeError) as exc:
        sys.exit(str(exc))


def authorize(cfg: dict[str, str]) -> None:
    """Serve the MusicKit page locally and store the user token it returns."""
    page = PAGE.replace("%TOKEN%", mint(cfg, 3600))
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:  # keep tokens out of the log
            return

        def do_GET(self) -> None:  # noqa: N802
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/token":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            token = str(data.get("token") or "")
            if not token:
                self.send_response(400)
                self.end_headers()
                return
            DIR.mkdir(parents=True, exist_ok=True)
            USER_TOKEN.write_text(token)
            os.chmod(USER_TOKEN, 0o600)
            self.send_response(204)
            self.end_headers()
            done.set()

    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    url = f"http://localhost:{PORT}/"  # MusicKit JS is happier with a hostname
    print(f"otwieram {url} — kliknij „Autoryzuj”, zaloguj się u Apple, wróć.")
    webbrowser.open(url)
    done.wait(timeout=600)
    srv.shutdown()
    if done.is_set():
        print(f"token użytkownika zapisany: {USER_TOKEN} (0600)")
    else:
        sys.exit("nie doczekałem się autoryzacji (10 min) — uruchom ponownie")


def collection_stream_ids() -> set[str] | None:
    """Catalog ids rekordbox stores for streams, read-only; None when unreadable."""
    try:
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.db6 import tables
        db = Rekordbox6Database()
    except Exception as exc:  # noqa: BLE001
        print(f"rekordbox nieczytelny ({type(exc).__name__}) — pokrycie kolekcji nieznane")
        return None
    try:
        out = set()
        for r in db.session.query(tables.DjmdContent).all():
            fp = str(r.FolderPath or "")
            if fp.startswith("apple-music:tracks:"):
                out.add(fp.rsplit(":", 1)[1])
        return out
    finally:
        db.close()


def library(cfg: dict[str, str]) -> None:
    """Download the library and print the numbers that matter."""
    if not USER_TOKEN.exists():
        sys.exit(f"brak {USER_TOKEN} — najpierw: apple_music_biblioteka.py autoryzuj")
    client = AppleMusicClient(mint(cfg, 3600), USER_TOKEN.read_text().strip(),
                              refresh=lambda: mint(cfg, 3600))
    lib = fetch_library(client)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(lib, ensure_ascii=False))
    s = summarize(lib, collection_stream_ids())
    print(f"zapisane: {OUTPUT}")
    print(f"utworów w bibliotece : {s['songs']}")
    print(f"  z id katalogu      : {s['with_catalog_id']}")
    print(f"  z gatunkiem        : {s['with_genre']}")
    print(f"playlist             : {s['playlists']}")
    if s["collection_streams"] is None:
        print("strumieni w rekordbox: nieznane (baza nieczytelna)")
    else:
        print(f"strumieni w rekordbox: {s['collection_streams']}")
        print(f"  pokrytych biblioteką: {s['matching_collection']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("krok", choices=["autoryzuj", "biblioteka"])
    args = ap.parse_args()
    cfg = load_config()
    if args.krok == "autoryzuj":
        authorize(cfg)
    else:
        library(cfg)


if __name__ == "__main__":
    main()

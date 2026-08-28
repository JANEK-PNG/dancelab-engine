"""Makieta GUI DanceLab — statyczny podgląd czterech ekranów.

Uruchomienie:
    uv run python docs/gui/serwer.py [port]      (domyślnie 8658)
"""
from __future__ import annotations
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KATALOG = pathlib.Path(__file__).parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8658


class Serwer(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        sciezka = self.path.split("?")[0]
        plik = "index.html" if sciezka in ("/", "/index.html") else sciezka.lstrip("/")
        # Audytor UI jest wspólny dla wszystkich paneli — leży piętro wyżej.
        cel = (KATALOG.parent / "audyt-ui.js") if plik == "audyt-ui.js" \
              else KATALOG / plik
        if not cel.exists() or not cel.is_file():
            self.send_response(404)
            self.end_headers()
            return
        typ = "text/html; charset=utf-8" if cel.suffix == ".html" else "text/plain; charset=utf-8"
        tresc = cel.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(tresc)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(tresc)


print(f"Makieta GUI: http://localhost:{PORT}/")
ThreadingHTTPServer(("127.0.0.1", PORT), Serwer).serve_forever()

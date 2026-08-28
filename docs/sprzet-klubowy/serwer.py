"""Sprzęt klubowy — czego DDJ-FLX4 nie nauczy.

Serwuje statyczny model zestawu CDJ-3000 + DJM-900NXS2 z inwentarzem kontrolek
w kontraście do tego, co Janek ma na własnym kontrolerze.

Uruchomienie:
    cd ~/Developer/dancelab-engine
    uv run python docs/sprzet-klubowy/serwer.py [port]
Domyślny port 8657. Strona: http://localhost:8657/

Serwer nie ma stanu i niczego nie zapisuje — cała treść siedzi w
kontrolki.json obok.
"""

from __future__ import annotations

import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KATALOG = pathlib.Path(__file__).parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8657

PLIKI = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/kontrolki.json": ("kontrolki.json", "application/json; charset=utf-8"),
}


class Serwer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self) -> None:
        wpis = PLIKI.get(self.path.split("?")[0])
        if wpis is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"nie ma takiej strony")
            return
        nazwa, typ = wpis
        tresc = (KATALOG / nazwa).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(tresc)))
        # Bez cache — inaczej po edycji JSON-a panel serwuje stare dane.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(tresc)


def main() -> None:
    print(f"Sprzęt klubowy: http://localhost:{PORT}/")
    print("Zatrzymanie: Ctrl+C")
    ThreadingHTTPServer(("127.0.0.1", PORT), Serwer).serve_forever()


if __name__ == "__main__":
    main()

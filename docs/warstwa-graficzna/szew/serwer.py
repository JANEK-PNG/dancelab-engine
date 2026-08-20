"""Serwer płótna szwu, który NIE POZWALA się buforować.

Ta sama lekcja co przy scenie v2 (13.08): zwykły `http.server` oddaje pliki
z nagłówkami, przez które przeglądarka i pośrednik podglądu trzymają starą
kopię — i ocenia się wtedy nie ten obraz, który wisi na dysku. No-store na
każdym pliku; strona jest maleńka i lokalna, pomyłka kosztuje godziny.
"""

from __future__ import annotations

import http.server
import pathlib
import sys

TU = pathlib.Path(__file__).parent


class BezCache(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(TU), **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):  # cisza w konsoli
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8654
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), BezCache) as srv:
        print(f"płótno szwu bez cache na http://localhost:{port}", flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()

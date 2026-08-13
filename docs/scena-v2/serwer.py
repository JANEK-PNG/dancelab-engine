"""Serwer sceny, który NIE POZWALA się buforować.

Powód (13.08): zwykły `python -m http.server` oddaje pliki z nagłówkami,
przez które przeglądarka i pośrednik podglądu trzymają starą kopię. Janek
odświeżał stronę i widział poprzednią wersję — raz jako „nic się nie
zmieniło", raz jako „nie działa strona". Ja też dwa razy oceniałem stary
obraz i szukałem błędu tam, gdzie go nie było.

Wysyłamy więc no-store przy każdym pliku. Scena jest maleńka i lokalna,
więc nie ma czego oszczędzać, a pomyłka kosztuje godziny.
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

    def log_message(self, fmt, *args):        # cisza w konsoli
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8652
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), BezCache) as srv:
        print(f"scena-v2 bez cache na http://localhost:{port}", flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()

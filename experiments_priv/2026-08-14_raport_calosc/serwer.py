"""Podgląd raportu z jawnym kodowaniem i bez pamięci podręcznej.

Wbudowany `http.server` nie deklaruje charsetu, więc przeglądarka zgaduje
latin-1 i polskie znaki się sypią. To NIE jest wada strony — opublikowany
artefakt dostaje `<meta charset>` z ramki. Ten serwer istnieje tylko po to,
żeby podgląd lokalny pokazywał to samo, co zobaczy czytelnik.
"""

import http.server
import pathlib
import socketserver

KATALOG = pathlib.Path(__file__).parent
PORT = 8771


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(KATALOG), **kw)

    def guess_type(self, path):
        typ = super().guess_type(path)
        if typ == "text/html":
            return "text/html; charset=utf-8"
        return typ

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


with socketserver.TCPServer(("", PORT), Handler) as srv:
    srv.allow_reuse_address = True
    print(f"raport: http://localhost:{PORT}/raport.html")
    srv.serve_forever()

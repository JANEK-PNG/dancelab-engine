"""Serwerek partii dla strony music.apple.com (CORS) — tylko odczyt, localhost."""
import http.server, functools
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()
http.server.HTTPServer(("127.0.0.1", 8648), functools.partial(
    H, directory="/Users/jantrybus/Developer/dancelab-engine/experiments_priv/2026-08-03_dj_mapa")
).serve_forever()

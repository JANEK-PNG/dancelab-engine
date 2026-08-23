"""Cyfrowy model DDJ-FLX4 — serwer: MIDI z kontrolera → przeglądarka (SSE).

Tylko NASŁUCH wejścia (zero MIDI-OUT), więc działa obok Rekordboxa
(zmierzone 23.08.2026: 3820 komunikatów przy grającym Rekordboksie).

Uruchomienie:
    uv run --with mido --with python-rtmidi python docs/flx4-konsola/serwer.py [port]
Domyślny port 8655. Strona: http://localhost:8655/

Do testów bez kontrolera: GET /test?raw=90+0B+7F wstrzykuje komunikat.
"""

from __future__ import annotations

import json
import pathlib
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

KATALOG = pathlib.Path(__file__).parent
START = time.monotonic()
_klienci: list[queue.Queue] = []
_lock = threading.Lock()
_stan = {"port_midi": None, "komunikatow": 0}


def rozglos(msg) -> None:
    if msg.type in ("active_sensing", "clock"):   # tykanie bez treści
        return
    rek = {
        "t": round(time.monotonic() - START, 4),
        "type": msg.type,
        "ch": getattr(msg, "channel", None),
        "d1": getattr(msg, "note", getattr(msg, "control", None)),
        "d2": getattr(msg, "velocity", getattr(msg, "value", None)),
        "raw": msg.hex(),
    }
    _stan["komunikatow"] += 1
    with _lock:
        for q in list(_klienci):
            try:
                q.put_nowait(rek)
            except queue.Full:
                pass


def watek_midi() -> None:
    import mido
    while True:
        nazwa = next((n for n in mido.get_input_names() if "FLX4" in n), None)
        if not nazwa:
            _stan["port_midi"] = None
            time.sleep(2.0)
            continue
        _stan["port_midi"] = nazwa
        try:
            with mido.open_input(nazwa, callback=rozglos):
                while nazwa in mido.get_input_names():
                    time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001 — odpięty kabel itp.
            print("MIDI:", exc)
            time.sleep(2.0)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # cisza w terminalu
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            tresc = (KATALOG / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(tresc)))
            self.end_headers()
            self.wfile.write(tresc)
        elif u.path == "/set":
            import glob
            pliki = sorted(glob.glob(str(KATALOG.parents[1] /
                "experiments_priv/2026-08-23_set_rejestracja/widok_setu.html")))
            if not pliki:
                self.send_response(404); self.end_headers(); return
            tresc = pathlib.Path(pliki[-1]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(tresc)))
            self.end_headers()
            self.wfile.write(tresc)
        elif u.path == "/stan":
            tresc = json.dumps(_stan).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(tresc)))
            self.end_headers()
            self.wfile.write(tresc)
        elif u.path == "/test":
            import mido
            raw = parse_qs(u.query).get("raw", [""])[0]
            bajty = [int(b, 16) for b in raw.replace("+", " ").split()]
            rozglos(mido.Message.from_bytes(bajty))
            self.send_response(204)
            self.end_headers()
        elif u.path == "/events":
            q: queue.Queue = queue.Queue(maxsize=5000)
            with _lock:
                _klienci.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    try:
                        rek = q.get(timeout=5.0)
                        self.wfile.write(f"data: {json.dumps(rek)}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with _lock:
                    if q in _klienci:
                        _klienci.remove(q)
        else:
            self.send_response(404)
            self.end_headers()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8655
    threading.Thread(target=watek_midi, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"konsola FLX4: http://localhost:{port}/  (Ctrl+C kończy)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

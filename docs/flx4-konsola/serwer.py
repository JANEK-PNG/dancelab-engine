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
REJESTRY = KATALOG.parents[1] / "experiments_priv/2026-08-24_rejestry_konsoli"
START = time.monotonic()
_klienci: list[queue.Queue] = []
_lock = threading.Lock()
_stan = {"port_midi": None, "komunikatow": 0}
_rec = {"f": None, "plik": None, "nazwa": None, "start": None, "n": 0}
_replay = {"watek": None, "stop": False, "plik": None, "poz": 0, "n": 0, "blad": None}
_port_wirt = {"port": None, "we": None}   # wirtualne „DDJ-FLX4": źródło + CEL (Rekordbox musi móc mówić do „urządzenia")
_od_rb = []                                # co Rekordbox wysłał do naszego wirtualnego kontrolera


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
    if _rec["f"] is not None:
        _rec["f"].write(json.dumps({**rek, "ts": round(time.time(), 4)}) + "\n")
        _rec["n"] += 1
    with _lock:
        for q in list(_klienci):
            try:
                q.put_nowait(rek)
            except queue.Full:
                pass


def watek_midi() -> None:
    import mido
    while True:
        if _port_wirt["port"] is not None:      # tryb emulacji: nie podpinaj się pod własną podróbkę
            _stan["port_midi"] = "emulacja (wirtualny DDJ-FLX4)"
            time.sleep(2.0)
            continue
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

    def _json(self, obj):
        tresc = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

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
        elif u.path == "/rec/start":
            import re as _re
            from datetime import datetime as _dt
            if _rec["f"] is not None:
                self._json({"blad": "nagrywanie już trwa"}); return
            nazwa = _re.sub(r"[^\w-]+", "_", parse_qs(u.query).get("nazwa", [""])[0])[:40] or "bez_nazwy"
            REJESTRY.mkdir(parents=True, exist_ok=True)
            plik = REJESTRY / f"rejestr_{_dt.now():%Y%m%d_%H%M%S}_{nazwa}.jsonl"
            _rec.update(f=open(plik, "w", encoding="utf-8", buffering=1),
                        plik=plik.name, nazwa=nazwa, start=time.time(), n=0)
            self._json({"ok": True, "plik": plik.name})
        elif u.path == "/rec/stop":
            if _rec["f"] is None:
                self._json({"blad": "nic nie jest nagrywane"}); return
            _rec["f"].close()
            wynik = {"ok": True, "plik": _rec["plik"], "zdarzen": _rec["n"],
                     "sekund": round(time.time() - _rec["start"], 1)}
            _rec.update(f=None, plik=None, nazwa=None, start=None, n=0)
            self._json(wynik)
        elif u.path == "/rec/lista":
            REJESTRY.mkdir(parents=True, exist_ok=True)
            lista = []
            for p2 in sorted(REJESTRY.glob("rejestr_*.jsonl"), reverse=True):
                linie = p2.read_text(encoding="utf-8").splitlines()
                dl = 0.0
                if len(linie) >= 2:
                    try:
                        dl = json.loads(linie[-1])["t"] - json.loads(linie[0])["t"]
                    except Exception:
                        dl = 0.0
                lista.append({"plik": p2.name, "zdarzen": len(linie), "sekund": round(dl, 1)})
            self._json({"rejestry": lista, "nagrywa": _rec["plik"],
                        "replay": _replay["plik"] if _replay["watek"] else None})
        elif u.path == "/rec/dane":
            plik = parse_qs(u.query).get("plik", [""])[0]
            cel = (REJESTRY / plik).resolve()
            if not plik.endswith(".jsonl") or REJESTRY.resolve() not in cel.parents or not cel.exists():
                self.send_response(404); self.end_headers(); return
            tresc = cel.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(tresc)))
            self.end_headers()
            self.wfile.write(tresc)
        elif u.path == "/replay/start":
            import mido
            if _replay["watek"] is not None:
                self._json({"blad": "replay już trwa"}); return
            obce = sum(1 for n in mido.get_input_names() if "FLX4" in n)                    - (1 if _port_wirt["port"] is not None else 0)
            if obce > 0:
                self._json({"blad": "odłącz prawdziwy kontroler — dwa porty DDJ-FLX4 "
                                    "pomyliłyby Rekordboxa"}); return
            plik = parse_qs(u.query).get("plik", [""])[0]
            cel = (REJESTRY / plik).resolve()
            if not plik.endswith(".jsonl") or REJESTRY.resolve() not in cel.parents or not cel.exists():
                self._json({"blad": "nie ma takiego rejestru"}); return
            linie = [json.loads(l) for l in cel.read_text(encoding="utf-8").splitlines()]
            _replay.update(stop=False, plik=plik, poz=0, n=len(linie), blad=None)

            def graj():
                try:
                    # port WIRTUALNY o nazwie kontrolera — Rekordbox widzi „DDJ-FLX4”;
                    # NIGDY nie otwieramy wyjścia do prawdziwego urządzenia.
                    # Port wstaje raz i zostaje otwarty między odtworzeniami.
                    if _port_wirt["port"] is None:
                        _port_wirt["port"] = mido.open_output("DDJ-FLX4", virtual=True)
                        def od_rb(m):
                            _od_rb.append({"ts": round(time.time(), 3), "raw": m.hex(),
                                           "type": m.type})
                            del _od_rb[:-200]
                        _port_wirt["we"] = mido.open_input("DDJ-FLX4", virtual=True,
                                                           callback=od_rb)
                    port = _port_wirt["port"]
                    t0 = time.monotonic()
                    start_t = linie[0]["t"] if linie else 0.0
                    for i, rek2 in enumerate(linie):
                        if _replay["stop"]:
                            break
                        cel_t = rek2["t"] - start_t
                        while time.monotonic() - t0 < cel_t:
                            if _replay["stop"]:
                                break
                            time.sleep(0.001)
                        msg = mido.Message.from_hex(rek2["raw"])
                        port.send(msg)
                        rozglos(msg)          # model animuje to, co gra
                        _replay["poz"] = i + 1
                except Exception as exc:  # noqa: BLE001
                    _replay["blad"] = f"{type(exc).__name__}: {exc}"
                finally:
                    _replay["watek"] = None

            w = threading.Thread(target=graj, daemon=True)
            _replay["watek"] = w
            w.start()
            self._json({"ok": True, "zdarzen": len(linie)})
        elif u.path == "/replay/stop":
            _replay["stop"] = True
            self._json({"ok": True})
        elif u.path == "/emulacja/stop":
            for k in ("port", "we"):
                if _port_wirt[k] is not None:
                    try: _port_wirt[k].close()
                    except Exception: pass
                    _port_wirt[k] = None
            self._json({"ok": True, "info": "porty wirtualne zamknięte — wracam do nasłuchu"})
        elif u.path == "/emulacja/stan":
            self._json({"port_zrodlo": _port_wirt["port"] is not None,
                        "port_cel": _port_wirt["we"] is not None,
                        "od_rekordboxa": _od_rb[-30:],
                        "odebrano_od_rb": len(_od_rb)})
        elif u.path == "/replay/stan":
            self._json({"gra": _replay["watek"] is not None, "plik": _replay["plik"],
                        "poz": _replay["poz"], "n": _replay["n"], "blad": _replay["blad"],
                        "nagrywa": _rec["plik"], "nagrano": _rec["n"]})
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

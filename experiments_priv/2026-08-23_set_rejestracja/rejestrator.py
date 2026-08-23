"""Rejestrator setu: każdy komunikat MIDI z DDJ-FLX4 → JSONL, z zegarem ściennym.

Tylko nasłuch wejścia (zero MIDI-OUT) — działa obok Rekordboxa (zmierzone).
`ts` = czas epoki (do zgrania z nagraniem WAV Rekordboxa), `t` = monotoniczny.
Użycie: uv run --with mido --with python-rtmidi python rejestrator.py [sekundy]
"""
import json, pathlib, sys, time
from datetime import datetime

KATALOG = pathlib.Path(__file__).parent

def main():
    import mido
    sekundy = float(sys.argv[1]) if len(sys.argv) > 1 else 4 * 3600
    nazwa = next((n for n in mido.get_input_names() if "FLX4" in n), None)
    if not nazwa:
        print("brak DDJ-FLX4"); return 2
    plik = KATALOG / f"set_{datetime.now():%Y%m%d_%H%M%S}_midi.jsonl"
    f = open(plik, "w", encoding="utf-8", buffering=1)
    start = time.monotonic()
    def cb(msg):
        if msg.type in ("active_sensing", "clock"): return
        f.write(json.dumps({"ts": round(time.time(), 4),
                            "t": round(time.monotonic() - start, 4),
                            "type": msg.type, "ch": getattr(msg, "channel", None),
                            "d1": getattr(msg, "note", getattr(msg, "control", None)),
                            "d2": getattr(msg, "velocity", getattr(msg, "value", None)),
                            "raw": msg.hex()}) + "\n")
    print("zapis:", plik)
    with mido.open_input(nazwa, callback=cb):
        time.sleep(sekundy)
    f.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

"""Nasłuch DDJ-FLX4: surowe MIDI → plik JSONL + tłumaczenie na nazwy kontrolek.

Tłumaczenie według OFICJALNEJ „List of MIDI messages" Ver 1.0 (AlphaTheta),
wyciąg w NOTATKI_INSTRUKCJA.md. Tylko WEJŚCIE — skrypt nic nie wysyła do
urządzenia (hipoteza: dzięki temu może działać obok Rekordboxa).

Kanały w kodzie są 0-based (mido); PDF Pioneera liczy od 1.

Użycie:
    uv run --with mido --with python-rtmidi python nasluch.py [sekundy]
Domyślnie 30 s. Plik: nasluch_<stempel>.jsonl obok skryptu.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
from datetime import datetime

KATALOG = pathlib.Path(__file__).parent

# ---- przyciski na kanale decka (0 = deck 1, 1 = deck 2) ----
NUTY_DECK = {
    11: "PLAY/PAUSE", 14: "PLAY/PAUSE+SHIFT", 12: "CUE", 72: "CUE+SHIFT",
    63: "SHIFT", 54: "JOG touch", 103: "JOG touch+SHIFT",
    16: "IN", 76: "IN+SHIFT", 17: "OUT", 78: "OUT+SHIFT",
    77: "4BEAT/EXIT", 80: "4BEAT/EXIT+SHIFT",
    81: "CUE/LOOP CALL <", 62: "CUE/LOOP CALL <+SHIFT",
    83: "CUE/LOOP CALL >", 61: "CUE/LOOP CALL >+SHIFT",
    88: "BEAT SYNC", 92: "BEAT SYNC long", 96: "BEAT SYNC+SHIFT",
    27: "HOT CUE mode", 105: "HOT CUE mode+SHIFT(KEYBOARD)",
    30: "PAD FX1 mode", 107: "PAD FX1 mode+SHIFT(PAD FX2)",
    32: "BEAT JUMP mode", 109: "BEAT JUMP mode+SHIFT(BEAT LOOP)",
    34: "SAMPLER mode", 111: "SAMPLER mode+SHIFT(KEY SHIFT)",
    84: "CH CUE", 104: "CH CUE+SHIFT",
    102: "FADER START → PLAY", 82: "FADER START → CUE",
    23: "VINYL MODE (MIDI-OUT?)",
}
CC_DECK = {
    0: "TEMPO msb", 32: "TEMPO lsb", 4: "TRIM msb", 36: "TRIM lsb",
    7: "EQ HI msb", 39: "EQ HI lsb", 11: "EQ MID msb", 43: "EQ MID lsb",
    15: "EQ LOW msb", 47: "EQ LOW lsb", 19: "CH FADER msb", 51: "CH FADER lsb",
    34: "JOG platter (vinyl ON)", 35: "JOG platter (vinyl OFF)",
    41: "JOG platter+SHIFT", 33: "JOG wheel side",
}
# ---- kanał globalny 6 (PDF: 7) ----
NUTY_GLOB = {
    99: "MASTER CUE", 120: "MASTER CUE+SHIFT", 0: "SMART CFX", 8: "SMART CFX+SHIFT",
    1: "SMART FADER", 9: "SMART FADER+SHIFT", 65: "BROWSE press", 66: "BROWSE press+SHIFT",
    70: "LOAD deck1", 104: "LOAD deck1+SHIFT", 71: "LOAD deck2", 122: "LOAD deck2+SHIFT",
    109: "Android MONO/STEREO",
}
CC_GLOB = {
    23: "CFX deck1 msb", 55: "CFX deck1 lsb", 24: "CFX deck2 msb", 56: "CFX deck2 lsb",
    31: "CROSSFADER msb", 63: "CROSSFADER lsb", 8: "MASTER LEVEL msb", 40: "MASTER LEVEL lsb",
    5: "MIC LEVEL msb", 37: "MIC LEVEL lsb", 12: "HP MIX msb", 44: "HP MIX lsb",
    13: "HP LEVEL msb", 45: "HP LEVEL lsb", 64: "BROWSE rotate", 100: "BROWSE rotate+SHIFT",
}
# ---- efekty: kanał 4 (PDF 5) i 5 (PDF 6) ----
NUTY_FX = {
    99: "FX SELECT", 100: "FX SELECT+SHIFT", 74: "BEAT <", 102: "BEAT <+SHIFT",
    75: "BEAT >", 107: "BEAT >+SHIFT", 71: "FX ON/OFF", 67: "FX ON/OFF+SHIFT(RELEASE)",
    16: "FX CH SELECT bit16", 17: "FX CH SELECT bit17",
}
CC_FX = {2: "LEVEL/DEPTH msb", 34: "LEVEL/DEPTH lsb"}
TRYBY_PADOW = {0x00: "HOT CUE", 0x10: "PAD FX1", 0x20: "BEAT JUMP", 0x30: "SAMPLER",
               0x40: "KEYBOARD", 0x50: "PAD FX2", 0x60: "BEAT LOOP", 0x70: "KEY SHIFT"}


def nazwij(msg) -> str:
    typ = msg.type
    if not hasattr(msg, "channel"):
        return f"{typ} {msg.hex()}"
    ch = msg.channel
    if typ in ("note_on", "note_off"):
        n, v = msg.note, msg.velocity
        if ch in (0, 1):
            return f"deck{ch+1} {NUTY_DECK.get(n, f'NOTE?{n}')} {'ON' if v else 'OFF'}"
        if ch == 6:
            return f"glob {NUTY_GLOB.get(n, f'NOTE?{n}')} {'ON' if v else 'OFF'}"
        if ch in (4, 5):
            return f"fx{ch-3} {NUTY_FX.get(n, f'NOTE?{n}')} {'ON' if v else 'OFF'} (v={v})"
        if ch in (7, 8, 9, 10):
            deck = 1 if ch in (7, 8) else 2
            shift = "+SHIFT" if ch in (8, 10) else ""
            tryb = TRYBY_PADOW.get(n & 0x70, f"tryb?{n & 0x70:02X}")
            return f"deck{deck} PAD {(n & 0x0F) + 1} [{tryb}]{shift} {'ON' if v else 'OFF'}"
        return f"ch{ch} NOTE {n} v={v}"
    if typ == "control_change":
        c, v = msg.control, msg.value
        if ch in (0, 1):
            return f"deck{ch+1} {CC_DECK.get(c, f'CC?{c}')} = {v}"
        if ch == 6:
            return f"glob {CC_GLOB.get(c, f'CC?{c}')} = {v}"
        if ch in (4, 5):
            return f"fx{ch-3} {CC_FX.get(c, f'CC?{c}')} = {v}"
        return f"ch{ch} CC {c} = {v}"
    return str(msg)


def main() -> int:
    import mido
    sekundy = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    nazwa = next((n for n in mido.get_input_names() if "FLX4" in n), None)
    if not nazwa:
        print("⛔ nie widzę DDJ-FLX4 wśród wejść MIDI:", mido.get_input_names())
        return 2
    stempel = f"{datetime.now():%Y%m%d_%H%M%S}"
    plik = KATALOG / f"nasluch_{stempel}.jsonl"
    print(f"słucham „{nazwa}” przez {sekundy:.0f} s → {plik.name}")
    start = time.monotonic()
    n = 0
    with mido.open_input(nazwa) as port, open(plik, "w", encoding="utf-8") as f:
        while time.monotonic() - start < sekundy:
            for msg in port.iter_pending():
                t = time.monotonic() - start
                rek = {"t": round(t, 4), "type": msg.type, "ch": getattr(msg, "channel", None),
                       "d1": getattr(msg, "note", getattr(msg, "control", None)),
                       "d2": getattr(msg, "velocity", getattr(msg, "value", None)),
                       "raw": msg.hex(), "nazwa": nazwij(msg)}
                f.write(json.dumps(rek, ensure_ascii=False) + "\n")
                n += 1
                if n <= 400:
                    print(f"{t:7.3f}  {msg.hex():<10} {rek['nazwa']}")
            time.sleep(0.002)
    print(f"\nkomunikatów: {n} · plik: {plik}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

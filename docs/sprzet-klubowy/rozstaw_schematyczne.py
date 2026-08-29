"""Rozstawienie kontrolek SCHEMATYCZNYCH wokół zmierzonych punktów.

Po wstawieniu prawdziwych wymiarów talerz CDJ-3000 (⌀202 mm) zajął środek
panelu i wszedł na kontrolki, które nadal stały na pozycjach zgadywanych pod
mniejszy rysunek. To nie był błąd pomiaru — to był konflikt między tym, co
zmierzone, a tym, co nadal zmyślone.

Skrypt układa kontrolki bez pomiaru w wolnych strefach, które zostają po
zmierzonych: wąska kolumna po lewej (62 mm), wąska po prawej (64 mm) i pasy
nad ekranem oraz pod listwą hot cue. Strefy wynikają z geometrii zmierzonej,
więc rozmieszczenie jest wiarygodne co do OBSZARU, dalej nie co do milimetra —
i te elementy dalej rysują się kreską przerywaną.
"""

from __future__ import annotations

import json
import pathlib

TU = pathlib.Path(__file__).parent

# strefy CDJ (mm): talerz zajmuje x 62–265, ekran y 27–136, hot cue y 146–165
CDJ = {
    "TAG LIST / playlisty na urządzeniu": (6, 6, 50, 14),
    "Dwa gniazda USB + PRO DJ LINK":      (6, 24, 50, 14),
    "QUANTIZE":                           (6, 42, 50, 14),
    "SLIP":                               (6, 60, 50, 14),
    "LOOP IN / OUT":                      (6, 172, 50, 15),
    "AUTO BEAT LOOP":                     (6, 191, 50, 15),
    "CALL ◁ ▷":                           (6, 210, 50, 15),
    "REVERSE":                            (6, 229, 50, 15),
    "VINYL SPEED ADJUST (TOUCH / RELEASE)": (6, 248, 50, 15),
    "Tryb VINYL / CDJ":                   (6, 267, 50, 15),
    "CUE":                                (6, 350, 50, 34),
    "PLAY / PAUSE":                       (6, 392, 50, 34),
    "BEAT SYNC":                          (271, 172, 52, 15),
    "KEY SYNC / KEY RESET":               (271, 191, 52, 15),
    "MASTER TEMPO":                       (271, 210, 52, 15),
    "TEMPO RANGE (±6 / 10 / 16 / WIDE)":  (271, 229, 52, 15),
    "Suwak TEMPO (100 mm)":               (287, 260, 20, 150),
}
# DJM: kanały i sekcje boczne są zmierzone, reszta idzie w pasy między nimi
DJM = {
    "SEND / RETURN":  (66, 6, 160, 16),
    "SOUND COLOR FX": (66, 26, 160, 16),
    "Cztery kanały zamiast dwóch": (62, 50, 168, 10),
    "Crossfader":     (62, 380, 200, 18),
    "Przełącznik krzywej crossfadera i faderów": (270, 380, 56, 18),
    "MASTER LEVEL":   (296, 30, 0, 0),
    "BOOTH z własnym poziomem": (296, 62, 0, 0),
}
DJM_KOLA = {"MASTER LEVEL": (296.6, 30.0, 13.0),
            "BOOTH z własnym poziomem": (296.6, 62.0, 13.0)}


def main() -> int:
    plik = TU / "uklad.json"
    u = json.loads(plik.read_text(encoding="utf-8"))
    ruszone = 0
    for d in u["urzadzenia"]:
        mapa = CDJ if d["nazwa"].startswith("CDJ") else DJM
        for e in d.get("elementy") or []:
            if e.get("zmierzone"):
                continue
            if e["k"] in DJM_KOLA and not d["nazwa"].startswith("CDJ"):
                x, y, r = DJM_KOLA[e["k"]]
                e.update(ksztalt="kolo", x=x, y=y, r=r)
                e.pop("w", None), e.pop("h", None)
                ruszone += 1
                continue
            if e["k"] not in mapa:
                continue
            x, y, w, h = mapa[e["k"]]
            e.update(ksztalt="prostokat", x=x, y=y, w=w, h=h)
            e.pop("r", None)
            ruszone += 1
    plik.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"przestawionych kontrolek schematycznych: {ruszone}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Podmiana geometrii schematycznej na zmierzoną — CDJ-3000 i DJM-900NXS2.

Do 29.08 `uklad.json` niósł ostrzeżenie „GEOMETRIA SCHEMATYCZNA, NIE ZMIERZONA".
Instrukcje dotarły, więc część rysunku przestaje być zgadywana:

* CDJ-3000 — rzut płaski ze strony 14 instrukcji, skala z danych technicznych
  (s. 83: 329 × 453 × 118 mm). Zmierzone: talerz, ekran, listwa hot cue,
  pokrętło browse.
* DJM-900NXS2 — rzut WEKTOROWY ze strony 7 instrukcji; szerokość 332 mm
  z katalogu, potwierdzona proporcją obrysu (0,803 wobec 0,801).
  Zmierzone: rozstaw kanałów, bloki EQ, sekcje boczne.

Reszta kontrolek zostaje na pozycjach schematycznych i **jest tak oznaczona**
(`zmierzone: false`), a rysunek pokazuje je linią przerywaną. Model, który nie
mówi, czego nie wie, jest gorszy od modelu, który wie mniej.
"""

from __future__ import annotations

import json
import pathlib
import shutil

TU = pathlib.Path(__file__).parent
CDJ_W, CDJ_H = 329.0, 453.0
DJM_W, DJM_H = 332.0, 413.2
PRZERWA = 22.0                      # odstęp między urządzeniami NA RYSUNKU

# zmierzone: (nazwa elementu) → nowa geometria w mm, środek dla kół
CDJ_ZMIERZONE = {
    'Ekran dotykowy 9"': dict(ksztalt="prostokat", x=163.0 - 199.5 / 2,
                              y=81.6 - 108.8 / 2, w=199.5, h=108.8),
    "Pokrętło ROTARY SELECTOR": dict(ksztalt="kolo", x=290.9, y=78.6, r=20.0),
    "HOT CUE A–H (osiem)": dict(ksztalt="prostokat", x=142.8 - 268.5 / 2,
                                y=155.6 - 18.8 / 2, w=268.5, h=18.8),
    "Jog 206 mm z regulacją oporu": dict(ksztalt="kolo", x=163.6, y=296.5,
                                         r=101.1),
    "Ekran na talerzu": dict(ksztalt="kolo", x=163.8, y=296.5, r=44.5),
}
DJM_ZMIERZONE = {
    "BEAT FX": dict(ksztalt="prostokat", x=296.6 - 57.6 / 2, y=161.5 - 124.6 / 2,
                    w=57.6, h=124.6),
    "Słuchawki: MIXING / LEVEL": dict(ksztalt="prostokat", x=30.9 - 52.0 / 2,
                                      y=223.9 - 67.4 / 2, w=52.0, h=67.4),
}
KANALY_X = [82.0, 124.6, 167.4, 210.2]      # zmierzone środki kanałów


def przeskaluj(e: dict, sx: float, sy: float) -> dict:
    e = dict(e)
    for k, s in (("x", sx), ("w", sx), ("y", sy), ("h", sy)):
        if k in e and isinstance(e[k], (int, float)):
            e[k] = round(e[k] * s, 1)
    if "r" in e:
        e["r"] = round(e["r"] * (sx + sy) / 2, 1)
    return e


def main() -> int:
    plik = TU / "uklad.json"
    shutil.copy2(plik, TU / "uklad_schematyczny_2026-08-28.json")
    u = json.loads(plik.read_text(encoding="utf-8"))

    u["jednostka"] = "milimetr (rzeczywisty)"
    u["UWAGA"] = (
        "GEOMETRIA MIESZANA. Elementy z `zmierzone: true` pochodzą z rzutów "
        "płaskich w instrukcjach obsługi: CDJ-3000 ze strony 14 (skala z danych "
        "technicznych, s. 83: 329 × 453 mm), DJM-900NXS2 ze strony 7 (rzut "
        "wektorowy; szerokość 332 mm z katalogu, potwierdzona proporcją obrysu "
        "0,803 wobec 0,801). Elementy z `zmierzone: false` mają pozycje "
        "SCHEMATYCZNE — rozmieszczenie się zgadza, milimetry nie — i na rysunku "
        "są kreską przerywaną. Odstęp między urządzeniami jest rysunkowy, nie "
        "wynika z ustawienia w klubie.")
    u["zrodla_pomiaru"] = {
        "CDJ-3000": "instrukcja s.14 (rzut płaski) + s.83 (dane techniczne)",
        "DJM-900NXS2": "instrukcja s.7 (rzut wektorowy) + proporcja obrysu",
    }

    for d in u["urzadzenia"]:
        cdj = d["nazwa"].startswith("CDJ")
        stara_w, stara_h = d["w"], d["h"]
        d["w"], d["h"] = (CDJ_W, CDJ_H) if cdj else (DJM_W, DJM_H)
        sx, sy = d["w"] / stara_w, d["h"] / stara_h
        zmierzone = CDJ_ZMIERZONE if cdj else DJM_ZMIERZONE
        nowe = []
        for e in d.get("elementy") or []:
            if e["k"] in zmierzone:
                e = {**e, **zmierzone[e["k"]], "zmierzone": True}
                if e["k"].startswith("Jog"):
                    e["k"] = "Jog ⌀202 mm z regulacją oporu"
                    e["etykieta"] = "jog"
            else:
                e = {**przeskaluj(e, sx, sy), "zmierzone": False}
            nowe.append(e)
        if nowe:
            d["elementy"] = nowe
        if not cdj:
            d["kanaly_x"] = KANALY_X
            d["kanaly_zmierzone"] = True

    # ustawienie w rzędzie: CDJ · DJM · CDJ, wyrównane przednią krawędzią
    x = 0.0
    for d in u["urzadzenia"]:
        d["x"], d["y"] = round(x, 1), 0
        x += d["w"] + PRZERWA
    u["plotno_mm"] = {"szerokosc": round(x - PRZERWA, 1),
                      "wysokosc": max(d["h"] for d in u["urzadzenia"])}

    plik.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")
    ile_z = sum(1 for d in u["urzadzenia"] for e in (d.get("elementy") or [])
                if e.get("zmierzone"))
    ile_s = sum(1 for d in u["urzadzenia"] for e in (d.get("elementy") or [])
                if not e.get("zmierzone"))
    print(f"płótno: {u['plotno_mm']['szerokosc']:.0f} × "
          f"{u['plotno_mm']['wysokosc']:.0f} mm")
    for d in u["urzadzenia"]:
        print(f"  {d['nazwa']:<14} {d['w']:>5.1f} × {d['h']:<5.1f} mm  @ x={d['x']}")
    print(f"elementów zmierzonych: {ile_z} · schematycznych: {ile_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

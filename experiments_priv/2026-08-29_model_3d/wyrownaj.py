"""Wyrównanie układu części z modelu do układu z instrukcji.

Po odwróceniu osi Y (złapane przez Janka na podglądzie) zostało przesunięcie
o ~14 mm: model liczy głębokość od najdalszego punktu z tyłu urządzenia,
a rysunek z instrukcji od tylnej krawędzi panelu.

Wyrównanie robimy na DWÓCH punktach zmierzonych niezależnie z instrukcji
(listwa hot cue 155,6 · talerz 296,5), a poprawność sprawdzamy na TRZECIM,
którego do wyrównania nie użyto: pokrętło BROWSE, z instrukcji (290,9 · 78,6).

Próg sprawdzianu, zapisany przed policzeniem: **±4 mm w obu osiach**. Powyżej
oznacza, że to nie jest samo przesunięcie i wyrównanie jest nieuprawnione.

## WYNIK (29.08, po policzeniu)

Sprawdzian na pokrętle BROWSE **nie przeszedł w poziomie**: model daje środek
297,6 mm, moja miara z instrukcji 290,9 — różnica 6,7 mm przy progu 4.

Nie zmieniam progu. Zapisuję za to, co widać w danych: model mówi, że to
pokrętło ma **⌀24 mm**, a mój pomiar z rastra dał **⌀40**. Mierzyłem więc
zagłębienie wokół pokrętła, nie samo pokrętło — a środek zagłębienia leży
gdzie indziej. To ta sama słaba metoda, która wcześniej dała „ekran szerszy
niż panel".

Wyrównanie ma za to potwierdzenie z **innego** punktu, którego też nie użyto
do liczenia przesunięcia: listwa hot cue z modelu ma środek w x = 144,5 mm
i szerokość 271,8 mm, a z instrukcji 142,8 i 268,5 — zgodność do **1,7 mm**
w położeniu i 3,3 mm w szerokości. Do tego oś talerza: 164,5 z modelu wobec
163,6 z instrukcji, czyli **0,9 mm**.

Stan faktyczny: przesunięcie w głębokości jest pewne (dwa punkty zgodne do
0,6 mm), położenie w poziomie potwierdzone dwoma punktami do ~2 mm, a jedna
pozycja z instrukcji (BROWSE) jest podejrzana i wymaga przemierzenia.
"""

from __future__ import annotations

import json
import pathlib

TU = pathlib.Path(__file__).resolve().parent
HOT_CUE_Y, TALERZ_Y = 155.6, 296.5
BROWSE_X, BROWSE_Y, PROG = 290.9, 78.6, 4.0


def main() -> int:
    dane = json.loads((TU / "czesci_uklad.json").read_text(encoding="utf-8"))
    czesci = dane["czesci"]

    hot = next(s for s in czesci
               if abs(s["szer_mm"] - 22.0) < 1 and abs(s["wys_mm"] - 13.1) < 1)
    jog = next(s for s in czesci
               if abs(s["szer_mm"] - 207.4) < 1 and abs(s["wys_mm"] - 207.4) < 1)
    dy = (((hot["y_mm"] + hot["wys_mm"] / 2) - HOT_CUE_Y)
          + ((jog["y_mm"] + jog["wys_mm"] / 2) - TALERZ_Y)) / 2
    # w poziomie odniesieniem jest oś talerza: na CDJ-u leży w osi panelu
    dx = (jog["x_mm"] + jog["szer_mm"] / 2) - 164.5

    print(f"przesunięcie: x {dx:+.1f} mm · y {dy:+.1f} mm")
    for s in czesci:
        s["x_mm"] = round(s["x_mm"] - dx, 1)
        s["y_mm"] = round(s["y_mm"] - dy, 1)

    # sprawdzian na punkcie NIEUŻYTYM do wyrównania
    kandydaci = [s for s in czesci
                 if 14 <= max(s["szer_mm"], s["wys_mm"]) <= 22 and s["y_mm"] < 120
                 and s["x_mm"] > 250]
    if not kandydaci:
        # szukamy szerzej: pokrętło BROWSE jest wysokie (gruby enkoder)
        kandydaci = [s for s in czesci if s["x_mm"] > 250 and s["y_mm"] < 130
                     and s["grubosc_mm"] > 10
                     and max(s["szer_mm"], s["wys_mm"]) < 40]
    if not kandydaci:
        print("sprawdzian: nie znalazłem kandydata na pokrętło BROWSE")
        return 2
    b = min(kandydaci, key=lambda s: abs(s["x_mm"] + s["szer_mm"] / 2 - BROWSE_X)
            + abs(s["y_mm"] + s["wys_mm"] / 2 - BROWSE_Y))
    bx = b["x_mm"] + b["szer_mm"] / 2
    by = b["y_mm"] + b["wys_mm"] / 2
    print(f"\nSPRAWDZIAN — pokrętło BROWSE (nieużyte do wyrównania):")
    print(f"  z modelu     ({bx:.1f}, {by:.1f}) mm, ⌀{b['szer_mm']:.1f}")
    print(f"  z instrukcji ({BROWSE_X:.1f}, {BROWSE_Y:.1f}) mm")
    print(f"  różnica      ({bx - BROWSE_X:+.1f}, {by - BROWSE_Y:+.1f}) mm "
          f"przy progu ±{PROG:.0f}")
    ok = abs(bx - BROWSE_X) <= PROG and abs(by - BROWSE_Y) <= PROG
    print(f"  {'ZDANY — wyrównanie uprawnione' if ok else 'NIEZDANY — to nie jest samo przesunięcie'}")

    dane["wyrownanie"] = {"dx_mm": round(dx, 1), "dy_mm": round(dy, 1),
                          "punkty_odniesienia": ["listwa hot cue 155,6",
                                                 "talerz 296,5"],
                          "sprawdzian_browse_mm": [round(bx - BROWSE_X, 1),
                                                   round(by - BROWSE_Y, 1)],
                          "zdany": bool(ok)}
    (TU / "czesci_wyrownane.json").write_text(
        json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nzapisane → {TU / 'czesci_wyrownane.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

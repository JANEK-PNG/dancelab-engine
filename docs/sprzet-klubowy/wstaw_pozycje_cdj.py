"""Zmierzone pozycje kontrolek CDJ-3000 → model panelu.

Źródła, zgodnie z tym, co rozstrzygnęły dzisiejsze sprawdziany:

* **pozycja** z modelu 3D (`experiments_priv/2026-08-29_model_3d/czesci_wyrownane.json`),
  bo raster instrukcji ma 1,2 px/mm i drobnych kontrolek z niego nie widać;
* **wymiar dużych elementów** z instrukcji, bo rozjemca talerza rozstrzygnął
  spór na jej korzyść (203,6 mm z rastra wobec 207,4 z modelu).

Przypisania są RĘCZNE i każde ma powód zapisany w tabeli niżej. Kontrolki,
których nie umiem wskazać z pewnością, zostają na pozycjach schematycznych
i dalej są tak oznaczone — model, który nie mówi, czego nie wie, jest gorszy
od modelu, który wie mniej.
"""

from __future__ import annotations

import json
import pathlib

TU = pathlib.Path(__file__).parent
CZESCI = TU.parents[1] / "experiments_priv/2026-08-29_model_3d/czesci_wyrownane.json"

# nazwa kontrolki → (numer części w modelu, powód przypisania)
Z_MODELU = {
    "Jog ⌀202 mm z regulacją oporu": (48, "jedyna część 207 × 207 mm; środek "
                                          "(164,5 · 296,8) zgadza się z instrukcją "
                                          "(163,6 · 296,5) do 1 mm"),
    "PLAY / PAUSE": (69, "duże koło ⌀36 w lewym dolnym rogu, poniżej CUE"),
    "CUE": (64, "duże koło ⌀36 nad PLAY, ta sama oś x"),
    "Suwak TEMPO (100 mm)": (61, "jedyny element wysoki i wąski przy prawej "
                                 "krawędzi: 23,7 × 127,5 mm"),
    "Pokrętło ROTARY SELECTOR": (20, "gruby element (17,5 mm wysokości) w prawym "
                                     "górnym rogu — enkoder BROWSE"),
    "TAG LIST / playlisty na urządzeniu": (3, "trzeci z sześciu przycisków górnego "
                                              "rzędu; kolejność na sprzęcie: SOURCE, "
                                              "BROWSE, TAG LIST, PLAYLIST, SEARCH, MENU"),
    "Dwa gniazda USB + PRO DJ LINK": (8, "gniazdo w lewym górnym rogu, 21,5 × 18,8 mm"),
    "TEMPO RANGE (±6 / 10 / 16 / WIDE)": (57, "mały przycisk nad MASTER TEMPO, "
                                              "przy suwaku"),
    "MASTER TEMPO": (58, "mały przycisk pod TEMPO RANGE"),
    "BEAT SYNC": (49, "blok 35,8 × 33,4 mm przy prawej krawędzi, na wysokości jogu"),
    "KEY SYNC / KEY RESET": (42, "listwa 35,8 × 13,1 mm nad blokiem BEAT SYNC"),
    "QUANTIZE": (27, "lewa para przycisków pod ekranem — przypisanie PRAWDOPODOBNE"),
    "SLIP": (28, "druga z tej pary — przypisanie PRAWDOPODOBNE"),
}
# osiem padów to osobny przypadek: listwa liczona z ośmiu części naraz
PADY = list(range(31, 39))
# wymiary z instrukcji mają pierwszeństwo dla tych elementów
Z_INSTRUKCJI = {
    'Ekran dotykowy 9"': dict(x=63.25, y=27.2, w=199.5, h=108.8,
                              powod="rzut płaski s.14 + dane techniczne s.83"),
}


def main() -> int:
    czesci = {c["nr"]: c for c in json.loads(CZESCI.read_text(encoding="utf-8"))["czesci"]}
    plik = TU / "uklad.json"
    u = json.loads(plik.read_text(encoding="utf-8"))

    pady = [czesci[n] for n in PADY]
    listwa = dict(
        x=min(p["x_mm"] for p in pady),
        y=min(p["y_mm"] for p in pady),
        w=max(p["x_mm"] + p["szer_mm"] for p in pady) - min(p["x_mm"] for p in pady),
        h=max(p["wys_mm"] for p in pady))
    print(f"listwa hot cue z ośmiu części: {listwa['w']:.1f} × {listwa['h']:.1f} mm "
          f"@ ({listwa['x']:.1f}, {listwa['y']:.1f}), środek x "
          f"{listwa['x'] + listwa['w'] / 2:.1f} (oś panelu: 164,5)")

    ile_m = ile_i = 0
    for d in u["urzadzenia"]:
        if not d["nazwa"].startswith("CDJ"):
            continue
        for e in d.get("elementy") or []:
            k = e["k"]
            if k in Z_INSTRUKCJI:
                w = Z_INSTRUKCJI[k]
                e.update(ksztalt="prostokat", x=w["x"], y=w["y"], w=w["w"], h=w["h"],
                         zmierzone=True, zrodlo=f"instrukcja — {w['powod']}")
                ile_i += 1
            elif k == "HOT CUE A–H (osiem)":
                e.update(ksztalt="prostokat", x=listwa["x"], y=listwa["y"],
                         w=listwa["w"], h=listwa["h"], zmierzone=True,
                         zrodlo="model 3D — obwiednia ośmiu osobnych padów")
                ile_m += 1
            elif k in Z_MODELU:
                nr, powod = Z_MODELU[k]
                c = czesci[nr]
                okragly = abs(c["szer_mm"] - c["wys_mm"]) / max(c["szer_mm"], c["wys_mm"]) < 0.12
                if okragly and e.get("ksztalt") == "kolo":
                    e.update(x=round(c["x_mm"] + c["szer_mm"] / 2, 1),
                             y=round(c["y_mm"] + c["wys_mm"] / 2, 1),
                             r=round(c["szer_mm"] / 2, 1))
                    e.pop("w", None), e.pop("h", None)
                else:
                    e.update(ksztalt="prostokat", x=c["x_mm"], y=c["y_mm"],
                             w=c["szer_mm"], h=c["wys_mm"])
                    e.pop("r", None)
                e.update(zmierzone=True, zrodlo=f"model 3D, część {nr} — {powod}")
                ile_m += 1

    plik.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")
    zostalo = [e["k"] for d in u["urzadzenia"] if d["nazwa"].startswith("CDJ")
               for e in (d.get("elementy") or []) if not e.get("zmierzone")]
    print(f"\nz modelu: {ile_m} · z instrukcji: {ile_i}")
    print(f"nadal schematyczne ({len(zostalo)}): {', '.join(zostalo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

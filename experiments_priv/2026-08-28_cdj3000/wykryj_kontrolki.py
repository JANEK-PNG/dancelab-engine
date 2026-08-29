"""Wykrywanie kontrolek z płaskiego rzutu panelu — pierwsze podejście.

Metoda (docs/metoda-ui-konsoli.md) mówi: geometria WYŁĄCZNIE z rzutu płaskiego
z instrukcji, nigdy z ujęcia pod kątem. Rzut mamy (strona 14 instrukcji
CDJ-3000), skalę też (9,888 px/mm przy 1000 dpi, szerokość 329 mm ze
specyfikacji ze strony 83).

Ten skrypt NIE rysuje konsoli. Wypisuje kandydatów na kontrolki: każdy kształt
zamknięty w rzucie, z pozycją i wielkością w milimetrach. To jest materiał do
sprawdzenia okiem, nie gotowy układ — dlatego wynik idzie do JSON-a i na obraz
kontrolny z zaznaczeniami, a nie prosto do modelu.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

TU = pathlib.Path(__file__).parent
POMIAR = TU / "pomiar"
PROG_ATRAMENTU = 170          # ciemniej niż to = kreska rysunku
MIN_MM, MAX_MM = 2.5, 145.0   # od najmniejszego przycisku do talerza jog


def main() -> int:
    skala = json.loads((POMIAR / "cdj3000_instrukcja_s14_skala.json").read_text())
    px_mm = skala["px_na_mm"]
    p = skala["panel_px"]

    import pymupdf
    d = pymupdf.open(TU / "cdj3000_instrukcja.pdf")
    pix = d[skala["strona"] - 1].get_pixmap(dpi=skala["dpi"])
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    im = im.crop((p["lewa"], p["gora"], p["prawa"], p["dol"])).convert("L")

    # zmniejszenie do ~4 px/mm — kreski zostają, liczenie jest wykonalne
    cel = 4.0
    skala_zmn = cel / px_mm
    maly = im.resize((int(im.width * skala_zmn), int(im.height * skala_zmn)),
                     Image.LANCZOS)
    a = np.asarray(maly)
    atrament = a < PROG_ATRAMENTU

    # zamknięte kształty: dziury w atramencie = wnętrza przycisków i gałek
    wypelnione = ndimage.binary_fill_holes(atrament)
    wnetrza = wypelnione & ~atrament
    etykiety, ile = ndimage.label(wnetrza)
    print(f"obszar panelu: {maly.width}×{maly.height} px przy {cel} px/mm")
    print(f"zamkniętych kształtów znalezionych: {ile}")

    kontrolki = []
    for i, wycinek in enumerate(ndimage.find_objects(etykiety), 1):
        if wycinek is None:
            continue
        ys, xs = wycinek
        h_mm = (ys.stop - ys.start) / cel
        w_mm = (xs.stop - xs.start) / cel
        if not (MIN_MM <= max(w_mm, h_mm) <= MAX_MM):
            continue
        maska = etykiety[wycinek] == i
        pole_mm2 = maska.sum() / (cel * cel)
        wypelnienie = pole_mm2 / (w_mm * h_mm)
        if wypelnienie < 0.45:                 # obwódki liter, pozostałości linii
            continue
        cy, cx = ndimage.center_of_mass(maska)
        x_mm = (xs.start + cx) / cel
        y_mm = (ys.start + cy) / cel
        okragly = abs(w_mm - h_mm) / max(w_mm, h_mm) < 0.18 and wypelnienie > 0.7
        kontrolki.append({
            "x_mm": round(x_mm, 1), "y_mm": round(y_mm, 1),
            "szer_mm": round(w_mm, 1), "wys_mm": round(h_mm, 1),
            "ksztalt": "okrag" if okragly else "prostokat",
            "wypelnienie": round(wypelnienie, 2),
        })

    kontrolki.sort(key=lambda k: (k["y_mm"], k["x_mm"]))
    print(f"kandydatów po odsianiu: {len(kontrolki)}")
    duze = [k for k in kontrolki if max(k["szer_mm"], k["wys_mm"]) > 25]
    print(f"  w tym duże (>25 mm): {len(duze)} — "
          f"{[f'{k[chr(34)+chr(34)] if False else k}' for k in []] or ''}")
    for k in duze[:8]:
        print(f"    {k['ksztalt']:<9} {k['szer_mm']:>5.1f}×{k['wys_mm']:<5.1f} mm "
              f"@ ({k['x_mm']:.0f}, {k['y_mm']:.0f})")

    (TU / "kontrolki_wykryte.json").write_text(
        json.dumps({"zrodlo": "instrukcja CDJ-3000 s.14, rzut płaski",
                    "panel_mm": {"szerokosc": 329.0, "glebokosc": 453.0},
                    "px_na_mm_oryginal": px_mm,
                    "kontrolki": kontrolki}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # obraz kontrolny — bez niego to są tylko liczby
    podglad = maly.convert("RGB")
    rys = ImageDraw.Draw(podglad)
    for k in kontrolki:
        x, y = k["x_mm"] * cel, k["y_mm"] * cel
        w, h = k["szer_mm"] * cel / 2, k["wys_mm"] * cel / 2
        kolor = (200, 40, 40) if k["ksztalt"] == "okrag" else (40, 90, 200)
        rys.rectangle([x - w, y - h, x + w, y + h], outline=kolor, width=2)
    podglad.save(POMIAR / "wykryte.png")
    print(f"\nobraz kontrolny → {POMIAR / 'wykryte.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

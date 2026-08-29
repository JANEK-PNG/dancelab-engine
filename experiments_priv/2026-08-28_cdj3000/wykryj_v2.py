"""Szkielet mechaniczny CDJ-3000: punkty odniesienia z rzutu płaskiego.

Metoda mówi wprost: najpierw szkielet, dopiero potem wygląd. Ten skrypt szuka
NIE wszystkich pięćdziesięciu kontrolek naraz, tylko tych, które trzymają
proporcje całości — talerz, ekran, suwak tempa, PLAY, CUE, rząd hot cue.
Reszta dokłada się później, względem nich.

Koła znajduje transformata odległości: dla każdego piksela wnętrza liczy
odległość do najbliższej kreski, a jej lokalne maksima leżą w środkach kół
i mają promień równy tej odległości. To łapie duże tarcze, które wypełnianie
dziur gubiło.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

TU = pathlib.Path(__file__).parent
POMIAR = TU / "pomiar"
PROG = 170
CEL = 4.0            # px na mm w obrazie roboczym


def obraz_panelu(skala: dict) -> Image.Image:
    import pymupdf
    d = pymupdf.open(TU / "cdj3000_instrukcja.pdf")
    pix = d[skala["strona"] - 1].get_pixmap(dpi=skala["dpi"])
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    p = skala["panel_px"]
    im = im.crop((p["lewa"], p["gora"], p["prawa"], p["dol"])).convert("L")
    z = CEL / skala["px_na_mm"]
    return im.resize((int(im.width * z), int(im.height * z)), Image.LANCZOS)


def kola(atrament: np.ndarray, min_r_mm: float, max_r_mm: float) -> list[dict]:
    """Środki kół z transformaty odległości + tłumienie sąsiadów."""
    odl = ndimage.distance_transform_edt(~atrament)
    szczyty = (odl == ndimage.maximum_filter(odl, size=int(2.5 * CEL))) & \
              (odl >= min_r_mm * CEL)
    ys, xs = np.nonzero(szczyty)
    kandydaci = sorted(((float(odl[y, x]), int(x), int(y)) for y, x in zip(ys, xs)),
                       reverse=True)
    wynik: list[dict] = []
    for r_px, x, y in kandydaci:
        r_mm = r_px / CEL
        if r_mm > max_r_mm:
            continue
        if any((x - k["_x"]) ** 2 + (y - k["_y"]) ** 2 < (k["_r"] * 0.8) ** 2
               for k in wynik):
            continue
        wynik.append({"_x": x, "_y": y, "_r": r_px,
                      "x_mm": round(x / CEL, 1), "y_mm": round(y / CEL, 1),
                      "srednica_mm": round(2 * r_mm, 1)})
    return wynik


def main() -> int:
    skala = json.loads((POMIAR / "cdj3000_instrukcja_s14_skala.json").read_text())
    im = obraz_panelu(skala)
    a = np.asarray(im)
    atrament = a < PROG
    print(f"panel {im.width / CEL:.0f}×{im.height / CEL:.0f} mm w {CEL} px/mm")

    okragle = kola(atrament, min_r_mm=2.0, max_r_mm=110.0)
    print(f"\nKOŁA (średnica ≥ 4 mm): {len(okragle)}")
    for k in sorted(okragle, key=lambda k: -k["srednica_mm"])[:12]:
        print(f"  ⌀{k['srednica_mm']:>6.1f} mm  @ ({k['x_mm']:>5.1f}, {k['y_mm']:>5.1f})")

    # prostokąty: wypełnianie dziur, ale bez progu wypełnienia — ekran i suwak
    # mają w środku rysunek, więc „gęstość" nie jest tu żadnym kryterium
    wypelnione = ndimage.binary_fill_holes(atrament)
    etykiety, ile = ndimage.label(wypelnione & ~atrament)
    prostokaty = []
    for i, w in enumerate(ndimage.find_objects(etykiety), 1):
        ys, xs = w
        h_mm, w_mm = (ys.stop - ys.start) / CEL, (xs.stop - xs.start) / CEL
        if max(w_mm, h_mm) < 15:
            continue
        prostokaty.append({"x_mm": round((xs.start + xs.stop) / 2 / CEL, 1),
                           "y_mm": round((ys.start + ys.stop) / 2 / CEL, 1),
                           "szer_mm": round(w_mm, 1), "wys_mm": round(h_mm, 1)})
    prostokaty.sort(key=lambda k: -(k["szer_mm"] * k["wys_mm"]))
    print(f"\nPROSTOKĄTY (bok ≥ 15 mm): {len(prostokaty)}")
    for k in prostokaty[:10]:
        print(f"  {k['szer_mm']:>6.1f} × {k['wys_mm']:<6.1f} mm  @ "
              f"({k['x_mm']:>5.1f}, {k['y_mm']:>5.1f})")

    podglad = im.convert("RGB")
    rys = ImageDraw.Draw(podglad)
    for k in okragle:
        x, y, r = k["_x"], k["_y"], k["_r"]
        rys.ellipse([x - r, y - r, x + r, y + r], outline=(210, 40, 40), width=2)
    for k in prostokaty:
        x, y = k["x_mm"] * CEL, k["y_mm"] * CEL
        w, h = k["szer_mm"] * CEL / 2, k["wys_mm"] * CEL / 2
        rys.rectangle([x - w, y - h, x + w, y + h], outline=(30, 90, 210), width=2)
    podglad.save(POMIAR / "wykryte_v2.png")

    (TU / "szkielet_wykryty.json").write_text(json.dumps(
        {"zrodlo": "instrukcja CDJ-3000 s.14 (rzut płaski), skala z s.83",
         "panel_mm": {"szerokosc": 329.0, "glebokosc": 453.0},
         "kola": [{k: v for k, v in k_.items() if not k.startswith("_")}
                  for k_ in okragle],
         "prostokaty": prostokaty}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nobraz kontrolny → {POMIAR / 'wykryte_v2.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

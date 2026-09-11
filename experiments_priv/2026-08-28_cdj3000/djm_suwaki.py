"""DJM-900NXS2: knobs, faders and crossfader from the vector PATHS of manual p.7.

    python3 experiments_priv/2026-08-28_cdj3000/djm_suwaki.py   (needs pymupdf)

`djm_z_wektorow.py` (29.08) took only rectangles, so every control drawn with
curves or polygons — all knobs, the channel faders, the crossfader — never
made it into the layout. Same page, same panel outline, same scale
(332 mm / outline width; checked then by the 0.803 vs 0.801 aspect test), so
the numbers here line up with the ones already in `uklad.json`.

Prints per channel column (x within 15 mm of the measured channel x) the
round shapes top to bottom with diameters, the tall narrow shapes (faders),
and the long flat ones near the bottom (crossfader); writes everything to
djm900_sciezki.json beside this script.
"""

from __future__ import annotations

import json
import pathlib

TU = pathlib.Path(__file__).parent
SZEROKOSC_MM = 332.0
KANALY_X = [82.0, 124.6, 167.4, 210.2]        # zmierzone 29.08 (uklad.json: kanaly_x)


def main() -> int:
    import pymupdf

    p = pymupdf.open(TU / "djm900nxs2_instrukcja.pdf")[6]
    rys = p.get_drawings()
    obrys = max(rys, key=lambda r: r["rect"].width * r["rect"].height)["rect"]
    x0, y0 = obrys.x0, obrys.y0
    skala = SZEROKOSC_MM / (obrys.x1 - obrys.x0)

    def mm(v: float, o: float) -> float:
        return round((v - o) * skala, 1)

    ksztalty = []
    for r in rys:
        rect = r["rect"]
        if rect.width * rect.height >= obrys.width * obrys.height * 0.5:
            continue                                       # the outline itself
        if rect.x0 < x0 - 1 or rect.x1 > obrys.x1 + 1 or rect.y0 < y0 - 1 or rect.y1 > obrys.y1 + 1:
            continue                                       # callouts outside the panel
        w, h = rect.width * skala, rect.height * skala
        if max(w, h) < 3:
            continue
        rodzaje = sorted({it[0] for it in r["items"]})
        ksztalty.append({
            "x": mm(rect.x0, x0), "y": mm(rect.y0, y0), "w": round(w, 1), "h": round(h, 1),
            "cx": mm((rect.x0 + rect.x1) / 2, x0), "cy": mm((rect.y0 + rect.y1) / 2, y0),
            "krzywe": "c" in rodzaje, "elementow": len(r["items"]),
            "wypelnione": r.get("fill") is not None,
        })
    kola = [k for k in ksztalty if k["krzywe"] and 0.85 <= k["w"] / max(k["h"], 0.1) <= 1.18 and 5 <= k["w"] <= 30]
    wysokie = [k for k in ksztalty if k["h"] >= 40 and k["w"] <= 25]
    plaskie = [k for k in ksztalty if k["w"] >= 30 and k["h"] <= 25 and k["cy"] > 330]
    print(f"skala {skala:.4f} mm/pt · kształtów {len(ksztalty)} · kół {len(kola)} · "
          f"wysokich {len(wysokie)} · płaskich u dołu {len(plaskie)}")

    for i, kx in enumerate(KANALY_X, 1):
        kol = sorted((k for k in kola if abs(k["cx"] - kx) <= 15), key=lambda k: k["cy"])
        # merge concentric rings of one knob: keep the largest per 3 mm of height
        gałki = []
        for k in kol:
            if gałki and abs(gałki[-1]["cy"] - k["cy"]) < 3 and abs(gałki[-1]["cx"] - k["cx"]) < 3:
                if k["w"] > gałki[-1]["w"]:
                    gałki[-1] = k
                continue
            gałki.append(k)
        print(f"\nkanał {i} (x={kx}): {len(gałki)} okrągłych")
        for g in gałki:
            print(f"   ⌀{g['w']:5.1f}  środek ({g['cx']:6.1f}, {g['cy']:6.1f})")
        for k in sorted((k for k in wysokie if abs(k["cx"] - kx) <= 15), key=lambda k: k["cy"]):
            print(f"   WYSOKI {k['w']:5.1f} × {k['h']:5.1f}  od ({k['x']:6.1f}, {k['y']:6.1f})  krzywe={k['krzywe']}")
    print("\npłaskie u dołu (crossfader i przełączniki):")
    for k in sorted(plaskie, key=lambda k: (k["cy"], k["cx"])):
        print(f"   {k['w']:5.1f} × {k['h']:5.1f}  od ({k['x']:6.1f}, {k['y']:6.1f})  środek ({k['cx']}, {k['cy']})")
    print("\nokrągłe poza kolumnami kanałów (x < 60 albo x > 235):")
    poza = sorted((k for k in kola if k["cx"] < 60 or k["cx"] > 235), key=lambda k: (round(k["cx"] / 20), k["cy"]))
    for k in poza:
        print(f"   ⌀{k['w']:5.1f}  środek ({k['cx']:6.1f}, {k['cy']:6.1f})")

    (TU / "djm900_sciezki.json").write_text(json.dumps({
        "zrodlo": "instrukcja DJM-900NXS2, s.7, ścieżki wektorowe (get_drawings)",
        "skala_mm_na_pt": round(skala, 5), "kola": kola, "wysokie": wysokie,
        "plaskie_u_dolu": plaskie}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

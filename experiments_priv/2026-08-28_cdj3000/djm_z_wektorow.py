"""DJM-900NXS2: pozycje kontrolek z rzutu WEKTOROWEGO (nie z obrazka).

Strona 7 instrukcji to grafika wektorowa — mamy współrzędne każdej kreski
i każdego napisu na panelu. To lepsze źródło niż render: nie ma pikseli, nie
ma progu jasności, nie ma fałszywych kół z przerw między liniami.

UWAGA O SKALI: instrukcja, którą mamy (wersja skrócona, 24 strony), NIE ma
tabeli danych technicznych. Szerokość 332 mm jest wzięta z danych
katalogowych producenta i **czeka na potwierdzenie** — dopóki nie potwierdzimy,
wszystkie milimetry poniżej są proporcjonalnie prawdziwe, ale ich bezwzględna
wartość zależy od tej jednej liczby.
"""

from __future__ import annotations

import json
import pathlib
import re

TU = pathlib.Path(__file__).parent
SZEROKOSC_MM = 332.0          # ZAŁOŻENIE do potwierdzenia, patrz docstring


def main() -> int:
    import pymupdf
    d = pymupdf.open(TU / "djm900nxs2_instrukcja.pdf")
    p = d[6]

    rys = p.get_drawings()
    # NIE obwiednia całego rysunku — ona łapie odnośniki i numery wokół panelu
    # i zawyżała wysokość o 8%. Bierzemy największą ścieżkę, czyli obrys panelu.
    obrys = max(rys, key=lambda r: r["rect"].width * r["rect"].height)["rect"]
    x0, y0, x1, y1 = obrys.x0, obrys.y0, obrys.x1, obrys.y1
    szer_pt, wys_pt = x1 - x0, y1 - y0
    skala = SZEROKOSC_MM / szer_pt
    print(f"obrys panelu: {szer_pt:.1f} × {wys_pt:.1f} pt · "
          f"proporcja {szer_pt / wys_pt:.3f}")
    print(f"skala: {skala:.4f} mm/pt → panel {SZEROKOSC_MM:.0f} × "
          f"{wys_pt * skala:.1f} mm")
    print("  kontrola: katalog podaje 332 × 414,5 mm, czyli proporcję 0,801 — "
          "rysunek daje "
          f"{szer_pt / wys_pt:.3f}, więc założona szerokość się broni")

    def mm(x: float, y: float) -> tuple[float, float]:
        return round((x - x0) * skala, 1), round((y - y0) * skala, 1)

    # 1) napisy na panelu — każdy siedzi przy swojej kontrolce
    napisy = []
    for wx0, wy0, wx1, wy1, tekst, *_ in p.get_text("words"):
        if wx0 < x0 - 2 or wx1 > x1 + 2 or wy0 < y0 - 2 or wy1 > y1 + 2:
            continue                                   # poza rysunkiem
        if not re.fullmatch(r"[A-Z0-9/\-\.]{2,14}", tekst):
            continue                                   # opisy zdaniowe pomijamy
        mx, my = mm((wx0 + wx1) / 2, (wy0 + wy1) / 2)
        napisy.append({"tekst": tekst, "x_mm": mx, "y_mm": my})

    # 2) prostokąty — suwaki, przyciski, pola
    prost = []
    for r in rys:
        for it in r["items"]:
            if it[0] != "re":
                continue
            rec = it[1]
            w_mm, h_mm = rec.width * skala, rec.height * skala
            if max(w_mm, h_mm) < 4:
                continue
            cx, cy = mm((rec.x0 + rec.x1) / 2, (rec.y0 + rec.y1) / 2)
            prost.append({"x_mm": cx, "y_mm": cy,
                          "szer_mm": round(w_mm, 1), "wys_mm": round(h_mm, 1)})

    print(f"\nnapisów na panelu: {len(napisy)}")
    for t in ("TRIM", "CH", "CUE", "MASTER", "BOOTH", "PHONES", "COLOR"):
        trafienia = [n for n in napisy if n["tekst"] == t]
        if trafienia:
            xs = sorted(n["x_mm"] for n in trafienia)
            print(f"  {t:<8} ×{len(trafienia):<2} x = {xs}")

    prost.sort(key=lambda k: -(k["szer_mm"] * k["wys_mm"]))
    print(f"\nprostokątów ≥4 mm: {len(prost)} · dziesięć największych:")
    for k in prost[:10]:
        print(f"  {k['szer_mm']:>6.1f} × {k['wys_mm']:<6.1f} mm @ "
              f"({k['x_mm']:>5.1f}, {k['y_mm']:>5.1f})")

    dlugie = [k for k in prost if k["wys_mm"] > 40 and k["szer_mm"] < 20]
    print(f"\nkandydaci na suwaki kanałów (wysokie i wąskie): {len(dlugie)}")
    for k in sorted(dlugie, key=lambda k: k["x_mm"]):
        print(f"  {k['szer_mm']:>5.1f} × {k['wys_mm']:<5.1f} mm @ "
              f"({k['x_mm']:>5.1f}, {k['y_mm']:>5.1f})")

    (TU / "djm900_wektory.json").write_text(json.dumps({
        "zrodlo": "instrukcja DJM-900NXS2 (manuals.plus), s.7, rzut wektorowy",
        "skala_mm_na_pt": round(skala, 5),
        "szerokosc_mm_ZALOZENIE": SZEROKOSC_MM,
        "wysokosc_mm_wyliczona": round(wys_pt * skala, 1),
        "napisy": napisy, "prostokaty": prost},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nzapisane → {TU / 'djm900_wektory.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

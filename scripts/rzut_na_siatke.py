"""Przyrząd pomiarowy: płaski rzut z instrukcji → siatka milimetrowa.

Odtworzenie narzędzia, które powstało 24.08.2026 przy modelu DDJ-FLX4 i nie
zostało zapisane ("siatka co 10 mm naniesiona programowo (skrypt w sesji)").
Tabela wymiarów przetrwała w notatkach, przyrząd nie — przy następnej konsoli
trzeba go było budować od zera. Ten plik kończy ten cykl.

Do czego służy. Żeby narysować konsolę w skali, trzeba znać pozycję każdej
kontrolki w milimetrach. Instrukcja obsługi zawiera płaski rzut panelu z
podanymi wymiarami zewnętrznymi. Skrypt renderuje tę stronę w wysokim DPI,
znajduje krawędzie panelu, przelicza skalę px/mm i nakłada siatkę, z której
odczytuje się współrzędne.

UWAGA METODYCZNA, najdroższa lekcja z FLX4: rysunek w liście komunikatów MIDI
to ujęcie POD KĄTEM. Mierzenie z niego przekłamuje (jog wyszedł 104 mm zamiast
140). Nadaje się wyłącznie PŁASKI rzut z instrukcji obsługi.

Użycie — dwa kroki, bo obszar rysunku trzeba najpierw zobaczyć:

    # 1. podgląd z siatką ułamkową, żeby odczytać, gdzie leży sam rzut
    uv run python scripts/rzut_na_siatke.py INSTRUKCJA.pdf --strona 11 \
        --szerokosc-mm 482 --podglad --wyjscie KATALOG

    # 2. pomiar z zawężonym obszarem
    uv run python scripts/rzut_na_siatke.py INSTRUKCJA.pdf --strona 11 \
        --szerokosc-mm 482 --wycinek 0.10,0.162,0.90,0.468 --wyjscie KATALOG

Sprawdzone 28.08.2026 na instrukcji DDJ-FLX4 (strona 11, panel 482 × 272,4 mm
wg danych technicznych): powyższy wycinek dał skalę 4,432 px/mm przy 400 dpi i
wysokość 279,4 mm, czyli 2,6% ponad specyfikację — obwiednia liczy wraz z
grubością linii rysunku. Skala jest liczona z SZEROKOŚCI, którą podaje się
ręcznie, więc ten naddatek nie wchodzi do wyniku; wysokość służy wyłącznie jako
kontrola, czy obszar nie złapał czegoś spoza rzutu. Bez --wycinek ta sama
strona dawała 726 mm, bo obwiednia obejmowała nagłówek i opisy sekcji.

Wymaga: uv pip install -e ".[narzedzia]"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Renders at this DPI. 1000 was used for the FLX4 measurement and resolved
# individual printed captions; below ~600 the knob outlines start to blur.
DOMYSLNE_DPI = 1000

# A pixel darker than this counts as ink when locating the panel outline.
PROG_TUSZU = 200


def _pypdfium2():
    try:
        import pypdfium2
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Brak pypdfium2 — bez niego nie wyrenderuję strony PDF.\n"
            'Instalacja:  uv pip install -e ".[narzedzia]"\n'
            "(sprawdzone 28.08.2026: w tym środowisku nie ma też fitz ani "
            "pdftoppm; qlmanage renderuje tylko miniatury i nie nadaje się "
            "do pomiaru)"
        ) from exc
    return pypdfium2


def renderuj(pdf: Path, strona: int, dpi: int):
    """Zwraca stronę PDF jako obraz PIL w podanej rozdzielczości."""
    pdfium = _pypdfium2()
    dokument = pdfium.PdfDocument(str(pdf))
    if not 1 <= strona <= len(dokument):
        raise SystemExit(
            f"PDF ma {len(dokument)} stron, poproszono o {strona}"
        )
    return dokument[strona - 1].render(scale=dpi / 72).to_pil().convert("L")


def znajdz_panel(obraz, prog: int = PROG_TUSZU,
                 wycinek: tuple[float, float, float, float] | None = None
                 ) -> tuple[int, int, int, int]:
    """Prostokąt otaczający rysunek panelu (lewa, góra, prawa, dół).

    Obwiednia całego tuszu wystarcza tylko wtedy, gdy rzut jest jedyną rzeczą na
    stronie. Sprawdzone na instrukcji FLX4: strona 11 zawiera też nagłówek i
    opisy, więc obwiednia dała panel wysoki na 726 mm zamiast 273. Dlatego
    obszar zawęża się parametrem --wycinek podawanym w ułamkach strony, a
    wyliczona wysokość jest zawsze drukowana do porównania z instrukcją.
    """
    import numpy as np

    tab = np.asarray(obraz)
    if wycinek:
        x0 = int(wycinek[0] * tab.shape[1])
        y0 = int(wycinek[1] * tab.shape[0])
        x1 = int(wycinek[2] * tab.shape[1])
        y1 = int(wycinek[3] * tab.shape[0])
        tab = tab[y0:y1, x0:x1]
    else:
        x0 = y0 = 0

    tusz = tab < prog
    kolumny = np.flatnonzero(tusz.any(axis=0))
    wiersze = np.flatnonzero(tusz.any(axis=1))
    if not kolumny.size or not wiersze.size:
        raise SystemExit("nie znalazłem tuszu w podanym obszarze")
    return (x0 + int(kolumny[0]), y0 + int(wiersze[0]),
            x0 + int(kolumny[-1]), y0 + int(wiersze[-1]))


def nanies_siatke(obraz, panel, px_na_mm: float, co_mm: int = 10):
    """Rysuje siatkę milimetrową z podpisami, licząc od lewego górnego rogu panelu."""
    from PIL import ImageDraw

    kolor = obraz.convert("RGB")
    rysuj = ImageDraw.Draw(kolor)
    lewa, gora, prawa, dol = panel

    rysuj.rectangle([lewa, gora, prawa, dol], outline=(255, 0, 0), width=3)

    mm = 0
    while lewa + mm * px_na_mm <= prawa:
        x = lewa + mm * px_na_mm
        gruba = mm % (co_mm * 5) == 0
        rysuj.line([(x, gora), (x, dol)],
                   fill=(255, 0, 0) if gruba else (0, 160, 255),
                   width=2 if gruba else 1)
        if gruba:
            rysuj.text((x + 4, gora + 4), f"{mm}", fill=(255, 0, 0))
        mm += co_mm

    mm = 0
    while gora + mm * px_na_mm <= dol:
        y = gora + mm * px_na_mm
        gruba = mm % (co_mm * 5) == 0
        rysuj.line([(lewa, y), (prawa, y)],
                   fill=(255, 0, 0) if gruba else (0, 160, 255),
                   width=2 if gruba else 1)
        if gruba:
            rysuj.text((lewa + 4, y + 4), f"{mm}", fill=(255, 0, 0))
        mm += co_mm

    return kolor


def podglad_ulamkowy(obraz):
    """Strona z siatką co 0,1 szerokości/wysokości — do dobrania --wycinek."""
    from PIL import ImageDraw

    kolor = obraz.convert("RGB")
    rysuj = ImageDraw.Draw(kolor)
    for i in range(1, 10):
        x = kolor.width * i / 10
        y = kolor.height * i / 10
        rysuj.line([(x, 0), (x, kolor.height)], fill=(255, 0, 0), width=2)
        rysuj.line([(0, y), (kolor.width, y)], fill=(255, 0, 0), width=2)
        rysuj.text((x + 5, 5), f"{i / 10:.1f}", fill=(255, 0, 0))
        rysuj.text((5, y + 5), f"{i / 10:.1f}", fill=(255, 0, 0))
    return kolor


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description="Płaski rzut z instrukcji → siatka mm")
    a.add_argument("pdf", type=Path)
    a.add_argument("--strona", type=int, required=True,
                   help="strona z PŁASKIM rzutem panelu (nie z ujęciem pod kątem)")
    a.add_argument("--szerokosc-mm", type=float, required=True,
                   help="szerokość panelu w mm z danych technicznych instrukcji")
    a.add_argument("--dpi", type=int, default=DOMYSLNE_DPI)
    a.add_argument("--co-mm", type=int, default=10, help="krok siatki")
    a.add_argument("--wycinek", type=str, default=None,
                   help="obszar rysunku jako ułamki strony: x0,y0,x1,y1 "
                        "(np. 0,0.15,1,0.6). Bez tego brana jest obwiednia "
                        "całego tuszu, co przy stronie z tekstem daje zły wynik")
    a.add_argument("--podglad", action="store_true",
                   help="zapisz stronę z siatką ułamkową, żeby dobrać --wycinek")
    a.add_argument("--wyjscie", type=Path, required=True)
    args = a.parse_args(argv)

    if not args.pdf.exists():
        raise SystemExit(f"nie ma pliku: {args.pdf}")

    print(f"renderuję stronę {args.strona} w {args.dpi} dpi…", flush=True)
    obraz = renderuj(args.pdf, args.strona, args.dpi)
    print(f"  obraz {obraz.width}×{obraz.height} px")

    args.wyjscie.mkdir(parents=True, exist_ok=True)
    if args.podglad:
        sciezka = args.wyjscie / f"{args.pdf.stem}_s{args.strona}_podglad.png"
        podglad_ulamkowy(obraz).save(sciezka)
        print(f"podgląd do dobrania --wycinek: {sciezka}")

    wycinek = None
    if args.wycinek:
        czesci = [float(x) for x in args.wycinek.split(",")]
        if len(czesci) != 4:
            raise SystemExit("--wycinek wymaga czterech liczb: x0,y0,x1,y1")
        wycinek = tuple(czesci)

    panel = znajdz_panel(obraz, wycinek=wycinek)
    szer_px = panel[2] - panel[0]
    px_na_mm = szer_px / args.szerokosc_mm
    wys_mm = (panel[3] - panel[1]) / px_na_mm

    trzon = args.pdf.stem
    plik_png = args.wyjscie / f"{trzon}_s{args.strona}_siatka.png"
    plik_json = args.wyjscie / f"{trzon}_s{args.strona}_skala.json"

    nanies_siatke(obraz, panel, px_na_mm, args.co_mm).save(plik_png)

    skala = {
        "pdf": str(args.pdf),
        "strona": args.strona,
        "dpi": args.dpi,
        "panel_px": {"lewa": panel[0], "gora": panel[1],
                     "prawa": panel[2], "dol": panel[3]},
        "szerokosc_mm": args.szerokosc_mm,
        "wysokosc_mm_wyliczona": round(wys_mm, 1),
        "px_na_mm": round(px_na_mm, 4),
        "krok_siatki_mm": args.co_mm,
        "wycinek": args.wycinek,
        "jak_czytac": (
            "Współrzędne odczytuj z siatki, licząc od lewego górnego rogu "
            "czerwonej ramki. Aby przeliczyć piksel obrazu na mm: "
            "(x_px - panel_px.lewa) / px_na_mm."
        ),
        "ostrzezenie": (
            "Ten pomiar jest wiarygodny TYLKO dla płaskiego rzutu. Rysunek w "
            "perspektywie da wymiary przekłamane — przy FLX4 kosztowało to "
            "rundę poprawek (jog 104 mm zamiast 140)."
        ),
    }
    plik_json.write_text(json.dumps(skala, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    print(f"\npanel: {szer_px} px szerokości = {args.szerokosc_mm} mm")
    print(f"skala: {px_na_mm:.3f} px/mm")
    print(f"wysokość panelu wyliczona: {wys_mm:.1f} mm  "
          "← porównaj z danymi technicznymi; duża rozbieżność "
          "oznacza, że obwiednia złapała coś poza rzutem")
    print(f"\n  {plik_png}\n  {plik_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

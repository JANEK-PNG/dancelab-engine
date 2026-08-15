"""Badanie pięciu DJ-ów — arkusz do druku.

Janek 2026-08-14, po uwadze, że silnik jest skalibrowany wyłącznie na jego
uchu: „dawaj to badanie jako PDF do druku".

Po co papier, skoro wszystko jest cyfrowe: bo to badanie robi się PRZY
CZŁOWIEKU, nie w formularzu. Kartka leży na stole, DJ mówi, Ty notujesz.
Formularz online zmienia rozmowę w ankietę, a ankieta daje uprzejmość
zamiast prawdy.

CO TO JEST, A CZYM NIE JEST. To nie jest ankieta satysfakcji. To jest test
ślepy: DJ ocenia przejścia, nie wiedząc, które wyszły z silnika, a które
z cudzego seta albo z losowania. Bez tej ślepoty ocenia markę, nie muzykę.

TRZY ŹRÓDŁA PRZEJŚĆ, po równo, wymieszane:
  * SILNIK   — propozycja DanceLab
  * CZŁOWIEK — realne przejście z korpusu (ktoś to zagrał na imprezie)
  * LOSOWE   — dwa utwory z tej samej biblioteki, zestawione przypadkiem

Losowe jest w tym najważniejsze. To jest odpowiednik naiwnej prognozy
z Forecast Value Added: jeśli silnik nie bije losowania, nie ma o czym
rozmawiać, a cała reszta metodologii jest ozdobą.
"""

from __future__ import annotations

import pathlib

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")

# Arial Unicode ma polskie znaki. Wbudowana Helvetica z reportlab NIE ma —
# „ł" i „ę" wyszłyby jako puste prostokąty na wydruku.
FONTY = [
    ("Tekst", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ("TekstB", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
for nazwa, sciezka in FONTY:
    if pathlib.Path(sciezka).exists():
        pdfmetrics.registerFont(TTFont(nazwa, sciezka))

TUSZ = colors.HexColor("#1B1A20")
SZARY = colors.HexColor("#6E6B78")
LINIA = colors.HexColor("#D8D5CE")
AKCENT = colors.HexColor("#0A6A64")

S = {
    "h1": ParagraphStyle("h1", fontName="TekstB", fontSize=17, leading=21,
                         textColor=TUSZ, spaceAfter=3),
    "pod": ParagraphStyle("pod", fontName="Tekst", fontSize=9.5, leading=13,
                          textColor=SZARY, spaceAfter=12),
    "h2": ParagraphStyle("h2", fontName="TekstB", fontSize=11, leading=14,
                         textColor=AKCENT, spaceBefore=13, spaceAfter=5),
    "p": ParagraphStyle("p", fontName="Tekst", fontSize=9.5, leading=13.5,
                        textColor=TUSZ, alignment=TA_LEFT, spaceAfter=6),
    "mala": ParagraphStyle("mala", fontName="Tekst", fontSize=8, leading=11,
                           textColor=SZARY),
    "pyt": ParagraphStyle("pyt", fontName="TekstB", fontSize=9.5, leading=13,
                          textColor=TUSZ, spaceBefore=7, spaceAfter=2),
}


def linie(ile: int, szer: float = 170 * mm) -> Table:
    """Puste linie do pisania ręką."""
    t = Table([[""] for _ in range(ile)], colWidths=[szer], rowHeights=[9 * mm] * ile)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINIA)]))
    return t


def skala(etykieta: str) -> Table:
    """Skala 1-7 do zakreślenia. Siedem, nie pięć: przy pięciu ludzie
    lądują na środku, przy siedmiu muszą się opowiedzieć."""
    wiersz = [etykieta] + [str(i) for i in range(1, 8)]
    t = Table([wiersz], colWidths=[62 * mm] + [13 * mm] * 7, rowHeights=[9 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, 0), "Tekst", 9),
        ("FONT", (1, 0), (-1, 0), "Tekst", 10),
        ("ALIGN", (1, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (1, 0), (-1, 0), 0.4, LINIA),
        ("INNERGRID", (1, 0), (-1, 0), 0.4, LINIA),
        ("TEXTCOLOR", (0, 0), (0, 0), TUSZ),
    ]))
    return t


def karta_przejscia(nr: int) -> KeepTogether:
    """Jedna karta oceny. Numer jest jedyną etykietą — DJ NIE WIE, skąd
    przejście pochodzi, i to jest cały sens tego badania."""
    el = [
        Paragraph(f"PRZEJŚCIE {nr:02d}", S["h2"]),
        Table([["utwór wychodzący", "", "utwór wchodzący", ""]],
              colWidths=[34 * mm, 51 * mm, 34 * mm, 51 * mm], rowHeights=[8 * mm],
              style=TableStyle([
                  ("FONT", (0, 0), (-1, -1), "Tekst", 8),
                  ("TEXTCOLOR", (0, 0), (-1, -1), SZARY),
                  ("LINEBELOW", (1, 0), (1, 0), 0.4, LINIA),
                  ("LINEBELOW", (3, 0), (3, 0), 0.4, LINIA),
                  ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
              ])),
        Spacer(1, 3 * mm),
        skala("Czy to przejście ma sens?"),
        skala("Czy zagrałbyś je u siebie?"),
        Spacer(1, 2 * mm),
        Paragraph("Dlaczego? Jedno zdanie — najważniejsza rubryka na tej stronie.",
                  S["mala"]),
        linie(2),
        Spacer(1, 6 * mm),
    ]
    return KeepTogether(el)


def buduj() -> None:
    plik = OUT / "badanie_pieciu_djow.pdf"
    doc = BaseDocTemplate(str(plik), pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=16 * mm,
                          title="DanceLab — badanie pięciu DJ-ów",
                          author="Jan Trybus")
    ramka = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="n")

    def stopka(canvas, dokument):
        canvas.saveState()
        canvas.setFont("Tekst", 7.5)
        canvas.setFillColor(SZARY)
        canvas.drawString(20 * mm, 10 * mm,
                          "DanceLab · badanie ślepe · wersja 1 · 2026-08-14")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"str. {dokument.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[ramka], onPage=stopka)])

    e = []
    e.append(Paragraph("Badanie pięciu DJ-ów", S["h1"]))
    e.append(Paragraph("DanceLab · arkusz oceny przejść · badanie ślepe", S["pod"]))

    e.append(Paragraph("Dla prowadzącego — przeczytaj przed rozmową", S["h2"]))
    e.append(Paragraph(
        "Silnik DanceLab jest dziś skalibrowany na <b>jednym uchu</b> — moim. "
        "Kształt setu zmierzyłem na swoich nagraniach, regułę wejścia na 28 "
        "swoich przejściach. To badanie ma odpowiedzieć na jedno pytanie: "
        "czy to, co silnik uważa za dobre przejście, uważa tak ktoś jeszcze.", S["p"]))
    e.append(Paragraph(
        "<b>DJ nie może wiedzieć, skąd pochodzi przejście.</b> W arkuszu są trzy "
        "źródła, wymieszane i ponumerowane: propozycja silnika, realne przejście "
        "zagrane przez innego DJ-a oraz para losowa z tej samej biblioteki. "
        "Bez tej ślepoty ocenia markę, nie muzykę.", S["p"]))
    e.append(Paragraph(
        "<b>Para losowa jest najważniejsza.</b> To jest odpowiednik prognozy "
        "naiwnej: jeśli silnik nie bije losowania, nie ma o czym rozmawiać. "
        "Wynik „silnik lepszy od losowego, gorszy od człowieka” też jest wynikiem "
        "— i to użytecznym.", S["p"]))
    e.append(Paragraph(
        "Puść każde przejście <b>dwa razy</b>, po około 30 sekund przed i po. "
        "Nie komentuj, nie tłumacz, nie podpowiadaj. Notuj dosłownie.", S["p"]))

    e.append(Paragraph("Metryczka", S["h2"]))
    m = Table([
        ["Imię / ksywa", "", "Data", ""],
        ["Ile lat gra", "", "Gdzie zwykle gra", ""],
        ["Gatunki", "", "Ile setów miesięcznie", ""],
        ["Czym przygotowuje sety dziś", "", "", ""],
    ], colWidths=[46 * mm, 39 * mm, 39 * mm, 46 * mm], rowHeights=[10 * mm] * 4)
    m.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Tekst", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), SZARY),
        ("LINEBELOW", (1, 0), (1, -1), 0.4, LINIA),
        ("LINEBELOW", (3, 0), (3, -1), 0.4, LINIA),
        ("SPAN", (1, 3), (3, 3)),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    e.append(m)

    e.append(Paragraph("Zanim zaczniemy słuchać", S["h2"]))
    for pyt, ile in [
        ("Opowiedz, jak przygotowujesz set. Krok po kroku, od otwarcia "
         "programu do wyjścia z domu.", 4),
        ("Ile czasu Ci to zajmuje? Co w tym jest najbardziej męczące?", 3),
        ("Kiedy ostatnio utknąłeś, szukając następnego utworu? Co zrobiłeś?", 3),
    ]:
        e.append(Paragraph(pyt, S["pyt"]))
        e.append(linie(ile))

    for nr in range(1, 13):
        e.append(karta_przejscia(nr))

    e.append(Paragraph("Po odsłuchu", S["h2"]))
    for pyt, ile in [
        ("Które przejście było najlepsze i dlaczego? (nie patrz w notatki)", 3),
        ("Czy któreś brzmiało „maszynowo”? Po czym poznałeś?", 3),
        ("Gdyby program proponował Ci takie przejścia — kiedy byś go włączył, "
         "a kiedy wyłączył?", 4),
    ]:
        e.append(Paragraph(pyt, S["pyt"]))
        e.append(linie(ile))

    e.append(Paragraph("Pytanie o pieniądze — zadaj je na końcu", S["h2"]))
    e.append(Paragraph(
        "Nie pytaj „czy zapłaciłbyś”. Każdy powie tak z uprzejmości. Zapytaj tak:",
        S["p"]))
    for pyt, ile in [
        ("Ile miesięcznie wydajesz dziś na muzykę i narzędzia? Na co konkretnie?", 3),
        ("Gdybym Ci to sprzedał dzisiaj — ile byś dał i za co dokładnie? "
         "Za program, za bazę wiedzy o scenie, czy za coś innego?", 4),
        ("Czego ten program musiałby NIE robić, żebyś go w ogóle włączył?", 3),
    ]:
        e.append(Paragraph(pyt, S["pyt"]))
        e.append(linie(ile))

    e.append(Spacer(1, 4 * mm))
    e.append(Paragraph(
        "Klucz źródeł wypełnia PROWADZĄCY po rozmowie, nie przed. "
        "Przejścia: 1–12 · S = silnik · C = człowiek · L = losowe", S["mala"]))
    klucz = Table([[str(i) for i in range(1, 13)], [""] * 12],
                  colWidths=[14 * mm] * 12, rowHeights=[7 * mm, 9 * mm])
    klucz.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Tekst", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), SZARY),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINIA),
    ]))
    e.append(klucz)

    doc.build(e)
    print(f"zapisane: {plik}  ({plik.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    buduj()

"""docs/JAK_ODPALIC.md → PDF. Jedno źródło prawdy dla instrukcji.

Do 09.08 instrukcja żyła w dwóch miejscach: Markdown w repo i osobno
redagowany HTML dla PDF-a. Dwa źródła zawsze się rozjeżdżają — stąd ten
generator: PDF powstaje WYŁĄCZNIE z pliku Markdown, a zrzuty ekranu
wstawiają się w miejsca oznaczone komentarzem `<!-- zrzut: nazwa -->`.

Użycie:
    .venv/bin/python scripts/dokumentacja_pdf.py [PLIK_WYJŚCIOWY.pdf]

Zrzuty: docs/zrzuty/<nazwa>.svg (podpisy w PODPISY niżej).
Renderem PDF jest Chrome w trybie bez okna — to samo, co robi „Drukuj
do PDF", więc wynik wygląda tak, jak strona w przeglądarce.
"""

from __future__ import annotations

import base64
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote

KORZEN = pathlib.Path(__file__).resolve().parent.parent
ZRODLO = KORZEN / "docs" / "JAK_ODPALIC.md"
ARKUSZ = KORZEN / "docs" / "dokumentacja.css"
ZRZUTY = KORZEN / "docs" / "zrzuty"
DOMYSLNY_PDF = pathlib.Path.home() / "Desktop" / "DanceLab — jak odpalic.pdf"

PODPISY = {
    # Biblioteka
    "lib_widok": "Zakładka Biblioteka: sekcje po lewej, szukajka i filtry na "
                 "górze, tabela utworów pośrodku, wiersz Analizuj i odtwarzacz "
                 "na dole.",
    "lib_szukanie": "Szukanie i filtry w działaniu: wpisany fragment nazwy oraz "
                    "okno tempa; licznik nad tabelą pokazuje, ile utworów "
                    "zostało.",
    "lib_oznaczenia": "Oznaczenia utworów: ♥ ulubiony i ⚑ filar w pierwszych "
                      "kolumnach tabeli.",
    "lib_okladki": "Okładki włączone klawiszem K: miniatury w wierszach, "
                   "przełącznik „okładki” pod polem szukania.",
    "lib_sortowanie": "Sortowanie po kliknięciu w nagłówek kolumny: strzałka "
                      "w nagłówku i opis sortowania nad tabelą.",
    "lib_analizuj": "Wiersz Analizuj na dole zakładki: ścieżka folderu "
                    "z muzyką i przycisk uruchamiający analizę.",
    "lib_strumien": "Utwór ze strumienia: jest w Bibliotece i wchodzi do "
                    "setów, ale odsłuch odmawia z powodem — nie ma pliku na "
                    "dysku, więc zagrasz go w Rekordboksie.",
    "lib_notki": "Notki (klawisz L): dziennik silnika — czego nie wie i co "
                 "odrzucił, z licznikiem w pasku statusu.",
    # Set
    "set_brief": "Zakładka Set przed budową: brief po lewej z przypiętym na "
                 "dole przyciskiem „Buduj set”.",
    "set_gatunki": "Lista gatunków (Ctrl+G): tylko te, które są w Twojej "
                   "bibliotece, w nazewnictwie Beatportu, z liczbą utworów. "
                   "Enter dodaje gatunek i stawia przy nim ✓; na końcu listy "
                   "sekcja „poza taksonomią”.",
    "set_djs": "Lista DJ-ów do kotwicy (Ctrl+D): rodziny brzmieniowe policzone "
               "z nagrań, z opisem brzmienia i liczbą setów. Enter wybiera "
               "kotwicę i zamyka listę.",
    "set_filary_tryb": "Wybór trybu rozstawienia filarów (klawisz F): podpory, "
                       "równy rozstaw albo rama.",
    "set_lista": "Zbudowany set: tabela z tempem, tonacją, gatunkiem i sumą "
                 "minut; filary na złoto.",
    "set_podmiana": "Panel podmiany (klawisz Z): dziesięć propozycji ocenionych "
                    "w tym miejscu setu, z wyborem trybu oceny u góry.",
    "set_dopisz": "Panel dopisania utworu (klawisz A): te same propozycje "
                  "co przy podmianie, ale utwór wejdzie ZA zaznaczonym.",
    "set_szew": "Pasek szwu (klawisz C): fakty o przejściu — liczba uderzeń, "
                "tempo, miejsce wyjścia i wejścia. Sam nic nie gra.",
    "set_info": "Karta utworu (klawisz I): metadane silnika, plik na dysku "
                "oraz to, co o utworze wie Rekordbox.",
    "set_plany": "Lista zapisanych planów (klawisz O): nazwa, liczba utworów, "
                 "okno tempa, kotwica i data.",
    "set_nazwa_planu": "Okno zapisu planu (klawisz S): pole nazwy oraz "
                       "przyciski Zapisz i Anuluj.",
    # Eksport / Cue
    "cue_widok": "Zakładka Eksport / Cue: karta utworu z osią energii i siatką "
                 "padów u góry, lista setu pośrodku, odtwarzacz i przyciski "
                 "wysyłki na dole.",
    "cue_pad": "Pad wybrany literą: podświetlony w siatce 2×4, a pod nią "
               "szczegóły — typ, dokładny czas i propozycja silnika.",
    "cue_przesuniety": "Pad po przesunięciu o osiem uderzeń: propozycja "
                       "silnika zostaje widoczna, a pad jest opisany jako "
                       "ustawiony ręką.",
    "cue_czas": "Wpisywanie czasu pada (klawisz T) wprost w kratce, z listą "
                "gotowych czasów fraz do wyboru strzałkami.",
    "cue_potwierdz": "Po pierwszym naciśnięciu W: przycisk zmienia się na "
                     "„POTWIERDŹ zapis N padów”. Dopiero drugie naciśnięcie "
                     "zapisuje.",
    "cue_rb_otwarty": "Przy otwartym Rekordboksie przycisk wysyłki cue jest "
                      "wyszarzony i mówi wprost, co zrobić.",
}

CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _figura(nazwa: str) -> str:
    """Zrzut jako obrazek osadzony w stronie (PDF ma być jednym plikiem)."""
    plik = ZRZUTY / f"{nazwa}.svg"
    if not plik.exists():
        # brak zrzutu NIE psuje dokumentu, ale musi być widoczny — cicha
        # dziura w instrukcji byłaby gorsza niż brzydki komunikat
        return (f'<p class="stopka">[brak zrzutu „{nazwa}" — oczekiwany '
                f'w {plik.relative_to(KORZEN)}]</p>')
    dane = base64.b64encode(plik.read_bytes()).decode()
    podpis = PODPISY.get(nazwa, "")
    return (f'<figure><img src="data:image/svg+xml;base64,{dane}" alt="{podpis}">'
            f'<figcaption>{podpis}</figcaption></figure>')


def _slug(tekst: str) -> str:
    """Kotwica w stylu GitHuba — taka, jakiej używa spis treści w Markdownie."""
    czysty = re.sub(r"<[^>]+>", "", tekst).strip().lower()
    czysty = re.sub(r"[^\w\s-]", "", czysty, flags=re.UNICODE)
    # KAŻDA spacja osobno, nie ciągi — tak robi GitHub, a ten sam plik
    # czyta się też tam („Eksport / Cue" daje podwójny myślnik)
    return czysty.replace(" ", "-")


def _kotwice(html: str) -> str:
    """Nagłówki dostają `id`, inaczej odsyłacze spisu treści są MARTWE.

    markdown-it nie robi tego sam, a PDF bez działającego spisu treści to
    dokument, po którym nie da się nawigować."""
    def podmien(m):
        poziom, tresc = m.group(1), m.group(2)
        return f'<h{poziom} id="{_slug(tresc)}">{tresc}</h{poziom}>'
    return re.sub(r"<h([1-6])>(.*?)</h\1>", podmien, html, flags=re.DOTALL)


def _sprawdz_odsylacze(html: str) -> list[str]:
    """Zwraca odsyłacze wewnętrzne bez kotwicy — dokument ma się skarżyć
    GŁOŚNO, a nie po cichu prowadzić donikąd."""
    kotwice = set(re.findall(r'<h[1-6] id="([^"]+)"', html))
    linki = set(re.findall(r'href="#([^"]+)"', html))
    return sorted(linki - kotwice)


def zbuduj_html(markdown: str) -> str:
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark").enable("table")
    tresc = _kotwice(md.render(markdown))
    # markdown-it koduje polskie znaki w odsyłaczach procentowo (%C5%82),
    # a kotwice są surowe — bez tego spis treści prowadzi donikąd
    tresc = re.sub(r'href="#([^"]+)"',
                   lambda m: f'href="#{unquote(m.group(1))}"', tresc)
    martwe = _sprawdz_odsylacze(tresc)
    if martwe:
        print("UWAGA — odsyłacze bez kotwicy:", ", ".join(martwe))

    # znaczniki zrzutów przechodzą przez konwerter jako komentarze HTML
    for nazwa in PODPISY:
        tresc = tresc.replace(f"<!-- zrzut: {nazwa} -->", _figura(nazwa))

    # metryczka to pierwsza tabela dokumentu — dostaje własną klasę, żeby
    # kolumna etykiet miała stałą szerokość
    tresc = tresc.replace("<table>", '<table class="metryczka">', 1)

    return (f"<!doctype html>\n<html lang=\"pl\">\n<head>\n"
            f"<meta charset=\"utf-8\">\n"
            f"<title>DanceLab — instrukcja użytkownika</title>\n"
            f"<style>\n{ARKUSZ.read_text()}</style>\n</head>\n<body>\n"
            f"{tresc}\n"
            f'<p class="stopka">Dokument wygenerowany z '
            f'docs/JAK_ODPALIC.md — jedyne źródło prawdy dla tej '
            f'instrukcji.</p>\n</body>\n</html>\n')


def main() -> int:
    wyjscie = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DOMYSLNY_PDF
    if not pathlib.Path(CHROME).exists():
        print(f"nie znalazłem przeglądarki do renderu: {CHROME}")
        return 1

    html = zbuduj_html(ZRODLO.read_text())
    with tempfile.TemporaryDirectory() as katalog:
        strona = pathlib.Path(katalog) / "instrukcja.html"
        pdf = pathlib.Path(katalog) / "instrukcja.pdf"
        strona.write_text(html)
        wynik = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf}", strona.as_uri()],
            capture_output=True, text=True)
        if not pdf.exists():
            print("render nie wyszedł:", wynik.stderr[-400:])
            return 1
        wyjscie.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(pdf, wyjscie)
    print(f"PDF: {wyjscie}  ({wyjscie.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

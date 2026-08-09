"""Instrukcja użytkownika ma się nie rozjeżdżać po cichu.

Trzy rzeczy, które w dokumentacji psują się same i których nikt nie
zauważa przy czytaniu: martwy odsyłacz w spisie treści, znacznik zrzutu
bez pliku i procedura bez wyniku. Te testy pilnują formy, nie treści —
treść pilnuje Janek.
"""

import pathlib
import re
import sys

KORZEN = pathlib.Path(__file__).resolve().parent.parent
INSTRUKCJA = KORZEN / "docs" / "JAK_ODPALIC.md"
sys.path.insert(0, str(KORZEN / "scripts"))


def _html() -> str:
    from dokumentacja_pdf import zbuduj_html

    return zbuduj_html(INSTRUKCJA.read_text())


def test_spis_tresci_prowadzi_do_istniejacych_rozdzialow():
    html = _html()
    kotwice = set(re.findall(r'<h[1-6] id="([^"]+)"', html))
    linki = set(re.findall(r'href="#([^"]+)"', html))
    assert not (linki - kotwice), \
        f"odsyłacze bez kotwicy: {sorted(linki - kotwice)}"
    assert len(linki) >= 8, "spis treści zniknął albo się skurczył"


def test_kazdy_znacznik_zrzutu_ma_plik():
    from dokumentacja_pdf import PODPISY, ZRZUTY

    tekst = INSTRUKCJA.read_text()
    uzyte = set(re.findall(r"<!-- zrzut: (\w+) -->", tekst))
    assert uzyte, "instrukcja bez ani jednego zrzutu ekranu"
    for nazwa in uzyte:
        assert nazwa in PODPISY, f'zrzut {nazwa} bez podpisu w generatorze'
        assert (ZRZUTY / f"{nazwa}.svg").exists(), \
            f"brak pliku zrzutu: docs/zrzuty/{nazwa}.svg"


def _sekcje() -> list[tuple[str, str]]:
    """(tytuł, treść) dla każdego punktu ### instrukcji."""
    tekst = INSTRUKCJA.read_text()
    kawalki = re.split(r"^### ", tekst, flags=re.M)[1:]
    return [(k.splitlines()[0].strip(), k) for k in kawalki]


def test_kazda_czynnosc_ma_cel_warunki_kroki_i_wynik():
    """Wzorzec ogłoszony we wstępie: cel → warunki wstępne → kroki → wynik.
    Punkt bez wyniku zostawia czytelnika bez odpowiedzi na pytanie, skąd ma
    wiedzieć, że się udało."""
    czynnosci = [(t, k) for t, k in _sekcje() if "**Cel:**" in k]
    assert len(czynnosci) >= 20, f"czynności jest tylko {len(czynnosci)}"
    for tytul, tresc in czynnosci:
        for etykieta in ("**Cel:**", "**Warunki wstępne:**", "**Kroki",
                         "**Wynik:**"):
            assert etykieta in tresc, f'punkt {tytul} bez {etykieta}'


def test_kazdy_punkt_zakladek_ma_zrzut_ekranu():
    """Żądanie Janka z 09.08: każda opcja opatrzona zrzutem. Wyjątki są
    WYMIENIONE z nazwy i uzasadnione w samym dokumencie — cichych nie ma."""
    bez_zrzutu_swiadomie = {
        # zrzut wymagałby uruchomienia dźwięku (twarda zasada projektu)
        "5.6. Posłuchaj szwu do następnego utworu",
        # te punkty opisują ten sam ekran, co punkt „Co widać na ekranie"
        "5.3. Przestaw pad — duży skok",
        "5.8. Wyślij playlistę z tej zakładki",
        "3.8. Wyślij filary do zakładki Set",
        "4.12. Wyślij playlistę do Rekordboksa",
    }
    braki = []
    for tytul, tresc in _sekcje():
        if not tytul[0].isdigit() or tytul[0] not in "345":
            continue
        if tytul in bez_zrzutu_swiadomie:
            continue
        if "<!-- zrzut:" not in tresc:
            braki.append(tytul)
    assert not braki, f"punkty bez zrzutu ekranu: {braki}"


def test_naglowki_sa_ponumerowane_po_kolei():
    tekst = INSTRUKCJA.read_text()
    glowne = [int(m) for m in re.findall(r"^## (\d+)\. ", tekst, flags=re.M)]
    assert glowne == list(range(1, len(glowne) + 1)), \
        f"numeracja rozdziałów się rozjechała: {glowne}"

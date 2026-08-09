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


def test_kazda_procedura_ma_cel_kroki_i_wynik():
    """Rozdział 4 trzyma jeden wzorzec: cel → warunki wstępne → kroki →
    wynik. Procedura bez wyniku zostawia czytelnika bez odpowiedzi na
    pytanie skąd wiem, że się udało."""
    tekst = INSTRUKCJA.read_text()
    rozdzial = tekst[tekst.index("## 4. Procedury"):tekst.index("## 5. ")]
    kawalki = re.split(r"^### 4\.\d+\. ", rozdzial, flags=re.M)[1:]
    assert len(kawalki) >= 10, f"procedur jest tylko {len(kawalki)}"
    for kawalek in kawalki:
        nazwa = kawalek.splitlines()[0]
        for etykieta in ("**Cel:**", "**Warunki wstępne:**", "**Kroki",
                         "**Wynik:**"):
            assert etykieta in kawalek, f'procedura {nazwa} bez {etykieta}'


def test_naglowki_sa_ponumerowane_po_kolei():
    tekst = INSTRUKCJA.read_text()
    glowne = [int(m) for m in re.findall(r"^## (\d+)\. ", tekst, flags=re.M)]
    assert glowne == list(range(1, len(glowne) + 1)), \
        f"numeracja rozdziałów się rozjechała: {glowne}"

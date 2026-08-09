"""Gatunki na ekranie: liczenie, pokrycie i wybór z listy (Ctrl+G).

Sam SŁOWNIK nazw Beatportu mieszka w `decision.gatunki_beatport`, bo używa
go także silnik przy dopasowaniu gatunku. Tutaj jest tylko to, co dotyczy
widoku: ile czego masz w puli, co jest poza taksonomią i jak się to wybiera.
"""

from __future__ import annotations

import collections
import re

from dancelab.decision.gatunki_beatport import (  # noqa: F401 — API modułu
    ELECTRONIC,
    OPEN_FORMAT,
    POZA,
    TAKSONOMIA,
    _klucz,
    kanoniczny,
)

def policz(analyses) -> list[tuple[str, list[tuple[str, int]]]]:
    """[(sekcja, [(gatunek, ile utworów)])] — TYLKO gatunki obecne w puli.

    Sekcje w kolejności Beatportu, w środku malejąco po liczbie utworów.
    Tagi spoza taksonomii trafiają na koniec, do sekcji „poza taksonomią"."""
    liczby: collections.Counter = collections.Counter()
    obce: collections.Counter = collections.Counter()
    for a in analyses:
        tag = getattr(a.track, "style_label", None)
        if not tag:
            continue
        kanon = kanoniczny(tag)
        if kanon:
            liczby[kanon] += 1
        else:
            obce[re.sub(r"\s+", " ", str(tag).strip())] += 1

    wynik: list[tuple[str, list[tuple[str, int]]]] = []
    for sekcja, lista in TAKSONOMIA.items():
        obecne = [(g, liczby[g]) for g in lista if liczby[g]]
        if obecne:
            wynik.append((sekcja, sorted(obecne, key=lambda x: (-x[1], x[0]))))
    if obce:
        wynik.append((POZA, sorted(obce.items(), key=lambda x: (-x[1], x[0]))))
    return wynik


def pokrycie(analyses) -> tuple[int, int, int]:
    """(ile gatunków Beatportu masz, ile ich jest, ile utworów bez gatunku)."""
    grupy = dict(policz(analyses))
    mam = sum(len(g) for s, g in grupy.items() if s != POZA)
    bez = sum(1 for a in analyses
              if not getattr(a.track, "style_label", None))
    return mam, sum(len(v) for v in TAKSONOMIA.values()), bez


def wybrane_klucze(wybrane: str) -> set[str]:
    """Klucze gatunków wpisanych w polu — do zaznaczania ich na liście."""
    return {_klucz(s) for s in wybrane.split(",") if s.strip()}


def jest_wybrany(wybrane: str, gatunek: str) -> bool:
    return _klucz(gatunek) in wybrane_klucze(wybrane)


def przelacz(wybrane: str, gatunek: str) -> str:
    """Dodaj/usuń gatunek w polu „Gatunki" (lista po przecinku).

    Rozdzielamy TYLKO po przecinkach — ukośnik należy do nazwy gatunku."""
    lista = [s.strip() for s in wybrane.split(",") if s.strip()]
    klucze = [_klucz(s) for s in lista]
    k = _klucz(gatunek)
    if k in klucze:
        lista.pop(klucze.index(k))
    else:
        lista.append(gatunek)
    return ", ".join(lista)

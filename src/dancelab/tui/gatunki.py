"""Gatunki wg taksonomii BEATPORTU — słownik i grupowanie (decyzja Janka
09.08: „gatunki to powinniśmy mieć jak beatport").

Nazwy gatunków Beatportu są WIELOCZŁONOWE Z NATURY: „140 / Deep Dubstep /
Grime" to JEDEN gatunek, nie trzy. Rozbijanie ich na człony wymyśliłoby
byty, które nie istnieją („140" nie jest gatunkiem) — dlatego traktujemy
etykietę jako całość. Tagi w kolekcji Janka pochodzą prosto z Beatportu,
więc dopasowanie jest dosłowne (po znormalizowaniu wielkości liter
i odstępów).

Czego tu nie ma: zgadywania. Tag spoza taksonomii nie znika i nie jest
naciągany na najbliższy — ląduje w osobnej sekcji „poza taksonomią",
z liczbą utworów. To ta sama zasada co wszędzie: konflikt ma być widoczny.
"""

from __future__ import annotations

import collections
import re

# Taksonomia ze strony Beatportu (zrzut Janka 09.08.2026), dwie sekcje.
ELECTRONIC = [
    "140 / Deep Dubstep / Grime", "Afro House", "Amapiano",
    "Ambient / Experimental", "Bass / Club", "Bass House", "Brazilian Funk",
    "Breaks / Breakbeat / UK Bass", "Dance / Pop", "Deep House",
    "DJ Tools / Acapellas", "Downtempo", "Drum & Bass", "Dubstep",
    "Electro (Classic / Detroit / Modern)", "Electronica", "Funky House",
    "Hard Dance / Hardcore / Neo Rave", "Hard Techno", "House",
    "Indie Dance", "Jackin House", "Latin Electronic", "Mainstage",
    "Melodic House & Techno", "Minimal / Deep Tech", "Nu Disco / Disco",
    "Organic House", "Progressive House", "Psy-Trance", "Tech House",
    "Techno (Peak Time / Driving)", "Techno (Raw / Deep / Hypnotic)",
    "Trance (Main Floor)", "Trance (Raw / Deep / Hypnotic)",
    "Trap / Future Bass", "UK Garage / Bassline",
]
OPEN_FORMAT = [
    "African", "Caribbean", "Country", "DJ Edits", "Hip-Hop", "Latin",
    "Pop", "R&B", "Rock",
]
TAKSONOMIA = {"Electronic": ELECTRONIC, "Open Format": OPEN_FORMAT}
POZA = "poza taksonomią"


def _klucz(nazwa: str) -> str:
    return re.sub(r"\s+", " ", str(nazwa).strip()).casefold()


_KANON = {_klucz(g): g for lista in TAKSONOMIA.values() for g in lista}


def kanoniczny(tag: str) -> str | None:
    """Nazwa Beatportu dla tagu albo None, gdy tag jest spoza taksonomii."""
    return _KANON.get(_klucz(tag))


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

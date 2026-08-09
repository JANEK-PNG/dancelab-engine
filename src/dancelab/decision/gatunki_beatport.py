"""Taksonomia gatunków BEATPORTU — słownik nazw, wspólny dla silnika i ekranu.

Decyzja Janka 09.08: „gatunki to powinniśmy mieć jak beatport". Nazwy są
WIELOCZŁONOWE Z NATURY: „140 / Deep Dubstep / Grime" to JEDEN gatunek, nie
trzy. Rozbijanie ich na człony wymyśliłoby byty, które nie istnieją („140"
nie jest gatunkiem) — dlatego etykieta jest CAŁOŚCIĄ.

Moduł mieszka w warstwie decyzji, bo potrzebuje go SILNIK (dopasowanie
gatunku przy budowie setu), a ekran tylko go pokazuje. Do 09.08 leżał
w warstwie ekranu i silnik nie miał do niego dostępu — skutkiem było
dopasowanie po pojedynczych słowach (patrz `library_profile.style_matches`).

Czego tu nie ma: zgadywania. Tag spoza taksonomii nie znika i nie jest
naciągany na najbliższy — zostaje sobą.
"""

from __future__ import annotations

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

"""Skąd bierze się utwór: z Apple Music, z dysku, czy znikąd.

Janek 13.08: „utwory, które nie są bezpośrednio na dysku, oznaczmy jako
Apple Music, a które są — ikonką komputera. I dodajmy to do filtracji."

Policzone na jego bibliotece (1914 analiz) wyszło, że kategorie są TRZY,
nie dwie:

    Apple Music                 1563   ścieżka `apple-music:tracks:<id>`
    na dysku                     274   ścieżka istnieje
    niedostępne                   77   ścieżka wygląda jak plik, ale go nie ma

Te 77 to w 65 przypadkach `/Volumes/ANTYWIRUS/...`, czyli **odpięty dysk
zewnętrzny**. Nazwanie ich „Apple Music" byłoby nieprawdą: to są pliki
lokalne, tyle że w tej chwili nieosiągalne — i to jest informacja, którą
DJ chce zobaczyć PRZED setem, a nie odkryć przy deckach.
"""

from __future__ import annotations

import pathlib

APPLE = "apple"
DYSK = "dysk"
BRAK = "brak"

PREFIKS_APPLE = "apple-music:"

# Ikona w tabeli. Monochromatyczne znaki, nie emoji — emoji w wielu
# terminalach zajmuje dwie kolumny i rozjeżdża tabelę.
IKONA = {APPLE: "☁", DYSK: "▣", BRAK: "⚠"}
NAZWA = {APPLE: "Apple Music", DYSK: "Na dysku", BRAK: "Niedostępne"}


def zrodlo(source_path: str | None) -> str:
    """APPLE / DYSK / BRAK — bez zgadywania, po tym, co da się sprawdzić."""
    sp = (source_path or "").strip()
    if not sp:
        return BRAK
    if sp.startswith(PREFIKS_APPLE):
        return APPLE
    try:
        if pathlib.Path(sp).exists():
            return DYSK
    except OSError:          # np. za długa nazwa albo znaki nie do zniesienia
        return BRAK
    return BRAK


def ikona(source_path: str | None) -> str:
    return IKONA[zrodlo(source_path)]


def opis(source_path: str | None) -> str:
    return NAZWA[zrodlo(source_path)]

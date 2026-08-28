"""Okno aplikacji — pywebview na WKWebView (przeglądarka wbudowana w macOS).

Wybór stacku (decyzja Janka 28.08): okno natywne z Pythonem w tym samym
procesie. Nie Qt — ten został świadomie wycięty 24.07 i jest kruchy na
Darwin 25. Nie Electron — pakowałby własnego Chrome i wymagał drugiego procesu.

Uruchomienie:  dancelab gui
"""

from __future__ import annotations

import pathlib

from dancelab.gui.most import Most

STATYCZNE = pathlib.Path(__file__).parent / "statyczne"
TYTUL = "DanceLab"


def uruchom(*, szerokosc: int = 1440, wysokosc: int = 900,
            debug: bool = False) -> None:
    """Otwórz okno. Blokuje wątek do zamknięcia — tak działa pywebview."""
    try:
        import webview
    except ModuleNotFoundError as exc:
        raise SystemExit(
            'Brak pywebview.  Instalacja:  uv pip install -e ".[gui]"'
        ) from exc

    plik = STATYCZNE / "index.html"
    if not plik.exists():
        raise SystemExit(f"nie znalazłem strony: {plik}")

    webview.create_window(
        TYTUL,
        url=plik.as_uri(),
        js_api=Most(),
        width=szerokosc,
        height=wysokosc,
        min_size=(1040, 640),      # poniżej tego trzy strefy przestają się mieścić
        background_color="#0e1013",
    )
    webview.start(debug=debug)

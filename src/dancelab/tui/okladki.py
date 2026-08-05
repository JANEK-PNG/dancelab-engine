"""Okładki w terminalu — mozaika półbloków (znak ▀ = 2 piksele na komórkę).

Wybór Janka (06.08): poziom 1, działa w KAŻDYM terminalu z Terminal.app
włącznie. Źródło okładek: grafika osadzona w tagach pliku (mutagen — APIC
w mp3/aiff, covr w m4a, pictures we flac); zero sieci, zero pobierania.
Brak okładki = None, rysujemy pustkę, nie zmyślony obrazek. Mały cache
w pamięci, bo skalowanie PIL-em przy każdym ticku byłoby marnotrawstwem.
"""

from __future__ import annotations

import io
from functools import lru_cache


def _bajty_okladki(path: str) -> bytes | None:
    import mutagen
    try:
        plik = mutagen.File(path)
    except Exception:  # noqa: BLE001 — chory tag to brak okładki, nie awaria
        return None
    if plik is None:
        return None
    tagi = getattr(plik, "tags", None)
    if tagi is None:
        return None
    # ID3 (mp3/aiff/wav): APIC:*
    for klucz in getattr(tagi, "keys", lambda: [])():
        if str(klucz).startswith("APIC"):
            return tagi[klucz].data
    # MP4/M4A: covr
    covr = tagi.get("covr") if hasattr(tagi, "get") else None
    if covr:
        return bytes(covr[0])
    # FLAC: pictures
    obrazy = getattr(plik, "pictures", None)
    if obrazy:
        return obrazy[0].data
    return None


def _ostry_renderer():
    """Klasa renderera z textual-image, jeśli terminal mówi protokołem
    graficznym (Ghostty/kitty → TGP, iTerm2/WezTerm → Sixel). W terminalach
    bez grafiki (Terminal.app, testy) zostajemy przy naszej mozaice
    rich-pixels — jej kolory są sprawdzone. Wybór pada RAZ, przy imporcie
    textual-image (on sam odpytuje terminal) — i dlatego import MUSI zajść
    przed startem Textual: robi to `cli.analyze.tui`, bo pod działającym
    Textualem odpowiedzi terminala przepadają i wykrywanie zawsze pada."""
    try:
        from textual_image.renderable import Image as Auto
        # UWAGA: każda z klas nazywa się dosłownie "Image" — aliasy TGPImage/
        # SixelImage żyją tylko w imporcie __init__. Rozpoznawać można wyłącznie
        # po MODULE klasy (nauczka: warunek po __name__ nigdy nie był prawdziwy
        # i Ghostty dostawał mozaikę).
        if Auto.__module__.rsplit(".", 1)[-1] in ("tgp", "sixel"):
            return Auto
    except Exception:  # noqa: BLE001
        pass
    return None


@lru_cache(maxsize=128)
def mozaika(path: str, szer: int, wys: int):
    """Renderowalna okładka albo None: OSTRA (protokół graficzny terminala,
    poziom 2 — wybór Janka: Ghostty) albo mozaika półbloków (poziom 1,
    każdy terminal). `szer`×`wys` w komórkach terminala."""
    dane = _bajty_okladki(path)
    if not dane:
        return None
    try:
        from PIL import Image
        obraz = Image.open(io.BytesIO(dane)).convert("RGB")
        Ostry = _ostry_renderer()
        if Ostry is not None:
            return Ostry(obraz, width=szer, height=wys)
        from rich_pixels import Pixels
        return Pixels.from_image(obraz.resize((szer, wys * 2)))
    except Exception:  # noqa: BLE001
        return None

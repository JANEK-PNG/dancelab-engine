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


@lru_cache(maxsize=128)
def mozaika(path: str, szer: int, wys: int):
    """Renderowalna mozaika okładki (rich_pixels.Pixels) albo None.

    `szer`×`wys` w KOMÓRKACH terminala; pikseli jest szer × wys*2
    (górna/dolna połówka znaku ▀)."""
    dane = _bajty_okladki(path)
    if not dane:
        return None
    try:
        from PIL import Image
        from rich_pixels import Pixels
        obraz = Image.open(io.BytesIO(dane)).convert("RGB")
        obraz = obraz.resize((szer, wys * 2))
        return Pixels.from_image(obraz)
    except Exception:  # noqa: BLE001
        return None

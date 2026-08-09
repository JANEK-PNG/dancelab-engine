"""Takty tak, jak rysuje je Rekordbox — źródło prawdy dla pozycji hot cue.

Życzenie Janka 09.08: „hot cue powinno być ustawiane tak, jak te czerwone
linie taktów, czyli na pierwszym barze — 68.1, a nie 68.2".

Te czerwone linie to siatka REKORDBOXA, nie nasza. Nasz tracker znajduje
bity; fazę taktu (który bit jest jedynką) zna na pewno tylko wtedy, gdy
`downbeat_phase_verified`. Rekordbox natomiast trzyma numer bitu w takcie
wprost — w pliku analizy, w znaczniku PQTZ, jako pole `beat` o wartości
1–4. Skoro cue lądują W JEGO bazie i DJ patrzy na JEGO linie, to jego
siatka jest właściwym układem współrzędnych.

Moduł tylko CZYTA pliki analizy. Nie dotyka bazy, nie zmienia tempa ani
siatki (twardy invariant projektu). Gdy pliku nie ma — mówimy o tym wprost
i wracamy do naszej siatki, zamiast zgadywać fazę taktu.
"""

from __future__ import annotations

import pathlib
import unicodedata

KATALOG_ANALIZ = pathlib.Path.home() / "Library/Pioneer/rekordbox/share"

# {ścieżka pliku (NFC): [sekundy pierwszych bitów taktów]}
_PAMIEC: dict[str, list[float]] = {}


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s))


def _downbeaty_z_pliku(anlz_path: pathlib.Path) -> list[float]:
    """Sekundy bitów oznaczonych przez Rekordbox jako pierwszy w takcie."""
    from pyrekordbox.anlz import AnlzFile

    plik = AnlzFile.parse_file(str(anlz_path))
    czasy: list[float] = []
    for tag in plik.getall_tags("PQTZ"):
        for wpis in getattr(tag.content, "entries", None) or []:
            if int(getattr(wpis, "beat", 0)) == 1:
                czasy.append(float(wpis.time) / 1000.0)
        if czasy:
            break
    return sorted(czasy)


_MAPA: dict[str, str] | None = None


def _mapa_analiz() -> dict[str, str]:
    """{ścieżka pliku (NFC): ścieżka pliku analizy Rekordboxa}.

    Budowana RAZ — edytor cue pyta o takty przy każdym ruchu pada, a wiersz
    po wierszu przez całą kolekcję (1800+ utworów) trwałoby wieczność.
    """
    global _MAPA
    if _MAPA is not None:
        return _MAPA
    mapa: dict[str, str] = {}
    try:
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.db6 import tables

        db = Rekordbox6Database()
        try:
            for r in db.session.query(tables.DjmdContent).all():
                if r.FolderPath and r.AnalysisDataPath:
                    mapa[_nfc(r.FolderPath)] = str(r.AnalysisDataPath)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — brak Rekordboxa to STAN, nie awaria
        mapa = {}
    _MAPA = mapa
    return mapa


def downbeaty_dla_sciezki(source_path: str) -> list[float]:
    """Takty utworu wg Rekordboxa; pusta lista = nie wiemy (i tak mówimy).

    Wynik jest zapamiętywany, bo edytor cue pyta o to przy każdym ruchu pada.
    """
    klucz = _nfc(source_path)
    if klucz in _PAMIEC:
        return _PAMIEC[klucz]
    czasy: list[float] = []
    anlz = _mapa_analiz().get(klucz)
    if anlz:
        plik = KATALOG_ANALIZ / str(anlz).lstrip("/")
        if plik.exists():
            try:
                czasy = _downbeaty_z_pliku(plik)
            except Exception:  # noqa: BLE001 — uszkodzony plik ≠ awaria
                czasy = []
    _PAMIEC[klucz] = czasy
    return czasy


def numer_taktu(downbeaty: list[float], sekundy: float) -> int | None:
    """Numer taktu (1 = pierwszy takt utworu) albo None bez siatki."""
    if not downbeaty:
        return None
    for i, t in enumerate(downbeaty):
        if abs(t - sekundy) < 0.02:
            return i + 1
    return None


def do_taktu(downbeaty: list[float], sekundy: float) -> tuple[float, int] | None:
    """(czas najbliższego taktu, jego numer) albo None, gdy siatki nie ma."""
    if not downbeaty:
        return None
    i = min(range(len(downbeaty)), key=lambda n: abs(downbeaty[n] - sekundy))
    return downbeaty[i], i + 1


def sasiedni_takt(downbeaty: list[float], sekundy: float,
                  o_ile: int) -> tuple[float, int] | None:
    """Takt przesunięty o `o_ile` względem najbliższego (±1, ±8, ±32…)."""
    if not downbeaty:
        return None
    i = min(range(len(downbeaty)), key=lambda n: abs(downbeaty[n] - sekundy))
    j = max(0, min(len(downbeaty) - 1, i + o_ile))
    return downbeaty[j], j + 1

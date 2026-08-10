"""Kotwice DJ-ów: „graj jak X" jako dane wejściowe, nie jako wiedza silnika.

Silnik pozostaje neutralny (założenie nr 2 rejestru): nie ma zdania, kim jest
Ben UFO ani czym jest „dobre prowadzenie". Ma za to plik `dj_anchors.json` —
zmierzone podpisy z publicznych miksów (centroid brzmienia + kontur skoków),
zbudowany przez `scripts/build_dj_anchors.py`. Ten moduł go tylko CZYTA
i rozstrzyga nazwę.

Rozstrzyganie nazw jest celowo nudne: dokładne trafienie bez uwzględniania
wielkości liter. Przy braku — odmowa z listą najbliższych nazw, nigdy
zgadywanie. Biblioteka Janka ma duplikaty tytułów i ta klasa błędów już raz
wystrzeliła; nazwiska DJ-ów traktujemy tą samą regułą co cue-writer:
niejednoznaczność = odmowa (audyt 24.07).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

DEFAULT_PATH = pathlib.Path("data/reports/dj_anchors.json")


@dataclass(frozen=True)
class DJAnchor:
    name: str
    n_tracks: int
    n_mixes: int
    centroid: list[float]
    contour: list[float]
    cos_median: float | None
    cos_q25: float | None
    cos_q75: float | None
    source: str


class AnchorError(ValueError):
    """Brak/niejednoznaczność kotwicy — z powodem i podpowiedzią, bez zgadywania."""


def load_anchor_book(path: str | pathlib.Path = DEFAULT_PATH) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        raise AnchorError(
            f"brak pliku kotwic: {p} — zbuduj go: "
            f".venv/bin/python scripts/build_dj_anchors.py")
    book = json.loads(p.read_text())
    if book.get("schema_version") != "dj-anchors-v1":
        raise AnchorError(
            f"nieznany schemat kotwic: {book.get('schema_version')!r}")
    return book


MOJE_ULUBIONE = "★ moje ulubione"


def kotwica_z_utworow(analizy, nazwa: str = MOJE_ULUBIONE) -> DJAnchor:
    """Kotwica policzona z WŁASNYCH utworów DJ-a, nie z księgi.

    Powód (test person 09.08): księga ma 285 DJ-ów zmierzonych z ich setów,
    a Kuba gra jak Amelie Lens, której tam nie ma — i nie ma jak jej dodać
    bez jej setlist. Własne utwory rozwiązują to bez zgadywania: bierzemy
    ŚREDNI wektor wskazanych nagrań i traktujemy go jak każdą inną kotwicę
    (wyśrodkowanie i sito działają tak samo).

    Kontur skoków zostaje PUSTY — to cecha sposobu grania DJ-a, której
    z samego zbioru utworów nie da się odczytać, a udawanie jej byłoby
    zmyślaniem.
    """
    import numpy as np

    wektory = [a.track.sound_embedding for a in analizy
               if getattr(a.track, "sound_embedding", None)]
    if len(wektory) < 3:
        raise AnchorError(
            f"za mało utworów z wektorem brzmienia na własną kotwicę "
            f"({len(wektory)}) — potrzeba co najmniej 3")
    srodek = np.asarray(wektory, dtype=float).mean(axis=0)
    return DJAnchor(name=nazwa, n_tracks=len(wektory), n_mixes=0,
                    centroid=[float(x) for x in srodek], contour=[],
                    cos_median=None, cos_q25=None, cos_q75=None,
                    source="wlasne utwory")


def resolve_anchor(name: str,
                   path: str | pathlib.Path = DEFAULT_PATH) -> DJAnchor:
    """Kotwica dla nazwy DJ-a. Dokładne dopasowanie albo odmowa z podpowiedzią."""
    book = load_anchor_book(path)
    djs: dict[str, dict] = book["djs"]
    wanted = name.strip().lower()
    hits = [k for k in djs if k.lower() == wanted]
    if len(hits) == 1:
        d = djs[hits[0]]
        return DJAnchor(name=hits[0], n_tracks=int(d["n_tracks"]),
                        n_mixes=int(d["n_mixes"]),
                        centroid=list(d["centroid"]), contour=list(d["contour"]),
                        cos_median=d.get("cos_median"), cos_q25=d.get("cos_q25"),
                        cos_q75=d.get("cos_q75"),
                        source=str(book.get("source", "?")))

    # Odmowa z podpowiedzią: podciągi + wspólne tokeny, posortowane po wielkości
    # próbki. To jest lista do wyboru dla człowieka, nie decyzja za niego.
    tokens = set(wanted.split())
    close = [k for k in djs
             if wanted in k.lower() or tokens & set(k.lower().split())]
    close.sort(key=lambda k: -djs[k]["n_tracks"])
    hint = ", ".join(close[:8]) if close else "brak podobnych"
    raise AnchorError(
        f"nie znam DJ-a {name!r} (kotwic w pliku: {len(djs)}). "
        f"Najbliższe nazwy: {hint}")


def list_anchors(path: str | pathlib.Path = DEFAULT_PATH,
                 limit: int = 40) -> list[tuple[str, int, float | None]]:
    """(nazwa, n_wektorów, mediana skoku) — do `--jak ?` w CLI."""
    book = load_anchor_book(path)
    rows = [(k, int(v["n_tracks"]), v.get("cos_median"))
            for k, v in book["djs"].items()]
    rows.sort(key=lambda r: -r[1])
    return rows[:limit]

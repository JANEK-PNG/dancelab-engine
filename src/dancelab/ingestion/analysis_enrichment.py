"""Dokarmianie analiz tym, co silnik już konsumuje, ale czego nikt nie podawał.

Dwa organy były podłączone do mózgu i nigdy niekarmione (zmierzone 04.08):

  * `Track.sound_embedding` — pole istnieje od dawna, `transition_score` miesza
    je w ocenę w trybie smart (`sound_affinity_weight` 0,6 w wagach), ale ŻADNA
    ścieżka go nie wypełniała. Wektory biblioteki leżą policzone
    w `data/reports/library_embeddings.json` od 21.07.
  * `Track.style_label` — `build_set` umie preferować style (z uczciwym
    rozluźnieniem), ale etykieta szła wyłącznie z tagów PLIKÓW, których 72%
    biblioteki nie ma. Tymczasem Janek opisał gatunki we WŁASNEJ taksonomii
    w Rekordboksie — i ona jest trafna (pomiar 03.08: iTunes wrzuca wszystko
    do „Dance", jego tagi rozróżniają garage/breaks/bass/dubstep).

Reguły:
  * dokarmianie NIGDY nie nadpisuje wartości już obecnej w analizie — uzupełnia
    braki; wyjątkiem jest gatunek, gdzie tag Rekordboxa (ręczna taksonomia
    Janka) wygrywa z tagiem pliku, bo pomiar pokazał, który jest wiarygodny;
  * brak źródła (nie ma pliku wektorów, nie ma Rekordboxa) = raport z powodem,
    nigdy wyjątek, nigdy zmyślona wartość — playlist ma powstać, tylko z mniejszą
    wiedzą i głośną informacją o tym.
"""

from __future__ import annotations

import json
import pathlib
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from dancelab.core.models import AnalysisResult

LIBRARY_EMBEDDINGS = pathlib.Path("data/reports/library_embeddings.json")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s))


@dataclass(frozen=True)
class EnrichmentReport:
    attached: int
    missing: int
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- brzmienie

def load_embedding_catalogue(
    path: str | pathlib.Path = LIBRARY_EMBEDDINGS,
) -> tuple[dict[str, list[float]], str]:
    """(ścieżka NFC → wektor, notka o źródle). Pusty słownik + powód, gdy brak."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}, f"brak katalogu wektorów: {p} (uruchom scripts/library_e_embeddings.py)"
    data = json.loads(p.read_text())
    root = _nfc(data.get("library_root", ""))
    out = {f"{root}/{_nfc(rel)}": vec for rel, vec in (data.get("tracks") or {}).items()}
    return out, f"wektory brzmienia: {len(out)} z {p.name}"


def attach_sound_embeddings(
    analyses: Iterable[AnalysisResult],
    catalogue: dict[str, list[float]] | None = None,
) -> EnrichmentReport:
    """Wypełnia `track.sound_embedding` z katalogu. Nie nadpisuje istniejących."""
    notes: list[str] = []
    if catalogue is None:
        catalogue, note = load_embedding_catalogue()
        notes.append(note)
    attached = missing = 0
    for analysis in analyses:
        track = analysis.track
        if track.sound_embedding is not None:
            continue
        vec = catalogue.get(_nfc(track.source_path))
        if vec is None:
            missing += 1
            continue
        track.sound_embedding = list(vec)
        attached += 1
    if missing:
        notes.append(
            f"{missing} utworów bez wektora brzmienia — składnik brzmienia "
            f"dla nich wypada z oceny (waga rozłożona, nie zero)")
    return EnrichmentReport(attached=attached, missing=missing, notes=notes)


# ---------------------------------------------------------------- gatunki

def load_rekordbox_genre_map() -> tuple[dict[str, str], str]:
    """Gatunki z bazy Rekordboxa (tylko odczyt). Pusty słownik + powód przy braku."""
    try:
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.db6 import tables
    except Exception as exc:  # noqa: BLE001
        return {}, f"pyrekordbox niedostępny ({type(exc).__name__}) — gatunki tylko z plików"
    try:
        db = Rekordbox6Database()
    except Exception as exc:  # noqa: BLE001
        return {}, f"nie mogę otworzyć bazy Rekordboxa ({type(exc).__name__}) — gatunki tylko z plików"
    try:
        genres = {g.ID: g.Name for g in db.session.query(tables.DjmdGenre).all()}
        out = {}
        for row in db.session.query(tables.DjmdContent).all():
            fp = row.FolderPath or ""
            name = genres.get(row.GenreID)
            if fp.startswith("/") and name:
                out[_nfc(fp)] = str(name)
    finally:
        db.close()
    return out, f"gatunki z Rekordboxa: {len(out)} utworów otagowanych"


def attach_rekordbox_genres(
    analyses: Iterable[AnalysisResult],
    genre_map: dict[str, str] | None = None,
) -> EnrichmentReport:
    """Tag Rekordboxa → `track.style_label`. Taksonomia Janka wygrywa z tagiem pliku."""
    notes: list[str] = []
    if genre_map is None:
        genre_map, note = load_rekordbox_genre_map()
        notes.append(note)
    attached = missing = 0
    for analysis in analyses:
        track = analysis.track
        genre = genre_map.get(_nfc(track.source_path))
        if genre is None:
            missing += 1
            continue
        if track.style_label != genre:
            track.style_label = genre
            attached += 1
    return EnrichmentReport(attached=attached, missing=missing, notes=notes)

"""Utwory bez pliku (strumienie) → pula DanceLaba, z analiz Rekordboxa.

Zmierzone 09.08: kolekcja Janka to 1880 pozycji, z czego 1571 to strumienie
Apple Music bez pliku na dysku. Rekordbox ma dla nich komplet: tempo,
tonację, gatunek, siatkę taktów, falę energii i podział na frazy. Ten skrypt
przenosi to do puli, żeby silnik miał z czego budować.

Użycie:
    .venv/bin/python scripts/import_z_rekordboxa.py [--limit N] [--pula ŚCIEŻKA]

Nic nie nadpisuje analiz policzonych przez nas: bierze WYŁĄCZNIE utwory,
których nie ma na dysku, i zapisuje je pod własnymi identyfikatorami `rbNNN`
z `engine_version="rekordbox-anlz"`.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

KORZEN = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / "src"))

PULA_DOMYSLNA = "experiments_priv/2026-07-30_rebuild/processed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pula", default=PULA_DOMYSLNA)
    args = parser.parse_args()

    from dancelab.ingestion.rekordbox_import import importuj
    from dancelab.storage.repositories import FileAnalysisRepository

    analizy, notatki = importuj(limit=args.limit)
    for n in notatki:
        print("·", n)
    if not analizy:
        print("nic do zapisania")
        return 1

    repo = FileAnalysisRepository(args.pula)
    pathlib.Path(args.pula).mkdir(parents=True, exist_ok=True)
    zapisane = 0
    for a in analizy:
        repo.save(a)
        zapisane += 1
    z_sekcjami = sum(1 for a in analizy if a.segments)
    z_energia = sum(1 for a in analizy if a.features)
    z_tonacja = sum(1 for a in analizy if a.track.key_estimate)
    print(f"\nzapisane do {args.pula}: {zapisane}")
    print(f"  z tonacją : {z_tonacja:5} ({z_tonacja / zapisane:.0%})")
    print(f"  z energią : {z_energia:5} ({z_energia / zapisane:.0%})")
    print(f"  z sekcjami: {z_sekcjami:5} ({z_sekcjami / zapisane:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

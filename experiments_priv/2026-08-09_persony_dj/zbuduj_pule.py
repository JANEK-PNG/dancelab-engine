"""Pule person — PRZEKSZTAŁCENIA realnej puli, nie zmyślone utwory.

Zasada: liczby mają zostać prawdziwe (tempo, tonacja, energia, sekcje
pochodzą z realnych analiz), a łamie się dokładnie ta JEDNA rzecz, o którą
w danej personie chodzi. Dzięki temu test mierzy aplikację, a nie fantazję.

Czego NIE robimy: nie powielamy utworów, żeby udawać większą bibliotekę.
Persona „8400 utworów" dostaje największą pulę, jaką realnie mamy, i jest to
w wyniku napisane wprost.

Użycie:
    .venv/bin/python experiments_priv/2026-08-09_persony_dj/zbuduj_pule.py
"""

from __future__ import annotations

import pathlib
import shutil
import sys

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))

ZRODLO = KORZEN / "experiments_priv/2026-07-30_rebuild/processed"
PULE = pathlib.Path(__file__).resolve().parent / "pule"


def zapisz(nazwa: str, analizy: list, opis: str) -> None:
    from dancelab.storage.repositories import FileAnalysisRepository

    kat = PULE / nazwa
    shutil.rmtree(kat, ignore_errors=True)
    kat.mkdir(parents=True, exist_ok=True)
    repo = FileAnalysisRepository(kat)
    for a in analizy:
        repo.save(a)
    (kat / "OPIS.txt").write_text(f"{opis}\nutworów: {len(analizy)}\n")
    print(f"  {nazwa:12} {len(analizy):5} utworów — {opis}")


def main() -> int:
    from dancelab.ingestion.analysis_enrichment import attach_rekordbox_keys
    from dancelab.storage.repositories import FileAnalysisRepository

    repo = FileAnalysisRepository(ZRODLO)
    wszystko = [repo.get(t) for t in repo.list_track_ids()]
    wszystko = [a for a in wszystko if (a.track.duration_sec or 0) <= 900]
    attach_rekordbox_keys(wszystko)
    pliki = [a for a in wszystko if a.track.source_path.startswith("/")]
    strumienie = [a for a in wszystko if not a.track.source_path.startswith("/")]
    print(f"źródło: {len(wszystko)} utworów ({len(pliki)} plików, "
          f"{len(strumienie)} strumieni)")
    PULE.mkdir(parents=True, exist_ok=True)

    # P2 · Marta — same pliki, mała pula, wszystko grywalne
    zapisz("marta", pliki[:310],
           "same pliki na dysku, zero strumieni — mała pula, wszystko gra")

    # P3 · Bartek — największa realnie dostępna pula, pełna rozpiętość tempa
    zapisz("bartek", wszystko,
           "największa realna pula (8400 z persony jest NIEOSIĄGALNE bez "
           "zmyślania utworów) — pełna rozpiętość tempa i gatunków")

    # P4 · Kuba — jeden świat brzmieniowy, wąskie tempo
    kuba = [a for a in wszystko
            if (a.track.style_label or "").lower().startswith("techno")
            or "techno" in (a.track.style_label or "").lower()]
    kuba = [a for a in kuba if 130 <= (a.track.bpm_estimate or 0) <= 150]
    zapisz("kuba", kuba, "samo techno w oknie 130-150 — pula jednorodna")

    # P5 · Zosia — tylko strumienie, mało, nic nie gra lokalnie
    zapisz("zosia", strumienie[:180],
           "180 pozycji, WSZYSTKIE ze strumieni — zero plików do odsłuchu")

    # P6 · Olek — pliki spoza kolekcji Rekordboxa, bez fazy taktu
    olek = []
    for a in pliki[:220]:
        kopia = a.model_copy(deep=True)
        stara = pathlib.Path(kopia.track.source_path)
        kopia.track.source_path = f"/Users/olek/bounces/{stara.stem}.wav"
        kopia.track.title = f"mixdown_{kopia.track.track_id[:6]}_FINAL"
        kopia.track.artist = None
        kopia.track.style_label = None          # świeży bounce nie ma tagu
        if kopia.beatgrid is not None:
            kopia.beatgrid.downbeat_phase_verified = False
            kopia.beatgrid.downbeats_sec = []
        olek.append(kopia)
    zapisz("olek", olek,
           "świeże bounce'y: brak wpisu w Rekordboksie, brak tagów, "
           "brak fazy taktu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

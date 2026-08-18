"""Dziesięć playlist do oceny NA PAPIERZE + formularz z literatury.

DECYZJA JANKA (17.08): „zrób mi 10 losowych playlist, różne długości i style,
i formularz do wydruku — nie z czapy, ze sprawdzonych źródeł".

PROJEKT BADANIA (nie tylko playlisty)
-------------------------------------
Ocena bez punktu odniesienia jest nieczytelna — to jest kultura tego projektu
(kontrole negatywne wszędzie). Dlatego w dziesiątce jest ślepa kontrola:

  * 6 playlist = pełne wyjście silnika (dobór + KOLEJNOŚĆ),
  * 4 playlisty = te same utwory, które wybrał silnik, ale kolejność
    PRZETASOWANA. To izoluje dokładnie to, co silnik twierdzi, że dodaje:
    porządek. Jeśli oceny obu grup wyjdą takie same — kolejność silnika
    nie wnosi nic słyszalnego i trzeba to będzie napisać w OBALONE.md.

Przydział zapieczętowany w `PRZYDZIAL_NIE_OTWIERAC.json` — otworzyć DOPIERO
po wpisaniu wszystkich ocen. Nazwy playlist neutralne (OCENA A…J).

FORMULARZ — SKĄD SIĘ WZIĄŁ (źródła sprawdzone 17.08)
----------------------------------------------------
* Skala 1–5 na przejście: MOS wg ITU-T P.800 (standard ocen odsłuchowych),
  kotwice słowne przetłumaczone na sytuację DJ-ską.
* Wymiary oceny CAŁEJ playlisty: Bonnin & Jannach, „Automated Generation of
  Music Playlists" (ACM Computing Surveys 2014) — spójność/homogeniczność,
  różnorodność, płynność przejść; rozdział spójność-vs-różnorodność
  potwierdzony w EPJ Data Science 2025.
* Ocena przejść w automatycznym miksie per aspekt (dobór, moment, tempo):
  Vande Veire & De Bie, EURASIP JASMP 2018 (automatyczny DJ dla DnB).
* Kategorie „co zgrzyta" = 1:1 słownik `TOPIC_KEYWORDS` z naszego
  `validation/dj_benchmark.py` — żeby papier dał się przepisać do CSV,
  które istniejąca bramka umie policzyć (5 sesji × ≥30 przejść).

SESJE: playlisty sparowane tak, żeby jedna sesja (dwie playlisty) miała
≥30 przejść — bo `MIN_RATED_TRANSITIONS_PER_SESSION = 30`.

Tryby: bez argumentu = próba na sucho. `--na-serio` = zapis do Rekordboxa.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import unicodedata as U
from datetime import datetime

import numpy as np

KATALOG = pathlib.Path(__file__).parent
ROOT = KATALOG.parents[1]
sys.path.insert(0, str(ROOT / "experiments_priv/2026-08-14_raport_calosc"))

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
PIONEER = pathlib.Path.home() / "Library" / "Pioneer" / "rekordbox"
ZIARNO = 20260817

# (nazwa, długość, pasmo bpm) — pary sesji sumują się do ≥30 przejść
PLAN = [
    ("OCENA A", 20, (122, 130)), ("OCENA B", 12, (134, 142)),   # sesja 1: 30
    ("OCENA C", 25, (118, 126)), ("OCENA D", 8, (140, 152)),    # sesja 2: 31
    ("OCENA E", 18, (126, 134)), ("OCENA F", 15, (100, 120)),   # sesja 3: 31
    ("OCENA G", 22, (128, 136)), ("OCENA H", 10, (136, 146)),   # sesja 4: 30
    ("OCENA I", 24, (120, 132)), ("OCENA J", 14, (130, 140)),   # sesja 5: 36
]
SESJE = [("SESJA 1", ["OCENA A", "OCENA B"]), ("SESJA 2", ["OCENA C", "OCENA D"]),
         ("SESJA 3", ["OCENA E", "OCENA F"]), ("SESJA 4", ["OCENA G", "OCENA H"]),
         ("SESJA 5", ["OCENA I", "OCENA J"])]

nfc = lambda s: U.normalize("NFC", str(s or ""))  # noqa: E731


def main() -> int:
    na_serio = "--na-serio" in sys.argv
    from dancelab.core.config import load_weights
    from dancelab.decision.set_builder import build_set
    from dancelab.ingestion.playlist_publish import BACKUP_DIR, rekordbox_running
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    if rekordbox_running():
        print("⛔ Rekordbox działa — zamknij go")
        return 2

    print("wczytuję analizy…")
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])

    # NAJPIERW mapowanie na Rekordbox — playlista na papierze musi być
    # IDENTYCZNA z tą w Rekordboksie, więc utwór bez odpowiednika w bazie
    # nie ma prawa wejść do puli. Złapane w próbie na sucho: 14 braków.
    from pyrekordbox import Rekordbox6Database as _RB
    from pyrekordbox.db6 import tables as _tb
    _db = _RB()
    try:
        _by_path = {nfc(r.FolderPath or ""): str(r.ID)
                    for r in _db.session.query(_tb.DjmdContent).all()}
    finally:
        _db.close()

    def _cid(a):
        tid = a.track.track_id
        if tid.startswith("rb"):
            return tid[2:]
        return _by_path.get(nfc(a.track.source_path))

    widok = [a for a in widok if _cid(a)]
    print(f"pula po ograniczeniu do utworów obecnych w Rekordboksie: {len(widok)}")
    W = load_weights("configs/descriptor_weights.yaml")
    g = np.random.default_rng(ZIARNO)

    # kontrola: 4 z 10 pozycji planu, wylosowane raz, zapieczętowane
    kontrolne = sorted(g.choice(10, size=4, replace=False).tolist())
    przydzial = {PLAN[i][0]: ("KONTROLA-TASOWANIE" if i in kontrolne
                              else "SILNIK") for i in range(10)}

    playlisty: dict[str, list] = {}
    for idx, (nazwa, dlugosc, (lo, hi)) in enumerate(PLAN):
        pula = [a for a in widok
                if a.track.bpm_estimate and lo - 2 <= a.track.bpm_estimate <= hi + 2]
        if len(pula) > 420:
            wyb = g.choice(len(pula), size=420, replace=False)
            pula = [pula[i] for i in wyb]
        plan = build_set(pula, W, arc="off", target_track_count=dlugosc,
                         bpm_min=float(lo), bpm_max=float(hi),
                         seed=ZIARNO + idx)
        kolej = list(plan.track_order)[:dlugosc]
        if przydzial[nazwa] == "KONTROLA-TASOWANIE":
            gg = np.random.default_rng(ZIARNO * 7 + idx)
            gg.shuffle(kolej)
        by_id = {a.track.track_id: a for a in pula}
        playlisty[nazwa] = [by_id[t] for t in kolej if t in by_id]
        print(f"  {nazwa}: {len(playlisty[nazwa])} utw. · {lo}–{hi} BPM")

    # ---- mapowanie na Rekordbox i zapis ----
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database()
    try:
        wiersze = db.session.query(tables.DjmdContent).all()
        by_path = {nfc(r.FolderPath or ""): str(r.ID) for r in wiersze}
        cidy: dict[str, list[str]] = {}
        braki: dict[str, int] = {}
        for nazwa, tracki in playlisty.items():
            out = []
            brak = 0
            for a in tracki:
                cid = _cid(a)
                if cid:
                    out.append(cid)
                else:
                    brak += 1
            cidy[nazwa], braki[nazwa] = out, brak
            print(f"  {nazwa}: w Rekordboksie {len(out)}/{len(tracki)}"
                  + (f" (brak {brak})" if brak else ""))

        if not na_serio:
            print("\nPRÓBA NA SUCHO — nic nie zapisano. Zapis: --na-serio")
        else:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            backup = BACKUP_DIR / f"master.PRE_OCENA_{datetime.now():%Y%m%d_%H%M%S}.db"
            shutil.copy2(PIONEER / "master.db", backup)
            for b in (".db-wal", ".db-shm"):
                src = (PIONEER / "master.db").with_suffix(b)
                if src.exists():
                    shutil.copy2(src, backup.with_suffix(b))
            from dancelab.ingestion.rekordbox_playlist import create_set_playlist
            idki = {}
            for nazwa, lista in cidy.items():
                pl = create_set_playlist(db, tables, name=nazwa,
                                         content_ids=lista,
                                         folder_name="DanceLab Ocena")
                idki[nazwa] = (str(pl.ID), len(lista))
            db.commit()
            print(f"kopia zapasowa: {backup.name}")
    finally:
        db.close()

    if na_serio:
        db2 = Rekordbox6Database()
        try:
            for nazwa, (pid, ocz) in idki.items():
                got = db2.session.query(tables.DjmdSongPlaylist).filter(
                    tables.DjmdSongPlaylist.PlaylistID == pid,
                    tables.DjmdSongPlaylist.rb_local_deleted == 0).count()
                print(f"  {'✓' if got == ocz else '⛔'} {nazwa}: {got}/{ocz}")
        finally:
            db2.close()

    # ---- pieczęć, CSV, dane do formularza ----
    (KATALOG / "PRZYDZIAL_NIE_OTWIERAC.json").write_text(json.dumps(
        {"uwaga": "OTWORZYĆ DOPIERO PO WPISANIU WSZYSTKICH OCEN",
         "przydzial": przydzial}, ensure_ascii=False, indent=1), encoding="utf-8")

    dane = {}
    for nazwa, tracki in playlisty.items():
        dane[nazwa] = [{
            "track_id": a.track.track_id,
            "artysta": a.track.artist or "",
            "tytul": a.track.title or pathlib.Path(str(a.track.source_path)).stem,
            "bpm": a.track.bpm_estimate,
        } for a in tracki]
    (KATALOG / "playlisty_dane.json").write_text(
        json.dumps(dane, ensure_ascii=False), encoding="utf-8")

    for snazwa, czlonkowie in SESJE:
        w = ["pair_id,track_id_a,track_id_b,engine_score,dj_mixability_rating,comment,blind"]
        for nazwa in czlonkowie:
            t = dane[nazwa]
            for i in range(len(t) - 1):
                w.append(f"{nazwa.replace(' ', '_')}_{i+1:02d},"
                         f"{t[i]['track_id']},{t[i+1]['track_id']},0.0,,,true")
        (KATALOG / f"{snazwa.replace(' ', '_')}_transition_ratings.csv"
         ).write_text("\n".join(w) + "\n", encoding="utf-8")
    print("zapisano: playlisty_dane.json · PRZYDZIAL_NIE_OTWIERAC.json · "
          "5 szkieletów CSV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

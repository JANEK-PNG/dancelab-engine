"""Druga dziesiątka playlist do ślepego odsłuchu — RUNDA 2 (OCENA K–T).

DECYZJA JANKA (29.08): „zaproponuj kolejne 10 do testów, a zwycięska playlista
będzie kupiona". Runda pierwsza dała wynik na najmniejszym możliwym marginesie
(p = 0,0476 przy progu 0,05), więc powtórka na nowej dziesiątce jest dokładnie
tym, czego ten wynik potrzebuje — nie nowym eksperymentem, tylko replikacją.

CO ZOSTAJE BEZ ZMIANY (i to jest cel):
  * 6 playlist = pełne wyjście silnika, 4 = te same utwory w kolejności
    PRZETASOWANEJ; przydział zapieczętowany do czasu kompletu ocen,
  * te same długości i pasma tempa, więc każda sesja ma ≥30 przejść,
  * ten sam formularz i ta sama skala 1–5,
  * **te same progi H1/H2 co 18.08** — replikacja bez ruszania kryteriów.

CO SIĘ ZMIENIA, ŚWIADOMIE:
  * inne ziarno (29.08) — inne losowanie kontroli i inne sety,
  * **utwory z rundy pierwszej są WYKLUCZONE z puli**. Powód: gdyby wróciły
    te same utwory, powtórka nie byłaby niezależna, a efekt jednej mocnej
    playlisty (OCENA C dostała same piątki) mógłby się przenieść.

CZEGO TA RUNDA NIE NAPRAWIA: większość biblioteki to strumienie Apple Music
bez pliku, więc i tutaj część utworów będzie nieanalizowalna. Dlatego Janek
kupuje zwycięską playlistę — po zakupie mamy JEDNĄ playlistę z kompletem
audio, wektorów i deskryptorów, a do niej gotowe oceny ucha.
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

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
PIONEER = pathlib.Path.home() / "Library" / "Pioneer" / "rekordbox"
ZIARNO = 20260829

# (nazwa, długość, pasmo bpm) — pary sesji sumują się do ≥30 przejść
PLAN = [
    ("OCENA K", 20, (122, 130)), ("OCENA L", 12, (134, 142)),   # sesja 1: 30
    ("OCENA M", 25, (118, 126)), ("OCENA N", 8, (140, 152)),    # sesja 2: 31
    ("OCENA O", 18, (126, 134)), ("OCENA P", 15, (100, 120)),   # sesja 3: 31
    ("OCENA R", 22, (128, 136)), ("OCENA S", 10, (136, 146)),   # sesja 4: 30
    ("OCENA T", 24, (120, 132)), ("OCENA U", 14, (130, 140)),   # sesja 5: 36
]
SESJE = [("SESJA 1", ["OCENA K", "OCENA L"]), ("SESJA 2", ["OCENA M", "OCENA N"]),
         ("SESJA 3", ["OCENA O", "OCENA P"]), ("SESJA 4", ["OCENA R", "OCENA S"]),
         ("SESJA 5", ["OCENA T", "OCENA U"])]

nfc = lambda s: U.normalize("NFC", str(s or ""))  # noqa: E731


def main() -> int:
    na_serio = "--na-serio" in sys.argv
    from dancelab.core.config import load_weights
    from dancelab.decision.set_builder import build_set
    from dancelab.ingestion.playlist_publish import BACKUP_DIR, rekordbox_running
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    # Próba na sucho tylko CZYTA bazę, więc wolno ją zrobić przy otwartym
    # Rekordboksie. Blokada dotyczy wyłącznie zapisu — tam otwarty Rekordbox
    # nadpisałby zmianę własnym buforem.
    if rekordbox_running() and na_serio:
        print("⛔ Rekordbox działa — zamknij go przed zapisem playlist")
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

    # Runda 2 musi być niezależna od pierwszej — te same utwory przeniosłyby
    # ze sobą efekt jednej mocnej playlisty i powtórka nie byłaby powtórką.
    runda1 = json.loads((ROOT / "experiments_priv/2026-08-17_ocena_papierowa"
                         / "playlisty_dane.json").read_text(encoding="utf-8"))
    zuzyte = {t["track_id"] for lista in runda1.values() for t in lista}
    przed = len(widok)
    widok = [a for a in widok if a.track.track_id not in zuzyte]
    print(f"pula po wykluczeniu {len(zuzyte)} utworów z rundy 1: "
          f"{len(widok)} (było {przed})")
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
        # mapowanie ścieżek policzone już wyżej (`_by_path`) — tu tylko wysyłka
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
            backup = BACKUP_DIR / f"master.PRE_OCENA2_{datetime.now():%Y%m%d_%H%M%S}.db"
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
                                         folder_name="DanceLab Ocena 2")
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

"""Łapacz utworów z Rekordboxa: co 45 s czyta KOPIĘ master.db i notuje nowe
wpisy Historii (co gra / grało). Oryginału NIGDY nie dotyka.

Użycie: uv run python historia_poller.py [sekundy]
"""
import json, pathlib, shutil, sys, time
from datetime import datetime

KATALOG = pathlib.Path(__file__).parent
PIONEER = pathlib.Path.home() / "Library" / "Pioneer" / "rekordbox"
SCRATCH = pathlib.Path("/private/tmp/claude-501/-Users-jantrybus-Desktop-AI/ae2e7309-426b-47ac-a3e6-2b2cdb758053/scratchpad")
KOPIA = SCRATCH / "master_poller_kopia.db"

def odczyt():
    shutil.copy2(PIONEER / "master.db", KOPIA)
    for b in (".db-wal", ".db-shm"):
        src = (PIONEER / "master.db").with_suffix(b)
        cel = KOPIA.with_suffix(b)
        if src.exists(): shutil.copy2(src, cel)
        elif cel.exists(): cel.unlink()
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(KOPIA)
    try:
        tytul = {}
        for r in db.session.query(tables.DjmdContent).all():
            art = r.Artist.Name if getattr(r, "Artist", None) else ""
            tytul[str(r.ID)] = f"{art} — {r.Title or ''}"
        wpisy = []
        for r in db.session.query(tables.DjmdSongHistory).all():
            wpisy.append((str(r.HistoryID), r.TrackNo, str(r.ContentID),
                          str(r.created_at), tytul.get(str(r.ContentID), "?")))
        return wpisy
    finally:
        db.close()

def main():
    sekundy = float(sys.argv[1]) if len(sys.argv) > 1 else 4 * 3600
    plik = KATALOG / f"set_{datetime.now():%Y%m%d_%H%M%S}_utwory.jsonl"
    f = open(plik, "w", encoding="utf-8", buffering=1)
    print("zapis:", plik)
    znane = set()
    start = time.time()
    while time.time() - start < sekundy:
        try:
            for w in odczyt():
                klucz = (w[0], w[1], w[2])
                if klucz in znane: continue
                znane.add(klucz)
                rek = {"ts": round(time.time(), 4), "historia": w[0], "nr": w[1],
                       "content_id": w[2], "created_at": w[3], "utwor": w[4]}
                f.write(json.dumps(rek, ensure_ascii=False) + "\n")
                print(f"{datetime.now():%H:%M:%S}  #{w[1]}  {w[4]}")
        except Exception as e:
            print("odczyt nieudany (spróbuję za chwilę):", type(e).__name__, e)
        time.sleep(45)
    f.close()

if __name__ == "__main__":
    main()

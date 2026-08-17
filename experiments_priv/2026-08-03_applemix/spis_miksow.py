"""Spis miksów Boiler Room i Warehouse Project z katalogu Apple.

Decyzja Janka (03.08): korpus v2 z oficjalnych wydań DJ Mix, na start te dwie
serie. Powód: tracklisty są rozpisane i publiczne, a repertuar pokrywa gatunki,
których korpus djmix nie ma (12 miksów UK Garage, zero UK Bass).

API wyszukiwania Apple NIE stronicuje — `offset` zwraca to samo. Więc spis
budujemy kulą śnieżną: z każdego znalezionego wydania bierzemy nazwisko
wykonawcy i pytamy o „<seria> <wykonawca>", aż przestaną dochodzić nowe.
Zaczynamy od nazwisk z korpusu, bo je już mamy.

Grzecznie: 3 s przerwy między zapytaniami (limit Apple to ~20/min).
Zapisuje po każdej rundzie, więc przerwany bieg nie traci roboty.
"""

from __future__ import annotations

import json
import pathlib
import re
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).parent
OUT = HERE / "spis_miksow.json"
CORPUS_DJ = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
UA = {"User-Agent": "DanceLab-research/1.0 (local, non-commercial)"}
PAUSE = 3.0
SERIES = {
    "Boiler Room": lambda n: n.startswith("Boiler Room"),
    "The Warehouse Project": lambda n: "Warehouse Project" in n or "HAÇIENDA" in n.upper(),
}


def search(term: str) -> list[dict]:
    u = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": term, "entity": "album", "limit": 200})
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
            return json.loads(r.read()).get("results", [])
    except Exception as e:
        print(f"  ⚠ {term[:40]}: {type(e).__name__}", flush=True)
        return []


def seed_names() -> list[str]:
    """Nazwiska z korpusu — mamy je, więc czemu nie."""
    if not CORPUS_DJ.exists():
        return []
    ds = json.loads(CORPUS_DJ.read_text(encoding="utf-8", errors="replace"))
    out = set()
    for m in ds:
        t = m.get("title", "")
        mt = re.search(r"^\s*[\d\-]{4,10}\s*-\s*(.+?)\s*(?:@|\||-\s|\()", t)
        if mt:
            n = mt.group(1).strip()
            if 2 < len(n) < 40:
                out.add(n)
    return sorted(out)


def main() -> int:
    found: dict[str, dict] = {}
    if OUT.exists():
        found = {k: v for k, v in json.loads(OUT.read_text())["albums"].items()}
        print(f"wznawiam: {len(found)} wydań już w spisie", flush=True)

    asked: set[str] = set()
    queue = [s for s in SERIES]                       # zapytania bazowe
    queue += [f"{s} {n}" for s in SERIES for n in seed_names()[:200]]
    print(f"zapytań w kolejce: {len(queue)}", flush=True)

    new_artists: set[str] = set()
    round_no = 0
    while queue:
        round_no += 1
        print(f"\n── runda {round_no}: {len(queue)} zapytań", flush=True)
        for i, q in enumerate(queue, 1):
            if q in asked:
                continue
            asked.add(q)
            for r in search(q):
                name = r.get("collectionName") or ""
                if "(DJ Mix)" not in name:
                    continue
                for ser, test in SERIES.items():
                    if test(name):
                        cid = str(r["collectionId"])
                        if cid not in found:
                            found[cid] = {"series": ser, "name": name,
                                          "artist": r.get("artistName"),
                                          "tracks": r.get("trackCount"),
                                          "date": (r.get("releaseDate") or "")[:10]}
                            a = r.get("artistName")
                            if a:
                                new_artists.add(a)
                        break
            if i % 20 == 0:
                print(f"  {i}/{len(queue)} · wydań: {len(found)}", flush=True)
                OUT.write_text(json.dumps({"albums": found}, ensure_ascii=False))
            time.sleep(PAUSE)

        # kolejna runda: pytamy o wykonawców, których jeszcze nie pytaliśmy
        queue = [f"{s} {a}" for s in SERIES for a in sorted(new_artists)
                 if f"{s} {a}" not in asked]
        new_artists.clear()
        OUT.write_text(json.dumps({"albums": found}, ensure_ascii=False))
        if round_no >= 3:
            print("\nstop po 3 rundach", flush=True)
            break

    OUT.write_text(json.dumps({"albums": found}, ensure_ascii=False))
    from collections import Counter
    c = Counter(v["series"] for v in found.values())
    print(f"\n══ SPIS GOTOWY ══")
    for k, v in c.most_common():
        print(f"  {v:4d}  {k}")
    print(f"  {len(found):4d}  RAZEM")
    print(f"  utworów łącznie (wg metadanych): "
          f"{sum(v.get('tracks') or 0 for v in found.values())}")
    print(f"\nzapisane: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

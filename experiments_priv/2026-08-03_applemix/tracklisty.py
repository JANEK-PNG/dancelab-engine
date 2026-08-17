"""Tracklisty miksów Boiler Room / Warehouse Project — kolejność i czasy.

To jest rzecz, po którą w ogóle idziemy: KOLEJNOŚĆ. Model rankingu uczy się
„co po czym", a tego nie ma w żadnym katalogu utworów — jest tylko w setach.

Strona wydania niesie w `application/ld+json` pełną listę w kolejności, każdy
utwór z własnym identyfikatorem Apple i dokładnym czasem trwania. Identyfikator
jest kluczowy: dalsze dopasowanie idzie po NIM, a nie po tytule, więc znika
cała klasa błędów, która w tym projekcie już raz wystrzeliła (biblioteka ma
duplikaty tytułów: 2× Movement, 3× Srekye).

Dwie fazy:
  A. tracklisty ze stron wydań        → kolejność + czasy + id utworów
  B. wykonawcy przez lookup po id     → kto gra, partiami po 100

CZEGO TO NIE DAJE, mówię od razu: utwory oznaczone „ID" są niezidentyfikowane
przez samego wydawcę (u Four Teta 3 z 19) i zostają dziurami w kolejności.
Nie zgadujemy ich.

Grzecznie: 2 s między stronami, 3 s między partiami lookupu. Wznawialne —
zapis po każdych 20 wydaniach.
"""

from __future__ import annotations

import json
import pathlib
import re
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).parent
SPIS = HERE / "spis_miksow.json"
OUT = HERE / "tracklisty.json"

UA_PAGE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}
UA_API = {"User-Agent": "DanceLab-research/1.0 (local, non-commercial)"}
LD = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>')
DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def secs(iso: str) -> int | None:
    m = DUR.fullmatch(iso or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def tracklist(cid: str) -> dict | None:
    url = f"https://music.apple.com/us/album/{cid}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA_PAGE), timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    m = LD.search(html)
    if not m:
        return {"error": "brak ld+json"}
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        return {"error": f"ld+json niepoprawny: {type(e).__name__}"}
    tr = []
    for i, t in enumerate(d.get("tracks") or [], 1):
        u = t.get("url") or ""
        tr.append({"n": i,
                   "id": u.rsplit("/", 1)[-1] if u else None,
                   "sec": secs(t.get("duration")),
                   "name": t.get("name")})
    return {"date": d.get("datePublished"),
            "genre": d.get("genre"),
            "artist": [a.get("name") for a in (d.get("byArtist") or [])],
            "tracks": tr}


def faza_a():
    albums = json.loads(SPIS.read_text())["albums"]
    done = json.loads(OUT.read_text())["albums"] if OUT.exists() else {}
    todo = [c for c in albums if c not in done]
    print(f"faza A · wydań w spisie {len(albums)} · do pobrania {len(todo)}",
          flush=True)

    ok = err = 0
    for i, cid in enumerate(todo, 1):
        r = tracklist(cid)
        if r and "error" not in r:
            done[cid] = {**albums[cid], **r}
            ok += 1
        else:
            done[cid] = {**albums[cid], "error": (r or {}).get("error", "?")}
            err += 1
        if i % 20 == 0:
            OUT.write_text(json.dumps({"albums": done}, ensure_ascii=False))
            n = sum(len(v.get("tracks") or []) for v in done.values())
            print(f"  {i}/{len(todo)} · ok {ok} · błędy {err} · utworów {n}",
                  flush=True)
        time.sleep(2.0)

    OUT.write_text(json.dumps({"albums": done}, ensure_ascii=False))
    return done


def faza_b(done: dict):
    """Wykonawca per utwór — lookup po identyfikatorze, partiami po 100."""
    ids = [t["id"] for v in done.values() for t in (v.get("tracks") or [])
           if t.get("id")]
    ids = sorted(set(ids))
    cache_p = HERE / "utwory_meta.json"
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    todo = [i for i in ids if i not in cache]
    print(f"\nfaza B · utworów unikalnych {len(ids)} · do sprawdzenia {len(todo)}",
          flush=True)

    for i in range(0, len(todo), 100):
        chunk = todo[i: i + 100]
        u = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
            {"id": ",".join(chunk)})
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers=UA_API), timeout=30) as r:
                res = json.loads(r.read()).get("results", [])
        except Exception as e:
            print(f"  ⚠ partia {i//100+1}: {type(e).__name__}", flush=True)
            res = []
        for x in res:
            if x.get("trackId"):
                cache[str(x["trackId"])] = {
                    "artist": x.get("artistName"),
                    "track": x.get("trackName"),
                    "preview": x.get("previewUrl"),
                    "genre": x.get("primaryGenreName"),
                }
        for c in chunk:                     # brak odpowiedzi = zapamiętujemy brak
            cache.setdefault(c, None)
        cache_p.write_text(json.dumps(cache, ensure_ascii=False))
        print(f"  {min(i+100, len(todo))}/{len(todo)} · znanych {sum(1 for v in cache.values() if v)}",
              flush=True)
        time.sleep(3.0)
    return cache


def main() -> int:
    done = faza_a()
    cache = faza_b(done)

    good = {k: v for k, v in done.items() if "error" not in v}
    tr = sum(len(v.get("tracks") or []) for v in good.values())
    ids = {t["id"] for v in good.values() for t in (v.get("tracks") or []) if t.get("id")}
    known = sum(1 for i in ids if cache.get(i))
    with_prev = sum(1 for i in ids if (cache.get(i) or {}).get("preview"))
    idtracks = sum(1 for v in good.values() for t in (v.get("tracks") or [])
                   if (t.get("name") or "").startswith("ID"))

    print("\n" + "═" * 60)
    print(f"  miksów z tracklistą : {len(good)} (błędy: {len(done)-len(good)})")
    print(f"  utworów w kolejności: {tr}")
    print(f"  przejść A→B         : {tr - len(good)}")
    print(f"  unikalnych utworów  : {len(ids)}")
    print(f"  z metadanymi        : {known} ({100*known/max(1,len(ids)):.1f}%)")
    print(f"  z próbką audio      : {with_prev} ({100*with_prev/max(1,len(ids)):.1f}%)")
    print(f"  niezidentyfikowanych przez wydawcę (ID): {idtracks}")
    print(f"\n  {OUT}\n  {HERE/'utwory_meta.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

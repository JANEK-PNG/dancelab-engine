"""Tracklisty DJ-miksów ze stron music.apple.com (segmenty miksów są
streaming-only i NIE istnieją w iTunes Lookup — złapane 08.08). Strona
albumu niesie pełny track-list w `serialized-server-data`: tytuł, artysta,
czas (ms; dwell time!), numer. Wznawialne; ~1 s przerwy między stronami."""

import json
import pathlib
import re
import sys
import time

sys.path.insert(0, "src")
from dancelab.ingestion.artwork_sync import _http

KATALOG = pathlib.Path(__file__).parent
STAN = json.loads((KATALOG / "miksy_katalog.json").read_text())
TRACKLISTY = KATALOG / "tracklisty"
TRACKLISTY.mkdir(exist_ok=True)


def tracklista_ze_strony(cid):
    html = _http(f"https://music.apple.com/us/album/{cid}").decode(
        "utf-8", "replace")
    m = re.search(r'id="serialized-server-data"[^>]*>(.*?)</script>',
                  html, re.S)
    if not m:
        raise ValueError("strona bez serialized-server-data")
    sekcje = json.loads(m.group(1))["data"][0]["data"]["sections"]
    for s in sekcje:
        if str(s.get("id", "")).startswith("track-list ") \
                or str(s.get("id", "")).startswith("track-list-"):
            itemy = [i for i in s.get("items", []) if i.get("title")]
            if itemy:
                return [{"nr": i.get("trackNumber"),
                         "artysta": i.get("artistName"),
                         "tytul": i.get("title"),
                         "ms": i.get("duration")} for i in itemy]
    raise ValueError("brak sekcji track-list")


zrobione, bledy = 0, 0
albumy = [(k, r) for k, r in STAN.items() if r.get("collection_id")]
for i, (klucz, rekord) in enumerate(albumy):
    cid = rekord["collection_id"]
    plik = TRACKLISTY / f"{cid}.json"
    if plik.exists() and json.loads(plik.read_text()):
        zrobione += 1
        continue
    try:
        lista = tracklista_ze_strony(cid)
        plik.write_text(json.dumps(lista, ensure_ascii=False, indent=1))
        rekord["tracklista_n"] = len(lista)
        rekord.pop("tracklista_blad", None)
        zrobione += 1
    except Exception as exc:  # noqa: BLE001
        rekord["tracklista_blad"] = str(exc)
        bledy += 1
    (KATALOG / "miksy_katalog.json").write_text(
        json.dumps(STAN, ensure_ascii=False, indent=1))
    if (i + 1) % 15 == 0:
        print(f"{i+1}/{len(albumy)} · tracklisty {zrobione} · błędy {bledy}",
              flush=True)
    time.sleep(1.0)

utwory = sum(r.get("tracklista_n", 0) for _, r in albumy)
print(f"\nKONIEC: {len(albumy)} albumów → {zrobione} tracklist "
      f"({utwory} utworów) · błędy {bledy}")

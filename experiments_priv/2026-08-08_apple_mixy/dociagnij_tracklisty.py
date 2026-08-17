"""OCR-owe miksy → kanoniczne albumy iTunes + tracklisty.

iTunes jest tu CZYŚCICIELEM OCR-u: szukamy po ogonie tytułu (napisy z okładek
doklejają się z PRZODU) + nazwie DJ-a; bierzemy tylko album, którego nazwa
kończy się na "(DJ Mix)". Pewne dopasowanie albo odmowa z powodem — jak przy
okładkach. Lookup albumu zwraca KOLEJNOŚĆ utworów i czasy (dwell time).
Wznawialne przez checkpoint. Limit tempa ~1 zapytanie/s (iTunes dławi)."""

import json
import pathlib
import re
import time
import urllib.parse

import sys
sys.path.insert(0, "src")
from dancelab.ingestion.artwork_sync import _http, _norm

KATALOG = pathlib.Path(__file__).parent
WEJSCIE = json.loads((KATALOG / "miksy_ocr.json").read_text())
WYJSCIE = KATALOG / "miksy_katalog.json"
TRACKLISTY = KATALOG / "tracklisty"
TRACKLISTY.mkdir(exist_ok=True)

stan = json.loads(WYJSCIE.read_text()) if WYJSCIE.exists() else {}


def ogon_tytulu(tytul: str, slow: int) -> str:
    t = re.sub(r"\(DJ(\s+Mix\)?)?\s*$", "", tytul).strip()
    return " ".join(t.split()[-slow:])


def szukaj_albumu(wpis):
    for slow in (7, 4):
        fraza = urllib.parse.quote(f"{ogon_tytulu(wpis['tytul'], slow)} "
                                   f"{wpis['dj']}")
        url = (f"https://itunes.apple.com/search?term={fraza}"
               f"&media=music&entity=album&limit=8")
        try:
            wyniki = json.loads(_http(url)).get("results", [])
        except Exception as exc:  # noqa: BLE001
            return None, f"iTunes nie odpowiedział: {exc}"
        for w in wyniki:
            nazwa = w.get("collectionName", "")
            if "dj mix" not in nazwa.lower():
                continue
            if (_norm(wpis["dj"]) in _norm(w.get("artistName", ""))
                    or _norm(ogon_tytulu(wpis["tytul"], 4)) in _norm(nazwa)):
                return w, "dopasowane"
        time.sleep(0.6)
    return None, "nie znalezione pewnie w iTunes"


def tracklista(collection_id):
    url = (f"https://itunes.apple.com/lookup?id={collection_id}"
           f"&entity=song&limit=200")
    dane = json.loads(_http(url)).get("results", [])
    return [{"nr": t.get("trackNumber"), "artysta": t.get("artistName"),
             "tytul": t.get("trackName"), "ms": t.get("trackTimeMillis"),
             "track_id": t.get("trackId"), "gatunek": t.get("primaryGenreName")}
            for t in dane if t.get("wrapperType") == "track"]


for i, wpis in enumerate(WEJSCIE):
    klucz = re.sub(r"[^a-z0-9]+", "", wpis["tytul"].lower())[:60]
    if klucz in stan:
        continue
    album, powod = szukaj_albumu(wpis)
    rekord = {"ocr": wpis, "powod": powod}
    if album:
        cid = album["collectionId"]
        rekord.update({"collection_id": cid,
                       "album": album.get("collectionName"),
                       "artysta": album.get("artistName"),
                       "gatunek": album.get("primaryGenreName"),
                       "utworow": album.get("trackCount")})
        try:
            lista = tracklista(cid)
            (TRACKLISTY / f"{cid}.json").write_text(
                json.dumps(lista, ensure_ascii=False, indent=1))
            rekord["tracklista_n"] = len(lista)
        except Exception as exc:  # noqa: BLE001
            rekord["tracklista_blad"] = str(exc)
        time.sleep(0.6)
    stan[klucz] = rekord
    WYJSCIE.write_text(json.dumps(stan, ensure_ascii=False, indent=1))
    if (i + 1) % 10 == 0:
        ok = sum(1 for r in stan.values() if r.get("collection_id"))
        print(f"{i+1}/{len(WEJSCIE)} · dopasowane {ok}", flush=True)
    time.sleep(0.6)

ok = [r for r in stan.values() if r.get("collection_id")]
listy = [r for r in ok if r.get("tracklista_n")]
print(f"\nKONIEC: {len(stan)} wpisów OCR → {len(ok)} albumów iTunes → "
      f"{len(listy)} tracklist ({sum(r['tracklista_n'] for r in listy)} utworów)")

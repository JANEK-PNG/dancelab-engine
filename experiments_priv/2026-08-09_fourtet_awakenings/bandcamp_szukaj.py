"""Które utwory z seta Four Teta są na Bandcampie — wyszukiwarka z pewnym
dopasowaniem (ta sama filozofia co artwork/iTunes: pewne albo odmowa)."""

import json
import pathlib
import re
import sys
import time
import urllib.parse

sys.path.insert(0, "src")
from dancelab.ingestion.artwork_sync import _http, _norm

KAT = pathlib.Path(__file__).parent
TRACKLISTA = json.loads((KAT / "tracklista_mixesdb.json").read_text())["utwory"]
OUT = KAT / "bandcamp_wyniki.json"

stan = json.loads(OUT.read_text()) if OUT.exists() else {}

def szukaj(artysta, tytul):
    """API autocomplete Bandcampa (strona wyszukiwarki wymaga JS)."""
    import urllib.request
    req = urllib.request.Request(
        "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic",
        data=json.dumps({"search_text": f"{artysta} {tytul}"[:100],
                         "search_filter": "t", "fan_id": None,
                         "full_page": False}).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X "
                               "10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"})
    with urllib.request.urlopen(req, timeout=20) as o:
        wyniki = json.loads(o.read()).get("auto", {}).get("results", [])
    czysty = re.sub(r"\s*\((Original|Extended)[^)]*\)", "", tytul, flags=re.I)
    for w in wyniki:
        if w.get("type") != "t":
            continue
        if (_norm(czysty) and _norm(czysty) in _norm(w.get("name", ""))
                and _norm(artysta.split("&")[0].split("feat")[0])
                in _norm(w.get("band_name", ""))):
            return {"link": w["item_url_path"], "nazwa": w["name"],
                    "autor": w.get("band_name", "")}
    return None


for u in TRACKLISTA:
    klucz = str(u["nr"])
    if klucz in stan or u["artysta"] == "Unknown":
        continue
    try:
        traf = szukaj(u["artysta"], u["tytul"])
    except Exception as exc:  # noqa: BLE001
        traf = {"blad": str(exc)[:120]}
    stan[klucz] = {"artysta": u["artysta"], "tytul": u["tytul"],
                   "bandcamp": traf}
    OUT.write_text(json.dumps(stan, ensure_ascii=False, indent=1))
    print(f"{u['nr']:2d}. {u['artysta'][:24]} – {u['tytul'][:30]}: "
          f"{'TAK' if traf and 'link' in traf else 'brak'}", flush=True)
    time.sleep(1.2)

ok = sum(1 for r in stan.values()
         if r.get("bandcamp") and "link" in r["bandcamp"])
print(f"\nKONIEC: {ok} z {len(stan)} na Bandcampie → {OUT}")

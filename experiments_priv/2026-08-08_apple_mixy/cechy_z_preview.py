"""Cechy dla 2114 utworów z żniw: preview iTunes → analiza silnika → cechy.

Reguły twarde:
* audio pobierane TYLKO do policzenia cech i od razu KASOWANE
  (wzorzec mix-deconstruction: pobierz → licz → skasuj);
* wznawialne: gotowa analiza = pomijamy; porażka zapisana imiennie;
* cechy liczone TYM SAMYM silnikiem co korpus H (analyze_track, default.yaml)
  — spójność z wyścigiem priors/triplet.

Etapy: (1) previewUrl ze stron albumów (ponowny odczyt stron — tracklisty
zapisano bez adresów), (2) pobranie m4a, (3) analiza, (4) kasacja audio.
"""

import json
import pathlib
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.ingestion.artwork_sync import _http  # noqa: E402

KATALOG = pathlib.Path(__file__).parent
TRACKLISTY = KATALOG / "tracklisty"
AUDIO = KATALOG / "preview_audio"
ANALIZY = KATALOG / "analizy"
PORAZKI = KATALOG / "cechy_porazki.json"
AUDIO.mkdir(exist_ok=True)
ANALIZY.mkdir(exist_ok=True)

_CONFIG = None


def _init_worker():
    global _CONFIG
    from dancelab.core.config import load_config
    _CONFIG = load_config(str(ROOT / "configs/default.yaml"))


def _analizuj(tid: str, sciezka: str) -> tuple[str, str]:
    from dancelab.core.pipeline import analyze_track
    out = ANALIZY / f"{tid}.json"
    try:
        wynik = analyze_track(sciezka, _CONFIG)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(wynik.model_dump_json())
        tmp.replace(out)
        return tid, ""
    except Exception as exc:  # noqa: BLE001
        return tid, f"{type(exc).__name__}: {exc}"[:200]


def urls_ze_stron():
    """Etap 1: previewUrl per (album, nr) — dopisywane do tracklist."""
    for plik in sorted(TRACKLISTY.glob("*.json")):
        lista = json.loads(plik.read_text())
        if lista and "preview" in lista[0]:
            continue
        cid = plik.stem
        html = _http(f"https://music.apple.com/us/album/{cid}").decode(
            "utf-8", "replace")
        m = re.search(r'id="serialized-server-data"[^>]*>(.*?)</script>',
                      html, re.S)
        itemy = []
        for s in json.loads(m.group(1))["data"][0]["data"]["sections"]:
            if str(s.get("id", "")).startswith("track-list"):
                itemy = [i for i in s.get("items", []) if i.get("title")]
                if itemy:
                    break
        po_nr = {i.get("trackNumber"): i.get("previewUrl") for i in itemy}
        for t in lista:
            t["preview"] = po_nr.get(t["nr"])
        plik.write_text(json.dumps(lista, ensure_ascii=False, indent=1))
        print(f"urls: {cid} ({sum(1 for t in lista if t['preview'])}/"
              f"{len(lista)})", flush=True)
        time.sleep(1.0)


def pobierz_i_analizuj():
    zadania = []
    for plik in sorted(TRACKLISTY.glob("*.json")):
        cid = plik.stem
        for t in json.loads(plik.read_text()):
            tid = f"{cid}-{t['nr']}"
            if (ANALIZY / f"{tid}.json").exists() or not t.get("preview"):
                continue
            zadania.append((tid, t["preview"]))
    print(f"do policzenia: {len(zadania)}", flush=True)

    porazki = json.loads(PORAZKI.read_text()) if PORAZKI.exists() else {}
    paczka = 60
    for start in range(0, len(zadania), paczka):
        czesc = zadania[start:start + paczka]
        sciezki = {}
        for tid, url in czesc:                       # etap 2: pobranie
            cel = AUDIO / f"{tid}.m4a"
            try:
                cel.write_bytes(_http(url))
                sciezki[tid] = str(cel)
            except Exception as exc:  # noqa: BLE001
                porazki[tid] = f"pobranie: {exc}"[:200]
            time.sleep(0.25)
        with ProcessPoolExecutor(max_workers=4,                # etap 3
                                 initializer=_init_worker) as ex:
            fut = {ex.submit(_analizuj, tid, p): tid
                   for tid, p in sciezki.items()}
            for f in as_completed(fut):
                tid, blad = f.result()
                if blad:
                    porazki[tid] = blad
        for tid in sciezki:                          # etap 4: kasacja audio
            pathlib.Path(sciezki[tid]).unlink(missing_ok=True)
        PORAZKI.write_text(json.dumps(porazki, ensure_ascii=False, indent=1))
        print(f"{min(start + paczka, len(zadania))}/{len(zadania)} · "
              f"analiz: {len(list(ANALIZY.glob('*.json')))} · "
              f"porażek: {len(porazki)}", flush=True)


if __name__ == "__main__":
    urls_ze_stron()
    pobierz_i_analizuj()
    print(f"\nKONIEC: analiz {len(list(ANALIZY.glob('*.json')))} · "
          f"porażki w {PORAZKI.name}")

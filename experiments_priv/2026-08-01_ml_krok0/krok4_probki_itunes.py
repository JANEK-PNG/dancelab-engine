"""KROK 4 · próbki iTunes dla strumieni z historii Janka → wektory CLAP.

81,4% historii grania Janka to strumienie Apple Music bez pliku na dysku, więc
dla trzech czwartych jego przejść nie da się policzyć NICZEGO z audio. To jest
wąskie gardło warstwy osobistej: 222 pary treningowe po filtrze odstępów.

Rekordbox zapisuje takie utwory jako `apple-music:tracks:1459041006`, a ten
numer to wprost identyfikator katalogu iTunes — dopasowanie jeden-do-jednego,
bez zgadywania po tytule (biblioteka ma duplikaty tytułów, więc to ma znaczenie).
Publiczne API zwraca `previewUrl` do ~30-sekundowej próbki.

ZASADY, na które zgodził się Janek (02.08):
  * pobierz → policz → SKASUJ audio. Na dysku nigdy nie leży więcej niż jeden plik.
  * katalog roboczy w repo (poza iCloud), nigdy na Pulpicie.
  * wysyłamy wyłącznie numery katalogowe, nic o użytkowniku.
  * każdy wektor dostaje `source: "preview"` — bo powstał z 30 s ze ŚRODKA
    utworu, a wektory biblioteki z 5 okien rozłożonych po całym pliku. Kto
    kiedykolwiek porówna te dwa zbiory, ma prawo o tym wiedzieć.

CZEGO TO NIE DA: początku utworu, struktury, wykonalności szwu. Tych rzeczy
nie ma w 30 sekundach ze środka i żadne przeliczenie ich nie wyczaruje.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "data/reports/apple_preview_embeddings.json"
TMP = ROOT / "experiments_priv/_cache/previews"
LOOKUP = "https://itunes.apple.com/lookup"
BATCH = 100          # API przyjmuje do 200 ID naraz; 100 jest bezpieczne
PAUSE = 3.0          # sekundy między zapytaniami — limit to ~20/min
SCHEMA = "apple-preview-embeddings-v1"
MIN_TRACKS = 5
UA = "DanceLab-research/1.0 (local, non-commercial)"


def stream_ids() -> dict[str, str]:
    """{itunes_id: rekordbox_content_id} dla strumieni z par historii."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    content = {str(r.ID): (r.FolderPath or "") for r in
               db.session.query(tables.DjmdContent).all()}
    plays = defaultdict(list)
    for r in (db.session.query(tables.DjmdSongHistory)
              .order_by(tables.DjmdSongHistory.TrackNo).all()):
        plays[str(r.HistoryID)].append(str(r.ContentID))
    db.close()

    used = set()
    for ids in plays.values():
        if len(ids) >= MIN_TRACKS:
            for a, b in zip(ids, ids[1:]):
                if a != b:
                    used.update((a, b))

    out = {}
    for cid in used:
        fp = content.get(cid, "")
        if fp.startswith("apple-music:tracks:"):
            out[fp.rsplit(":", 1)[1]] = cid
    return out


def lookup(ids: list[str]) -> dict[str, dict]:
    url = f"{LOOKUP}?{urllib.parse.urlencode({'id': ','.join(ids)})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    return {str(x.get("trackId")): x for x in data.get("results", [])
            if x.get("trackId")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="tylko sprawdź pokrycie, nic nie pobieraj")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    want = stream_ids()
    ids = sorted(want)
    if args.limit:
        ids = ids[: args.limit]
    print(f"strumieni w parach historii: {len(ids)}", flush=True)

    meta: dict[str, dict] = {}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i: i + BATCH]
        try:
            meta.update(lookup(chunk))
        except Exception as e:
            print(f"  ⚠ paczka {i // BATCH + 1}: {type(e).__name__} {e}", flush=True)
        print(f"  odpytane {min(i + BATCH, len(ids))}/{len(ids)} · "
              f"znalezione {len(meta)}", flush=True)
        if i + BATCH < len(ids):
            time.sleep(PAUSE)

    with_prev = {k: v for k, v in meta.items() if v.get("previewUrl")}
    print(f"\n  w katalogu iTunes : {len(meta)}/{len(ids)} "
          f"({100*len(meta)/max(1,len(ids)):.1f}%)")
    print(f"  z próbką audio    : {len(with_prev)} "
          f"({100*len(with_prev)/max(1,len(ids)):.1f}%)")
    missing = [i for i in ids if i not in meta]
    if missing:
        print(f"  bez odpowiedzi    : {len(missing)} "
              f"(np. {', '.join(missing[:3])})")

    if args.probe:
        print("\n  --probe: nic nie pobrano")
        return 0

    # ── pobieranie + CLAP, jeden plik naraz, kasowany od razu
    import torch
    from transformers import ClapModel, ClapProcessor
    from library_e_embeddings import MODEL_ID, embed_track

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"\n  ładuję CLAP ({MODEL_ID}) na {device}…", flush=True)
    model = ClapModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(MODEL_ID)

    TMP.mkdir(parents=True, exist_ok=True)
    done = json.loads(OUT.read_text())["tracks"] if OUT.exists() else {}
    ok = fail = 0
    for n, (tid, m) in enumerate(sorted(with_prev.items()), 1):
        if tid in done:
            continue
        f = TMP / f"{tid}.m4a"
        try:
            req = urllib.request.Request(m["previewUrl"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r, f.open("wb") as fh:
                fh.write(r.read())
            vec = embed_track(f, model, processor, device)
        except Exception as e:
            print(f"  ⚠ {tid}: {type(e).__name__} {e}", flush=True)
            vec = None
        finally:
            f.unlink(missing_ok=True)          # audio nie zostaje NIGDY

        if vec is None:
            fail += 1
            continue
        done[tid] = {
            "vector": vec,
            "content_id": want.get(tid),
            "artist": m.get("artistName"),
            "title": m.get("trackName"),
            "source": "preview",               # 30 s ze ŚRODKA, nie cały utwór
            "preview_sec": 30,
        }
        ok += 1
        if ok % 25 == 0:
            OUT.write_text(json.dumps(
                {"schema_version": SCHEMA, "model": MODEL_ID,
                 "note": "wektory z 30-sekundowych próbek iTunes; audio skasowane",
                 "tracks": done}, ensure_ascii=False))
            print(f"  … {n}/{len(with_prev)} · policzone {ok} · błędy {fail}",
                  flush=True)

    OUT.write_text(json.dumps(
        {"schema_version": SCHEMA, "model": MODEL_ID,
         "note": "wektory z 30-sekundowych próbek iTunes; audio skasowane",
         "tracks": done}, ensure_ascii=False))
    left = list(TMP.glob("*.m4a"))
    print(f"\n  gotowe: {ok} wektorów · błędy {fail} · "
          f"plików audio pozostawionych: {len(left)}")
    print(f"  zapisane: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

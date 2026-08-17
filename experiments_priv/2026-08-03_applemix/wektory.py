"""Wektory CLAP dla utworów z miksów Boiler Room / Warehouse Project.

Ostatni krok korpusu v2: 7743 utwory z tracklist dostają wektor brzmienia,
żeby model rankingu miał czym opisać kandydata.

ZASADY (te same, na które zgodził się Janek 02.08):
  * pobierz → policz → SKASUJ audio; na dysku nigdy więcej niż jeden plik
  * katalog roboczy w repo, poza iCloud
  * flaga `source: "preview_mixed"` — bo próbka pochodzi z wersji ZMIKSOWANEJ,
    nie z oryginalnego wydania utworu. Kto później zestawi to z wektorami
    biblioteki (5 okien z całego pliku) albo korpusu, ma prawo o tym wiedzieć.
    Ta różnica raz już zawyżyła wynik — patrz przeciek źródła wektora, 02.08.

Utwory oznaczone „ID" są niezidentyfikowane przez wydawcę, ALE mają audio,
więc wektor liczy się dla nich normalnie. Model nie potrzebuje tytułu,
potrzebuje brzmienia.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

HERE = pathlib.Path(__file__).parent
META = HERE / "utwory_meta.json"
OUT = ROOT / "data/reports/applemix_embeddings.json"
TMP = ROOT / "experiments_priv/_cache/applemix_previews"
UA = {"User-Agent": "DanceLab-research/1.0 (local, non-commercial)"}
SCHEMA = "applemix-embeddings-v1"


def main() -> int:
    import torch
    from transformers import ClapModel, ClapProcessor
    from library_e_embeddings import MODEL_ID, embed_track

    meta = json.loads(META.read_text())
    want = {k: v for k, v in meta.items() if v and v.get("preview")}
    done = json.loads(OUT.read_text())["tracks"] if OUT.exists() else {}
    todo = [k for k in want if k not in done]
    print(f"utworów z próbką: {len(want)} · policzonych: {len(done)} · "
          f"do zrobienia: {len(todo)}", flush=True)
    if not todo:
        print("nic do roboty")
        return 0

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"ładuję CLAP na {device}…", flush=True)
    model = ClapModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(MODEL_ID)
    TMP.mkdir(parents=True, exist_ok=True)

    ok = fail = 0
    for n, tid in enumerate(todo, 1):
        rec = want[tid]
        f = TMP / f"{tid}.m4a"
        try:
            req = urllib.request.Request(rec["preview"], headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r, f.open("wb") as fh:
                fh.write(r.read())
            vec = embed_track(f, model, processor, device)
        except Exception as e:
            print(f"  ⚠ {tid}: {type(e).__name__}", flush=True)
            vec = None
        finally:
            f.unlink(missing_ok=True)          # audio nie zostaje NIGDY

        if vec is None:
            fail += 1
            continue
        done[tid] = {"vector": vec, "artist": rec.get("artist"),
                     "track": rec.get("track"), "genre": rec.get("genre"),
                     "source": "preview_mixed", "preview_sec": 30}
        ok += 1
        if ok % 100 == 0:
            OUT.write_text(json.dumps(
                {"schema_version": SCHEMA, "model": MODEL_ID,
                 "note": "wektory z 30-sekundowych próbek WERSJI ZMIKSOWANYCH; "
                         "audio skasowane po przeliczeniu",
                 "tracks": done}, ensure_ascii=False))
            print(f"  {n}/{len(todo)} · policzone {ok} · błędy {fail}", flush=True)

    OUT.write_text(json.dumps(
        {"schema_version": SCHEMA, "model": MODEL_ID,
         "note": "wektory z 30-sekundowych próbek WERSJI ZMIKSOWANYCH; "
                 "audio skasowane po przeliczeniu",
         "tracks": done}, ensure_ascii=False))
    left = list(TMP.glob("*.m4a"))
    print(f"\n  gotowe: {len(done)} wektorów · błędy {fail} · "
          f"plików audio pozostawionych: {len(left)}")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

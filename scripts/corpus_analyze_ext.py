"""Cechy dla CAŁEGO korpusu — tempo, tonacja, energia dla ~12,7 tys. utworów.

Po co: benchmark przejść w trudności produktu (cała biblioteka jako kandydaci,
nie 20 utworów z jednego miksu) wymaga cech dla każdego utworu, który w korpusie
występuje. Dziś ma je 2881 — zamrożony zbiór Korda pod bramkę. Reszta, ~9,8 tys.,
leży na dysku z policzonym CLAP-em, ale bez BPM i tonacji, więc nie da się jej
użyć do niczego, co porównuje pary.

Dlaczego własna, chuda ścieżka zamiast `analyze_track`:

  * pełny pipeline liczy 108 s na utwór (zmierzone) — 293 godziny na resztę
    korpusu. Wąskim gardłem NIE jest analiza, tylko dekodowanie webm przez
    wolną ścieżkę loadera.
  * ffmpeg dekoduje ten sam plik w 1,6 s. Sztywna siatka 10,7 s, tonacja 2,5 s.
    Razem 14,8 s — siedem razy szybciej, a do benchmarku potrzeba dokładnie
    tych trzech liczb: tempa, tonacji w Camelocie i energii.
  * segmenty, wokal i stemy są tu niepotrzebne i to one kosztują najwięcej.

Wznawialne: wyniki dopisywane do JSONL po każdym utworze, przy starcie
wczytywane i pomijane. Ubicie procesu w połowie nie kosztuje nic poza
utworem w locie. Postęp leci do `status.json` (dla podglądu na żywo)
i do logu.

To NIE rusza zamrożonego zbioru 2881 — pisze do osobnego pliku, więc
aparatura bramki Korda zostaje nietknięta.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import pathlib
import subprocess
import tempfile
import time

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACKS = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/tracks")
EMB = ROOT / "data/reports/corpus_embeddings_full.json"
FROZEN = ROOT / "data/reports/corpus_ordering/analysis_index.json"
OUT_DIR = ROOT / "data/reports/corpus_features_ext"
OUT = OUT_DIR / "features.jsonl"
STATUS = OUT_DIR / "status.json"

SR = 22050


def analyse_one(path: pathlib.Path) -> dict:
    """Trzy liczby, których potrzebuje scoring. Nic więcej."""
    from dancelab.core.rigid_grid import fit_rigid_grid
    from dancelab.features.key import estimate_key

    tmp = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                        "-ac", "1", "-ar", str(SR), tmp],
                       check=True, capture_output=True, timeout=180)
        y, sr = sf.read(tmp, dtype="float32")
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)

    if y.size < sr * 30:
        return {"id": path.stem, "error": "krótszy niż 30 s"}

    g = fit_rigid_grid(y, sr)
    name, camelot, conf = estimate_key(y, sr)
    # energia: RMS w oknach 1 s, mediana — odporna na intro i ciszę
    w = sr
    n = (len(y) // w) * w
    rms = np.sqrt((y[:n].reshape(-1, w) ** 2).mean(axis=1)) if n else np.array([0.0])
    return {
        "id": path.stem,
        "bpm": float(g.bpm) if g else None,
        "grid_contrast": float(g.contrast) if g else None,
        "grid_snapped": bool(g.snapped_to_musical) if g else None,
        "key_name": name,
        "camelot": camelot,
        "key_conf": float(conf),
        "energy": float(np.median(rms)),
        "duration_sec": float(len(y) / sr),
    }


def worker(path_str: str) -> dict:
    try:
        return analyse_one(pathlib.Path(path_str))
    except Exception as exc:                                   # noqa: BLE001
        return {"id": pathlib.Path(path_str).stem,
                "error": f"{type(exc).__name__}: {exc}"[:120]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) - 2))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    emb = set(json.loads(EMB.read_text())["tracks"])
    frozen = set(json.loads(FROZEN.read_text()).get("tracks", {}))
    done: set[str] = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:                                  # noqa: BLE001
                pass

    avail = {}
    for f in TRACKS.iterdir():
        if f.suffix.lower() in (".webm", ".m4a", ".mp4", ".opus", ".ogg"):
            avail[f.stem] = str(f)

    # KOLEJNOŚĆ WEDŁUG OPŁACALNOŚCI, nie alfabetu. Zewnętrzny dysk daje
    # 3,3 utworu na minutę (wąskie gardło to I/O, nie procesor — 8 wątków
    # liczy tyle samo co 4), czyli cały korpus to 49 h. Ale przejście da się
    # policzyć dopiero, gdy OBIE strony pary mają cechy, więc opłaca się
    # najpierw domykać miksy, którym brakuje najmniej. Zmierzone: pierwsze
    # 500 utworów odblokowuje 2220 par (13 % korpusu, ale 9× więcej niż
    # 28 przejść Janka), pierwsze 1000 — 3304 pary.
    mixes = json.loads(pathlib.Path(
        "/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json").read_text())
    rows = []
    for m in mixes:
        ids = [t.get("id") for t in (m.get("tracklist") or [])
               if t.get("id") in emb and t.get("id") in avail]
        if len(ids) < 2:
            continue
        miss = [i for i in ids if i not in frozen and i not in done]
        rows.append(((len(miss) / max(len(ids) - 1, 1)), miss))
    rows.sort(key=lambda r: r[0])

    todo, seen = [], set()
    for _, miss in rows:
        for i in miss:
            if i not in seen:
                seen.add(i)
                todo.append(avail[i])
    if args.limit:
        todo = todo[: args.limit]

    total = len(todo)
    print(f"korpus: {len(emb)} z CLAP · gotowe wcześniej {len(frozen)} (Kord) "
          f"+ {len(done)} (my) · DO ZROBIENIA {total}", flush=True)
    if not total:
        return 0

    t0 = time.time()
    okc = errc = 0
    with OUT.open("a") as fh, mp.Pool(args.workers) as pool:
        for i, res in enumerate(pool.imap_unordered(worker, todo, chunksize=4), 1):
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            if res.get("error"):
                errc += 1
            else:
                okc += 1
            el = time.time() - t0
            rate = i / el
            eta = (total - i) / rate if rate else 0
            STATUS.write_text(json.dumps({
                "zrobione": i, "wszystkie": total,
                "ok": okc, "bledy": errc,
                "tempo_utw_min": round(rate * 60, 1),
                "minelo_min": round(el / 60, 1),
                "zostalo_min": round(eta / 60, 1),
                "ostatni": res.get("id"),
                "ostatni_bpm": res.get("bpm"),
                "ostatni_key": res.get("camelot"),
                "aktualizacja": time.strftime("%H:%M:%S"),
            }, ensure_ascii=False))
            if i % 25 == 0 or i == total:
                print(f"  {i}/{total} · {rate * 60:.1f} utw/min · "
                      f"zostało {eta / 60:.0f} min · błędy {errc}", flush=True)
    print(f"\nGOTOWE: {okc} policzonych, {errc} błędów, "
          f"{(time.time() - t0) / 3600:.1f} h", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

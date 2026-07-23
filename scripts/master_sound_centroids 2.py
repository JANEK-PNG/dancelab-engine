"""Master sound centroids — the sound signature of each corpus DJ.

For every DJ profiled by the style harvester: collect the youtube IDs of the
tracks they actually played (djmix-dataset tracklists), look up their CLAP
vectors in the FULL corpus catalogue (12,668), and store the L2-normalised
mean as the DJ's sound centroid. This is the measured "sounds like [master]"
foundation for the inspiration board — evidence-backed, per CORPUS_ETHICS
(features only, corpus audio never plays).

Proof-of-consumer demo included: nearest corpus tracks per master + a
master↔master similarity matrix (genres must separate or the centroid is noise).

Usage: PYTHONPATH=src python3 scripts/master_sound_centroids.py [--min-tracks 10]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
FULL_EMB = ROOT / "data/reports/corpus_embeddings_full.json"
OUT = ROOT / "data/reports/master_centroids.json"

_DATE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*[-–]?\s*")


def dj_of(title: str) -> str:
    t = _DATE.sub("", title or "")
    t = re.split(r"\s@\s|\bBoiler Room\b|\bEssential Mix\b|\blive at\b|\b@\b", t, flags=re.I)[0]
    t = re.split(r"\s[-–]\s", t)[0]
    return t.strip().strip("-–").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-tracks", type=int, default=10,
                    help="minimum embedded played-tracks for an honest centroid")
    args = ap.parse_args()

    emb = json.loads(FULL_EMB.read_text())["tracks"]
    print(f"wektorów w pełnym katalogu: {len(emb)}", flush=True)

    data = json.loads(DATASET.read_text())
    by_dj: dict[str, set] = defaultdict(set)
    titles: dict[str, str] = {}
    for mix in data:
        dj = dj_of(mix.get("title", ""))
        if not dj or len(dj) <= 2 or dj[0].isdigit():
            continue
        for tr in mix.get("tracklist") or []:
            tid = tr.get("id") if isinstance(tr, dict) else None
            if not tid:
                continue
            by_dj[dj].add(tid)
            t = tr.get("title", "")
            if t:
                titles[tid] = re.sub(r"^\[\d+\]\s*", "", t)

    centroids: dict[str, dict] = {}
    skipped = 0
    for dj, ids in by_dj.items():
        vecs = [emb[t] for t in ids if t in emb]
        if len(vecs) < args.min_tracks:
            skipped += 1
            continue
        v = np.asarray(vecs, dtype=np.float64).mean(axis=0)
        n = np.linalg.norm(v)
        if not np.isfinite(n) or n <= 1e-9:
            skipped += 1
            continue
        centroids[dj] = {
            "centroid": (v / n).tolist(),
            "n_tracks_embedded": len(vecs),
            "n_tracks_played": len(ids),
        }

    OUT.write_text(json.dumps({
        "schema_version": "master-sound-centroids-v1",
        "source": "djmix-dataset tracklists x corpus_embeddings_full (CLAP)",
        "min_tracks": args.min_tracks,
        "n_masters": len(centroids),
        "masters": centroids,
    }))
    print(f"centroidy: {len(centroids)} mistrzów (≥{args.min_tracks} embedowanych tracków); "
          f"pominięto {skipped} (za mało danych) → {OUT}", flush=True)

    # ── DOWÓD-KONSUMENT ──────────────────────────────────────────────
    demo = [d for d in ("Adam Beyer", "Armin van Buuren", "John B", "Claptone", "Scuba")
            if d in centroids]
    names = list(emb)
    V = np.asarray([emb[n] for n in names])

    for dj in demo[:3]:
        c = np.asarray(centroids[dj]["centroid"])
        sims = V @ c
        top = np.argsort(-sims)[:10]
        print(f"\n🎯 najbliżej brzmienia: {dj} "
              f"({centroids[dj]['n_tracks_embedded']} tracków w centroidzie)")
        for i in top:
            print(f"   {sims[i]:.3f}  {titles.get(names[i], names[i])[:64]}")

    if len(demo) >= 3:
        print("\n=== MACIERZ mistrz↔mistrz (gatunki muszą się rozdzielać) ===")
        print(f"{'':<18}" + "".join(f"{d[:12]:>14}" for d in demo))
        for a in demo:
            ca = np.asarray(centroids[a]["centroid"])
            row = "".join(f"{float(np.asarray(centroids[b]['centroid']) @ ca):>14.3f}" for b in demo)
            print(f"{a[:16]:<18}{row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Digging list — corpus tracks closest to YOUR taste that you DON'T own.

Join: user library CLAP (296) x full corpus CLAP (12,668) + corpus titles.
For every corpus track: similarity to its NEAREST library track ("how close to
your world"). Exclude probable-owned (cosine > 0.985 ≈ same recording).
Output: a shopping list — artist/title only (CORPUS_ETHICS: corpus audio never
plays, no links; you buy it where you buy music).

Usage: PYTHONPATH=src python3 scripts/digging_list.py [--top 30]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIB_EMB = ROOT / "data/reports/library_embeddings.json"
FULL_EMB = ROOT / "data/reports/corpus_embeddings_full.json"
DATASET = Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
OUT = ROOT / "data/reports/digging_list.md"

OWNED_SIM = 0.985  # above this = probably the same recording you already have


def corpus_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    for mix in json.loads(DATASET.read_text()):
        for tr in mix.get("tracklist") or []:
            tid = tr.get("id") if isinstance(tr, dict) else None
            t = tr.get("title", "") if isinstance(tr, dict) else ""
            if tid and t and tid not in titles:
                titles[tid] = re.sub(r"^\[[^\]]*\]\s*", "", t).strip()
    return titles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--anchor", default=None,
                    help="digging wokół kotwicy (substring nazwy pliku z biblioteki); "
                         "bez tego: cała biblioteka")
    ap.add_argument("--seed-neighbors", type=int, default=4,
                    help="ilu sąsiadów kotwicy współtworzy seed-klaster vibe'u")
    args = ap.parse_args()

    lib = json.loads(LIB_EMB.read_text())["tracks"]
    lib_names = list(lib)
    L = np.asarray([lib[n] for n in lib_names])          # [296, 512]
    full = json.loads(FULL_EMB.read_text())["tracks"]
    c_names = list(full)
    C = np.asarray([full[n] for n in c_names])           # [12668, 512]
    titles = corpus_titles()
    print(f"biblioteka: {len(lib_names)} | korpus: {len(c_names)} | tytuły: {len(titles)}", flush=True)

    S = C @ L.T                                           # [corpus, lib]
    top3_lib = np.argsort(-S, axis=1)[:, :3]              # explanation candidates
    best_sim = S.max(axis=1)                              # owned-detection zawsze vs cała biblioteka

    # tryb kotwicy: ranking po centroidzie [kotwica + jej najbliżsi sąsiedzi]
    seed_info = ""
    if args.anchor:
        hits = [i for i, n in enumerate(lib_names) if args.anchor.lower() in n.lower()]
        if not hits:
            raise SystemExit(f"kotwica '{args.anchor}' nie znaleziona w bibliotece")
        a = hits[0]
        neigh = [j for j in np.argsort(-(L @ L[a]))[: args.seed_neighbors + 1] if j != a]
        seed_idx = [a] + [int(j) for j in neigh[: args.seed_neighbors]]
        seed = L[seed_idx].mean(axis=0)
        seed /= np.linalg.norm(seed)
        rank_sim = C @ seed
        seed_info = " · ".join(lib_names[j].split("/")[-1][:36] for j in seed_idx)
        print(f"seed-klaster: {seed_info}", flush=True)
    else:
        rank_sim = best_sim

    HUB_CAP = 2  # max list entries explained by the same library track (anti-hub)
    order = np.argsort(-rank_sim)
    picked: list[tuple[str, float, str]] = []
    seen_titles: set[str] = set()
    seen_vecs: list[np.ndarray] = []
    hub_count: dict[int, int] = {}
    owned_skipped = 0
    for i in order:
        sim = float(rank_sim[i])
        if float(best_sim[i]) > OWNED_SIM:                # probably owned (vs cała biblioteka)
            owned_skipped += 1
            continue
        title = titles.get(c_names[i])
        if not title:                                     # no metadata → can't shop it
            continue
        tkey = re.sub(r"\W+", "", title.lower())[:48]
        if tkey in seen_titles:                           # same title, other rip
            continue
        if any(float(C[i] @ v) > 0.995 for v in seen_vecs):  # near-dup audio
            continue
        # anti-hub: first non-full explanation among top-3 library matches
        lib_idx = next((int(j) for j in top3_lib[i] if hub_count.get(int(j), 0) < HUB_CAP), None)
        if lib_idx is None:
            continue
        picked.append((title, sim, lib_names[lib_idx].split("/")[-1]))
        hub_count[lib_idx] = hub_count.get(lib_idx, 0) + 1
        seen_titles.add(tkey)
        seen_vecs.append(C[i])
        if len(picked) >= args.top:
            break

    out_path = OUT if not args.anchor else OUT.with_name("digging_list_kotwica.md")

    lines = [
        (f"# Digging list — wokół kotwicy: {args.anchor}" if args.anchor else "# Digging list — brzmi jak to, co kochasz, a nie posiadasz"),
        "",
        f"Źródło: {len(c_names)} tracków granych przez realnych DJ-ów (korpus) × Twoja biblioteka ({len(lib_names)}).",
        f"Wykluczone prawdopodobnie-posiadane (cos>{OWNED_SIM}): {owned_skipped}.",
        "Kupujesz tam, gdzie kupujesz muzykę (Bandcamp/Beatport) — audio korpusu nie gra w apce.",
        "",
        "| # | track (z setów realnych DJ-ów) | vibe | bo brzmi jak twój |",
        "|---|---|---|---|",
    ]
    for n, (title, sim, closest) in enumerate(picked, 1):
        lines.append(f"| {n} | {title[:70]} | {sim:.3f} | {closest[:44]} |")
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n=== DIGGING LIST — top {len(picked)} ===")
    for n, (title, sim, closest) in enumerate(picked, 1):
        print(f"{n:>3}. {sim:.3f}  {title[:56]}")
        print(f"        ↳ bo brzmi jak twój: {closest[:52]}")
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

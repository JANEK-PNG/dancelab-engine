"""Priors loop, step 3: does SOUND similarity (CLAP) predict real DJ choices?

Measures the CLAP-cosine distribution of real DJ transitions vs chance pairs
(same method as corpus_priors.py), then re-runs the observation validation with
the measured sound-lift added to the measured scorer. If top1 rises above the
bpm+harmonic measured scorer, sound similarity has EARNED a measured weight in
the engine — no guessing.

Usage: PYTHONPATH=src python3 scripts/corpus_priors_clap.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ALIGN_DIR = Path("/Volumes/MY_PC/DanceLabCorpus/alignments")
EMB = ROOT / "data/reports/corpus_ordering/embeddings.json"
DATASET = ROOT / "data/reports/corpus_ordering/dataset.json"
PRIORS = ROOT / "data/reports/corpus_priors/priors_v1.json"
H_DIR = ROOT / "data/reports/corpus_ordering/h_analysis"
INDEX = ROOT / "data/reports/corpus_ordering/analysis_index.json"
OUT = ROOT / "data/reports/corpus_priors/priors_clap_v1.json"

from dancelab.decision._common import nearest_bpm_variant
from dancelab.decision.harmonic import harmonic_relation

BUCKETS = [(-1.0, 0.6, "<0.60"), (0.6, 0.7, "0.60-0.70"), (0.7, 0.8, "0.70-0.80"),
           (0.8, 0.85, "0.80-0.85"), (0.85, 0.9, "0.85-0.90"), (0.9, 2.0, ">=0.90")]


def bucket(v: float) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= v < hi:
            return name
    return BUCKETS[-1][2]


def load_vectors() -> dict[str, np.ndarray]:
    data = json.loads(EMB.read_text())["tracks"]
    return {k: np.array(v) for k, v in data.items()}


def load_h_features() -> dict[str, dict]:
    idx = json.loads(INDEX.read_text())["tracks"]
    feats: dict[str, dict] = {}
    for yid, rel in idx.items():
        try:
            d = json.loads((H_DIR / rel).read_text())
        except (OSError, json.JSONDecodeError):
            continue
        tr = d.get("track", {})
        feats[yid] = {"bpm": tr.get("bpm_estimate"), "camelot": tr.get("key_estimate")}
    return feats


def real_and_chance_pairs(vec: dict[str, np.ndarray]):
    real: list[float] = []
    pools: list[list[str]] = []
    for path in sorted(ALIGN_DIR.glob("mix*.json")):
        try:
            d = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        sha2yid = {r.get("track_id"): r.get("youtube_id")
                   for r in (d.get("results") or []) if r.get("track_id") and r.get("youtube_id")}
        pool = [y for y in sha2yid.values() if y in vec]
        if len(pool) >= 2:
            pools.append(pool)
        for t in d.get("transitions") or []:
            if not t.get("valid", True):
                continue
            ya, yb = sha2yid.get(t.get("previous_source_id")), sha2yid.get(t.get("next_source_id"))
            if ya in vec and yb in vec:
                real.append(float(vec[ya] @ vec[yb]))
    rng = random.Random(11)
    fake: list[float] = []
    while len(fake) < len(real) and pools:
        pool = rng.choice(pools)
        ya, yb = rng.sample(pool, 2)
        fake.append(float(vec[ya] @ vec[yb]))
    return real, fake


def dist(vals: list[float]) -> dict[str, float]:
    c: dict[str, int] = {}
    for v in vals:
        c[bucket(v)] = c.get(bucket(v), 0) + 1
    tot = len(vals) or 1
    return {name: round(c.get(name, 0) / tot * 100, 1) for _, _, name in BUCKETS}


def main() -> int:
    vec = load_vectors()
    real, fake = real_and_chance_pairs(vec)
    print(f"przejścia z CLAP po obu stronach: {len(real)} | baseline: {len(fake)}", flush=True)

    dr, df = dist(real), dist(fake)
    med_r, med_f = float(np.median(real)), float(np.median(fake))
    clap_lift = {name: round(dr.get(name, 0.1) / max(df.get(name, 0.1), 0.1), 3)
                 for _, _, name in BUCKETS}

    print("\n=== PODOBIEŃSTWO BRZMIENIA przejść: DJ-e vs przypadek ===")
    print(f"{'cosinus CLAP':<12} {'DJ-e':>7} {'losowo':>8} {'lift':>6}")
    for _, _, name in BUCKETS:
        print(f"  {name:<10} {dr.get(name,0):>6}% {df.get(name,0):>7}% {clap_lift[name]:>6}")
    print(f"mediana: DJ-e {med_r:.3f} vs losowo {med_f:.3f}")

    # walidacja: measured(bpm+harm) vs measured+clap na obserwacjach
    p = json.loads(PRIORS.read_text())
    harm_lift = {k: p["camelot_relation_pct"]["real_djs"].get(k, 0.1) /
                    max(p["camelot_relation_pct"]["chance_baseline"].get(k, 0.1), 0.1)
                 for k in set(p["camelot_relation_pct"]["real_djs"]) | set(p["camelot_relation_pct"]["chance_baseline"])}
    bpm_lift = {k: p["bpm_delta_folded_pct"]["real_djs"].get(k, 0.1) /
                   max(p["bpm_delta_folded_pct"]["chance_baseline"].get(k, 0.1), 0.1)
                for k in set(p["bpm_delta_folded_pct"]["real_djs"]) | set(p["bpm_delta_folded_pct"]["chance_baseline"])}
    feats = load_h_features()

    def bpm_bucket(a: float, b: float) -> str:
        v = abs(nearest_bpm_variant(a, b) - a) / a * 100
        return "0-2%" if v < 2 else "2-4%" if v < 4 else "4-6%" if v < 6 else "6-10%" if v < 10 else ">10%"

    def score(a_id: str, b_id: str, use_clap: bool) -> float:
        a, b = feats.get(a_id, {}), feats.get(b_id, {})
        s = 1.0
        if a.get("bpm") and b.get("bpm"):
            s *= bpm_lift.get(bpm_bucket(a["bpm"], b["bpm"]), 1.0)
        if a.get("camelot") and b.get("camelot"):
            try:
                s *= harm_lift.get(harmonic_relation(a["camelot"], b["camelot"]), 1.0)
            except Exception:
                pass
        if use_clap and a_id in vec and b_id in vec:
            s *= clap_lift.get(bucket(float(vec[a_id] @ vec[b_id])), 1.0)
        return s

    def evaluate(use_clap: bool) -> dict:
        obs_list = json.loads(DATASET.read_text())["observations"]
        ranks = []
        for obs in obs_list:
            hist = [t for t in obs.get("history_track_ids", []) if t in feats]
            sel = obs.get("selected_track_id")
            cands = [c for c in obs.get("candidate_track_ids", []) if c in feats]
            if not hist or sel not in cands or len(cands) < 5:
                continue
            scored = sorted(cands, key=lambda c: -score(hist[-1], c, use_clap))
            ranks.append(scored.index(sel) + 1)
        n = len(ranks)
        return {"n": n,
                "top1_pct": round(sum(r == 1 for r in ranks) / n * 100, 1),
                "mrr": round(sum(1 / r for r in ranks) / n, 3)} if n else {"n": 0}

    base, withclap = evaluate(False), evaluate(True)
    print("\n=== WALIDACJA na realnych wyborach DJ-ów ===")
    print(f"  zmierzone bpm+harmonia:        top1 {base['top1_pct']}%  MRR {base['mrr']}  (n={base['n']})")
    print(f"  zmierzone bpm+harmonia+BRZMIENIE: top1 {withclap['top1_pct']}%  MRR {withclap['mrr']}")

    OUT.write_text(json.dumps({
        "schema_version": "corpus-priors-clap-v1",
        "n_real": len(real), "median_real": round(med_r, 4), "median_chance": round(med_f, 4),
        "clap_cosine_pct": {"real_djs": dr, "chance_baseline": df},
        "clap_lift": clap_lift,
        "validation": {"measured_bpm_harm": base, "measured_plus_clap": withclap},
    }, indent=2))
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

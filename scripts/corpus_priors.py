"""Priors loop, step 1: MEASURE what real DJs do across the aligned corpus.

Joins 801 mix alignments (real transitions with cue points) with the H
analysis catalogue (BPM / Camelot key / energy for 2881 tracks) and reports
the empirical distributions the engine's hand-set weights pretend to know:

  - Camelot relation of real transitions (same/adjacent/relative/energy_boost/
    dissonant) — classified with the ENGINE'S OWN harmonic_relation()
  - BPM delta (octave-folded, %) actually bridged by DJs
  - energy delta across the seam
  - transition length in beats

Baseline for contrast: the same stats over RANDOM pairs drawn from the same
mixes' track pools — "DJ choice vs chance". The gap IS the preference signal
that should replace invented weights.

Output: data/reports/corpus_priors/priors_v1.json + stdout summary.
Usage: PYTHONPATH=src python3 scripts/corpus_priors.py
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ALIGN_DIR = Path("/Volumes/MY_PC/DanceLabCorpus/alignments")
H_DIR = ROOT / "data/reports/corpus_ordering/h_analysis"
INDEX = ROOT / "data/reports/corpus_ordering/analysis_index.json"
OUT_DIR = ROOT / "data/reports/corpus_priors"

from dancelab.decision._common import nearest_bpm_variant  # octave-fold
from dancelab.decision.harmonic import harmonic_relation, parse_camelot


def load_h_features() -> dict[str, dict]:
    """youtube_id -> {bpm, camelot, energy} from the H analysis catalogue."""
    idx = json.loads(INDEX.read_text())["tracks"]
    feats: dict[str, dict] = {}
    for yid, rel in idx.items():
        p = H_DIR / rel
        try:
            d = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        tr = d.get("track", {})
        frames = d.get("features") or []
        rms = [f.get("rms") for f in frames if f.get("rms") is not None]
        feats[yid] = {
            "bpm": tr.get("bpm_estimate"),
            "camelot": tr.get("key_estimate"),
            "energy": (sum(rms) / len(rms)) if rms else None,
        }
    return feats


def pair_stats(a: dict, b: dict) -> dict | None:
    """Camelot relation + folded BPM delta + energy delta for one A→B pair."""
    out: dict = {}
    ca, cb = a.get("camelot"), b.get("camelot")
    if ca and cb:
        try:
            parse_camelot(ca), parse_camelot(cb)
            out["relation"] = harmonic_relation(ca, cb)
        except Exception:
            pass
    ba, bb = a.get("bpm"), b.get("bpm")
    if ba and bb:
        folded = nearest_bpm_variant(ba, bb)
        out["bpm_delta_pct"] = abs(folded - ba) / ba * 100
    ea, eb = a.get("energy"), b.get("energy")
    if ea is not None and eb is not None:
        out["energy_delta"] = eb - ea
    return out or None


def main() -> int:
    feats = load_h_features()
    print(f"H features: {len(feats)} tracków", flush=True)

    real: list[dict] = []
    lengths: list[float] = []
    pools: list[list[str]] = []  # per-mix youtube pools for the chance baseline
    n_trans = n_valid = n_joined = 0

    for path in sorted(ALIGN_DIR.glob("mix*.json")):
        try:
            d = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        # sha source_id -> youtube_id
        sha2yid = {}
        for r in d.get("results") or []:
            yid = r.get("youtube_id")
            sid = r.get("track_id")
            if yid and sid:
                sha2yid[sid] = yid
        pool = [y for y in sha2yid.values() if y in feats]
        if len(pool) >= 2:
            pools.append(pool)
        for t in d.get("transitions") or []:
            n_trans += 1
            if not t.get("valid", True):
                continue
            n_valid += 1
            ya = sha2yid.get(t.get("previous_source_id"))
            yb = sha2yid.get(t.get("next_source_id"))
            if not (ya in feats and yb in feats):
                continue
            st = pair_stats(feats[ya], feats[yb])
            if st:
                n_joined += 1
                real.append(st)
                if t.get("transition_length_beats"):
                    lengths.append(t["transition_length_beats"])

    print(f"przejścia: {n_trans} total | valid {n_valid} | join z H: {n_joined}", flush=True)

    # chance baseline: random within-mix pairs, same sample size
    rng = random.Random(11)
    fake: list[dict] = []
    while len(fake) < len(real) and pools:
        pool = rng.choice(pools)
        ya, yb = rng.sample(pool, 2)
        st = pair_stats(feats[ya], feats[yb])
        if st:
            fake.append(st)

    def rel_dist(rows: list[dict]) -> dict[str, float]:
        c = Counter(r["relation"] for r in rows if "relation" in r)
        tot = sum(c.values()) or 1
        return {k: round(v / tot * 100, 1) for k, v in c.most_common()}

    def bpm_hist(rows: list[dict]) -> dict[str, float]:
        vals = [r["bpm_delta_pct"] for r in rows if "bpm_delta_pct" in r]
        if not vals:
            return {}
        bins = {"0-2%": 0, "2-4%": 0, "4-6%": 0, "6-10%": 0, ">10%": 0}
        for v in vals:
            k = "0-2%" if v < 2 else "2-4%" if v < 4 else "4-6%" if v < 6 else "6-10%" if v < 10 else ">10%"
            bins[k] += 1
        tot = len(vals)
        return {k: round(v / tot * 100, 1) for k, v in bins.items()}

    def med(vals: list[float]) -> float | None:
        if not vals:
            return None
        s = sorted(vals)
        return round(s[len(s) // 2], 2)

    # energy prior: bucket by CHANCE-distribution quintiles (scale-free)
    e_real = [r["energy_delta"] for r in real if "energy_delta" in r]
    e_fake = [r["energy_delta"] for r in fake if "energy_delta" in r]
    energy = {}
    if len(e_real) > 100 and len(e_fake) > 100:
        qs = sorted(e_fake)
        edges = [qs[int(len(qs) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
        names = ["duży spadek", "spadek", "płasko", "wzrost", "duży wzrost"]

        def ebucket(v: float) -> str:
            for edge, name in zip(edges, names):
                if v < edge:
                    return name
            return names[-1]

        def edist(vals):
            c = {}
            for v in vals:
                c[ebucket(v)] = c.get(ebucket(v), 0) + 1
            return {n: round(c.get(n, 0) / len(vals) * 100, 1) for n in names}

        dr_e, df_e = edist(e_real), edist(e_fake)
        energy = {
            "quintile_edges": [round(e, 4) for e in edges],
            "real_djs": dr_e, "chance_baseline": df_e,
            "lift": {n: round(dr_e.get(n, 0.1) / max(df_e.get(n, 0.1), 0.1), 3) for n in names},
        }

    report = {
        "schema_version": "corpus-priors-v1",
        "n_transitions_joined": n_joined,
        "n_baseline_pairs": len(fake),
        "camelot_relation_pct": {"real_djs": rel_dist(real), "chance_baseline": rel_dist(fake)},
        "bpm_delta_folded_pct": {"real_djs": bpm_hist(real), "chance_baseline": bpm_hist(fake)},
        "bpm_delta_median": {"real_djs": med([r.get("bpm_delta_pct") for r in real if "bpm_delta_pct" in r]),
                              "chance": med([r.get("bpm_delta_pct") for r in fake if "bpm_delta_pct" in r])},
        "energy_delta_median": {"real_djs": med([r.get("energy_delta") for r in real if "energy_delta" in r]),
                                 "chance": med([r.get("energy_delta") for r in fake if "energy_delta" in r])},
        "energy_delta_quintiles": energy,
        "transition_length_beats_median": med(lengths),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "priors_v1.json").write_text(json.dumps(report, indent=2))

    print("\n=== CO ROBIĄ REALNI DJ-e vs PRZYPADEK ===")
    print(f"{'relacja Camelot':<16} {'DJ-e':>7} {'losowo':>8}")
    keys = set(report["camelot_relation_pct"]["real_djs"]) | set(report["camelot_relation_pct"]["chance_baseline"])
    for k in sorted(keys, key=lambda x: -report["camelot_relation_pct"]["real_djs"].get(x, 0)):
        print(f"  {k:<14} {report['camelot_relation_pct']['real_djs'].get(k, 0):>6}% "
              f"{report['camelot_relation_pct']['chance_baseline'].get(k, 0):>7}%")
    print(f"\n{'ΔBPM (folded)':<16} {'DJ-e':>7} {'losowo':>8}")
    for k in ["0-2%", "2-4%", "4-6%", "6-10%", ">10%"]:
        print(f"  {k:<14} {report['bpm_delta_folded_pct']['real_djs'].get(k, 0):>6}% "
              f"{report['bpm_delta_folded_pct']['chance_baseline'].get(k, 0):>7}%")
    if energy:
        print(f"\n{'Δ energii (kwintyle vs przypadek)':<20} {'DJ-e':>7} {'losowo':>8} {'lift':>6}")
        for name in ["duży spadek", "spadek", "płasko", "wzrost", "duży wzrost"]:
            print(f"  {name:<18} {energy['real_djs'].get(name, 0):>6}% "
                  f"{energy['chance_baseline'].get(name, 0):>7}% {energy['lift'].get(name, 0):>6}")
    print(f"\nmediana ΔBPM: DJ-e {report['bpm_delta_median']['real_djs']}% vs losowo {report['bpm_delta_median']['chance']}%")
    print(f"mediana Δenergii: DJ-e {report['energy_delta_median']['real_djs']} vs losowo {report['energy_delta_median']['chance']}")
    print(f"mediana długości przejścia: {report['transition_length_beats_median']} beatów")
    print(f"\n→ {OUT_DIR/'priors_v1.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Priors loop, step 2: do MEASURED weights predict real DJ choices better?

Head-to-head on the 1604 ordering observations (history + candidates + the
track the DJ ACTUALLY played next):

  scorer A (hand):     engine component functions (bpm_score, harmonic_
                       compatibility) combined with the current hand-set blend
  scorer B (measured): same components re-weighted by corpus likelihood ratios
                       (real-DJ distribution / chance baseline, priors_v1)
  scorer R (random):   shuffle — floor reference

Metric per observation: rank of the DJ's actual pick among candidates when
scored A→candidate from the last history track. Report top-1 / top-5 / MRR /
median rank. No human opinion anywhere in the loop.

Usage: PYTHONPATH=src python3 scripts/priors_validation.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATASET = ROOT / "data/reports/corpus_ordering/dataset.json"
H_DIR = ROOT / "data/reports/corpus_ordering/h_analysis"
INDEX = ROOT / "data/reports/corpus_ordering/analysis_index.json"
PRIORS = ROOT / "data/reports/corpus_priors/priors_v1.json"
OUT = ROOT / "data/reports/corpus_priors/validation_v1.json"

from dancelab.decision._common import nearest_bpm_variant
from dancelab.decision.harmonic import harmonic_compatibility, harmonic_relation
from dancelab.decision.set_builder import bpm_score


def load_h_features() -> dict[str, dict]:
    idx = json.loads(INDEX.read_text())["tracks"]
    feats: dict[str, dict] = {}
    for yid, rel in idx.items():
        try:
            d = json.loads((H_DIR / rel).read_text())
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


def build_lifts() -> tuple[dict[str, float], dict[str, float]]:
    """Likelihood ratios real/chance from priors_v1 — measured preference."""
    p = json.loads(PRIORS.read_text())
    rel_real = p["camelot_relation_pct"]["real_djs"]
    rel_chance = p["camelot_relation_pct"]["chance_baseline"]
    harm_lift = {k: (rel_real.get(k, 0.1) / max(rel_chance.get(k, 0.1), 0.1))
                 for k in set(rel_real) | set(rel_chance)}
    bpm_real = p["bpm_delta_folded_pct"]["real_djs"]
    bpm_chance = p["bpm_delta_folded_pct"]["chance_baseline"]
    bpm_lift = {k: (bpm_real.get(k, 0.1) / max(bpm_chance.get(k, 0.1), 0.1))
                for k in set(bpm_real) | set(bpm_chance)}
    return harm_lift, bpm_lift


def bpm_bucket(bpm_a: float, bpm_b: float) -> str:
    folded = nearest_bpm_variant(bpm_a, bpm_b)
    v = abs(folded - bpm_a) / bpm_a * 100
    return "0-2%" if v < 2 else "2-4%" if v < 4 else "4-6%" if v < 6 else "6-10%" if v < 10 else ">10%"


def score_hand(a: dict, b: dict) -> float:
    """Engine's real component functions, current hand blend (bpm+harmonic+energy)."""
    s = 0.0
    if a["bpm"] and b["bpm"]:
        s += 0.4 * bpm_score(a["bpm"], b["bpm"])
    if a["camelot"] and b["camelot"]:
        try:
            s += 0.4 * harmonic_compatibility(a["camelot"], b["camelot"])
        except Exception:
            pass
    if a["energy"] is not None and b["energy"] is not None:
        s += 0.2 * (1.0 - min(abs(b["energy"] - a["energy"]) * 10, 1.0))
    return s


def score_measured(a: dict, b: dict, harm_lift: dict, bpm_lift: dict) -> float:
    """Naive-Bayes style: product of measured likelihood ratios."""
    s = 1.0
    if a["bpm"] and b["bpm"]:
        s *= bpm_lift.get(bpm_bucket(a["bpm"], b["bpm"]), 1.0)
    if a["camelot"] and b["camelot"]:
        try:
            s *= harm_lift.get(harmonic_relation(a["camelot"], b["camelot"]), 1.0)
        except Exception:
            pass
    return s


def usable_cases(observations, feats, min_cands: int) -> list[tuple[str, list[str], str]]:
    """(last_history_id, candidates, selected) for every observation that can be scored."""
    cases = []
    for obs in observations:
        hist = [t for t in obs.get("history_track_ids", []) if t in feats]
        sel = obs.get("selected_track_id")
        cands = [c for c in obs.get("candidate_track_ids", []) if c in feats]
        if hist and sel in feats and sel in cands and len(cands) >= min_cands:
            cases.append((hist[-1], cands, sel))
    return cases


def ranks_for(cases, feats, scorer) -> list[tuple[int, int]]:
    """(rank_of_actual_pick, n_candidates) per case — pairable across scorers."""
    out = []
    for a_id, cands, sel in cases:
        a = feats[a_id]
        scored = sorted(cands, key=lambda c: -scorer(a, feats[c]))
        out.append((scored.index(sel) + 1, len(cands)))
    return out


def evaluate(cases, feats, scorer) -> dict:
    rr = ranks_for(cases, feats, scorer)
    big = [(r, n) for r, n in rr if n >= 5]
    pct = [(r - 1) / (n - 1) for r, n in rr if n > 1]  # 0=best, random≈0.5
    out = {"n_all": len(rr), "pct_rank_mean": round(sum(pct) / max(len(pct), 1), 3)}
    if big:
        n = len(big)
        out.update({
            "n_ge5": n,
            "top1_pct": round(sum(r == 1 for r, _ in big) / n * 100, 1),
            "mrr": round(sum(1 / r for r, _ in big) / n, 3),
        })
    return out


def paired_bootstrap(cases, feats, scorer_a, scorer_b, iters: int = 3000) -> float:
    """P(scorer_b not better than a) on mean percentile rank, paired over cases."""
    ra = ranks_for(cases, feats, scorer_a)
    rb = ranks_for(cases, feats, scorer_b)
    diffs = [((a_r - 1) / (a_n - 1)) - ((b_r - 1) / (b_n - 1))
             for (a_r, a_n), (b_r, b_n) in zip(ra, rb) if a_n > 1]
    rng = random.Random(3)
    n = len(diffs)
    worse = 0
    for _ in range(iters):
        s = sum(diffs[rng.randrange(n)] for _ in range(n)) / n
        if s <= 0:
            worse += 1
    return worse / iters


def main() -> int:
    feats = load_h_features()
    observations = json.loads(DATASET.read_text())["observations"]
    harm_lift, bpm_lift = build_lifts()
    print(f"obserwacje: {len(observations)} | H features: {len(feats)}", flush=True)
    print("lifty harmoniczne:", {k: round(v, 2) for k, v in sorted(harm_lift.items())})
    print("lifty BPM:", {k: round(v, 2) for k, v in sorted(bpm_lift.items())})

    cases = usable_cases(observations, feats, min_cands=2)
    print(f"użyteczne obserwacje (≥2 kandydatów, historia, pokrycie H): {len(cases)} z {len(observations)}")

    rng = random.Random(7)
    measured = lambda a, b: score_measured(a, b, harm_lift, bpm_lift)  # noqa: E731
    res = {
        "hand_weights": evaluate(cases, feats, score_hand),
        "measured_priors": evaluate(cases, feats, measured),
        "random_floor": evaluate(cases, feats, lambda a, b: rng.random()),
    }
    p_boot = paired_bootstrap(cases, feats, score_hand, measured)
    res["p_measured_beats_hand"] = round(p_boot, 4)

    OUT.write_text(json.dumps({"schema_version": "priors-validation-v2", **res,
                               "harm_lift": harm_lift, "bpm_lift": bpm_lift}, indent=2))

    print("\n=== KTO PRZEWIDUJE REALNY WYBÓR DJ-a ===")
    print("percentyl rangi: 0=zawsze pierwszy strzał, 0.5=losowo — wszystkie obserwacje")
    print(f"{'scorer':<18} {'n_all':>6} {'percentyl':>10} {'| n≥5':>6} {'top1':>6} {'MRR':>6}")
    for name, r in [("wagi ręczne", res["hand_weights"]),
                    ("wagi ZMIERZONE", res["measured_priors"]),
                    ("losowo (podłoga)", res["random_floor"])]:
        print(f"{name:<18} {r['n_all']:>6} {r['pct_rank_mean']:>10} "
              f"{r.get('n_ge5','–'):>6} {str(r.get('top1_pct','–')):>5}% {r.get('mrr','–'):>6}")
    print(f"\nparowany bootstrap (zmierzone vs ręczne): p = {p_boot:.4f} "
          f"({'ISTOTNE' if p_boot < 0.05 else 'nieistotne'} przy α=0.05)")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

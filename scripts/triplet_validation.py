"""Triplet thesis, step 1: does knowing C (the NEXT track) help predict B?

Janek's thesis (voice session 2026-08-08, archived in docs/BADANIA_2026-08-08):
the middle track is a BRIDGE — B is defined by how it connects a fixed A and
a fixed C, not just by what follows A. Hide-B test on the same ordering
observations as priors_validation v2, so numbers are directly comparable:

  pair (hand / measured):     score(A→B')                — what the engine does
  triplet (hand / measured):  score(A→B') ⊗ score(B'→C)  — the thesis
  future-only:                score(B'→C)                — control: is it C
                                                           doing all the work?
  random:                     floor

Only observations where the DJ's actual NEXT pick (C) exists are used, and
every scorer runs on that SAME subset — an honest paired race. Metric:
rank percentile (0=best, 0.5=random) over all cases; top-1/MRR on n≥5;
plus "interchangeable top-1" (exact hit OR same Camelot + folded ΔBPM ≤4%
— the MIREX-style partial credit from the thesis).

Usage: PYTHONPATH=src python3 scripts/triplet_validation.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import priors_validation as pv  # noqa: E402 — wspólny harness pomiaru

from dancelab.decision._common import nearest_bpm_variant  # noqa: E402

DATASET = ROOT / "data/reports/corpus_ordering/dataset.json"
OUT = ROOT / "data/reports/corpus_priors/triplet_v1.json"


def triplet_cases(observations, feats, min_cands: int):
    """(A, kandydaci, B*, C) — tylko obserwacje z ZNANYM następnikiem C.

    C = faktyczny wybór DJ-a na pozycji+1 tego samego przebiegu. C != B*
    (duplikat oznaczałby zdegenerowany przypadek).

    PUŁAPKA (złapana w pierwszym biegu): kandydaci w tym datasecie to utwory,
    które DOPIERO zagrają — więc C jest wśród nich, a scorer tripletowy daje
    kandydatowi „C" idealne przejście C→C i systematycznie wygrywa nim nad
    prawdziwym B. W teście „ukryj B" C jest USTALONE, więc wylatuje z puli —
    dla WSZYSTKICH scorerów tak samo (uczciwy, parowany wyścig)."""
    nastepny = {}
    for o in observations:
        nastepny[(o.get("run_id"), o.get("position"))] = o.get(
            "selected_track_id")
    cases = []
    for o in observations:
        hist = [t for t in o.get("history_track_ids", []) if t in feats]
        sel = o.get("selected_track_id")
        c_next = nastepny.get((o.get("run_id"), o.get("position", -1) + 1))
        cands = [c for c in o.get("candidate_track_ids", [])
                 if c in feats and c != c_next]
        if (hist and sel in feats and sel in cands and len(cands) >= min_cands
                and c_next and c_next in feats and c_next != sel):
            cases.append((hist[-1], cands, sel, c_next))
    return cases


def ranks_for3(cases, feats, scorer3):
    """(ranga faktycznego B*, liczba kandydatów, top1_id, B*) na przypadek."""
    out = []
    for a_id, cands, sel, c_id in cases:
        a, c = feats[a_id], feats[c_id]
        scored = sorted(cands, key=lambda t: -scorer3(a, feats[t], c))
        out.append((scored.index(sel) + 1, len(cands), scored[0], sel))
    return out


def wymienny(feats, top1: str, sel: str) -> bool:
    """Punktacja częściowa z tezy: trafienie dokładne ALBO „muzycznie
    wymienny" — ta sama tonacja Camelot i złożone ΔBPM ≤ 4%."""
    if top1 == sel:
        return True
    t, s = feats[top1], feats[sel]
    if not (t["camelot"] and s["camelot"] and t["bpm"] and s["bpm"]):
        return False
    if t["camelot"] != s["camelot"]:
        return False
    folded = nearest_bpm_variant(s["bpm"], t["bpm"])
    return abs(folded - s["bpm"]) / s["bpm"] * 100 <= 4.0


def evaluate3(cases, feats, scorer3) -> dict:
    rr = ranks_for3(cases, feats, scorer3)
    pct = [(r - 1) / (n - 1) for r, n, _, _ in rr if n > 1]
    big = [(r, n) for r, n, _, _ in rr if n >= 5]
    out = {
        "n_all": len(rr),
        "pct_rank_mean": round(sum(pct) / max(len(pct), 1), 3),
        "top1_wymienny_pct": round(
            sum(wymienny(feats, t1, sel) for _, _, t1, sel in rr)
            / max(len(rr), 1) * 100, 1),
    }
    if big:
        n = len(big)
        out.update({
            "n_ge5": n,
            "top1_pct": round(sum(r == 1 for r, _ in big) / n * 100, 1),
            "mrr": round(sum(1 / r for r, _ in big) / n, 3),
        })
    return out


def paired_bootstrap3(cases, feats, scorer_a, scorer_b, iters=3000) -> float:
    """P(scorer_b nie lepszy niż a) na średnim percentylu rangi, parowane."""
    ra = ranks_for3(cases, feats, scorer_a)
    rb = ranks_for3(cases, feats, scorer_b)
    diffs = [((a_r - 1) / (a_n - 1)) - ((b_r - 1) / (b_n - 1))
             for (a_r, a_n, _, _), (b_r, b_n, _, _) in zip(ra, rb) if a_n > 1]
    rng = random.Random(3)
    n = len(diffs)
    worse = 0
    for _ in range(iters):
        s = sum(diffs[rng.randrange(n)] for _ in range(n)) / n
        if s <= 0:
            worse += 1
    return worse / iters


def cases_z_dystraktorami(cases, feats, ile: int = 24, seed: int = 11):
    """Bieg 2 — pula 25: prawdziwy B* + `ile` losowych dystraktorów z całego
    korpusu H. Teza mówi o wypełnianiu luki wśród WIELU możliwości; pula
    wewnątrz-miksowa (~3,5 kandydata, sami pasujący) jest za ciasna, żeby
    most A—C miał czym różnicować. Dystraktory deterministyczne (seed)."""
    wszystkie = sorted(feats)
    rng = random.Random(seed)
    out = []
    for a_id, _, sel, c_id in cases:
        zakaz = {a_id, sel, c_id}
        dys = []
        while len(dys) < ile:
            t = wszystkie[rng.randrange(len(wszystkie))]
            if t not in zakaz:
                dys.append(t)
                zakaz.add(t)
        out.append((a_id, [sel, *dys], sel, c_id))
    return out


def main() -> int:
    feats = pv.load_h_features()
    observations = json.loads(DATASET.read_text())["observations"]
    harm_lift, bpm_lift = pv.build_lifts()
    cases = triplet_cases(observations, feats, min_cands=2)
    print(f"obserwacje: {len(observations)} | z ZNANYM C i pokryciem cech: "
          f"{len(cases)}", flush=True)
    if not cases:
        print("brak przypadków — nie ma czego mierzyć")
        return 1

    def m(a, b):
        return pv.score_measured(a, b, harm_lift, bpm_lift)

    rng = random.Random(7)
    scorers = {
        "para (ręczne)": lambda a, b, c: pv.score_hand(a, b),
        "para (zmierzone)": lambda a, b, c: m(a, b),
        "TRIPLET (ręczne)": lambda a, b, c: pv.score_hand(a, b)
        + pv.score_hand(b, c),
        "TRIPLET (zmierzone)": lambda a, b, c: m(a, b) * m(b, c),
        "tylko przyszłość": lambda a, b, c: m(b, c),
        "losowo (podłoga)": lambda a, b, c: rng.random(),
    }
    def tabela(nazwa, przypadki):
        res = {n: evaluate3(przypadki, feats, s) for n, s in scorers.items()}
        p_hand = paired_bootstrap3(przypadki, feats,
                                   scorers["para (ręczne)"],
                                   scorers["TRIPLET (ręczne)"])
        p_meas = paired_bootstrap3(przypadki, feats,
                                   scorers["para (zmierzone)"],
                                   scorers["TRIPLET (zmierzone)"])
        print(f"\n=== {nazwa} ===")
        print("percentyl rangi: 0=zawsze pierwszy strzał, 0.5=losowo")
        print(f"{'scorer':<22} {'n':>5} {'percentyl':>10} {'wymienny':>9} "
              f"{'| n≥5':>6} {'top1':>6} {'MRR':>6}")
        for n, r in res.items():
            print(f"{n:<22} {r['n_all']:>5} {r['pct_rank_mean']:>10} "
                  f"{r['top1_wymienny_pct']:>8}% {r.get('n_ge5', '–'):>6} "
                  f"{str(r.get('top1_pct', '–')):>5}% {r.get('mrr', '–'):>6}")
        print(f"parowany bootstrap (triplet vs para): "
              f"ręczne p={p_hand:.4f} · zmierzone p={p_meas:.4f}")
        return {"results": res, "p_triplet_beats_pair_hand": round(p_hand, 4),
                "p_triplet_beats_pair_measured": round(p_meas, 4)}

    bieg1 = tabela("BIEG 1 · pula wewnątrz-miksowa (jak priors v2)", cases)
    cases25 = cases_z_dystraktorami(cases, feats)
    bieg2 = tabela("BIEG 2 · pula 25 (B* + 24 dystraktory z korpusu)", cases25)

    OUT.write_text(json.dumps({
        "schema_version": "triplet-validation-v1",
        "n_cases": len(cases),
        "bieg1_pula_miksowa": bieg1,
        "bieg2_pula_25": bieg2,
    }, indent=2))
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

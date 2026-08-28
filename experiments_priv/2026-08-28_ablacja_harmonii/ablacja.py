"""Ablation: does harmony carry any information about what the DJ played next?

Reuses the scorers and metrics from scripts/priors_validation.py unchanged and
removes one component at a time, on the 1604 corpus observations that record
both the pick and the candidates that were passed over.

Threshold and sanity checks registered beforehand: see HIPOTEZA.md.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from priors_validation import (  # noqa: E402
    DATASET,
    bpm_bucket,
    build_lifts,
    evaluate,
    load_h_features,
    paired_bootstrap,
    usable_cases,
)

from dancelab.decision.harmonic import (  # noqa: E402
    harmonic_compatibility,
    harmonic_relation,
)
from dancelab.decision.set_builder import bpm_score  # noqa: E402

WYNIK = Path(__file__).parent / "wynik.json"


def hand(a, b, *, tempo=True, harmonia=True):
    """score_hand with components switchable off; weights untouched."""
    s = 0.0
    if tempo and a["bpm"] and b["bpm"]:
        s += 0.4 * bpm_score(a["bpm"], b["bpm"])
    if harmonia and a["camelot"] and b["camelot"]:
        try:
            # .harmonic_compatibility_score — the function returns a result
            # object; multiplying it raised TypeError into the except below and
            # made this component invisible. Same bug this script was written
            # to find, faithfully copied from the original.
            s += 0.4 * harmonic_compatibility(
                a["camelot"], b["camelot"]
            ).harmonic_compatibility_score
        except Exception:
            pass
    if a["energy"] is not None and b["energy"] is not None:
        s += 0.2 * (1.0 - min(abs(b["energy"] - a["energy"]) * 10, 1.0))
    return s


def measured(a, b, hl, bl, *, tempo=True, harmonia=True):
    """score_measured with components switchable off."""
    s = 1.0
    if tempo and a["bpm"] and b["bpm"]:
        s *= bl.get(bpm_bucket(a["bpm"], b["bpm"]), 1.0)
    if harmonia and a["camelot"] and b["camelot"]:
        try:
            s *= hl.get(harmonic_relation(a["camelot"], b["camelot"]), 1.0)
        except Exception:
            pass
    return s


def main() -> int:
    feats = load_h_features()
    obs = json.loads(DATASET.read_text())["observations"]
    cases = usable_cases(obs, feats, min_cands=2)
    hl, bl = build_lifts()
    print(f"przypadków: {len(cases)}  (z >=5 kandydatami: "
          f"{sum(1 for _, c, _ in cases if len(c) >= 5)})\n")

    rng = random.Random(7)
    warianty = {
        "pelny":        (lambda a, b: hand(a, b),
                         lambda a, b: measured(a, b, hl, bl)),
        "bez_harmonii": (lambda a, b: hand(a, b, harmonia=False),
                         lambda a, b: measured(a, b, hl, bl, harmonia=False)),
        "bez_tempa":    (lambda a, b: hand(a, b, tempo=False),
                         lambda a, b: measured(a, b, hl, bl, tempo=False)),
        "losowy":       (lambda a, b: rng.random(), lambda a, b: rng.random()),
    }

    wynik: dict = {"n_cases": len(cases), "reczne": {}, "mierzone": {}}
    for nazwa, (fh, fm) in warianty.items():
        wynik["reczne"][nazwa] = evaluate(cases, feats, fh)
        wynik["mierzone"][nazwa] = evaluate(cases, feats, fm)

    # Paired bootstrap against the full model: p = P(ablated is NOT worse).
    # A small p means removing the component genuinely hurt.
    for rodzaj, idx in (("reczne", 0), ("mierzone", 1)):
        pelny = warianty["pelny"][idx]
        for nazwa in ("bez_harmonii", "bez_tempa", "losowy"):
            p = paired_bootstrap(cases, feats, warianty[nazwa][idx], pelny)
            wynik[rodzaj][nazwa]["p_nie_gorszy_od_pelnego"] = round(p, 4)

    WYNIK.write_text(json.dumps(wynik, ensure_ascii=False, indent=2))

    for rodzaj in ("reczne", "mierzone"):
        print(f"=== wagi {rodzaj}")
        print(f"{'wariant':<15}{'pct_rank':>10}{'top1%':>8}{'mrr':>7}{'p':>9}")
        for nazwa in warianty:
            e = wynik[rodzaj][nazwa]
            p = e.get("p_nie_gorszy_od_pelnego")
            print(f"  {nazwa:<13}{e['pct_rank_mean']:>10}"
                  f"{e.get('top1_pct', 0):>8}{e.get('mrr', 0):>7}"
                  f"{'—' if p is None else p:>9}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Triplet v2 — wyścig na ŚWIEŻYCH sekwencjach z Apple Music (poza korpusem).

Te same scorery i metodologia co scripts/triplet_validation.py (percentyl
rangi, parowany bootstrap), ale przypadki hide-B budowane z tracklist żniw:
A/B*/C = pozycje i-1/i/i+1 realnego miksu, pula = B* + 24 dystraktory
z całych żniw. Cechy z analiz preview (TEN SAM silnik co korpus H).
Świeże dane = zero przecieku z tuningu priors (lifty mierzone na korpusie,
walidacja na Apple)."""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import priors_validation as pv  # noqa: E402
import triplet_validation as tv  # noqa: E402

KATALOG = pathlib.Path(__file__).parent
ANALIZY = KATALOG / "analizy"
TRACKLISTY = KATALOG / "tracklisty"
OUT = KATALOG / "triplet_v2_wynik.json"


def cechy() -> dict[str, dict]:
    feats = {}
    for p in ANALIZY.glob("*.json"):
        d = json.loads(p.read_text())
        tr = d.get("track", {})
        frames = d.get("features") or []
        rms = [f.get("rms") for f in frames if f.get("rms") is not None]
        feats[p.stem] = {
            "bpm": tr.get("bpm_estimate"),
            "camelot": tr.get("key_estimate"),
            "energy": (sum(rms) / len(rms)) if rms else None,
        }
    return feats


def przypadki(feats, ile_dystraktorow=24, seed=11):
    rng = random.Random(seed)
    wszystkie = sorted(feats)
    cases = []
    for plik in sorted(TRACKLISTY.glob("*.json")):
        cid = plik.stem
        lista = sorted(json.loads(plik.read_text()),
                       key=lambda t: t.get("nr") or 0)
        idki = [f"{cid}-{t['nr']}" for t in lista]
        for i in range(1, len(idki) - 1):
            a, b, c = idki[i - 1], idki[i], idki[i + 1]
            if not all(t in feats for t in (a, b, c)) or c == b:
                continue
            zakaz = {a, b, c}
            dys = []
            while len(dys) < ile_dystraktorow:
                t = wszystkie[rng.randrange(len(wszystkie))]
                if t not in zakaz:
                    dys.append(t)
                    zakaz.add(t)
            cases.append((a, [b, *dys], b, c))
    return cases


def main() -> int:
    feats = cechy()
    harm_lift, bpm_lift = pv.build_lifts()
    cases = przypadki(feats)
    print(f"cechy: {len(feats)} utworów · przypadków hide-B: {len(cases)}")
    if len(cases) < 100:
        print("za mało przypadków — sprawdź analizy")
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
    res = {n: tv.evaluate3(cases, feats, s) for n, s in scorers.items()}
    p_hand = tv.paired_bootstrap3(cases, feats, scorers["para (ręczne)"],
                                  scorers["TRIPLET (ręczne)"])
    p_meas = tv.paired_bootstrap3(cases, feats, scorers["para (zmierzone)"],
                                  scorers["TRIPLET (zmierzone)"])

    OUT.write_text(json.dumps({
        "schema_version": "triplet-v2-apple-v1",
        "n_cases": len(cases), "n_feats": len(feats),
        "results": res,
        "p_triplet_beats_pair_hand": round(p_hand, 4),
        "p_triplet_beats_pair_measured": round(p_meas, 4)}, indent=2))

    print("\n=== TRIPLET v2 · świeże miksy Apple Music (pula 25) ===")
    print(f"{'scorer':<22} {'n':>5} {'percentyl':>10} {'wymienny':>9} "
          f"{'top1':>6} {'MRR':>6}")
    for n, r in res.items():
        print(f"{n:<22} {r['n_all']:>5} {r['pct_rank_mean']:>10} "
              f"{r['top1_wymienny_pct']:>8}% "
              f"{str(r.get('top1_pct', '–')):>5}% {r.get('mrr', '–'):>6}")
    print(f"parowany bootstrap (triplet vs para): ręczne p={p_hand:.4f} · "
          f"zmierzone p={p_meas:.4f}")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

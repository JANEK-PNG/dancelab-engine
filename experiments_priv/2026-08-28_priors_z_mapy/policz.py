"""Measure transition priors on the DJ-map seams, the way the corpus was measured.

Repeats scripts/corpus_priors.py exactly — same engine functions, same
within-mix chance baseline, same buckets — but over the 2304 seams from the
festival map for which we hold an analysis of BOTH tracks. The question is
whether these seams carry a signal of their own or merely repeat the corpus.

Threshold registered before running: see HIPOTEZA.md.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.catalog.db import connect  # noqa: E402
from dancelab.decision._common import nearest_bpm_variant  # noqa: E402
from dancelab.decision.harmonic import harmonic_relation, parse_camelot  # noqa: E402

KORPUS = ROOT / "data/reports/corpus_priors/priors_v1.json"
WYNIK = Path(__file__).parent / "wynik.json"
BUCKETS = ("0-2%", "2-4%", "4-6%", "6-10%", ">10%")


def pair_stats(a: dict, b: dict) -> dict | None:
    """Camelot relation + folded BPM delta for one A→B pair (as in the corpus)."""
    out: dict = {}
    ca, cb = a.get("camelot"), b.get("camelot")
    if ca and cb:
        try:
            parse_camelot(ca)
            parse_camelot(cb)
            out["relation"] = harmonic_relation(ca, cb)
        except Exception:
            pass
    ba, bb = a.get("bpm"), b.get("bpm")
    if ba and bb:
        folded = nearest_bpm_variant(ba, bb)
        out["bpm_delta_pct"] = abs(folded - ba) / ba * 100
    return out or None


def bucket(pct: float) -> str:
    if pct <= 2:
        return "0-2%"
    if pct <= 4:
        return "2-4%"
    if pct <= 6:
        return "4-6%"
    if pct <= 10:
        return "6-10%"
    return ">10%"


def rozklad(rows: list[dict], pole: str) -> dict[str, float]:
    if pole == "relation":
        c = Counter(r["relation"] for r in rows if "relation" in r)
    else:
        c = Counter(bucket(r["bpm_delta_pct"]) for r in rows if "bpm_delta_pct" in r)
    n = sum(c.values()) or 1
    return {k: round(100 * v / n, 2) for k, v in c.items()}


def main() -> int:
    with connect() as conn, conn.cursor() as cur:
        # real: seams whose both sides resolve to an analysis
        cur.execute("""
            SELECT s.szew_id, s.link_setu,
                   aa.bpm, aa.tonacja, ab.bpm, ab.tonacja
            FROM szew s
            JOIN mapowanie ma ON ma.system_zrodlowy='utwor'
                 AND ma.id_zrodlowy=s.utwor_z_id AND ma.system_docelowy='analiza'
            JOIN mapowanie mb ON mb.system_zrodlowy='utwor'
                 AND mb.id_zrodlowy=s.utwor_do_id AND mb.system_docelowy='analiza'
            JOIN analiza aa ON aa.track_id=ma.id_docelowy
            JOIN analiza ab ON ab.track_id=mb.id_docelowy
        """)
        szwy = cur.fetchall()

        # chance pools: tracks that appeared in the same set and have an analysis
        cur.execute("""
            SELECT p.link_setu, a.bpm, a.tonacja
            FROM pozycja_tracklisty p
            JOIN mapowanie m ON m.system_zrodlowy='utwor' AND m.id_zrodlowy=p.utwor_id
                 AND m.system_docelowy='analiza'
            JOIN analiza a ON a.track_id=m.id_docelowy
            WHERE p.link_setu IS NOT NULL
              AND a.bpm IS NOT NULL AND a.tonacja IS NOT NULL
        """)
        pule: dict[str, list[dict]] = {}
        for link, bpm, ton in cur.fetchall():
            pule.setdefault(link, []).append({"bpm": float(bpm), "camelot": ton})

    real: list[dict] = []
    for _sid, _link, bpm_a, ton_a, bpm_b, ton_b in szwy:
        st = pair_stats(
            {"bpm": float(bpm_a) if bpm_a else None, "camelot": ton_a},
            {"bpm": float(bpm_b) if bpm_b else None, "camelot": ton_b},
        )
        if st:
            real.append(st)

    pools = [p for p in pule.values() if len(p) >= 2]
    rng = random.Random(11)
    fake: list[dict] = []
    proby = 0
    while len(fake) < len(real) and pools and proby < len(real) * 50:
        proby += 1
        pool = rng.choice(pools)
        a, b = rng.sample(pool, 2)
        st = pair_stats(a, b)
        if st:
            fake.append(st)

    korpus = json.loads(KORPUS.read_text()) if KORPUS.exists() else {}
    k_harm = (korpus.get("camelot_relation_pct") or {})
    k_bpm = (korpus.get("bpm_delta_folded_pct") or {})

    def lifty(pole: str, klucze) -> dict:
        r, f = rozklad(real, pole), rozklad(fake, pole)
        out = {}
        for k in klucze:
            udzial_r, udzial_f = r.get(k, 0.0), f.get(k, 0.0)
            out[k] = {
                "mapa_real_pct": udzial_r,
                "mapa_chance_pct": udzial_f,
                "lift": round(udzial_r / udzial_f, 3) if udzial_f else None,
                "n_par": sum(
                    1 for x in real
                    if (x.get("relation") == k) if pole == "relation"
                ) if pole == "relation" else sum(
                    1 for x in real
                    if "bpm_delta_pct" in x and bucket(x["bpm_delta_pct"]) == k
                ),
            }
        return out

    relacje = sorted({r["relation"] for r in real if "relation" in r})
    wynik = {
        "n_real": len(real),
        "n_chance": len(fake),
        "n_setow_w_puli": len(pools),
        "harmonia": lifty("relation", relacje),
        "tempo": lifty("bpm_delta_pct", BUCKETS),
        "korpus_dla_porownania": {
            "harmonia_real_pct": k_harm.get("real_djs"),
            "harmonia_chance_pct": k_harm.get("chance_baseline"),
            "tempo_real_pct": k_bpm.get("real_djs"),
            "tempo_chance_pct": k_bpm.get("chance_baseline"),
        },
    }
    WYNIK.write_text(json.dumps(wynik, ensure_ascii=False, indent=2))

    print(f"real: {len(real)} par | chance: {len(fake)} | pul: {len(pools)}\n")
    print(f"{'HARMONIA':<24} {'mapa':>7} {'losowo':>8} {'lift':>7} {'n':>6}")
    for k, v in sorted(wynik["harmonia"].items(), key=lambda x: -(x[1]["lift"] or 0)):
        print(f"  {k:<22} {v['mapa_real_pct']:>6}% {v['mapa_chance_pct']:>7}% "
              f"{str(v['lift']):>7} {v['n_par']:>6}")
    print(f"\n{'TEMPO (ΔBPM)':<24} {'mapa':>7} {'losowo':>8} {'lift':>7} {'n':>6}")
    for k in BUCKETS:
        v = wynik["tempo"][k]
        print(f"  {k:<22} {v['mapa_real_pct']:>6}% {v['mapa_chance_pct']:>7}% "
              f"{str(v['lift']):>7} {v['n_par']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Triplet v3 — domknięcie analizy: split po miksach, rekalibracja liftów,
wagi asymetryczne, trudne pule, rozbicie po gatunkach.

Zasady: strojenie (lifty Apple, α) WYŁĄCZNIE na miksach treningowych;
wszystkie tabele z miksów testowych; parowane bootstrapy na kluczowych
porównaniach. Cechy: te same trzy (BPM, tonacja, energia) co wszędzie."""

import json
import pathlib
import random
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import priors_validation as pv  # noqa: E402
import triplet_validation as tv  # noqa: E402

from dancelab.decision._common import nearest_bpm_variant  # noqa: E402
from dancelab.decision.harmonic import harmonic_relation  # noqa: E402

KAT = pathlib.Path(__file__).parent
OUT = KAT / "triplet_v3_wynik.json"


def cechy():
    feats = {}
    for p in (KAT / "analizy").glob("*.json"):
        d = json.loads(p.read_text())
        tr = d.get("track", {})
        frames = d.get("features") or []
        rms = [f.get("rms") for f in frames if f.get("rms") is not None]
        feats[p.stem] = {"bpm": tr.get("bpm_estimate"),
                         "camelot": tr.get("key_estimate"),
                         "energy": (sum(rms) / len(rms)) if rms else None}
    return feats


def miksy_i_gatunki(feats):
    katalog = json.loads((KAT / "miksy_katalog.json").read_text())
    gatunek_cid = {str(r["collection_id"]): (r.get("gatunek") or "?")
                   for r in katalog.values() if r.get("collection_id")}
    miksy = {}
    for plik in sorted((KAT / "tracklisty").glob("*.json")):
        lista = sorted(json.loads(plik.read_text()),
                       key=lambda t: t.get("nr") or 0)
        idki = [f"{plik.stem}-{t['nr']}" for t in lista]
        if sum(1 for t in idki if t in feats) >= 3:
            miksy[plik.stem] = idki
    return miksy, gatunek_cid


def pary_realne(miksy, feats):
    for idki in miksy.values():
        for a, b in zip(idki, idki[1:]):
            if a in feats and b in feats:
                yield feats[a], feats[b]


def pary_losowe(miksy, feats, rng, ile_na_miks=8):
    for idki in miksy.values():
        obecne = [t for t in idki if t in feats]
        for _ in range(min(ile_na_miks, len(obecne))):
            a, b = rng.sample(obecne, 2)
            yield feats[a], feats[b]


def dopasuj_lifty(miksy, feats, seed=5):
    """Lifty NB liczone NA TRENINGU Apple: rozkład realnych przejść vs
    losowe pary wewnątrz-miksowe (chance)."""
    rng = random.Random(seed)

    def rozklady(pary):
        bpm, harm = defaultdict(int), defaultdict(int)
        n = 0
        for a, b in pary:
            if not (a["bpm"] and b["bpm"] and a["camelot"] and b["camelot"]):
                continue
            bpm[pv.bpm_bucket(a["bpm"], b["bpm"])] += 1
            harm[harmonic_relation(a["camelot"], b["camelot"])] += 1
            n += 1
        return ({k: v / n * 100 for k, v in bpm.items()},
                {k: v / n * 100 for k, v in harm.items()}, n)

    b_real, h_real, n_r = rozklady(pary_realne(miksy, feats))
    b_ch, h_ch, n_c = rozklady(pary_losowe(miksy, feats, rng))
    bpm_lift = {k: b_real.get(k, 0.1) / max(b_ch.get(k, 0.1), 0.1)
                for k in set(b_real) | set(b_ch)}
    harm_lift = {k: h_real.get(k, 0.1) / max(h_ch.get(k, 0.1), 0.1)
                 for k in set(h_real) | set(h_ch)}
    return harm_lift, bpm_lift, n_r, n_c


def przypadki(miksy, feats, tryb, rng, ile=24):
    """hide-B: tryb 'losowa25' = dystraktory z całego katalogu;
    'ten_sam_miks' = pozostałe utwory tego miksu (worek DJ-a)."""
    wszystkie = sorted(feats)
    cases = []
    for mid, idki in miksy.items():
        for i in range(1, len(idki) - 1):
            a, b, c = idki[i - 1], idki[i], idki[i + 1]
            if not all(t in feats for t in (a, b, c)) or c == b:
                continue
            if tryb == "ten_sam_miks":
                pula = [t for t in idki
                        if t in feats and t not in (a, b, c)]
                if len(pula) < 4:
                    continue
                cands = [b, *pula]
            else:
                zakaz = {a, b, c}
                dys = []
                while len(dys) < ile:
                    t = wszystkie[rng.randrange(len(wszystkie))]
                    if t not in zakaz:
                        dys.append(t)
                        zakaz.add(t)
                cands = [b, *dys]
            cases.append((a, cands, b, c, mid))
    return cases


def main() -> int:
    feats = cechy()
    miksy, gatunek_cid = miksy_i_gatunki(feats)
    rng = random.Random(17)
    idy = sorted(miksy)
    rng.shuffle(idy)
    pol = len(idy) // 2
    trening = {m: miksy[m] for m in idy[:pol]}
    test = {m: miksy[m] for m in idy[pol:]}
    print(f"miksy: {len(miksy)} → trening {len(trening)} · test {len(test)}")

    harm_c, bpm_c = pv.build_lifts()                       # korpus
    harm_a, bpm_a, n_r, n_c = dopasuj_lifty(trening, feats)  # Apple-trening
    print(f"lifty Apple: {n_r} par realnych vs {n_c} losowych")

    def m_korpus(a, b):
        return pv.score_measured(a, b, harm_c, bpm_c)

    def m_apple(a, b):
        return pv.score_measured(a, b, harm_a, bpm_a)

    # --- strojenie α NA TRENINGU (ręczne: suma; zmierzone: potęga) ---
    rng_tr = random.Random(23)
    cases_tr = przypadki(trening, feats, "losowa25", rng_tr)

    def ocena(cases, scorer3):
        rr = tv.ranks_for3([c[:4] for c in cases], feats, scorer3)
        pct = [(r - 1) / (n - 1) for r, n, _, _ in rr if n > 1]
        return sum(pct) / max(len(pct), 1)

    def alfa_best(buduj):
        wyniki = {}
        for alfa in (0.25, 0.5, 0.75, 1.0, 1.5):
            wyniki[alfa] = ocena(cases_tr, buduj(alfa))
        best = min(wyniki, key=wyniki.get)
        return best, wyniki

    a_hand, siatka_h = alfa_best(
        lambda alfa: (lambda a, b, c:
                      pv.score_hand(a, b) + alfa * pv.score_hand(b, c)))
    a_meas, siatka_m = alfa_best(
        lambda alfa: (lambda a, b, c: m_apple(a, b) * (m_apple(b, c) ** alfa)))
    print(f"α (trening): ręczne {a_hand} {siatka_h} · zmierzone-Apple "
          f"{a_meas} {siatka_m}")

    rngt = random.Random(7)
    scorery = {
        "para (ręczne)": lambda a, b, c: pv.score_hand(a, b),
        "para (zmierz. korpus)": lambda a, b, c: m_korpus(a, b),
        "para (zmierz. APPLE)": lambda a, b, c: m_apple(a, b),
        "TRIPLET ręczne α=1": lambda a, b, c: pv.score_hand(a, b)
        + pv.score_hand(b, c),
        f"TRIPLET ręczne α={a_hand}": lambda a, b, c: pv.score_hand(a, b)
        + a_hand * pv.score_hand(b, c),
        "TRIPLET zm.APPLE α=1": lambda a, b, c: m_apple(a, b) * m_apple(b, c),
        f"TRIPLET zm.APPLE α={a_meas}": lambda a, b, c: m_apple(a, b)
        * (m_apple(b, c) ** a_meas),
        "losowo": lambda a, b, c: rngt.random(),
    }

    wynik = {"treningowe_miksy": len(trening), "testowe_miksy": len(test),
             "alfa_hand": a_hand, "alfa_measured": a_meas,
             "lifty_apple": {"harm": harm_a, "bpm": bpm_a}}
    for tryb in ("losowa25", "ten_sam_miks"):
        cases = przypadki(test, feats, tryb, random.Random(11))
        print(f"\n=== TEST · pula {tryb} · przypadków {len(cases)} ===")
        print(f"{'scorer':<26} {'percentyl':>10} {'top1':>6} {'MRR':>6}")
        tabela = {}
        cases4 = [c[:4] for c in cases]
        for nazwa, s in scorery.items():
            r = tv.evaluate3(cases4, feats, s)
            tabela[nazwa] = r
            print(f"{nazwa:<26} {r['pct_rank_mean']:>10} "
                  f"{str(r.get('top1_pct', '–')):>5}% {r.get('mrr', '–'):>6}")
        p1 = tv.paired_bootstrap3(cases4, feats,
                                  scorery["para (ręczne)"],
                                  scorery[f"TRIPLET ręczne α={a_hand}"])
        p2 = tv.paired_bootstrap3(cases4, feats,
                                  scorery["para (zmierz. APPLE)"],
                                  scorery[f"TRIPLET zm.APPLE α={a_meas}"])
        print(f"bootstrap: trip-ręczne vs para p={p1:.4f} · "
              f"trip-Apple vs para-Apple p={p2:.4f}")
        wynik[tryb] = {"n": len(cases), "tabela": tabela,
                       "p_hand": round(p1, 4), "p_measured": round(p2, 4)}

    # --- rozbicie po gatunkach (pula losowa25, scorer ręczny) ---
    cases = przypadki(test, feats, "losowa25", random.Random(11))
    po_gatunku = defaultdict(list)
    for case in cases:
        po_gatunku[gatunek_cid.get(case[4].split("-")[0], "?")].append(case)
    print("\n=== gatunki (test, pula losowa25, top1) ===")
    gat_tab = {}
    for g, cs in sorted(po_gatunku.items(), key=lambda x: -len(x[1])):
        if len(cs) < 60:
            continue
        cs4 = [c[:4] for c in cs]
        para = tv.evaluate3(cs4, feats, scorery["para (ręczne)"])
        trip = tv.evaluate3(cs4, feats,
                            scorery[f"TRIPLET ręczne α={a_hand}"])
        gat_tab[g] = {"n": len(cs), "para": para.get("top1_pct"),
                      "triplet": trip.get("top1_pct")}
        print(f"  {g:<14} n={len(cs):>4} · para {para.get('top1_pct')}% "
              f"→ triplet {trip.get('top1_pct')}%")
    wynik["gatunki"] = gat_tab

    OUT.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

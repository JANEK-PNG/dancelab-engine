"""Budowanie setu: PARA vs TRIPLET — sędzia = realne sety DJ-ów.

Zadanie: dostajesz worek utworów jednego realnego miksu (przetasowany)
i prawdziwy utwór otwierający; ułóż resztę. Budowniczy PARA wybiera
kolejny utwór po score(A→B); budowniczy TRIPLET po score(A→B) +
max_C score(B→C) (kandydat musi mieć dokąd pójść — patrzenie w przód
o jeden krok, „najlepszy środek okna"). TEN SAM scorer komponentowy
po obu stronach — mierzymy wyłącznie wpływ STRUKTURY.

Miary względem faktycznej kolejności DJ-a:
* odtworzone pary sąsiadów (kierunkowe) / (n-1);
* tau Kendalla pozycji.
Podłoga: losowa kolejność (seed). Parowany bootstrap po miksach.
"""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import priors_validation as pv  # noqa: E402

KAT = pathlib.Path(__file__).parent
OUT = KAT / "budowa_wynik.json"


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


def buduj_para(start, pula, feats):
    kolej, zostalo = [start], set(pula) - {start}
    while zostalo:
        a = feats[kolej[-1]]
        nast = max(sorted(zostalo), key=lambda t: pv.score_hand(a, feats[t]))
        kolej.append(nast)
        zostalo.discard(nast)
    return kolej


def buduj_triplet(start, pula, feats):
    kolej, zostalo = [start], set(pula) - {start}
    while zostalo:
        a = feats[kolej[-1]]

        def wart(b):
            fb = feats[b]
            reszta = zostalo - {b}
            przod = max((pv.score_hand(fb, feats[c]) for c in reszta),
                        default=0.0)
            return pv.score_hand(a, fb) + przod
        nast = max(sorted(zostalo), key=wart)
        kolej.append(nast)
        zostalo.discard(nast)
    return kolej


def pary_odtworzone(zbudowany, realny):
    realne = set(zip(realny, realny[1:]))
    trafione = sum(1 for p in zip(zbudowany, zbudowany[1:]) if p in realne)
    return trafione / max(len(realny) - 1, 1)


def tau(zbudowany, realny):
    poz = {t: i for i, t in enumerate(realny)}
    a = [poz[t] for t in zbudowany]
    n = len(a)
    zgodne = niezgodne = 0
    for i in range(n):
        for j in range(i + 1, n):
            if a[i] < a[j]:
                zgodne += 1
            else:
                niezgodne += 1
    total = n * (n - 1) / 2
    return (zgodne - niezgodne) / total if total else 0.0


def main() -> int:
    feats = cechy()
    rng = random.Random(29)
    wyniki = []
    for plik in sorted((KAT / "tracklisty").glob("*.json")):
        lista = sorted(json.loads(plik.read_text()),
                       key=lambda t: t.get("nr") or 0)
        realny = [f"{plik.stem}-{t['nr']}" for t in lista]
        realny = [t for t in realny if t in feats]
        if len(realny) < 8:
            continue
        pula = list(realny)
        start = realny[0]
        zb_p = buduj_para(start, pula, feats)
        zb_t = buduj_triplet(start, pula, feats)
        los = [start] + rng.sample(realny[1:], len(realny) - 1)
        wyniki.append({
            "miks": plik.stem, "n": len(realny),
            "pary": {"para": pary_odtworzone(zb_p, realny),
                     "triplet": pary_odtworzone(zb_t, realny),
                     "losowo": pary_odtworzone(los, realny)},
            "tau": {"para": tau(zb_p, realny),
                    "triplet": tau(zb_t, realny),
                    "losowo": tau(los, realny)}})

    def sred(metryka, kto):
        return sum(w[metryka][kto] for w in wyniki) / len(wyniki)

    def bootstrap(metryka, iters=3000):
        d = [w[metryka]["triplet"] - w[metryka]["para"] for w in wyniki]
        r = random.Random(3)
        n = len(d)
        gorzej = sum(1 for _ in range(iters)
                     if sum(d[r.randrange(n)] for _ in range(n)) / n <= 0)
        return gorzej / iters

    print(f"miksów w teście: {len(wyniki)}")
    print(f"{'':<10} {'pary sąsiadów':>14} {'tau Kendalla':>13}")
    for kto in ("para", "triplet", "losowo"):
        print(f"{kto:<10} {sred('pary', kto)*100:>13.1f}% "
              f"{sred('tau', kto):>13.3f}")
    p_pary = bootstrap("pary")
    p_tau = bootstrap("tau")
    print(f"bootstrap triplet>para: pary p={p_pary:.4f} · tau p={p_tau:.4f}")
    OUT.write_text(json.dumps({
        "n_miksow": len(wyniki),
        "srednie": {m: {k: sred(m, k) for k in ("para", "triplet", "losowo")}
                    for m in ("pary", "tau")},
        "p_pary": p_pary, "p_tau": p_tau,
        "per_miks": wyniki}, ensure_ascii=False, indent=1))
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Budowa MIĘDZY FILARAMI: para vs most — ostatnia hipoteza tezy tripletów.

Z realnego seta: filary = co 4. utwór (i ostatni) przybity na prawdziwej
pozycji; segment = utwory, które DJ zagrał między dwoma filarami
(jako worek). Zadanie: ułożyć segment od lewego filara do prawego.

Izolacja czysta: OBIE strony dostają optymalizator DOSKONAŁY (pełny
przegląd permutacji segmentu, cap 6! = 720) i TEN SAM scorer; różnica
wyłącznie w celu:
  PARA:  suma krawędzi PL→x1→…→xk          (nie wie, dokąd zmierza)
  MOST:  suma krawędzi PL→x1→…→xk→PR        (widzi wejście w prawy filar)
Miary: odtworzone krawędzie sąsiedztwa segmentu (w tym obie krawędzie
filarowe) + odsetek segmentów ułożonych DOKŁADNIE. Podłoga losowa.
"""

import itertools
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import priors_validation as pv  # noqa: E402

KAT = pathlib.Path(__file__).parent
OUT = KAT / "budowa_filary_wynik.json"
ROZSTAW = 4
MAKS_SEGMENT = 6


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


def najlepsza_permutacja(pl, worek, pr, feats, z_mostem):
    najlepszy, wynik = None, -1e9
    for perm in itertools.permutations(worek):
        s = pv.score_hand(feats[pl], feats[perm[0]])
        for x, y in zip(perm, perm[1:]):
            s += pv.score_hand(feats[x], feats[y])
        if z_mostem:
            s += pv.score_hand(feats[perm[-1]], feats[pr])
        if s > wynik:
            wynik, najlepszy = s, perm
    return list(najlepszy)


def krawedzie(pl, ulozenie, pr):
    return set(zip([pl, *ulozenie], [*ulozenie, pr]))


def main() -> int:
    feats = cechy()
    rng = random.Random(31)
    segmenty = []
    for plik in sorted((KAT / "tracklisty").glob("*.json")):
        lista = sorted(json.loads(plik.read_text()),
                       key=lambda t: t.get("nr") or 0)
        realny = [f"{plik.stem}-{t['nr']}" for t in lista]
        realny = [t for t in realny if t in feats]
        if len(realny) < ROZSTAW + 2:
            continue
        filary = sorted(set(range(0, len(realny), ROZSTAW))
                        | {len(realny) - 1})
        for a, b in zip(filary, filary[1:]):
            worek = realny[a + 1:b]
            if not 2 <= len(worek) <= MAKS_SEGMENT:
                continue
            segmenty.append((realny[a], worek, realny[b]))

    wyniki = []
    for pl, worek, pr in segmenty:
        realne_kraw = krawedzie(pl, worek, pr)
        n_kraw = len(worek) + 1
        para = najlepsza_permutacja(pl, worek, pr, feats, z_mostem=False)
        most = najlepsza_permutacja(pl, worek, pr, feats, z_mostem=True)
        los = rng.sample(worek, len(worek))
        rekord = {}
        for nazwa, ul in (("para", para), ("most", most), ("losowo", los)):
            traf = len(krawedzie(pl, ul, pr) & realne_kraw)
            rekord[nazwa] = {"kraw": traf / n_kraw,
                             "dokladnie": ul == worek}
        wyniki.append(rekord)

    def sred(kto, pole):
        v = [w[kto][pole] for w in wyniki]
        return sum(v) / len(v)

    def bootstrap(pole, iters=3000):
        d = [w["most"][pole] - w["para"][pole] for w in wyniki]
        r = random.Random(3)
        n = len(d)
        gorzej = sum(1 for _ in range(iters)
                     if sum(d[r.randrange(n)] for _ in range(n)) / n <= 0)
        return gorzej / iters

    print(f"segmentów: {len(wyniki)} (rozstaw filarów {ROZSTAW}, "
          f"worki 2–{MAKS_SEGMENT})")
    print(f"{'':<8} {'krawędzie odtw.':>16} {'segment DOKŁADNIE':>18}")
    for kto in ("para", "most", "losowo"):
        print(f"{kto:<8} {sred(kto, 'kraw')*100:>15.1f}% "
              f"{sred(kto, 'dokladnie')*100:>17.1f}%")
    p_k = bootstrap("kraw")
    p_d = bootstrap("dokladnie")
    print(f"bootstrap most>para: krawędzie p={p_k:.4f} · dokładnie p={p_d:.4f}")
    OUT.write_text(json.dumps({
        "n_segmentow": len(wyniki), "rozstaw": ROZSTAW,
        "srednie": {k: {"kraw": sred(k, "kraw"),
                        "dokladnie": sred(k, "dokladnie")}
                    for k in ("para", "most", "losowo")},
        "p_krawedzie": p_k, "p_dokladnie": p_d},
        ensure_ascii=False, indent=1))
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

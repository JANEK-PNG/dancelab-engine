"""Hide-B: chowamy środkowy utwór trójki i mierzymy, kto go odnajdzie.

POMYSŁ JANKA (2026-08-11): „w każdym miksie usuwać B między tripletami
i mierzyć predykcję programu". Czyli benchmark nie tylko geometrii brzmienia,
ale SAMEGO SILNIKA — na wyborach 869 realnych DJ-ów z mapy.

PROTOKÓŁ (zarejestrowany PRZED policzeniem wektorów, żeby nie dopasowywać
testu do wyniku):
  * trójka A→B→C z jednego setu, wszystkie trzy zmierzone;
  * kandydaci: policzone utwory TEGO SAMEGO setu bez A i C (B wśród nich);
  * trójki z <5 kandydatami odpadają — ranking na 3 nic nie mierzy;
  * miara: percentyl prawdziwego B w rankingu (1,0 = pierwsze miejsce),
    do tego top-1 i top-5; mediana po trójkach;
  * modele PAROWE znają tylko A; modele TRIPLETOWE znają A i C.
    Teza tripletów potwierdzona, jeśli wariant znający C jest wyraźnie
    lepszy od parowego W TEJ SAMEJ rodzinie cech.

MODELE:
  los            — permutacja losowa (podłoga)
  tempo-para     — bpm_score(A→x)                     [silnikowe, z oktawą]
  tempo-triplet  — bpm_score(A→x) · bpm_score(x→C)
  silnik-para    — bpm_score(A→x) · prior_lift(rel(A,x), bpm)   [zubożony*]
  silnik-triplet — to samo w obie strony
  clap-para      — cos(A,x)          [gdy wektory policzone]
  clap-triplet   — cos(A,x) + cos(x,C)

* „zubożony": pełny rdzeń silnika wymaga klatek cech (mixability), których
  mapa nie ma — używamy dokładnie tych funkcji silnika, które działają na
  kolumnach mapy (bpm_score, harmonic_relation, transition_prior_lift).
  To test tej części silnika, nie całości — i tak trzeba to raportować.

Wektory CLAP są z próbek 30 s i porównujemy je TYLKO między sobą
(przeciek źródła, AUC 0,889).

Użycie:
    .venv/bin/python ukryj_b.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
KATALOG = pathlib.Path(__file__).resolve().parent
MIN_KANDYDATOW = 5


def wczytaj():
    utw = {u["utwor_id"]: u for u in
           json.loads((KATALOG / "encje_utwor.json").read_text())}
    szwy = json.loads((KATALOG / "fakty_szew.json").read_text())
    sety = defaultdict(dict)
    for s in szwy:
        if s.get("utwor_z_id"):
            sety[s["set_link"]][s["pozycja_z"]] = s["utwor_z_id"]
        if s.get("utwor_do_id"):
            sety[s["set_link"]][s["pozycja_do"]] = s["utwor_do_id"]
    wektory = {}
    plik_w = KATALOG / "wektory_mapy.jsonl"
    if plik_w.exists():
        import numpy as np
        for linia in plik_w.read_text().splitlines():
            try:
                w = json.loads(linia)
                v = np.asarray(w["wektor"], dtype=float)
                n = float(np.linalg.norm(v))
                if n > 0:
                    wektory[w["utwor_id"]] = v / n
            except Exception:
                pass
    return utw, sety, wektory


def main() -> int:
    import numpy as np
    from dancelab.decision.harmonic import harmonic_relation
    from dancelab.decision.corpus_priors import transition_prior_lift
    from dancelab.decision.set_builder import bpm_score

    utw, sety, wektory = wczytaj()
    print(f"wektory brzmienia: {len(wektory)} utworów")

    def bpm(uid):
        b = utw.get(uid, {}).get("bpm")
        return float(b) if isinstance(b, (int, float)) and b else None
    def ton(uid):
        return utw.get(uid, {}).get("tonacja") or None

    def s_tempo(a, x):
        return bpm_score(bpm(a), bpm(x))
    def s_silnik(a, x):
        lift, _ = transition_prior_lift(harmonic_relation(ton(a), ton(x)),
                                        bpm(a), bpm(x))
        return bpm_score(bpm(a), bpm(x)) * lift
    def s_clap(a, x):
        va, vx = wektory.get(a), wektory.get(x)
        return float(va @ vx) if va is not None and vx is not None else None

    MODELE = {
        "los":            lambda a, c, x, rng: rng.random(),
        "tempo-para":     lambda a, c, x, rng: s_tempo(a, x),
        "tempo-triplet":  lambda a, c, x, rng: s_tempo(a, x) * s_tempo(x, c),
        "silnik-para":    lambda a, c, x, rng: s_silnik(a, x),
        "silnik-triplet": lambda a, c, x, rng: s_silnik(a, x) * s_silnik(x, c),
    }
    if wektory:
        MODELE["clap-para"] = lambda a, c, x, rng: s_clap(a, x)
        MODELE["clap-triplet"] = lambda a, c, x, rng: (
            None if s_clap(a, x) is None or s_clap(x, c) is None
            else s_clap(a, x) + s_clap(x, c))

    rng = np.random.default_rng(20260811)
    wyniki = {m: [] for m in MODELE}
    trojki = 0
    for link, poz in sety.items():
        policzone = [uid for uid in set(poz.values()) if bpm(uid) is not None]
        for p in sorted(poz):
            a, b, c = poz.get(p), poz.get(p + 1), poz.get(p + 2)
            if not (a and b and c) or None in (bpm(a), bpm(b), bpm(c)):
                continue
            kand = [x for x in policzone if x not in (a, c)]
            if b not in kand or len(kand) < MIN_KANDYDATOW:
                continue
            trojki += 1
            for nazwa, fn in MODELE.items():
                oceny = {x: fn(a, c, x, rng) for x in kand}
                if any(v is None for v in oceny.values()):
                    continue
                posort = sorted(kand, key=lambda x: -oceny[x])
                miejsce = posort.index(b)
                wyniki[nazwa].append({
                    "percentyl": 1.0 - miejsce / (len(kand) - 1),
                    "top1": miejsce == 0, "top5": miejsce < 5})

    print(f"trójek w teście: {trojki}\n")
    print(f"{'model':16} {'n':>5} {'mediana pct':>11} {'top-1':>6} {'top-5':>6}")
    for nazwa, w in wyniki.items():
        if not w:
            print(f"{nazwa:16}  brak danych (wektory niepoliczone?)")
            continue
        pct = float(np.median([x["percentyl"] for x in w]))
        t1 = np.mean([x["top1"] for x in w])
        t5 = np.mean([x["top5"] for x in w])
        print(f"{nazwa:16} {len(w):5} {pct:11.3f} {t1:6.1%} {t5:6.1%}")

    # sedno tezy: para vs triplet W TEJ SAMEJ rodzinie, na wspólnych trójkach
    print("\npara vs triplet (różnica median percentyla, dodatnia = C pomaga):")
    for rodzina in ("tempo", "silnik", "clap"):
        p, t = wyniki.get(f"{rodzina}-para"), wyniki.get(f"{rodzina}-triplet")
        if p and t and len(p) == len(t):
            dp = np.array([x["percentyl"] for x in t]) - \
                 np.array([x["percentyl"] for x in p])
            print(f"  {rodzina:8} Δ={np.median(dp):+.3f} "
                  f"(triplet lepszy w {np.mean(dp > 0):.0%} trójek, "
                  f"gorszy w {np.mean(dp < 0):.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

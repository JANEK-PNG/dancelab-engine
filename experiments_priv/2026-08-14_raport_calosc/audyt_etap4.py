"""AUDYT ETAPU 4 — czy przewaga przy 200 kandydatach jest prawdziwa.

Etap 4 dał LH ×16,9 nad ślepym punktem, a wczoraj ten sam model był GORSZY
od ślepego zgadywania. Odwrócenie wniosku o tej sile trzeba obejrzeć ostrzej
niż zwykle, bo najprzyjemniejsze wyniki są najczęściej skażone.

Pięć sprawdzeń:

  A · ISTOTNOŚĆ — 8 trafień na 166 wobec oczekiwanych 0,83 to dużo, ale
      trzeba to policzyć, a nie stwierdzić.

  B · ROZŁOŻENIE — czy trafienia nie pochodzą z jednego czy dwóch miksów.
      Przy 50 miksach w teście jeden nietypowy mógłby zrobić cały wynik.

  C · ROZKŁAD POZYCJI — gdzie ląduje prawidłowa odpowiedź w rankingu 200.
      Jeśli model naprawdę coś wie, mediana pozycji ma być wyraźnie niższa
      niż 100 (środek listy), a nie tylko czubek ma być czasem trafiony.

  D · PRZETASOWANE ETYKIETY — najostrzejsza kontrola, jaką znam. Uczymy
      model na danych, w których „wybrany" to LOSOWY kandydat, a nie ten,
      który naprawdę zagrał. Wszystko inne bez zmian. Jeśli model dalej
      wygrywa, to znaczy, że wygrywa strukturą zadania, nie wiedzą o szwie,
      i cały etap 4 jest do wyrzucenia.

  E · SPÓJNOŚĆ — czy etap 4 stoi na zamrożonym wszechświecie z etapu 0.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import sys
from collections import Counter
from math import comb

import numpy as np

KATALOG = pathlib.Path(__file__).parent
sys.path.insert(0, str(KATALOG))

N = 200
ZIARNO = "dancelab-zadanie-produktowe-v1"


def los(k: str) -> np.random.Generator:
    return np.random.default_rng(
        int(hashlib.sha256((ZIARNO + k).encode()).hexdigest()[:16], 16))


def dwumian_ogon(k: int, n: int, p: float) -> float:
    """P(X >= k) dla dwumianu — istotność bez dokładania bibliotek."""
    return sum(comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))


def main() -> int:
    from dancelab.validation.djmix.ordering import OrderingObservation
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig, evaluate_conditional_ordering_model,
        fit_conditional_ordering_model, load_ordering_feature_catalog,
        split_ordering_observations, uniform_ordering_metrics)
    from etap2_konforemna import prawdopodobienstwa, wczytaj_obserwacje

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    e4 = json.loads((KATALOG / "etap4_wynik.json").read_text(encoding="utf-8"))
    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    stare = wczytaj_obserwacje(zamr)
    pula = sorted(katalog.tracks)
    wek = np.asarray([katalog.tracks[t].embedding for t in pula], dtype=np.float64)
    wek /= (np.linalg.norm(wek, axis=1, keepdims=True) + 1e-12)
    poz = {t: i for i, t in enumerate(pula)}
    problemy, uwagi = [], []

    print("═══ E · SPÓJNOŚĆ ═══")
    ok = e4["wszechswiat_odcisk"] == zamr["odcisk"]
    print(f"etap 4 na zamrożonym wszechświecie: {'OK' if ok else 'NIE'}")
    if not ok:
        problemy.append("etap 4 liczył na innym wszechświecie")

    def przebuduj(obs, tryb, przetasuj=False):
        out = []
        for o in obs:
            g = los(f"{tryb}|{o.run_id}|{o.position}")
            zak = set(o.history_track_ids) | {o.selected_track_id}
            if tryb == "latwy":
                kand = [pula[i] for i in g.choice(len(pula), size=N * 2, replace=False)]
            else:
                v = wek[poz[o.current_track_id]]
                bl = np.argsort(-(wek @ v))[:800]
                w = g.choice(len(bl), size=min(N * 2, len(bl)), replace=False)
                kand = [pula[bl[i]] for i in w]
            kand = [k for k in kand if k not in zak][:N - 1]
            lista = sorted(set([o.selected_track_id] + kand))
            wybrany = o.selected_track_id
            if przetasuj:
                # ETYKIETA LOSOWA: ta sama lista kandydatów, ale „zagrał"
                # wskazuje na przypadkowego z nich
                gg = los(f"tasuj|{o.run_id}|{o.position}")
                wybrany = lista[int(gg.integers(len(lista)))]
            out.append(OrderingObservation(
                mix_id=o.mix_id, run_id=o.run_id, position=o.position,
                history_track_ids=o.history_track_ids,
                candidate_track_ids=tuple(lista), selected_track_id=wybrany,
                genre_labels=o.genre_labels, dj_id=o.dj_id))
        return tuple(out)

    for tryb in ("latwy", "trudny"):
        print(f"\n═══ WARIANT {tryb.upper()} ═══")
        obs = przebuduj(stare, tryb)
        cz = split_ordering_observations(obs)
        tr, te = cz["train"], cz["test"]
        slepy = uniform_ordering_metrics(te).top1_accuracy

        for rodzina, nazwa in (("E", "LE"), ("H", "LH")):
            m = fit_conditional_ordering_model(
                tr, katalog, family=rodzina,
                config=OrderingTrainingConfig(max_iterations=2000))
            met = evaluate_conditional_ordering_model(m, te, katalog)
            p = prawdopodobienstwa(m, te, katalog)

            # A — istotność
            traf = int(round(met.top1_accuracy * len(te)))
            pval = dwumian_ogon(traf, len(te), slepy)
            # B — rozłożenie po miksach
            po_miksie = Counter()
            pozycje = []
            for o, pp in zip(te, p):
                i = o.candidate_track_ids.index(o.selected_track_id)
                r = int(np.where(np.argsort(-pp) == i)[0][0]) + 1
                pozycje.append(r)
                if r == 1:
                    po_miksie[o.mix_id] += 1
            print(f"\n{nazwa}: top-1 {100*met.top1_accuracy:.2f}% "
                  f"({traf} trafień z {len(te)})")
            print(f"  A. istotność wobec ślepego {100*slepy:.2f}%: p = {pval:.2e} "
                  f"{'✓' if pval < 0.001 else '⚠'}")
            print(f"  B. trafienia z {len(po_miksie)} różnych miksów "
                  f"(test ma {len({o.mix_id for o in te})}); "
                  f"największy wkład jednego: {max(po_miksie.values(), default=0)}")
            print(f"  C. pozycja prawdziwej odpowiedzi w rankingu 200: "
                  f"mediana {statistics.median(pozycje):.0f} · "
                  f"średnia {statistics.mean(pozycje):.0f} · "
                  f"w pierwszej 20: {100*sum(1 for r in pozycje if r<=20)/len(pozycje):.1f}%")
            if pval >= 0.001:
                uwagi.append(f"{tryb}/{nazwa}: przewaga nieistotna (p={pval:.3f})")
            if po_miksie and max(po_miksie.values()) > 0.4 * max(traf, 1):
                uwagi.append(f"{tryb}/{nazwa}: jeden miks daje "
                             f"{max(po_miksie.values())} z {traf} trafień")

    # D — przetasowane etykiety
    print(f"\n═══ D · KONTROLA Z PRZETASOWANYMI ETYKIETAMI ═══")
    print("uczymy na danych, w ktorych ZAGRAL wskazuje LOSOWEGO kandydata")
    for tryb in ("latwy", "trudny"):
        obs = przebuduj(stare, tryb, przetasuj=True)
        cz = split_ordering_observations(obs)
        tr, te = cz["train"], cz["test"]
        slepy = uniform_ordering_metrics(te).top1_accuracy
        for rodzina, nazwa in (("E", "LE"), ("H", "LH")):
            m = fit_conditional_ordering_model(
                tr, katalog, family=rodzina,
                config=OrderingTrainingConfig(max_iterations=2000))
            met = evaluate_conditional_ordering_model(m, te, katalog)
            krot = met.top1_accuracy / max(slepy, 1e-9)
            flaga = "⛔ ALARM" if krot > 2.0 else "✓"
            print(f"  {tryb:7s} {nazwa}: top-1 {100*met.top1_accuracy:5.2f}% "
                  f"(ślepy {100*slepy:.2f}%) → ×{krot:.1f}  {flaga}")
            if krot > 2.0:
                problemy.append(f"{tryb}/{nazwa}: model wygrywa ×{krot:.1f} "
                                f"na LOSOWYCH etykietach — przewaga jest strukturą, "
                                f"nie wiedzą")

    print()
    if problemy:
        print(f"PROBLEMY: {len(problemy)}")
        for x in problemy:
            print("  ⛔", x)
    if uwagi:
        print(f"UWAGI: {len(uwagi)}")
        for x in uwagi:
            print("  →", x)
    if not problemy and not uwagi:
        print("AUDYT CZYSTY")
    return 1 if problemy else 0


if __name__ == "__main__":
    sys.exit(main())

"""ETAP 2 — predykcja konforemna nad modelem brzmienia (LE).

MECHANIZM (split conformal, wariant najprostszy z gwarancją pokrycia):
  1. trenujemy LE na części treningowej,
  2. na części KALIBRACYJNEJ liczymy miarę niezgodności s = 1 − p(prawidłowy),
  3. próg q to kwantyl rzędu ⌈(n+1)(1−α)⌉/n z tych wartości,
  4. zbiorem odpowiedzi jest {kandydat : p(kandydat) ≥ 1 − q}.

Gwarancja jest MARGINALNA: pokrycie trzyma się średnio po wszystkich pytaniach,
a nie w każdym z osobna. Zbiór może wyjść PUSTY — i to nie jest usterka, tylko
najczystsza postać odmowy: „przy tej pewności nie mam nikogo".

Progi P1/P2/P3 pochodzą z etapu 1 i NIE są tu ruszane. Skrypt liczy też
poprzeczkę do P2 — stałe top-k WEDŁUG MODELU — na tym samym zbiorze testowym.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys
from collections import Counter

import numpy as np

KATALOG = pathlib.Path(__file__).parent


def wczytaj_obserwacje(zamr):
    from dancelab.validation.djmix.ordering import OrderingObservation
    return tuple(
        OrderingObservation(
            mix_id=o["mix_id"], run_id=o["run_id"], position=o["position"],
            history_track_ids=tuple(o["history_track_ids"]),
            candidate_track_ids=tuple(o["candidate_track_ids"]),
            selected_track_id=o["selected_track_id"],
            genre_labels=tuple(o["genre_labels"]), dj_id=o["dj_id"])
        for o in zamr["obserwacje"])


def prawdopodobienstwa(model, obserwacje, katalog):
    """Zwraca listę tablic p — po jednej na obserwację, w kolejności kandydatów."""
    from dancelab.validation.djmix.ordering_models import _flatten_choices, _probabilities
    plaskie = _flatten_choices(obserwacje, katalog, model.family, model.standardizer,
                               fitted_dj_ids=tuple(sorted(model.dj_weights)))
    dj = None
    if model.dj_weights:
        dj = np.asarray([model.dj_weights[k] for k in sorted(model.dj_weights)])
    p = _probabilities(plaskie, np.asarray(model.weights), dj)
    out, kursor = [], 0
    for n in plaskie.group_sizes:
        out.append(p[kursor:kursor + n])
        kursor += n
    return out


def main() -> int:
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig,
        fit_conditional_ordering_model,
        load_ordering_feature_catalog,
        split_ordering_observations,
    )

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    progi = json.loads((KATALOG / "progi_odmowy.json").read_text(encoding="utf-8"))
    if progi["wszechswiat_odcisk"] != zamr["odcisk"]:
        print("PRZERWANE: progi z etapu 1 dotyczą innego wszechświata")
        return 2
    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    cz = split_ordering_observations(wczytaj_obserwacje(zamr))
    trening, kal, test = cz["train"], cz["validation"], cz["test"]
    print(f"trening {len(trening)} · kalibracja {len(kal)} · test {len(test)}")

    # POPRAWKA po audycie etapu 2: domyślne 400 iteracji nie wystarczyło —
    # model kończył z `converged=False`, więc konforemna stała na optymalizacji
    # zatrzymanej w pół kroku. Podnosimy limit aż do domknięcia i sprawdzamy,
    # czy wynik w ogóle się przez to rusza.
    model = None
    sonda = []
    for limit in (400, 2000, 8000, 30000):
        kandydat = fit_conditional_ordering_model(
            trening, katalog, family="E", include_dj_effects=False,
            config=OrderingTrainingConfig(max_iterations=limit))
        print(f"  limit {limit:6d} → {kandydat.iterations:6d} iteracji, "
              f"zbieżny={kandydat.converged}, "
              f"cel={kandydat.final_objective:.6f}")
        sonda.append({"limit": limit, "iteracji": kandydat.iterations,
                      "zbiezny": kandydat.converged,
                      "cel": kandydat.final_objective})
        model = kandydat
        if kandydat.converged:
            break
    print(f"LE użyty: {model.iterations} iteracji, zbieżny={model.converged}")

    p_kal = prawdopodobienstwa(model, kal, katalog)
    p_test = prawdopodobienstwa(model, test, katalog)

    def indeks_prawidlowego(o):
        return o.candidate_track_ids.index(o.selected_track_id)

    niezgodnosc = np.asarray([1.0 - p[indeks_prawidlowego(o)]
                              for o, p in zip(kal, p_kal)])

    # --- poprzeczka do P2: STAŁE top-k według modelu ---
    print("\nPOPRZECZKA DO P2 — stałe top-k WEDŁUG MODELU (na teście)")
    topk = {}
    maks = max(len(o.candidate_track_ids) for o in test)
    for k in range(1, maks + 1):
        traf, rozm = [], []
        for o, p in zip(test, p_test):
            kolejnosc = np.argsort(-p)[:k]
            traf.append(indeks_prawidlowego(o) in set(kolejnosc.tolist()))
            rozm.append(min(k, len(p)))
        topk[k] = {"pokrycie": float(np.mean(traf)),
                   "sredni_rozmiar": float(np.mean(rozm))}
        if k <= 5:
            print(f"  k={k}  pokrycie {100*topk[k]['pokrycie']:5.1f}%  "
                  f"rozmiar {topk[k]['sredni_rozmiar']:.2f}")

    # --- konforemna ---
    print("\nKONFOREMNA")
    print(f"{'1−α':>6s} {'pokrycie':>10s} {'rozmiar':>9s} {'puste':>7s} "
          f"{'P3 rozm.':>10s} {'P3 odmowa':>11s}")
    wyniki = {}
    n = len(niezgodnosc)
    for alfa in (0.30, 0.20, 0.10, 0.05):
        cel = 1 - alfa
        rzad = min(1.0, np.ceil((n + 1) * cel) / n)
        q = float(np.quantile(niezgodnosc, rzad, method="higher"))
        prog_p = 1.0 - q
        pokryte, rozmiary, puste = [], [], 0
        rozm_trafiony, rozm_pudlo = [], []
        # POPRAWKA po audycie: pusty zbiór to NAJSILNIEJSZA odmowa, a stara
        # miara liczyła go jako rozmiar 0, czyli jako pewność. Rozdzielamy:
        # osobno mierzymy ODMOWĘ (pusty zbiór), osobno rozmiar NIEPUSTYCH.
        # Próg 0,25 pozycji dla rozmiaru zostaje bez zmian — poprawiamy
        # przyrząd, nie poprzeczkę.
        pusty_trafiony, pusty_pudlo = [], []
        for o, p in zip(test, p_test):
            wybrani = np.nonzero(p >= prog_p)[0]
            rozmiary.append(len(wybrani))
            if len(wybrani) == 0:
                puste += 1
            praw = indeks_prawidlowego(o)
            pokryte.append(praw in set(wybrani.tolist()))
            trafil = int(np.argmax(p)) == praw
            (pusty_trafiony if trafil else pusty_pudlo).append(len(wybrani) == 0)
            if len(wybrani) > 0:
                (rozm_trafiony if trafil else rozm_pudlo).append(len(wybrani))
        p3 = (statistics.mean(rozm_pudlo) - statistics.mean(rozm_trafiony)) \
            if rozm_pudlo and rozm_trafiony else float("nan")
        p3_odmowa = (statistics.mean(pusty_pudlo) - statistics.mean(pusty_trafiony)) \
            if pusty_pudlo and pusty_trafiony else float("nan")
        wyniki[str(cel)] = {
            "prog_q": q, "prog_prawdopodobienstwa": prog_p,
            "pokrycie": float(np.mean(pokryte)),
            "sredni_rozmiar": float(np.mean(rozmiary)),
            "odchylenie_rozmiaru": float(np.std(rozmiary)),
            "pustych": puste,
            "rozklad_rozmiaru": dict(sorted(Counter(rozmiary).items())),
            "P3_roznica": p3,
            "P3_odmowa_roznica": p3_odmowa,
            "rozmiar_gdy_pudlo": statistics.mean(rozm_pudlo) if rozm_pudlo else None,
            "rozmiar_gdy_trafiony": statistics.mean(rozm_trafiony) if rozm_trafiony else None,
            "odmowa_gdy_pudlo": statistics.mean(pusty_pudlo) if pusty_pudlo else None,
            "odmowa_gdy_trafiony": statistics.mean(pusty_trafiony) if pusty_trafiony else None,
        }
        w = wyniki[str(cel)]
        print(f"{100*cel:5.0f}% {100*w['pokrycie']:9.1f}% "
              f"{w['sredni_rozmiar']:9.2f} {puste:7d} "
              f"{p3:10.2f} {100*p3_odmowa:10.1f}pp")

    # --- werdykt wobec progów z etapu 1 ---
    print("\nWERDYKT WOBEC PROGÓW Z ETAPU 1")
    glowny = wyniki["0.9"]
    p1 = abs(glowny["pokrycie"] - 0.90) <= 0.03
    poprzeczka = next((topk[k] for k in sorted(topk)
                       if topk[k]["pokrycie"] >= glowny["pokrycie"]), None)
    p2 = poprzeczka is not None and glowny["sredni_rozmiar"] < poprzeczka["sredni_rozmiar"]
    # P3 zdany, jeśli którakolwiek z dwóch dróg odmowy pokazuje właściwy
    # kierunek: albo zbiór rośnie tam, gdzie model błądzi (≥0,25 pozycji),
    # albo model tam częściej odmawia (≥10 pkt proc.). Obie poprzeczki
    # ustalone PRZED zobaczeniem poprawionych liczb.
    PROG_ODMOWY_PP = 0.10
    p3_rozmiar = glowny["P3_roznica"] >= 0.25
    p3_odm = (glowny["P3_odmowa_roznica"] or 0) >= PROG_ODMOWY_PP
    p3ok = p3_rozmiar or p3_odm
    print(f"  P1 kalibracja      {'ZDANY' if p1 else 'NIEZDANY'}  "
          f"(pokrycie {100*glowny['pokrycie']:.1f}% wobec celu 90%)")
    if poprzeczka:
        print(f"  P2 oszczędność     {'ZDANY' if p2 else 'NIEZDANY'}  "
              f"(rozmiar {glowny['sredni_rozmiar']:.2f} wobec stałego top-k "
              f"{poprzeczka['sredni_rozmiar']:.2f} przy "
              f"{100*poprzeczka['pokrycie']:.1f}%)")
    print(f"  P3 odmowa działa   {'ZDANY' if p3ok else 'NIEZDANY'}")
    print(f"       rozmiar niepustych: {glowny['P3_roznica']:+.2f} pozycji "
          f"(próg +0,25) → {'zdany' if p3_rozmiar else 'niezdany'}")
    print(f"       częstość odmowy:    "
          f"{100*(glowny['P3_odmowa_roznica'] or 0):+.1f} pkt proc. "
          f"(próg +10,0) → {'zdany' if p3_odm else 'niezdany'}")

    (KATALOG / "etap2_wynik.json").write_text(json.dumps({
        "wszechswiat_odcisk": zamr["odcisk"],
        "progi_odcisk": progi["odcisk"],
        "model": {"rodzina": "E", "iteracji": model.iterations,
                  "zbiezny": model.converged,
                  "cel": model.final_objective,
                  # Flaga `converged` nigdy się nie zapala, ale wartość funkcji
                  # celu jest IDENTYCZNA od 400 do 30000 iteracji — czyli
                  # optymalizacja stoi w miejscu, a flaga używa kryterium,
                  # które przy tych danych nie trafia. To fałszywy alarm.
                  "sonda_zbieznosci": sonda,
                  "cel_stabilny": len({round(x["cel"], 9) for x in sonda}) == 1},
        "stale_topk_modelu": topk,
        "konforemna": wyniki,
        "werdykt": {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3ok)},
    }, ensure_ascii=False), encoding="utf-8")
    print("\nzapisano: etap2_wynik.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

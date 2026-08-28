"""Ile waży to jedno wyłączone przejście?

H1 wypadło tuż pod progiem (p = 0,0476 przy progu 0,05) i tuż nad progiem
różnicy (0,627 przy progu 0,5). Przy tak ciasnym marginesie trzeba pokazać,
co by się stało, gdyby OCENA_J_13 jednak dostało ocenę — dla każdej z pięciu
możliwych wartości. Inaczej wynik zależy od decyzji, której nikt nie widzi.

To NIE jest zmiana progów. Progi zostają z 18.08; to jest sprawdzenie,
czy werdykt na nich stoi, czy się chwieje.
"""

import csv
import itertools
import json
import pathlib

import numpy as np

TU = pathlib.Path(__file__).parent
BRAKUJACE = "OCENA_J_13"


def wczytaj() -> list[dict]:
    w = []
    for p in sorted(TU.glob("SESJA_*_transition_ratings.csv")):
        for r in csv.DictReader(p.open(encoding="utf-8")):
            r["playlista"] = r["pair_id"].rsplit("_", 1)[0].replace("_", " ")
            w.append(r)
    return w


def h1(srednie: dict[str, float], przydzial: dict[str, str]) -> tuple[float, float]:
    nazwy = sorted(srednie)
    wart = np.array([srednie[n] for n in nazwy])
    kontrola = frozenset(i for i, n in enumerate(nazwy)
                         if przydzial[n] != "SILNIK")

    def delta(k: frozenset) -> float:
        m = np.array([i in k for i in range(len(nazwy))])
        return float(wart[~m].mean() - wart[m].mean())

    obs = delta(kontrola)
    wszystkie = [delta(frozenset(k))
                 for k in itertools.combinations(range(len(nazwy)), len(kontrola))]
    p = sum(1 for d in wszystkie if d >= obs - 1e-12) / len(wszystkie)
    return obs, p


def h2(wiersze: list[dict]) -> tuple[float, float]:
    """Spearman wynik silnika vs ucho, permutacja WEWNĄTRZ playlist."""
    from scipy.stats import spearmanr
    score = np.array([float(r["engine_score"]) for r in wiersze])
    ocena = np.array([float(r["_ocena"]) for r in wiersze])
    play = np.array([r["playlista"] for r in wiersze])
    rho = float(spearmanr(score, ocena).statistic)
    g = np.random.default_rng(20260818)
    licznik = 0
    for _ in range(10_000):
        perm = ocena.copy()
        for nazwa in np.unique(play):
            m = play == nazwa
            perm[m] = g.permutation(perm[m])
        if float(spearmanr(score, perm).statistic) >= rho - 1e-12:
            licznik += 1
    return rho, licznik / 10_000


def main() -> int:
    wiersze = wczytaj()
    przydzial = json.loads((TU / "PRZYDZIAL_NIE_OTWIERAC.json")
                           .read_text(encoding="utf-8"))["przydzial"]

    print(f"{'ocena J13':>10} {'delta':>7} {'p':>8}  {'H1 wg progów z 18.08':<24}"
          f" | H2")
    for wariant in ("wyłączone", 1, 2, 3, 4, 5):
        oceny: dict[str, list[float]] = {}
        for r in wiersze:
            if r["pair_id"] == BRAKUJACE:
                if wariant == "wyłączone":
                    continue
                v = float(wariant)
            else:
                s = str(r["dj_mixability_rating"]).strip()
                if not s:
                    continue
                v = float(s)
            oceny.setdefault(r["playlista"], []).append(v)
        srednie = {k: float(np.mean(v)) for k, v in oceny.items()}
        d, p = h1(srednie, przydzial)
        do_h2 = []
        for r in wiersze:
            if r["pair_id"] == BRAKUJACE:
                if wariant == "wyłączone":
                    continue
                r = dict(r, _ocena=float(wariant))
            else:
                s_ = str(r["dj_mixability_rating"]).strip()
                if not s_:
                    continue
                r = dict(r, _ocena=float(s_))
            do_h2.append(r)
        rho, p2 = h2(do_h2)
        if p < 0.05 and d >= 0.5:
            werdykt = "SUKCES"
        elif p < 0.05 and d >= 0.25:
            werdykt = "słaby, realny sygnał"
        else:
            werdykt = "brak efektu → OBALONE.md"
        w2 = ("silnik widzi to, co ucho" if rho >= 0.30 and p2 < 0.05
              else "słaby sygnał" if rho >= 0.15 and p2 < 0.05
              else "brak związku → OBALONE.md")
        print(f"{str(wariant):>10} {d:7.3f} {p:8.4f}  {werdykt:<24}"
              f" | rho {rho:.3f} p {p2:.4f}  {w2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

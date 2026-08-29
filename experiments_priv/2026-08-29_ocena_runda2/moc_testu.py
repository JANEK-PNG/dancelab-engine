"""Jaka jest szansa, że runda 2 potwierdzi rundę 1, JEŚLI efekt jest prawdziwy.

Bez tej liczby zdanie „nietrafienie w progi unieważnia rundę 1" jest pustym
zaklęciem: przy niskiej mocy nietrafienie jest zdarzeniem spodziewanym także
wtedy, gdy efekt istnieje.

Model: 6 średnich z grupy silnika i 4 z kontroli, rozrzut międzyplaylistowy
wzięty z rundy 1. Test dokładnie taki jak w `analiza.py` — permutacja po
wszystkich C(10,4) = 210 układach, próg p < 0,05 ORAZ różnica ≥ 0,5.
"""

from __future__ import annotations

import itertools
import json
import pathlib

import numpy as np

TU = pathlib.Path(__file__).parent
R1 = TU.parents[1] / "experiments_priv/2026-08-17_ocena_papierowa"
PROB = 4000


def maski(n: int, ile_kontroli: int) -> np.ndarray:
    """Wszystkie układy kontroli jako macierz zero-jedynkowa — raz, nie w pętli."""
    m = np.zeros((0, n), dtype=bool)
    lista = [np.isin(np.arange(n), c)
             for c in itertools.combinations(range(n), ile_kontroli)]
    return np.array(lista) if lista else m


def przechodzi(wart: np.ndarray, maski_kontroli: np.ndarray) -> tuple[float, float]:
    n = len(wart)
    ile_k = int(maski_kontroli[0].sum())
    sr_k = maski_kontroli @ wart / ile_k
    sr_s = (~maski_kontroli) @ wart / (n - ile_k)
    delty = sr_s - sr_k
    obs = float(wart[: n - ile_k].mean() - wart[n - ile_k :].mean())
    p = float(np.mean(delty >= obs - 1e-12))
    return obs, p


def main() -> int:
    wynik = json.loads((R1 / "wynik_analizy.json").read_text(encoding="utf-8"))
    sr, prz = wynik["srednie_per_playlista"], wynik["przydzial"]
    silnik = [sr[k] for k in sr if prz[k] == "SILNIK"]
    kontrola = [sr[k] for k in sr if prz[k] != "SILNIK"]
    # rozrzut wewnątrz grup — to on decyduje, czy różnicę da się zobaczyć
    sigma = float(np.sqrt(((np.var(silnik, ddof=1) * (len(silnik) - 1))
                           + (np.var(kontrola, ddof=1) * (len(kontrola) - 1)))
                          / (len(silnik) + len(kontrola) - 2)))
    print(f"runda 1: silnik {np.mean(silnik):.3f} · kontrola {np.mean(kontrola):.3f}"
          f" · różnica {np.mean(silnik) - np.mean(kontrola):.3f}")
    print(f"rozrzut wewnątrz grup (sigma): {sigma:.3f}\n")

    g = np.random.default_rng(20260829)
    for opis, n_s, n_k, prob in (("sama runda 2 (10 playlist)", 6, 4, PROB),
                                 ("obie rundy razem (20 playlist)", 12, 8, 600)):
        mk = maski(n_s + n_k, n_k)
        print(f"\n{opis} · układów: {len(mk)}")
        print(f"{'prawdziwa różnica':>18} {'szansa zdania OBU progów':>26}")
        for delta_prawdziwa in (0.632, 0.50, 0.43, 0.30):
            zdane = 0
            for _ in range(prob):
                wart = np.concatenate([g.normal(delta_prawdziwa, sigma, n_s),
                                       g.normal(0.0, sigma, n_k)])
                d, p = przechodzi(wart, mk)
                if p < 0.05 and d >= 0.5:
                    zdane += 1
            print(f"{delta_prawdziwa:>18.3f} {100 * zdane / prob:>25.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

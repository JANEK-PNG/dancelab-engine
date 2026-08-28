"""Pomiar dwóch poprawek punktacji wobec progów z PLAN.md.

A — renormalizacja wag, gdy składowa jest stała (energia przy arc="off").
B — prior korpusowy mieszany w logitach zamiast mnożenia z przycięciem.

Nic tu nie jest strojone pod te oceny: obie poprawki są bezparametrowe.
Walidacja „bez jednej playlisty" i tak biegnie, żeby to pokazać pomiarem.
"""

from __future__ import annotations

import csv
import json
import math
import pathlib

import numpy as np
from scipy.stats import spearmanr

TU = pathlib.Path(__file__).parent
OCENY = TU.parents[1] / "experiments_priv/2026-08-17_ocena_papierowa"

PROG_UNIKALNYCH = 120
PROG_RHO_NIE_GORZEJ = 0.315
PROG_RHO_POPRAWA = 0.40


def logit(p: float, eps: float = 1e-6) -> float:
    p = min(1 - eps, max(eps, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def warianty(sk: dict[str, list[float]], wagi: dict[str, float],
             prior_w: float) -> dict[str, np.ndarray]:
    """Cztery wersje wyniku dla tych samych 158 przejść."""
    h = np.array(sk["harmonia"]); t = np.array(sk["tempo"])
    e = np.array(sk["energia"]); m = np.array(sk["mixability"])
    stary_rdzen = (wagi["harmonic"] * h + wagi["bpm"] * t
                   + wagi["energy"] * e + wagi["mixability"] * m)
    # A: energia jest stała → jej waga rozdzielona proporcjonalnie na resztę
    stale = e.std() < 1e-9
    if stale:
        reszta = {k: wagi[k] for k in ("harmonic", "bpm", "mixability")}
        suma = sum(reszta.values())
        wa = {k: v / suma for k, v in reszta.items()}
        rdzen_A = wa["harmonic"] * h + wa["bpm"] * t + wa["mixability"] * m
    else:
        rdzen_A = stary_rdzen

    lift = np.array(sk["lift"])

    def stare_prior(rdzen: np.ndarray) -> np.ndarray:
        return np.clip(rdzen * (lift ** prior_w), 0.0, 1.0)

    def logit_prior(rdzen: np.ndarray) -> np.ndarray:
        return np.array([sigmoid(logit(float(r)) + prior_w * math.log(float(l)))
                         for r, l in zip(rdzen, lift)])

    dzis = stare_prior(stary_rdzen)
    return {
        "dziś (rdzeń·lift, przycięte)": dzis,
        "A — renormalizacja wag": stare_prior(rdzen_A),
        "B — prior w logitach": logit_prior(stary_rdzen),
        "A+B": logit_prior(rdzen_A),
        # DIAGNOSTYCZNE, nie kandydaci do silnika:
        "sam lift (goła flaga)": lift,
        "sam rdzeń (bez prioru)": stary_rdzen,
        # POST-HOC, zaproponowane PO zobaczeniu porażki A i B:
        "C — dzisiejszy + rozstrzyganie remisów rdzeniem":
            dzis + 1e-3 * stary_rdzen,
        "D — dzisiejszy + remisy po mixability":
            dzis + 1e-3 * np.array(sk["mixability"]),
    }


def bez_jednej_playlisty(w: np.ndarray, ucho: np.ndarray,
                         plej: np.ndarray) -> float:
    """Średnie rho liczone NA odłożonej playliście.

    Obie poprawki są bezparametrowe, więc „trenowanie" nic nie dopasowuje —
    ta walidacja pokazuje po prostu, czy zgodność trzyma się na każdej
    playliście osobno, czy stoi na jednej.
    """
    rhos = []
    for nazwa in np.unique(plej):
        m = plej == nazwa
        if w[m].std() < 1e-12 or ucho[m].std() < 1e-12:
            continue
        rhos.append(float(spearmanr(w[m], ucho[m]).statistic))
    return float(np.mean(rhos)) if rhos else float("nan")


def main() -> int:
    sk = json.loads((TU / "skladowe.json").read_text(encoding="utf-8"))
    meta = json.loads((TU / "meta.json").read_text(encoding="utf-8"))
    ucho = np.array(sk["ucho"])
    plej = np.array(sk["playlista"])

    war = warianty(sk, meta["wagi"], meta["prior_w"])
    stary = war["dziś (rdzeń·lift, przycięte)"]
    prog_top = int(0.5 * len(ucho))
    zle_stare = int((ucho[np.argsort(-stary)[:prog_top]] <= 2).sum())

    print(f"{'wariant':<30} {'unikalnych':>11} {'rho':>7} {'rho bez-1':>10}"
          f" {'zł. w top50%':>13}")
    for nazwa, w in war.items():
        uniq = len(np.unique(np.round(w, 4)))
        rho = float(spearmanr(w, ucho).statistic)
        oos = bez_jednej_playlisty(w, ucho, plej)
        zle = int((ucho[np.argsort(-w)[:prog_top]] <= 2).sum())
        print(f"{nazwa:<30} {uniq:>7d}/158 {rho:>+7.3f} {oos:>+10.3f} {zle:>13d}")

    print(f"\nprogi z PLAN.md: unikalnych ≥ {PROG_UNIKALNYCH}, "
          f"rho ≥ {PROG_RHO_NIE_GORZEJ} (poprawa od {PROG_RHO_POPRAWA}), "
          f"rho bez-1 nie gorsze niż dziś, złych w top 50% nie więcej niż "
          f"{zle_stare}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

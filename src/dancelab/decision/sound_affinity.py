"""Podobieństwo brzmienia jako składnik oceny przejścia.

Zmierzone 2026-08-03 na 45 miksach korpusu, przy nowej regule przyjmowania
wariantów (liczy się dolna tercja, nie średnia):

    grupa DJ-ów      bez brzmienia   z brzmieniem 0,60   zmiana
    nieprzewidywalni     0,6826            0,7537        +0,071
    środek               0,7946            0,8336        +0,039
    zachowawczy          0,8641            0,8997        +0,036

Pomaga wszystkim, a NAJBARDZIEJ tym, którzy tego najbardziej potrzebują —
u DJ-a zachowawczego następny utwór i tak jest przewidywalny bez nas.

Dwie rzeczy, które trzymają to uczciwie:

  * BRAK WEKTORA = BRAK WPŁYWU, nie zero. Utwór bez osadzenia nie dostaje
    kary „brzmi niepodobnie" — składnik jest po prostu pomijany, a waga
    wraca do pozostałych. Inaczej cała biblioteka bez CLAP-a rozjechałaby
    ranking w stronę tych nielicznych, które go mają.
  * TO NIE JEST UNIWERSALNE. Na setach Janka ten sam składnik dał −0,008.
    Jego rodzaj nieprzewidywalności (duże skoki brzmienia przy karnie
    trzymanym tempie) jest inny niż korpusowy. Zapisane jako znany limit,
    nie zamiecione.
"""

from __future__ import annotations

import numpy as np

# Waga wynikająca z pomiaru: przy 0,60 zysk dolnej tercji jest największy
# i nie kosztuje pozostałych grup. Konfigurowalna, bo to jest wybór produktu.
DEFAULT_WEIGHT = 0.60


def cosine_affinity(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    """Podobieństwo dwóch wektorów brzmienia w [0,1], albo None gdy brak danych.

    None jest odpowiedzią pełnoprawną — patrz ADR-005. Wywołujący ma wtedy
    rozłożyć wagę na pozostałe składniki, a nie wstawić zero.
    """
    if a is None or b is None:
        return None
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na <= 0 or nb <= 0 or va.shape != vb.shape:
        return None
    return float(np.clip((float(np.dot(va, vb)) / (na * nb) + 1.0) / 2.0, 0.0, 1.0))


def blend(core_score: float, affinity: float | None,
          weight: float = DEFAULT_WEIGHT) -> tuple[float, str]:
    """Wmieszaj brzmienie w ocenę rdzenia. Zwraca (ocena, zdanie do uzasadnienia)."""
    if affinity is None or weight <= 0:
        return core_score, "sound affinity unavailable — weight redistributed"
    mixed = (1.0 - weight) * core_score + weight * affinity
    return float(np.clip(mixed, 0.0, 1.0)), f"sound affinity {affinity:.2f} (w={weight:.2f})"

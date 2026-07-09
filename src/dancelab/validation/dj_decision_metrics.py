"""Validation metrics for DJ decision outputs (EXP009/010/011/012).

EXP009 metrics: top-1 hit, top-3 hit, mean temporal overlap,
rating correlation, false positive rate. Pure functions — no audio needed.
"""

from __future__ import annotations

import numpy as np


def window_overlap_sec(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Temporal overlap in seconds between two [start, end] windows."""
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def window_iou(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = window_overlap_sec(a, b)
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def top_k_hit(
    engine_windows: list[tuple[float, float]],
    dj_windows: list[tuple[float, float]],
    k: int,
    min_overlap_sec: float = 4.0,
) -> bool:
    """True if any of the engine's top-k windows overlaps a DJ window by
    at least min_overlap_sec. engine_windows must be ranked best-first."""
    for ew in engine_windows[:k]:
        if any(window_overlap_sec(ew, dw) >= min_overlap_sec for dw in dj_windows):
            return True
    return False


def mean_overlap(
    engine_windows: list[tuple[float, float]],
    dj_windows: list[tuple[float, float]],
) -> float:
    """Mean best-IoU of each engine window against DJ windows. 0 if either empty."""
    if not engine_windows or not dj_windows:
        return 0.0
    return float(np.mean([
        max(window_iou(ew, dw) for dw in dj_windows) for ew in engine_windows
    ]))


def false_positive_rate(
    engine_windows: list[tuple[float, float]],
    dj_windows: list[tuple[float, float]],
    min_overlap_sec: float = 4.0,
) -> float:
    """Fraction of engine windows with no DJ counterpart."""
    if not engine_windows:
        return 0.0
    misses = sum(
        1 for ew in engine_windows
        if not any(window_overlap_sec(ew, dw) >= min_overlap_sec for dw in dj_windows)
    )
    return misses / len(engine_windows)


def rating_correlation(engine_scores: list[float], dj_ratings: list[float]) -> float | None:
    """Pearson correlation between engine scores and DJ ratings (1–5).
    None when undefined (fewer than 3 pairs or zero variance) — never faked."""
    if len(engine_scores) != len(dj_ratings) or len(engine_scores) < 3:
        return None
    a, b = np.asarray(engine_scores, float), np.asarray(dj_ratings, float)
    if a.std() < 1e-12 or b.std() < 1e-12:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def spearman_rho(a: list[float], b: list[float]) -> float | None:
    """Spearman rank correlation ρ = 1 − 6·Σd²/(n(n²−1)) (Validation Metrics, S042).

    Uses the tie-free rank formula via rank-transform + Pearson (handles ties
    correctly). None when undefined."""
    if len(a) != len(b) or len(a) < 3:
        return None
    ra, rb = _rank(np.asarray(a, float)), _rank(np.asarray(b, float))
    if ra.std() < 1e-12 or rb.std() < 1e-12:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def kendall_tau(a: list[float], b: list[float]) -> float | None:
    """Kendall τ = (n_c − n_d) / (½ n(n−1)) (Validation Metrics, S041).

    τ-a form (no tie correction). None when undefined."""
    n = len(a)
    if n != len(b) or n < 3:
        return None
    a_arr, b_arr = np.asarray(a, float), np.asarray(b, float)
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            sign = np.sign(a_arr[i] - a_arr[j]) * np.sign(b_arr[i] - b_arr[j])
            if sign > 0:
                concordant += 1
            elif sign < 0:
                discordant += 1
    denom = 0.5 * n * (n - 1)
    return float((concordant - discordant) / denom) if denom else None


def cohen_kappa(rater_a: list, rater_b: list) -> float | None:
    """Cohen's κ = (p_o − p_e)/(1 − p_e) for two raters, nominal labels
    (Validation Metrics, S039). None when undefined (empty or p_e == 1)."""
    if len(rater_a) != len(rater_b) or not rater_a:
        return None
    labels = sorted(set(rater_a) | set(rater_b))
    n = len(rater_a)
    p_o = sum(1 for x, y in zip(rater_a, rater_b) if x == y) / n
    p_e = sum(
        (rater_a.count(lbl) / n) * (rater_b.count(lbl) / n) for lbl in labels
    )
    if abs(1 - p_e) < 1e-12:
        return None
    return float((p_o - p_e) / (1 - p_e))


def _rank(x: np.ndarray) -> np.ndarray:
    """Average ranks (ties share their mean rank)."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    ranks[order] = np.arange(1, len(x) + 1)
    # average tied ranks
    _, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    return (sums / counts)[inv]

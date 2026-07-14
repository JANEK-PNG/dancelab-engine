"""Evaluation metrics used by the DLASOT-13 DJ-mix validation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


DEFAULT_HIT_TOLERANCES_SEC = (15.0, 30.0, 60.0)


@dataclass(frozen=True)
class BoundaryEvaluation:
    total: int
    evaluated: int
    coverage: float
    failure_rate: float
    mean_absolute_error_sec: float | None
    median_absolute_error_sec: float | None
    p90_absolute_error_sec: float | None
    hit_rate_evaluated: tuple[tuple[float, float], ...]
    hit_rate_all: tuple[tuple[float, float], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "evaluated": self.evaluated,
            "coverage": self.coverage,
            "failure_rate": self.failure_rate,
            "mean_absolute_error_sec": self.mean_absolute_error_sec,
            "median_absolute_error_sec": self.median_absolute_error_sec,
            "p90_absolute_error_sec": self.p90_absolute_error_sec,
            "hit_rate_evaluated": {
                str(tolerance): rate for tolerance, rate in self.hit_rate_evaluated
            },
            "hit_rate_all": {str(tolerance): rate for tolerance, rate in self.hit_rate_all},
        }


def evaluate_boundary_predictions(
    predicted_sec: Iterable[float | None],
    ground_truth_sec: Iterable[float],
    *,
    tolerances_sec: Iterable[float] = DEFAULT_HIT_TOLERANCES_SEC,
) -> BoundaryEvaluation:
    """Summarize cue errors while keeping missing-prediction coverage explicit."""

    predictions = tuple(predicted_sec)
    ground_truth = np.asarray(tuple(ground_truth_sec), dtype=np.float64)
    if len(predictions) != len(ground_truth):
        raise ValueError("predicted and ground-truth sequences must have equal length")
    if not np.all(np.isfinite(ground_truth)):
        raise ValueError("ground-truth boundaries must be finite")

    tolerances = tuple(dict.fromkeys(float(value) for value in tolerances_sec))
    if any(not np.isfinite(value) or value <= 0.0 for value in tolerances):
        raise ValueError("tolerances must be finite positive seconds")

    valid_predictions: list[float] = []
    valid_truth: list[float] = []
    for prediction, truth in zip(predictions, ground_truth, strict=True):
        if prediction is None or not np.isfinite(prediction):
            continue
        valid_predictions.append(float(prediction))
        valid_truth.append(float(truth))

    total = len(ground_truth)
    evaluated = len(valid_predictions)
    coverage = evaluated / total if total else 0.0
    if evaluated:
        errors = np.abs(np.asarray(valid_predictions) - np.asarray(valid_truth))
        mean_error = round(float(np.mean(errors)), 8)
        median_error = round(float(np.median(errors)), 8)
        p90_error = round(float(np.percentile(errors, 90)), 8)
    else:
        errors = np.array([], dtype=np.float64)
        mean_error = median_error = p90_error = None

    evaluated_rates: list[tuple[float, float]] = []
    all_rates: list[tuple[float, float]] = []
    for tolerance in tolerances:
        hits = int(np.count_nonzero(errors <= tolerance))
        evaluated_rate = hits / evaluated if evaluated else 0.0
        all_rate = hits / total if total else 0.0
        evaluated_rates.append((tolerance, round(evaluated_rate, 8)))
        all_rates.append((tolerance, round(all_rate, 8)))

    return BoundaryEvaluation(
        total=total,
        evaluated=evaluated,
        coverage=round(coverage, 8),
        failure_rate=round(1.0 - coverage if total else 0.0, 8),
        mean_absolute_error_sec=mean_error,
        median_absolute_error_sec=median_error,
        p90_absolute_error_sec=p90_error,
        hit_rate_evaluated=tuple(evaluated_rates),
        hit_rate_all=tuple(all_rates),
    )

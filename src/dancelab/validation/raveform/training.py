"""Leakage-aware training and evaluation for Raveform duration priors."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from typing import Callable, Iterable

import numpy as np

from dancelab.validation.raveform.models import (
    DURATION_BUCKETS_BEATS,
    ConditionalDistribution,
    MulticlassMetrics,
    TransitionDurationPrior,
    TransitionObservation,
)


SYMMETRIC_DIRICHLET_ALPHA = 0.5
PRIOR_STRENGTH_CANDIDATES = (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
SPLIT_RATIOS = (0.70, 0.15, 0.15)
ONE_SIDED_95_Z = 1.6448536269514722


def _mix_hash(mix_id: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}\0{mix_id}".encode()).hexdigest()


def split_by_mix(
    observations: Iterable[TransitionObservation],
    *,
    seed: str = "dancelab-raveform-v1",
) -> dict[str, tuple[TransitionObservation, ...]]:
    """Create deterministic train/validation/test sets with no mix leakage."""

    values = tuple(observations)
    mix_ids = sorted({item.mix_id for item in values}, key=lambda value: _mix_hash(value, seed))
    if len(mix_ids) < 3:
        raise ValueError("at least three distinct mixes are required for grouped splitting")
    train_end = max(1, int(len(mix_ids) * SPLIT_RATIOS[0]))
    validation_end = max(train_end + 1, int(len(mix_ids) * sum(SPLIT_RATIOS[:2])))
    validation_end = min(validation_end, len(mix_ids) - 1)
    groups = {
        "train": set(mix_ids[:train_end]),
        "validation": set(mix_ids[train_end:validation_end]),
        "test": set(mix_ids[validation_end:]),
    }
    return {
        name: tuple(item for item in values if item.mix_id in selected)
        for name, selected in groups.items()
    }


def _target_index(observation: TransitionObservation, buckets: tuple[int, ...]) -> int:
    try:
        return buckets.index(observation.duration_bucket_beats)
    except ValueError as exc:
        raise ValueError(
            f"unsupported target duration: {observation.duration_bucket_beats}"
        ) from exc


def _global_distribution(
    observations: Iterable[TransitionObservation],
    buckets: tuple[int, ...],
    alpha: float,
) -> ConditionalDistribution:
    values = tuple(observations)
    counts = np.zeros(len(buckets), dtype=np.float64)
    for item in values:
        counts[_target_index(item, buckets)] += 1.0
    probabilities = (counts + alpha) / (counts.sum() + alpha * len(buckets))
    return ConditionalDistribution(
        sample_count=len(values),
        probabilities=tuple(round(float(value), 12) for value in probabilities),
    )


def _context_counts(
    observations: Iterable[TransitionObservation],
    buckets: tuple[int, ...],
    contexts: Callable[[TransitionObservation], tuple[str, ...]],
) -> dict[str, np.ndarray]:
    counts: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(len(buckets), dtype=np.float64))
    for item in observations:
        for context in dict.fromkeys(contexts(item)):
            counts[context][_target_index(item, buckets)] += 1.0
    return dict(counts)


def _smoothed_distributions(
    counts: dict[str, np.ndarray],
    global_probabilities: tuple[float, ...],
    strength: float,
) -> dict[str, ConditionalDistribution]:
    if not np.isfinite(strength) or strength <= 0.0:
        raise ValueError("prior strength must be finite and positive")
    base = np.asarray(global_probabilities, dtype=np.float64)
    distributions = {}
    for key, context_counts in counts.items():
        sample_count = int(context_counts.sum())
        posterior = (context_counts + strength * base) / (sample_count + strength)
        distributions[key] = ConditionalDistribution(
            sample_count=sample_count,
            probabilities=tuple(round(float(value), 12) for value in posterior),
        )
    return distributions


def _fit_model(
    observations: Iterable[TransitionObservation],
    *,
    genre_strength: float,
    section_strength: float,
    buckets: tuple[int, ...] = DURATION_BUCKETS_BEATS,
    alpha: float = SYMMETRIC_DIRICHLET_ALPHA,
    genre_context_enabled: bool = True,
    section_context_enabled: bool = False,
) -> TransitionDurationPrior:
    values = tuple(observations)
    if not values:
        raise ValueError("cannot fit a prior without observations")
    global_distribution = _global_distribution(values, buckets, alpha)
    genre_counts = _context_counts(values, buckets, lambda item: item.genres)
    section_counts = _context_counts(
        values,
        buckets,
        lambda item: (item.section_pair,) if item.section_pair else (),
    )
    return TransitionDurationPrior(
        buckets_beats=buckets,
        global_distribution=global_distribution,
        genre_distributions=_smoothed_distributions(
            genre_counts,
            global_distribution.probabilities,
            genre_strength,
        ),
        section_pair_distributions=_smoothed_distributions(
            section_counts,
            global_distribution.probabilities,
            section_strength,
        ),
        genre_prior_strength=genre_strength,
        section_prior_strength=section_strength,
        symmetric_alpha=alpha,
        genre_context_enabled=genre_context_enabled,
        section_context_enabled=section_context_enabled,
    )


def evaluate_model(
    model: TransitionDurationPrior,
    observations: Iterable[TransitionObservation],
    *,
    mode: str,
) -> MulticlassMetrics:
    values = tuple(observations)
    if not values:
        return MulticlassMetrics(0, 0.0, 0.0, 0.0, 0.0, ())

    probabilities: list[np.ndarray] = []
    targets: list[int] = []
    sources: Counter[str] = Counter()
    for item in values:
        prediction, source = model.predict(
            genres=item.genres,
            outgoing_section=item.outgoing_section,
            incoming_section=item.incoming_section,
            mode=mode,
        )
        probabilities.append(np.asarray(prediction, dtype=np.float64))
        targets.append(_target_index(item, model.buckets_beats))
        sources[source] += 1

    matrix = np.asarray(probabilities, dtype=np.float64)
    target_array = np.asarray(targets, dtype=np.int64)
    selected = np.clip(matrix[np.arange(len(values)), target_array], 1e-12, 1.0)
    negative_log_likelihood = float(-np.mean(np.log(selected)))
    one_hot = np.eye(len(model.buckets_beats), dtype=np.float64)[target_array]
    brier_score = float(np.mean(np.sum((matrix - one_hot) ** 2, axis=1)))
    predicted_class = np.argmax(matrix, axis=1)
    correct = predicted_class == target_array
    top1_accuracy = float(np.mean(correct))
    confidence = np.max(matrix, axis=1)
    expected_calibration_error = 0.0
    bin_edges = np.linspace(0.0, 1.0, 11)
    for lower, upper in zip(bin_edges[:-1], bin_edges[1:], strict=True):
        in_bin = (confidence > lower) & (confidence <= upper)
        if not np.any(in_bin):
            continue
        expected_calibration_error += float(np.mean(in_bin)) * abs(
            float(np.mean(correct[in_bin])) - float(np.mean(confidence[in_bin]))
        )
    return MulticlassMetrics(
        count=len(values),
        negative_log_likelihood=round(negative_log_likelihood, 8),
        brier_score=round(brier_score, 8),
        top1_accuracy=round(top1_accuracy, 8),
        expected_calibration_error=round(expected_calibration_error, 8),
        prediction_sources=tuple(sorted(sources.items())),
    )


def _select_strength(
    train: tuple[TransitionObservation, ...],
    validation: tuple[TransitionObservation, ...],
    *,
    context: str,
    candidates: tuple[float, ...],
) -> tuple[float, list[dict[str, float]]]:
    if context == "genre":
        validation_rows = tuple(item for item in validation if item.genres)
        mode = "genre"
    elif context == "section":
        validation_rows = tuple(item for item in validation if item.section_pair)
        mode = "section"
    else:
        raise ValueError("context must be genre or section")
    if not validation_rows:
        return candidates[-1], []

    trials = []
    for strength in candidates:
        model = _fit_model(
            train,
            genre_strength=strength if context == "genre" else candidates[-1],
            section_strength=strength if context == "section" else candidates[-1],
        )
        metrics = evaluate_model(model, validation_rows, mode=mode)
        trials.append({
            "strength": strength,
            "negative_log_likelihood": metrics.negative_log_likelihood,
        })
    selected = min(
        trials,
        key=lambda item: (item["negative_log_likelihood"], item["strength"]),
    )["strength"]
    return float(selected), trials


def _paired_nll_gate(
    model: TransitionDurationPrior,
    observations: tuple[TransitionObservation, ...],
    *,
    context_mode: str,
) -> dict[str, float | int | bool | str]:
    """Require a one-sided 95% paired log-loss improvement on validation rows."""

    deltas = []
    for item in observations:
        target = _target_index(item, model.buckets_beats)
        global_prediction, _ = model.predict(mode="global")
        context_prediction, _ = model.predict(
            genres=item.genres,
            outgoing_section=item.outgoing_section,
            incoming_section=item.incoming_section,
            mode=context_mode,
        )
        global_loss = -np.log(max(float(global_prediction[target]), 1e-12))
        context_loss = -np.log(max(float(context_prediction[target]), 1e-12))
        deltas.append(context_loss - global_loss)
    if len(deltas) < 2:
        return {
            "enabled": False,
            "count": len(deltas),
            "mean_nll_delta_context_minus_global": 0.0,
            "standard_error": 0.0,
            "upper_one_sided_95": 0.0,
            "rule": "insufficient paired validation rows",
        }
    values = np.asarray(deltas, dtype=np.float64)
    mean_delta = float(np.mean(values))
    standard_error = float(np.std(values, ddof=1) / np.sqrt(len(values)))
    upper_bound = mean_delta + ONE_SIDED_95_Z * standard_error
    return {
        "enabled": upper_bound < 0.0,
        "count": len(values),
        "mean_nll_delta_context_minus_global": round(mean_delta, 8),
        "standard_error": round(standard_error, 8),
        "upper_one_sided_95": round(upper_bound, 8),
        "rule": "enable only when one-sided 95% paired NLL upper bound is below zero",
    }


def _track_overlap_audit(
    splits: dict[str, tuple[TransitionObservation, ...]],
) -> dict[str, object]:
    track_sets = {
        name: {
            track_id
            for item in values
            for track_id in (item.previous_track_id, item.next_track_id)
        }
        for name, values in splits.items()
    }
    pairs = {
        "train_validation": ("train", "validation"),
        "train_test": ("train", "test"),
        "validation_test": ("validation", "test"),
    }
    return {
        "distinct_tracks": {name: len(values) for name, values in track_sets.items()},
        "intersections": {
            label: len(track_sets[left] & track_sets[right])
            for label, (left, right) in pairs.items()
        },
        "smaller_split_overlap_share": {
            label: round(
                len(track_sets[left] & track_sets[right])
                / max(min(len(track_sets[left]), len(track_sets[right])), 1),
                8,
            )
            for label, (left, right) in pairs.items()
        },
    }


def _target_distribution(
    observations: tuple[TransitionObservation, ...],
    buckets: tuple[int, ...] = DURATION_BUCKETS_BEATS,
) -> np.ndarray:
    counts = np.zeros(len(buckets), dtype=np.float64)
    for item in observations:
        counts[_target_index(item, buckets)] += 1.0
    return counts / max(counts.sum(), 1.0)


def _split_distribution_audit(
    splits: dict[str, tuple[TransitionObservation, ...]],
) -> dict[str, object]:
    distributions = {name: _target_distribution(rows) for name, rows in splits.items()}
    return {
        "probabilities": {
            name: {
                str(bucket): round(float(probability), 8)
                for bucket, probability in zip(
                    DURATION_BUCKETS_BEATS,
                    values,
                    strict=True,
                )
            }
            for name, values in distributions.items()
        },
        "total_variation": {
            "train_validation": round(
                float(0.5 * np.abs(distributions["train"] - distributions["validation"]).sum()),
                8,
            ),
            "train_test": round(
                float(0.5 * np.abs(distributions["train"] - distributions["test"]).sum()),
                8,
            ),
        },
    }


def train_raveform_prior(
    observations: Iterable[TransitionObservation],
    *,
    split_seed: str = "dancelab-raveform-v1",
    strength_candidates: tuple[float, ...] = PRIOR_STRENGTH_CANDIDATES,
) -> tuple[TransitionDurationPrior, dict[str, object]]:
    """Select smoothing on validation mixes, refit, then evaluate held-out mixes."""

    values = tuple(observations)
    splits = split_by_mix(values, seed=split_seed)
    genre_strength, genre_trials = _select_strength(
        splits["train"],
        splits["validation"],
        context="genre",
        candidates=strength_candidates,
    )
    section_strength, section_trials = _select_strength(
        splits["train"],
        splits["validation"],
        context="section",
        candidates=strength_candidates,
    )
    selection_model = _fit_model(
        splits["train"],
        genre_strength=genre_strength,
        section_strength=section_strength,
    )
    genre_validation_rows = tuple(item for item in splits["validation"] if item.genres)
    section_validation_rows = tuple(
        item for item in splits["validation"] if item.section_pair
    )
    genre_validation_global = evaluate_model(
        selection_model,
        genre_validation_rows,
        mode="global",
    )
    genre_validation_context = evaluate_model(
        selection_model,
        genre_validation_rows,
        mode="genre",
    )
    section_validation_global = evaluate_model(
        selection_model,
        section_validation_rows,
        mode="global",
    )
    section_validation_context = evaluate_model(
        selection_model,
        section_validation_rows,
        mode="section",
    )
    genre_gate = _paired_nll_gate(
        selection_model,
        genre_validation_rows,
        context_mode="genre",
    )
    section_gate = _paired_nll_gate(
        selection_model,
        section_validation_rows,
        context_mode="section",
    )
    genre_enabled = bool(genre_gate["enabled"])
    section_enabled = bool(section_gate["enabled"])
    fit_rows = splits["train"] + splits["validation"]
    model = _fit_model(
        fit_rows,
        genre_strength=genre_strength,
        section_strength=section_strength,
        genre_context_enabled=genre_enabled,
        section_context_enabled=section_enabled,
    )
    structured_test = tuple(item for item in splits["test"] if item.section_pair)
    metrics = {
        "global_test": evaluate_model(model, splits["test"], mode="global").as_dict(),
        "genre_test": evaluate_model(model, splits["test"], mode="genre").as_dict(),
        "hybrid_test": evaluate_model(model, splits["test"], mode="hybrid").as_dict(),
        "global_structured_test": evaluate_model(
            model,
            structured_test,
            mode="global",
        ).as_dict(),
        "section_structured_test": evaluate_model(
            model,
            structured_test,
            mode="section",
        ).as_dict(),
    }
    split_mix_ids = {
        name: {item.mix_id for item in rows}
        for name, rows in splits.items()
    }
    if any(
        split_mix_ids[left] & split_mix_ids[right]
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
    ):
        raise AssertionError("mix leakage detected after grouped split")
    report = {
        "schema_version": "1.0.0",
        "scope": "offline population prior; no engine mutation",
        "eligible_for_engine_influence": False,
        "model": model.as_dict(),
        "split": {
            "seed": split_seed,
            "ratios": list(SPLIT_RATIOS),
            "mix_counts": {name: len(ids) for name, ids in split_mix_ids.items()},
            "observation_counts": {name: len(rows) for name, rows in splits.items()},
            "mix_id_overlap": 0,
            "track_id_overlap": _track_overlap_audit(splits),
            "target_distribution": _split_distribution_audit(splits),
            "track_overlap_note": (
                "Track-disjoint splitting is infeasible because 94.5% of mixes form one "
                "shared-track component; track IDs are not model features."
            ),
        },
        "selection": {
            "genre_prior_strength": genre_strength,
            "section_prior_strength": section_strength,
            "genre_validation_trials": genre_trials,
            "section_validation_trials": section_trials,
            "context_gates": {
                "genre": {
                    **genre_gate,
                    "global": genre_validation_global.as_dict(),
                    "context": genre_validation_context.as_dict(),
                },
                "section_pair": {
                    **section_gate,
                    "global": section_validation_global.as_dict(),
                    "context": section_validation_context.as_dict(),
                },
            },
        },
        "held_out_metrics": metrics,
        "limitations": [
            "Raveform mix points are DTW estimates, not manually captured fader moves.",
            "Mix-level genre tags are multi-label context, not track-level ground truth.",
            "Structure annotations cover a selected subset of frequently played tracks.",
            "Posterior means are empirical priors, not calibrated DJ-acceptance probabilities.",
            "Performed transitions contain no rejected alternatives and cannot learn pair quality.",
        ],
    }
    return model, report

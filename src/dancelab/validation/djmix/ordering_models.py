"""Five-model ordering evaluation over one immutable choice universe.

The module implements the bounded model ladder used by the DJ-mix
decomposition:

* L0: uniform random next-track choice from the observed remaining crate,
* LH: handcrafted descriptors,
* LE: frozen learned-audio embedding similarities,
* LHE: handcrafted and embedding features,
* LHEI: LHE plus regularized DJ-specific feature preferences.

All five losses are evaluated on the exact same held-out observations and
candidate sets. The feature catalogue is external by design: corpus alignment
reports do not contain embeddings, and this module must never invent them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Iterable, Literal, Mapping

import numpy as np

from dancelab.validation.djmix.decomposition import (
    DecompositionResult,
    ModelLosses,
    assess_crate_overlap,
    decompose_losses,
    evaluation_fingerprint,
)
from dancelab.validation.djmix.ordering import (
    CorpusOrderingDataset,
    OrderingObservation,
    observation_fingerprint,
)


ORDERING_FEATURE_SCHEMA_VERSION = "ordering-features-v1"
FeatureFamily = Literal["H", "E", "HE"]


def _clean_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _finite_tuple(values: object, *, field: str) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field} must be a list of finite numbers")
    result: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must contain only finite numbers") from exc
        if not math.isfinite(number):
            raise ValueError(f"{field} must contain only finite numbers")
        result.append(number)
    if not result:
        raise ValueError(f"{field} must not be empty")
    return tuple(result)


@dataclass(frozen=True)
class TrackOrderingFeatures:
    """Source-backed track-level features used by the ordering models."""

    handcrafted: tuple[float, ...]
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        _finite_tuple(self.handcrafted, field="handcrafted")
        _finite_tuple(self.embedding, field="embedding")

    def as_dict(self) -> dict[str, object]:
        return {
            "handcrafted": list(self.handcrafted),
            "embedding": list(self.embedding),
        }


@dataclass(frozen=True)
class OrderingFeatureCatalog:
    """Explicit feature source and trusted DJ identity mapping."""

    handcrafted_feature_names: tuple[str, ...]
    embedding_name: str
    tracks: Mapping[str, TrackOrderingFeatures]
    dj_by_mix: Mapping[str, str]
    fingerprint: str
    provenance: Mapping[str, object]
    schema_version: str = ORDERING_FEATURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.handcrafted_feature_names:
            raise ValueError("handcrafted_feature_names must not be empty")
        if not self.embedding_name.strip():
            raise ValueError("embedding_name must not be empty")
        if not self.tracks:
            raise ValueError("feature catalogue must contain tracks")
        handcrafted_dim = len(self.handcrafted_feature_names)
        embedding_dims = {len(item.embedding) for item in self.tracks.values()}
        handcrafted_dims = {len(item.handcrafted) for item in self.tracks.values()}
        if handcrafted_dims != {handcrafted_dim}:
            raise ValueError("handcrafted vector dimensions do not match feature names")
        if len(embedding_dims) != 1:
            raise ValueError("all embedding vectors must share one dimension")

    @property
    def handcrafted_dimension(self) -> int:
        return len(self.handcrafted_feature_names)

    @property
    def embedding_dimension(self) -> int:
        return len(next(iter(self.tracks.values())).embedding)

    def as_dict(self, *, include_vectors: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "handcrafted_feature_names": list(self.handcrafted_feature_names),
            "embedding_name": self.embedding_name,
            "handcrafted_dimension": self.handcrafted_dimension,
            "embedding_dimension": self.embedding_dimension,
            "track_count": len(self.tracks),
            "dj_mapping_count": len(self.dj_by_mix),
            "provenance": dict(self.provenance),
        }
        if include_vectors:
            payload["tracks"] = {key: value.as_dict() for key, value in sorted(self.tracks.items())}
            payload["dj_by_mix"] = dict(sorted(self.dj_by_mix.items()))
        return payload


def feature_catalog_from_payload(payload: Mapping[str, object]) -> OrderingFeatureCatalog:
    """Validate and freeze a feature catalogue payload."""

    schema_version = str(payload.get("schema_version") or "")
    if schema_version != ORDERING_FEATURE_SCHEMA_VERSION:
        raise ValueError(
            f"feature schema must be {ORDERING_FEATURE_SCHEMA_VERSION}, "
            f"got {schema_version or 'missing'}"
        )

    raw_names = payload.get("handcrafted_feature_names")
    if not isinstance(raw_names, list):
        raise ValueError("handcrafted_feature_names must be a list")
    feature_names = tuple(str(item).strip() for item in raw_names)
    if not feature_names or any(not item for item in feature_names):
        raise ValueError("handcrafted feature names must be non-empty")
    if len(set(feature_names)) != len(feature_names):
        raise ValueError("handcrafted feature names must be unique")

    embedding_name = str(payload.get("embedding_name") or "").strip()
    raw_tracks = payload.get("tracks")
    if not isinstance(raw_tracks, Mapping):
        raise ValueError("tracks must be an object keyed by catalogue track ID")
    tracks: dict[str, TrackOrderingFeatures] = {}
    for raw_track_id, raw_features in raw_tracks.items():
        track_id = _clean_identifier(raw_track_id)
        if track_id is None or not isinstance(raw_features, Mapping):
            raise ValueError("each track entry needs a non-empty ID and feature object")
        tracks[track_id] = TrackOrderingFeatures(
            handcrafted=_finite_tuple(
                raw_features.get("handcrafted"),
                field=f"tracks.{track_id}.handcrafted",
            ),
            embedding=_finite_tuple(
                raw_features.get("embedding"),
                field=f"tracks.{track_id}.embedding",
            ),
        )

    raw_dj_by_mix = payload.get("dj_by_mix", {})
    if not isinstance(raw_dj_by_mix, Mapping):
        raise ValueError("dj_by_mix must be an object")
    dj_by_mix = {
        mix_id: dj_id
        for raw_mix_id, raw_dj_id in raw_dj_by_mix.items()
        if (mix_id := _clean_identifier(raw_mix_id)) is not None
        and (dj_id := _clean_identifier(raw_dj_id)) is not None
    }
    provenance = payload.get("provenance", {})
    if not isinstance(provenance, Mapping):
        raise ValueError("provenance must be an object")

    canonical = {
        "schema_version": schema_version,
        "handcrafted_feature_names": list(feature_names),
        "embedding_name": embedding_name,
        "tracks": {key: value.as_dict() for key, value in sorted(tracks.items())},
        "dj_by_mix": dict(sorted(dj_by_mix.items())),
        "provenance": dict(provenance),
    }
    fingerprint = sha256(
        json.dumps(
            canonical,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return OrderingFeatureCatalog(
        handcrafted_feature_names=feature_names,
        embedding_name=embedding_name,
        tracks=tracks,
        dj_by_mix=dj_by_mix,
        fingerprint=fingerprint,
        provenance=dict(provenance),
    )


def load_ordering_feature_catalog(path: str | Path) -> OrderingFeatureCatalog:
    source = Path(path).expanduser().resolve()
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError("feature catalogue JSON must contain an object")
    return feature_catalog_from_payload(payload)


@dataclass(frozen=True)
class OrderingReadinessReport:
    total_observations: int
    eligible_observations: int
    eligible_mix_count: int
    eligible_dj_count: int
    missing_feature_observations: int
    missing_dj_observations: int
    ready_for_five_models: bool
    blockers: tuple[str, ...]

    @property
    def retained_fraction(self) -> float:
        if self.total_observations == 0:
            return 0.0
        return self.eligible_observations / self.total_observations

    def as_dict(self) -> dict[str, object]:
        return {
            "total_observations": self.total_observations,
            "eligible_observations": self.eligible_observations,
            "retained_fraction": self.retained_fraction,
            "eligible_mix_count": self.eligible_mix_count,
            "eligible_dj_count": self.eligible_dj_count,
            "missing_feature_observations": self.missing_feature_observations,
            "missing_dj_observations": self.missing_dj_observations,
            "ready_for_five_models": self.ready_for_five_models,
            "blockers": list(self.blockers),
        }


def _observation_track_ids(observation: OrderingObservation) -> set[str]:
    return set(observation.history_track_ids) | set(observation.candidate_track_ids)


def eligible_five_model_observations(
    dataset: CorpusOrderingDataset,
    catalog: OrderingFeatureCatalog,
) -> tuple[OrderingObservation, ...]:
    """Return the exact shared universe on which all five losses can be measured."""

    eligible: list[OrderingObservation] = []
    for observation in dataset.observations:
        if not _observation_track_ids(observation) <= catalog.tracks.keys():
            continue
        dj_id = catalog.dj_by_mix.get(observation.mix_id)
        if dj_id is None:
            continue
        eligible.append(
            OrderingObservation(
                mix_id=observation.mix_id,
                run_id=observation.run_id,
                position=observation.position,
                history_track_ids=observation.history_track_ids,
                candidate_track_ids=observation.candidate_track_ids,
                selected_track_id=observation.selected_track_id,
                genre_labels=observation.genre_labels,
                dj_id=dj_id,
            )
        )
    return tuple(eligible)


def assess_ordering_model_readiness(
    dataset: CorpusOrderingDataset,
    catalog: OrderingFeatureCatalog,
) -> OrderingReadinessReport:
    total = len(dataset.observations)
    missing_features = 0
    missing_dj = 0
    eligible = []
    for observation in dataset.observations:
        if not _observation_track_ids(observation) <= catalog.tracks.keys():
            missing_features += 1
            continue
        if observation.mix_id not in catalog.dj_by_mix:
            missing_dj += 1
            continue
        eligible.append(observation)

    mix_ids = {item.mix_id for item in eligible}
    dj_ids = {catalog.dj_by_mix[item.mix_id] for item in eligible}
    blockers: list[str] = []
    if total == 0:
        blockers.append("dataset has no qualified ordering observations")
    if missing_features:
        blockers.append(f"{missing_features} observation(s) lack complete H/E feature coverage")
    if missing_dj:
        blockers.append(f"{missing_dj} feature-complete observation(s) lack trusted DJ identity")
    if len(mix_ids) < 3:
        blockers.append("at least three eligible mixes are required for grouped splitting")
    if len(dj_ids) < 2:
        blockers.append("at least two trusted DJ identities are required for LHEI")

    return OrderingReadinessReport(
        total_observations=total,
        eligible_observations=len(eligible),
        eligible_mix_count=len(mix_ids),
        eligible_dj_count=len(dj_ids),
        missing_feature_observations=missing_features,
        missing_dj_observations=missing_dj,
        ready_for_five_models=not blockers,
        blockers=tuple(blockers),
    )


def _mix_hash(mix_id: str, seed: str) -> str:
    return sha256(f"{seed}\0{mix_id}".encode("utf-8")).hexdigest()


def split_ordering_observations(
    observations: Iterable[OrderingObservation],
    *,
    seed: str = "dancelab-corpus-ordering-v1",
) -> dict[str, tuple[OrderingObservation, ...]]:
    """Deterministically split whole mixes to prevent transition leakage."""

    values = tuple(observations)
    mix_ids = sorted(
        {item.mix_id for item in values},
        key=lambda value: _mix_hash(value, seed),
    )
    if len(mix_ids) < 3:
        raise ValueError("at least three distinct mixes are required for grouped splitting")
    train_end = max(1, int(len(mix_ids) * 0.70))
    validation_end = max(train_end + 1, int(len(mix_ids) * 0.85))
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


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denominator)


def _raw_candidate_features(
    observation: OrderingObservation,
    catalog: OrderingFeatureCatalog,
    family: FeatureFamily,
) -> np.ndarray:
    current = catalog.tracks[observation.current_track_id]
    history = [catalog.tracks[track_id] for track_id in observation.history_track_ids]
    candidates = [catalog.tracks[track_id] for track_id in observation.candidate_track_ids]
    blocks: list[np.ndarray] = []

    if family in {"H", "HE"}:
        current_h = np.asarray(current.handcrafted, dtype=np.float64)
        history_h = np.mean(
            np.asarray([item.handcrafted for item in history], dtype=np.float64),
            axis=0,
        )
        candidate_h = np.asarray(
            [item.handcrafted for item in candidates],
            dtype=np.float64,
        )
        blocks.append(
            np.concatenate(
                (
                    candidate_h,
                    candidate_h - current_h,
                    np.abs(candidate_h - current_h),
                    candidate_h - history_h,
                    np.abs(candidate_h - history_h),
                ),
                axis=1,
            )
        )

    if family in {"E", "HE"}:
        current_e = np.asarray(current.embedding, dtype=np.float64)
        history_e = np.mean(
            np.asarray([item.embedding for item in history], dtype=np.float64),
            axis=0,
        )
        candidate_e = np.asarray([item.embedding for item in candidates], dtype=np.float64)
        similarities = np.asarray(
            [
                (
                    _cosine(item, current_e),
                    _cosine(item, history_e),
                    -float(np.linalg.norm(item - current_e)),
                    -float(np.linalg.norm(item - history_e)),
                )
                for item in candidate_e
            ],
            dtype=np.float64,
        )
        blocks.append(similarities)

    if not blocks:
        raise ValueError(f"unsupported feature family: {family}")
    result = np.concatenate(blocks, axis=1)
    if not np.all(np.isfinite(result)):
        raise ValueError("candidate feature matrix contains non-finite values")
    return result


@dataclass(frozen=True)
class _Standardizer:
    mean: tuple[float, ...]
    scale: tuple[float, ...]

    @classmethod
    def fit(cls, matrices: Iterable[np.ndarray]) -> _Standardizer:
        values = tuple(matrices)
        if not values:
            raise ValueError("cannot fit a standardizer without feature rows")
        combined = np.concatenate(values, axis=0)
        mean = np.mean(combined, axis=0)
        scale = np.std(combined, axis=0)
        scale = np.where(scale < 1e-8, 1.0, scale)
        return cls(
            mean=tuple(float(value) for value in mean),
            scale=tuple(float(value) for value in scale),
        )

    def transform(self, matrix: np.ndarray) -> np.ndarray:
        return (matrix - np.asarray(self.mean, dtype=np.float64)) / np.asarray(
            self.scale, dtype=np.float64
        )


@dataclass(frozen=True)
class _FlatChoices:
    matrix: np.ndarray
    group_starts: np.ndarray
    group_sizes: np.ndarray
    target_rows: np.ndarray
    row_dj_indices: np.ndarray
    dj_ids: tuple[str, ...]
    observation_count: int


def _flatten_choices(
    observations: Iterable[OrderingObservation],
    catalog: OrderingFeatureCatalog,
    family: FeatureFamily,
    standardizer: _Standardizer,
    *,
    fitted_dj_ids: tuple[str, ...] = (),
) -> _FlatChoices:
    values = tuple(observations)
    dj_index = {dj_id: index for index, dj_id in enumerate(fitted_dj_ids)}
    matrices: list[np.ndarray] = []
    starts: list[int] = []
    sizes: list[int] = []
    targets: list[int] = []
    row_dj_indices: list[int] = []
    cursor = 0

    for observation in values:
        raw = _raw_candidate_features(observation, catalog, family)
        matrix = standardizer.transform(raw)
        target_local = observation.candidate_track_ids.index(observation.selected_track_id)
        starts.append(cursor)
        sizes.append(len(observation.candidate_track_ids))
        targets.append(cursor + target_local)
        matrices.append(matrix)
        row_dj_indices.extend([dj_index.get(observation.dj_id or "", -1)] * matrix.shape[0])
        cursor += matrix.shape[0]

    if not matrices:
        raise ValueError("cannot flatten an empty observation set")
    return _FlatChoices(
        matrix=np.concatenate(matrices, axis=0),
        group_starts=np.asarray(starts, dtype=np.int64),
        group_sizes=np.asarray(sizes, dtype=np.int64),
        target_rows=np.asarray(targets, dtype=np.int64),
        row_dj_indices=np.asarray(row_dj_indices, dtype=np.int64),
        dj_ids=fitted_dj_ids,
        observation_count=len(values),
    )


def _probabilities(
    flat: _FlatChoices,
    weights: np.ndarray,
    dj_weights: np.ndarray | None,
) -> np.ndarray:
    scores = flat.matrix @ weights
    if dj_weights is not None:
        known = flat.row_dj_indices >= 0
        if np.any(known):
            scores[known] += np.einsum(
                "ij,ij->i",
                flat.matrix[known],
                dj_weights[flat.row_dj_indices[known]],
            )
    maxima = np.maximum.reduceat(scores, flat.group_starts)
    shifted = scores - np.repeat(maxima, flat.group_sizes)
    exponentials = np.exp(np.clip(shifted, -700.0, 0.0))
    denominators = np.add.reduceat(exponentials, flat.group_starts)
    return exponentials / np.repeat(denominators, flat.group_sizes)


def _objective_and_gradients(
    flat: _FlatChoices,
    weights: np.ndarray,
    dj_weights: np.ndarray | None,
    *,
    l2: float,
    dj_l2: float,
) -> tuple[float, np.ndarray, np.ndarray | None]:
    probabilities = _probabilities(flat, weights, dj_weights)
    selected = np.clip(probabilities[flat.target_rows], 1e-15, 1.0)
    data_loss = -float(np.mean(np.log(selected)))
    residual = probabilities.copy()
    residual[flat.target_rows] -= 1.0
    residual /= flat.observation_count
    weight_gradient = flat.matrix.T @ residual + l2 * weights
    objective = data_loss + 0.5 * l2 * float(np.dot(weights, weights))

    if dj_weights is None:
        return objective, weight_gradient, None

    dj_gradient = np.zeros_like(dj_weights)
    known = flat.row_dj_indices >= 0
    if np.any(known):
        contributions = flat.matrix[known] * residual[known, np.newaxis]
        np.add.at(dj_gradient, flat.row_dj_indices[known], contributions)
    regularizer_scale = dj_l2 / max(len(dj_weights), 1)
    dj_gradient += regularizer_scale * dj_weights
    objective += 0.5 * regularizer_scale * float(np.sum(dj_weights**2))
    return objective, weight_gradient, dj_gradient


@dataclass(frozen=True)
class OrderingTrainingConfig:
    l2: float = 0.1
    dj_l2: float = 1.0
    learning_rate: float = 0.05
    max_iterations: int = 400
    tolerance: float = 1e-8
    patience: int = 20
    split_seed: str = "dancelab-corpus-ordering-v1"

    def __post_init__(self) -> None:
        if self.l2 < 0.0 or self.dj_l2 < 0.0:
            raise ValueError("regularization strengths must be non-negative")
        if self.learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        if self.max_iterations < 1 or self.patience < 1:
            raise ValueError("iteration limits must be positive")
        if self.tolerance <= 0.0:
            raise ValueError("tolerance must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "l2": self.l2,
            "dj_l2": self.dj_l2,
            "learning_rate": self.learning_rate,
            "max_iterations": self.max_iterations,
            "tolerance": self.tolerance,
            "patience": self.patience,
            "split_seed": self.split_seed,
        }


@dataclass(frozen=True)
class ConditionalOrderingModel:
    family: FeatureFamily
    standardizer: _Standardizer
    weights: tuple[float, ...]
    dj_weights: Mapping[str, tuple[float, ...]]
    iterations: int
    converged: bool
    final_objective: float
    l2: float
    dj_l2: float

    @property
    def uses_dj_effects(self) -> bool:
        return bool(self.dj_weights)

    def as_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "standardizer": {
                "mean": list(self.standardizer.mean),
                "scale": list(self.standardizer.scale),
            },
            "weights": list(self.weights),
            "dj_weights": {key: list(value) for key, value in sorted(self.dj_weights.items())},
            "iterations": self.iterations,
            "converged": self.converged,
            "final_objective": self.final_objective,
            "l2": self.l2,
            "dj_l2": self.dj_l2,
        }


def fit_conditional_ordering_model(
    observations: Iterable[OrderingObservation],
    catalog: OrderingFeatureCatalog,
    *,
    family: FeatureFamily,
    include_dj_effects: bool = False,
    config: OrderingTrainingConfig | None = None,
) -> ConditionalOrderingModel:
    """Fit a regularized conditional-logit ranker with full-batch Adam."""

    values = tuple(observations)
    if not values:
        raise ValueError("cannot fit an ordering model without observations")
    effective_config = config or OrderingTrainingConfig()
    raw_matrices = [_raw_candidate_features(observation, catalog, family) for observation in values]
    standardizer = _Standardizer.fit(raw_matrices)
    dj_ids: tuple[str, ...] = ()
    if include_dj_effects:
        if any(observation.dj_id is None for observation in values):
            raise ValueError("DJ-effect training requires a trusted DJ ID on every row")
        dj_ids = tuple(sorted({str(observation.dj_id) for observation in values}))
    flat = _flatten_choices(
        values,
        catalog,
        family,
        standardizer,
        fitted_dj_ids=dj_ids,
    )

    feature_count = flat.matrix.shape[1]
    weights = np.zeros(feature_count, dtype=np.float64)
    dj_weights = (
        np.zeros((len(dj_ids), feature_count), dtype=np.float64) if include_dj_effects else None
    )
    first_moment = np.zeros_like(weights)
    second_moment = np.zeros_like(weights)
    dj_first = np.zeros_like(dj_weights) if dj_weights is not None else None
    dj_second = np.zeros_like(dj_weights) if dj_weights is not None else None
    best_objective = math.inf
    best_weights = weights.copy()
    best_dj_weights = dj_weights.copy() if dj_weights is not None else None
    stable_iterations = 0
    converged = False
    final_objective = math.inf
    iteration = 0

    for iteration in range(1, effective_config.max_iterations + 1):
        objective, gradient, dj_gradient = _objective_and_gradients(
            flat,
            weights,
            dj_weights,
            l2=effective_config.l2,
            dj_l2=effective_config.dj_l2,
        )
        final_objective = objective
        previous_best = best_objective
        improvement = previous_best - objective
        if objective < previous_best:
            best_objective = objective
            best_weights = weights.copy()
            best_dj_weights = dj_weights.copy() if dj_weights is not None else None
        threshold = (
            effective_config.tolerance * max(1.0, abs(previous_best))
            if math.isfinite(previous_best)
            else 0.0
        )
        if math.isfinite(previous_best) and 0.0 <= improvement <= threshold:
            stable_iterations += 1
        else:
            stable_iterations = 0
        if stable_iterations >= effective_config.patience:
            converged = True
            break

        first_moment = 0.9 * first_moment + 0.1 * gradient
        second_moment = 0.999 * second_moment + 0.001 * (gradient**2)
        corrected_first = first_moment / (1.0 - 0.9**iteration)
        corrected_second = second_moment / (1.0 - 0.999**iteration)
        weights -= (
            effective_config.learning_rate * corrected_first / (np.sqrt(corrected_second) + 1e-8)
        )

        if dj_weights is not None and dj_gradient is not None:
            if dj_first is None or dj_second is None:
                raise RuntimeError("DJ optimizer state is inconsistent")
            dj_first = 0.9 * dj_first + 0.1 * dj_gradient
            dj_second = 0.999 * dj_second + 0.001 * (dj_gradient**2)
            corrected_dj_first = dj_first / (1.0 - 0.9**iteration)
            corrected_dj_second = dj_second / (1.0 - 0.999**iteration)
            dj_weights -= (
                effective_config.learning_rate
                * corrected_dj_first
                / (np.sqrt(corrected_dj_second) + 1e-8)
            )

    weights = best_weights
    dj_weights = best_dj_weights
    # Report the objective at the returned parameters, not one step before.
    final_objective, _, _ = _objective_and_gradients(
        flat,
        weights,
        dj_weights,
        l2=effective_config.l2,
        dj_l2=effective_config.dj_l2,
    )
    mapped_dj_weights = (
        {
            dj_id: tuple(float(value) for value in dj_weights[index])
            for index, dj_id in enumerate(dj_ids)
        }
        if dj_weights is not None
        else {}
    )
    return ConditionalOrderingModel(
        family=family,
        standardizer=standardizer,
        weights=tuple(float(value) for value in weights),
        dj_weights=mapped_dj_weights,
        iterations=iteration,
        converged=converged,
        final_objective=float(final_objective),
        l2=effective_config.l2,
        dj_l2=effective_config.dj_l2 if include_dj_effects else 0.0,
    )


@dataclass(frozen=True)
class OrderingMetrics:
    count: int
    total_nll: float
    mean_nll: float
    top1_accuracy: float
    mean_reciprocal_rank: float
    known_dj_count: int
    unseen_dj_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "total_nll": self.total_nll,
            "mean_nll": self.mean_nll,
            "top1_accuracy": self.top1_accuracy,
            "mean_reciprocal_rank": self.mean_reciprocal_rank,
            "known_dj_count": self.known_dj_count,
            "unseen_dj_count": self.unseen_dj_count,
        }


def evaluate_conditional_ordering_model(
    model: ConditionalOrderingModel,
    observations: Iterable[OrderingObservation],
    catalog: OrderingFeatureCatalog,
) -> OrderingMetrics:
    values = tuple(observations)
    if not values:
        return OrderingMetrics(0, 0.0, 0.0, 0.0, 0.0, 0, 0)

    fitted_dj_ids = tuple(sorted(model.dj_weights))
    flat = _flatten_choices(
        values,
        catalog,
        model.family,
        model.standardizer,
        fitted_dj_ids=fitted_dj_ids,
    )
    weights = np.asarray(model.weights, dtype=np.float64)
    dj_weights = (
        np.asarray([model.dj_weights[dj_id] for dj_id in fitted_dj_ids], dtype=np.float64)
        if fitted_dj_ids
        else None
    )
    probabilities = _probabilities(flat, weights, dj_weights)
    selected = np.clip(probabilities[flat.target_rows], 1e-15, 1.0)
    total_nll = -float(np.sum(np.log(selected)))
    correct = 0
    reciprocal_ranks: list[float] = []
    known_dj = 0

    for index, observation in enumerate(values):
        start = int(flat.group_starts[index])
        size = int(flat.group_sizes[index])
        local = probabilities[start : start + size]
        target_local = int(flat.target_rows[index] - start)
        predicted = int(np.argmax(local))
        correct += predicted == target_local
        target_probability = local[target_local]
        rank = 1 + int(np.sum(local > target_probability))
        reciprocal_ranks.append(1.0 / rank)
        known_dj += (observation.dj_id or "") in model.dj_weights

    return OrderingMetrics(
        count=len(values),
        total_nll=total_nll,
        mean_nll=total_nll / len(values),
        top1_accuracy=correct / len(values),
        mean_reciprocal_rank=float(np.mean(reciprocal_ranks)),
        known_dj_count=known_dj,
        unseen_dj_count=len(values) - known_dj,
    )


def uniform_ordering_metrics(
    observations: Iterable[OrderingObservation],
) -> OrderingMetrics:
    values = tuple(observations)
    if not values:
        return OrderingMetrics(0, 0.0, 0.0, 0.0, 0.0, 0, 0)
    losses = [math.log(len(item.candidate_track_ids)) for item in values]
    reciprocal_ranks = [
        sum(1.0 / rank for rank in range(1, len(item.candidate_track_ids) + 1))
        / len(item.candidate_track_ids)
        for item in values
    ]
    total_nll = sum(losses)
    return OrderingMetrics(
        count=len(values),
        total_nll=total_nll,
        mean_nll=total_nll / len(values),
        top1_accuracy=float(np.mean([1.0 / len(item.candidate_track_ids) for item in values])),
        mean_reciprocal_rank=float(np.mean(reciprocal_ranks)),
        known_dj_count=0,
        unseen_dj_count=0,
    )


@dataclass(frozen=True)
class FiveModelOrderingReport:
    dataset_fingerprint: str
    feature_catalog_fingerprint: str
    evaluation_hash: str
    readiness: OrderingReadinessReport
    split_counts: Mapping[str, int]
    split_mix_ids: Mapping[str, tuple[str, ...]]
    validation_metrics: Mapping[str, OrderingMetrics]
    test_metrics: Mapping[str, OrderingMetrics]
    losses: ModelLosses
    decomposition: DecompositionResult
    models: Mapping[str, ConditionalOrderingModel]
    training_config: OrderingTrainingConfig
    warnings: tuple[str, ...]

    def as_dict(self, *, include_model_parameters: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "scope": "ordering-given-observed-crate",
            "dataset_fingerprint": self.dataset_fingerprint,
            "feature_catalog_fingerprint": self.feature_catalog_fingerprint,
            "evaluation_hash": self.evaluation_hash,
            "readiness": self.readiness.as_dict(),
            "split_counts": dict(self.split_counts),
            "split_mix_ids": {key: list(value) for key, value in self.split_mix_ids.items()},
            "validation_metrics": {
                key: value.as_dict() for key, value in self.validation_metrics.items()
            },
            "test_metrics": {key: value.as_dict() for key, value in self.test_metrics.items()},
            "losses": self.losses.values(),
            "decomposition": self.decomposition.as_dict(),
            "training_config": self.training_config.as_dict(),
            "warnings": list(self.warnings),
        }
        if include_model_parameters:
            payload["models"] = {key: value.as_dict() for key, value in self.models.items()}
        else:
            payload["model_summaries"] = {
                key: {
                    "family": value.family,
                    "uses_dj_effects": value.uses_dj_effects,
                    "iterations": value.iterations,
                    "converged": value.converged,
                    "final_objective": value.final_objective,
                }
                for key, value in self.models.items()
            }
        return payload


def _crate_overlap_for_observations(
    observations: Iterable[OrderingObservation],
    catalog: OrderingFeatureCatalog,
) -> tuple[float | None, tuple[str, ...]]:
    crates: dict[str, set[str]] = {}
    set_counts: Counter[str] = Counter()
    for observation in observations:
        if observation.dj_id is None:
            continue
        crates.setdefault(observation.dj_id, set()).update(_observation_track_ids(observation))
        set_counts[observation.dj_id] += 1
    matrices = {
        dj_id: np.asarray(
            [catalog.tracks[track_id].embedding for track_id in sorted(track_ids)],
            dtype=np.float64,
        )
        for dj_id, track_ids in crates.items()
    }
    report = assess_crate_overlap(matrices, set_counts=set_counts)
    return report.weighted_q, report.warnings


def train_five_model_ordering_evaluation(
    dataset: CorpusOrderingDataset,
    catalog: OrderingFeatureCatalog,
    *,
    config: OrderingTrainingConfig | None = None,
) -> FiveModelOrderingReport:
    """Fit and compare the five declared models on one held-out universe."""

    effective_config = config or OrderingTrainingConfig()
    readiness = assess_ordering_model_readiness(dataset, catalog)
    if not readiness.ready_for_five_models:
        joined = "; ".join(readiness.blockers)
        raise ValueError(f"five-model ordering evaluation is blocked: {joined}")

    eligible = eligible_five_model_observations(dataset, catalog)
    splits = split_ordering_observations(eligible, seed=effective_config.split_seed)
    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]

    model_specs: dict[str, tuple[FeatureFamily, bool]] = {
        "LH": ("H", False),
        "LE": ("E", False),
        "LHE": ("HE", False),
        "LHEI": ("HE", True),
    }
    models: dict[str, ConditionalOrderingModel] = {}
    validation_metrics: dict[str, OrderingMetrics] = {"L0": uniform_ordering_metrics(validation)}
    test_metrics: dict[str, OrderingMetrics] = {"L0": uniform_ordering_metrics(test)}
    for name, (family, include_dj_effects) in model_specs.items():
        model = fit_conditional_ordering_model(
            train,
            catalog,
            family=family,
            include_dj_effects=include_dj_effects,
            config=effective_config,
        )
        models[name] = model
        validation_metrics[name] = evaluate_conditional_ordering_model(
            model,
            validation,
            catalog,
        )
        test_metrics[name] = evaluate_conditional_ordering_model(model, test, catalog)

    test_manifest_hash = observation_fingerprint(test)
    evaluation_hash = evaluation_fingerprint(
        {
            "scope": "ordering-given-observed-crate",
            "dataset_fingerprint": dataset.fingerprint,
            "feature_catalog_fingerprint": catalog.fingerprint,
            "split_seed": effective_config.split_seed,
            "test_observation_fingerprint": test_manifest_hash,
            "test_mix_ids": sorted({item.mix_id for item in test}),
        }
    )
    losses = ModelLosses.from_values(
        baseline=test_metrics["L0"].total_nll,
        handcrafted=test_metrics["LH"].total_nll,
        embedding=test_metrics["LE"].total_nll,
        combined=test_metrics["LHE"].total_nll,
        combined_dj=test_metrics["LHEI"].total_nll,
        evaluation_hash=evaluation_hash,
        scope="ordering-given-observed-crate",
    )
    q_d, overlap_warnings = _crate_overlap_for_observations(train, catalog)
    decomposition = decompose_losses(losses, q_d=q_d)
    warnings = list(overlap_warnings)
    if any(not model.converged for model in models.values()):
        warnings.append("one or more optimizers reached max_iterations; inspect model summaries")
    if test_metrics["LHEI"].unseen_dj_count:
        warnings.append("LHEI used the global LHE weights for test observations from unseen DJs")

    return FiveModelOrderingReport(
        dataset_fingerprint=dataset.fingerprint,
        feature_catalog_fingerprint=catalog.fingerprint,
        evaluation_hash=evaluation_hash,
        readiness=readiness,
        split_counts={key: len(value) for key, value in splits.items()},
        split_mix_ids={
            key: tuple(sorted({item.mix_id for item in value})) for key, value in splits.items()
        },
        validation_metrics=validation_metrics,
        test_metrics=test_metrics,
        losses=losses,
        decomposition=decomposition,
        models=models,
        training_config=effective_config,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def write_five_model_ordering_report(
    report: FiveModelOrderingReport,
    output_path: str | Path,
    *,
    include_model_parameters: bool = False,
) -> Path:
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            report.as_dict(include_model_parameters=include_model_parameters),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination

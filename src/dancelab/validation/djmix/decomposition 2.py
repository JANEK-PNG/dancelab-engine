"""Offline decomposition of DJ set selection and ordering evidence.

The functions in this module implement a measurement protocol. They do not
train a production ranker and must not influence runtime decisions without a
separate held-out validation gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

import numpy as np


SET_RULE_FORMULA_VERSION = "dj-set-rule-shapley-v1"


@dataclass(frozen=True)
class MeasuredLoss:
    """One held-out negative log-likelihood tied to an evaluation universe."""

    value: float
    evaluation_hash: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("loss must be finite")
        if not self.evaluation_hash:
            raise ValueError("evaluation_hash must not be empty")


@dataclass(frozen=True)
class ModelLosses:
    """Five nested model losses evaluated on exactly the same observations."""

    baseline: MeasuredLoss
    handcrafted: MeasuredLoss
    embedding: MeasuredLoss
    combined: MeasuredLoss
    combined_dj: MeasuredLoss
    scope: str

    @classmethod
    def from_values(
        cls,
        *,
        baseline: float,
        handcrafted: float,
        embedding: float,
        combined: float,
        combined_dj: float,
        evaluation_hash: str,
        scope: str,
    ) -> ModelLosses:
        """Build a bundle when all losses share one verified data fingerprint."""

        return cls(
            baseline=MeasuredLoss(baseline, evaluation_hash),
            handcrafted=MeasuredLoss(handcrafted, evaluation_hash),
            embedding=MeasuredLoss(embedding, evaluation_hash),
            combined=MeasuredLoss(combined, evaluation_hash),
            combined_dj=MeasuredLoss(combined_dj, evaluation_hash),
            scope=scope,
        )

    @property
    def evaluation_hash(self) -> str:
        hashes = {
            self.baseline.evaluation_hash,
            self.handcrafted.evaluation_hash,
            self.embedding.evaluation_hash,
            self.combined.evaluation_hash,
            self.combined_dj.evaluation_hash,
        }
        if len(hashes) != 1:
            raise ValueError(
                "all losses in one decomposition must use the same evaluation_hash"
            )
        return hashes.pop()

    def values(self) -> dict[str, float]:
        return {
            "L0": self.baseline.value,
            "LH": self.handcrafted.value,
            "LE": self.embedding.value,
            "LHE": self.combined.value,
            "LHEI": self.combined_dj.value,
        }


@dataclass(frozen=True)
class DecompositionResult:
    """Order-independent contribution split for handcrafted/audio/DJ effects."""

    c_rule: float
    c_similarity: float
    identity: float
    residual: float
    evaluation_hash: str
    scope: str
    flags: tuple[str, ...] = ()
    formula_version: str = SET_RULE_FORMULA_VERSION

    @property
    def total(self) -> float:
        return self.c_rule + self.c_similarity + self.identity + self.residual

    def as_dict(self) -> dict[str, object]:
        return {
            "C_rule": self.c_rule,
            "C_sim": self.c_similarity,
            "I": self.identity,
            "N": self.residual,
            "total": self.total,
            "scope": self.scope,
            "evaluation_hash": self.evaluation_hash,
            "flags": list(self.flags),
            "formula_version": self.formula_version,
        }


@dataclass(frozen=True)
class CrateOverlapReport:
    """Audio-space overlap used to qualify interpretation of the DJ effect."""

    epsilon_by_dj: Mapping[str, float | None]
    directional_overlap: Mapping[str, Mapping[str, float]]
    q_by_dj: Mapping[str, float | None]
    weighted_q: float | None
    alpha: float
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "epsilon_by_dj": dict(self.epsilon_by_dj),
            "directional_overlap": {
                source: dict(targets)
                for source, targets in self.directional_overlap.items()
            },
            "q_by_dj": dict(self.q_by_dj),
            "weighted_q": self.weighted_q,
            "alpha": self.alpha,
            "warnings": list(self.warnings),
        }


def evaluation_fingerprint(payload: object) -> str:
    """Hash the canonical manifest of sets, pools and transition risk sets."""

    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("evaluation payload must be finite and JSON serializable") from exc
    return hashlib.sha256(encoded).hexdigest()


def decompose_losses(
    losses: ModelLosses,
    *,
    q_d: float | None = None,
    identifiability_threshold: float = 0.3,
) -> DecompositionResult:
    """Apply the two-block Shapley decomposition to held-out model losses.

    Negative contributions are retained because they measure failure to
    generalize out of sample. Only non-finite inputs and a non-positive
    baseline are hard errors.
    """

    if not 0.0 <= identifiability_threshold <= 1.0:
        raise ValueError("identifiability_threshold must be within [0, 1]")
    if q_d is not None and (not math.isfinite(q_d) or not 0.0 <= q_d <= 1.0):
        raise ValueError("q_d must be finite and within [0, 1]")

    evaluation_hash = losses.evaluation_hash
    values = losses.values()
    l0 = values["L0"]
    if l0 <= 0.0:
        raise ValueError("L0 must be a positive, defined baseline")

    c_rule = ((l0 - values["LH"]) + (values["LE"] - values["LHE"])) / (2.0 * l0)
    c_similarity = (
        (l0 - values["LE"]) + (values["LH"] - values["LHE"])
    ) / (2.0 * l0)
    identity = (values["LHE"] - values["LHEI"]) / l0
    residual = values["LHEI"] / l0
    contributions = {
        "C_rule": c_rule,
        "C_sim": c_similarity,
        "I": identity,
        "N": residual,
    }
    total = sum(contributions.values())
    if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ArithmeticError("decomposition contributions do not sum to one")

    flags = [
        f"{name}>L0: model worse than random baseline on held-out data"
        for name, value in values.items()
        if name != "L0" and value > l0
    ]
    flags.extend(
        f"{name}<0: negative out-of-sample contribution"
        for name, value in contributions.items()
        if value < 0.0
    )
    if values["LHEI"] > values["LHE"] + 1e-9:
        flags.append("I<0: DJ effect does not generalize")
    if (
        values["LHEI"] < values["LHE"] - 1e-9
        and q_d is not None
        and q_d < identifiability_threshold
    ):
        flags.append(
            "I>0, but DJ effect is not separable from crate at the observed q_d"
        )

    return DecompositionResult(
        c_rule=c_rule,
        c_similarity=c_similarity,
        identity=identity,
        residual=residual,
        evaluation_hash=evaluation_hash,
        scope=losses.scope,
        flags=tuple(flags),
    )


def combine_joint_losses(selection: ModelLosses, ordering: ModelLosses) -> ModelLosses:
    """Add selection and ordering losses after verifying one evaluation universe."""

    selection_hash = selection.evaluation_hash
    ordering_hash = ordering.evaluation_hash
    if selection_hash != ordering_hash:
        raise ValueError(
            "selection and ordering losses must use the same evaluation_hash"
        )
    selection_values = selection.values()
    ordering_values = ordering.values()
    joint = {
        name: selection_values[name] + ordering_values[name]
        for name in selection_values
    }
    return ModelLosses.from_values(
        baseline=joint["L0"],
        handcrafted=joint["LH"],
        embedding=joint["LE"],
        combined=joint["LHE"],
        combined_dj=joint["LHEI"],
        evaluation_hash=selection_hash,
        scope="joint-selection-and-ordering",
    )


def log_fixed_size_partition(log_weights: Sequence[float], selection_size: int) -> float:
    """Compute ``log [z^m] prod_i (1 + z exp(log_weight_i))`` in O(n*m)."""

    values = np.asarray(tuple(log_weights), dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("log_weights must be a finite one-dimensional sequence")
    pool_size = int(values.size)
    if not 0 <= selection_size <= pool_size:
        raise ValueError("selection_size must be between zero and pool size")

    dp = np.full(selection_size + 1, -np.inf, dtype=np.float64)
    dp[0] = 0.0
    for item_index, log_weight in enumerate(values, start=1):
        upper = min(selection_size, item_index)
        for chosen in range(upper, 0, -1):
            dp[chosen] = np.logaddexp(dp[chosen], dp[chosen - 1] + log_weight)
    return float(dp[selection_size])


def fixed_size_selection_nll(
    log_weights: Sequence[float],
    selected_indices: Sequence[int],
) -> float:
    """Return exact NLL for one unordered selected subset of a fixed size."""

    values = np.asarray(tuple(log_weights), dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("log_weights must be a finite one-dimensional sequence")
    indices = tuple(selected_indices)
    if any(not isinstance(index, (int, np.integer)) for index in indices):
        raise ValueError("selected_indices must contain integers")
    normalized = tuple(int(index) for index in indices)
    if len(set(normalized)) != len(normalized):
        raise ValueError("selected_indices must not contain duplicates")
    if any(index < 0 or index >= len(values) for index in normalized):
        raise ValueError("selected index is outside the available pool")

    log_partition = log_fixed_size_partition(values, len(normalized))
    selected_score = float(sum(values[index] for index in normalized))
    return log_partition - selected_score


def random_selection_baseline_nll(pool_size: int, selection_size: int) -> float:
    """NLL of uniformly choosing one size-m subset from a pool of size n."""

    if not 0 <= selection_size <= pool_size:
        raise ValueError("selection_size must be between zero and pool size")
    return (
        math.lgamma(pool_size + 1)
        - math.lgamma(selection_size + 1)
        - math.lgamma(pool_size - selection_size + 1)
    )


def _embedding_matrix(values: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("each DJ crate must be a non-empty 2D embedding matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("embeddings must be finite")
    return matrix


def _nearest_distances(
    source: np.ndarray,
    target: np.ndarray,
    *,
    exclude_same_index: bool = False,
    chunk_size: int = 512,
) -> np.ndarray:
    nearest = np.full(source.shape[0], np.inf, dtype=np.float64)
    target_sq = np.sum(target * target, axis=1)
    for start in range(0, source.shape[0], chunk_size):
        stop = min(start + chunk_size, source.shape[0])
        chunk = source[start:stop]
        squared = (
            np.sum(chunk * chunk, axis=1)[:, None]
            + target_sq[None, :]
            - 2.0 * chunk @ target.T
        )
        np.maximum(squared, 0.0, out=squared)
        if exclude_same_index:
            rows = np.arange(stop - start)
            squared[rows, np.arange(start, stop)] = np.inf
        nearest[start:stop] = np.sqrt(np.min(squared, axis=1))
    return nearest


def assess_crate_overlap(
    embeddings_by_dj: Mapping[str, Sequence[Sequence[float]] | np.ndarray],
    *,
    set_counts: Mapping[str, int] | None = None,
    alpha: float = 2.5,
) -> CrateOverlapReport:
    """Measure whether a DJ effect can be separated from audio-space crate choice."""

    if not math.isfinite(alpha) or alpha <= 0.0:
        raise ValueError("alpha must be finite and positive")
    if not embeddings_by_dj:
        raise ValueError("at least one DJ crate is required")

    matrices = {
        str(dj): _embedding_matrix(embeddings)
        for dj, embeddings in embeddings_by_dj.items()
    }
    dimensions = {matrix.shape[1] for matrix in matrices.values()}
    if len(dimensions) != 1:
        raise ValueError("all DJ embeddings must use the same dimensionality")

    warnings: list[str] = []
    epsilon_by_dj: dict[str, float | None] = {}
    for dj, matrix in matrices.items():
        if matrix.shape[0] < 2:
            epsilon_by_dj[dj] = None
            warnings.append(f"{dj}: fewer than two tracks; local audio scale undefined")
            continue
        nearest = _nearest_distances(matrix, matrix, exclude_same_index=True)
        local_scale = float(np.median(nearest))
        if local_scale <= 0.0:
            epsilon_by_dj[dj] = None
            warnings.append(f"{dj}: collapsed embedding geometry; local audio scale undefined")
            continue
        epsilon_by_dj[dj] = alpha * local_scale

    directional: dict[str, dict[str, float]] = {dj: {} for dj in matrices}
    for source_dj, source in matrices.items():
        epsilon = epsilon_by_dj[source_dj]
        if epsilon is None:
            continue
        for target_dj, target in matrices.items():
            if source_dj == target_dj:
                continue
            nearest = _nearest_distances(source, target)
            directional[source_dj][target_dj] = float(np.mean(nearest < epsilon))

    q_by_dj: dict[str, float | None] = {}
    for dj in matrices:
        pair_scores = []
        for other in matrices:
            if other == dj:
                continue
            forward = directional[dj].get(other)
            reverse = directional[other].get(dj)
            if forward is not None and reverse is not None:
                pair_scores.append(min(forward, reverse))
        q_by_dj[dj] = max(pair_scores) if pair_scores else None
        if not pair_scores:
            warnings.append(f"{dj}: no mutually identifiable comparison crate")

    counts = dict(set_counts or {})
    weighted_numerator = 0.0
    weighted_denominator = 0
    for dj, q_value in q_by_dj.items():
        count = counts.get(dj, 1)
        if not isinstance(count, int) or count <= 0:
            raise ValueError("set_counts must contain positive integers")
        if q_value is not None:
            weighted_numerator += count * q_value
            weighted_denominator += count
    weighted_q = (
        weighted_numerator / weighted_denominator
        if weighted_denominator
        else None
    )

    return CrateOverlapReport(
        epsilon_by_dj=epsilon_by_dj,
        directional_overlap=directional,
        q_by_dj=q_by_dj,
        weighted_q=weighted_q,
        alpha=alpha,
        warnings=tuple(warnings),
    )


def block_bootstrap_set_ids(
    set_ids: Sequence[str],
    *,
    replicates: int,
    seed: int = 0,
) -> tuple[tuple[str, ...], ...]:
    """Sample whole DJ sets for external full-refit bootstrap replicates."""

    blocks = tuple(str(set_id) for set_id in set_ids)
    if not blocks or len(set(blocks)) != len(blocks):
        raise ValueError("set_ids must be a non-empty sequence of unique block IDs")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    rng = np.random.default_rng(seed)
    return tuple(
        tuple(blocks[index] for index in rng.integers(0, len(blocks), len(blocks)))
        for _ in range(replicates)
    )

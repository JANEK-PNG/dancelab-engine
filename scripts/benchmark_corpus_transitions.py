#!/usr/bin/env python3
"""Benchmark the production transition scorer on real DJ-mix adjacencies.

The benchmark asks the same question as the product-level Janek benchmark:
given the track currently playing and a product-sized library, how highly does
the production ``transition_score(..., planner_mode="smart")`` rank the track
that the DJ actually played next?

Candidate-pool contract (default ``--pool-size 230``):

* every case is one *direct* neighbouring pair in the raw MixesDB tracklist;
  missing positions are never skipped over to manufacture an adjacency;
* the true next track is included once;
* the other 229 tracks are sampled uniformly, without replacement, from the
  frozen H-analysis index after removing the current and true-next tracks;
* sampling is derived from ``seed + case identity`` and never uses features or
  scores, so changing ``--limit`` cannot change a retained case's pool;
* ``--pool-size 0`` uses every indexed H track except the current track.

This is leakage-safe with respect to candidate construction, but it is NOT a
fully out-of-sample model test: the production corpus priors were estimated on
DJ-mix transitions from the same underlying corpus.  The JSON and stdout call
that limitation out explicitly.  Confidence intervals use a cluster bootstrap
over whole mixes, preserving within-mix dependence.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/benchmark_corpus_transitions.py
    PYTHONPATH=src .venv/bin/python scripts/benchmark_corpus_transitions.py \
        --limit 3 --bootstrap-samples 100 --output /tmp/corpus-transition-smoke.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.core.config import load_weights  # noqa: E402
from dancelab.core.models import AnalysisResult  # noqa: E402
from dancelab.decision.mixability import precompute_mixability_inputs  # noqa: E402
from dancelab.decision.set_builder import track_energy, transition_score  # noqa: E402


DEFAULT_DATASET = Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
DEFAULT_INDEX = ROOT / "data/reports/corpus_ordering/analysis_index.json"
DEFAULT_ANALYSIS_DIR = ROOT / "data/reports/corpus_ordering/h_analysis"
DEFAULT_WEIGHTS = ROOT / "configs/descriptor_weights.yaml"
DEFAULT_OUTPUT = ROOT / "data/reports/corpus_transitions/benchmark.json"
DEFAULT_PRIORS = ROOT / "data/reports/corpus_priors/priors_v1.json"

SCHEMA_VERSION = "corpus-transition-benchmark-v1"
INDEX_SCHEMA_VERSION = "ordering-analysis-index-v1"
DEFAULT_POOL_SIZE = 230
DEFAULT_SEED = 20260801
DEFAULT_BOOTSTRAP_SAMPLES = 2_000
SCORE_TIE_ABS_TOLERANCE = 1e-12
FEATURE_MEAN_NAMES = (
    "rms",
    "low_freq_energy_ratio",
    "vocal_density_proxy",
    "tension_proxy",
)


class BenchmarkError(RuntimeError):
    """A clear input or benchmark-contract failure."""


@dataclass(frozen=True)
class TransitionCase:
    mix_id: str
    mix_index: int
    from_position: int
    current_track_id: str
    true_next_track_id: str

    @property
    def identity(self) -> str:
        return (
            f"{self.mix_id}\0{self.from_position}\0"
            f"{self.current_track_id}\0{self.true_next_track_id}"
        )


@dataclass(frozen=True)
class CandidatePool:
    track_ids: tuple[str, ...]
    random_control_track_id: str
    fingerprint: str


@dataclass(frozen=True)
class EvaluationRow:
    mix_id: str
    from_position: int
    current_track_id: str
    true_next_track_id: str
    candidate_pool_size: int
    candidate_pool_sha256: str
    midrank: float
    percentile: float
    true_score: float
    random_control_track_id: str
    random_control_score: float
    mean_decoy_score: float
    tie_block_size: int
    top_5: bool
    top_10: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "mix_id": self.mix_id,
            "from_position": self.from_position,
            "current_track_id": self.current_track_id,
            "true_next_track_id": self.true_next_track_id,
            "candidate_pool_size": self.candidate_pool_size,
            "candidate_pool_sha256": self.candidate_pool_sha256,
            "midrank": round(self.midrank, 6),
            "percentile": round(self.percentile, 8),
            "true_score": round(self.true_score, 8),
            "random_control_track_id": self.random_control_track_id,
            "random_control_score": round(self.random_control_score, 8),
            "mean_decoy_score": round(self.mean_decoy_score, 8),
            "tie_block_size": self.tie_block_size,
            "top_5": self.top_5,
            "top_10": self.top_10,
        }


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise BenchmarkError(f"required file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkError(f"invalid JSON in {path}: {exc}") from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise BenchmarkError(f"cannot fingerprint {path}: {exc}") from exc
    return digest.hexdigest()


def _clean_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_index(path: Path) -> dict[str, str]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise BenchmarkError("analysis index must be a JSON object")
    if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise BenchmarkError(
            "unexpected analysis-index schema: "
            f"{payload.get('schema_version')!r}; expected {INDEX_SCHEMA_VERSION!r}"
        )
    raw_tracks = payload.get("tracks")
    if not isinstance(raw_tracks, Mapping) or not raw_tracks:
        raise BenchmarkError("analysis index must contain a non-empty 'tracks' object")

    tracks: dict[str, str] = {}
    for raw_track_id, raw_relative_path in raw_tracks.items():
        track_id = _clean_id(raw_track_id)
        relative_path = _clean_id(raw_relative_path)
        if track_id is None or relative_path is None:
            raise BenchmarkError("analysis index contains an empty track ID or path")
        tracks[track_id] = relative_path
    if len(tracks) != len(raw_tracks):
        raise BenchmarkError("analysis index contains duplicate normalized track IDs")
    return dict(sorted(tracks.items()))


def _build_cases(
    dataset_path: Path,
    indexed_track_ids: set[str],
) -> tuple[list[TransitionCase], dict[str, int]]:
    payload = _read_json(dataset_path)
    if not isinstance(payload, list):
        raise BenchmarkError("djmix dataset must be a JSON list")

    cases: list[TransitionCase] = []
    seen_mix_ids: set[str] = set()
    audit: defaultdict[str, int] = defaultdict(int)
    audit["dataset_mixes"] = len(payload)

    for mix_index, mix in enumerate(payload):
        if not isinstance(mix, Mapping):
            raise BenchmarkError(f"mix at index {mix_index} is not an object")
        mix_id = _clean_id(mix.get("id"))
        if mix_id is None:
            raise BenchmarkError(f"mix at index {mix_index} has no ID")
        if mix_id in seen_mix_ids:
            raise BenchmarkError(f"duplicate mix ID in dataset: {mix_id}")
        seen_mix_ids.add(mix_id)

        tracklist = mix.get("tracklist")
        if not isinstance(tracklist, list):
            raise BenchmarkError(f"mix {mix_id} has no list-valued tracklist")
        audit["raw_adjacent_positions"] += max(0, len(tracklist) - 1)

        for zero_based_position in range(len(tracklist) - 1):
            left = tracklist[zero_based_position]
            right = tracklist[zero_based_position + 1]
            if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                raise BenchmarkError(
                    f"mix {mix_id} has a non-object track at position "
                    f"{zero_based_position + 1} or {zero_based_position + 2}"
                )
            current_id = _clean_id(left.get("id"))
            next_id = _clean_id(right.get("id"))
            if current_id is None or next_id is None:
                audit["excluded_missing_track_id"] += 1
                continue
            if current_id == next_id:
                audit["excluded_self_pair"] += 1
                continue
            if current_id not in indexed_track_ids or next_id not in indexed_track_ids:
                audit["excluded_missing_h_analysis"] += 1
                continue
            cases.append(
                TransitionCase(
                    mix_id=mix_id,
                    mix_index=mix_index,
                    # One-based position of A; B is therefore from_position + 1.
                    from_position=zero_based_position + 1,
                    current_track_id=current_id,
                    true_next_track_id=next_id,
                )
            )

    audit["eligible_direct_pairs"] = len(cases)
    audit["eligible_mixes"] = len({case.mix_id for case in cases})
    return cases, dict(audit)


def _select_cases(cases: Sequence[TransitionCase], limit: int, seed: int) -> list[TransitionCase]:
    if limit <= 0 or limit >= len(cases):
        return list(cases)
    rng = random.Random(seed)
    selected = rng.sample(list(cases), limit)
    return sorted(selected, key=lambda case: (case.mix_index, case.from_position))


def _case_rng(seed: int, case: TransitionCase) -> random.Random:
    material = f"{seed}\0{case.identity}".encode()
    derived_seed = int.from_bytes(hashlib.sha256(material).digest()[:16], "big")
    return random.Random(derived_seed)


def _candidate_pool(
    case: TransitionCase,
    universe: Sequence[str],
    pool_size: int,
    seed: int,
) -> CandidatePool:
    decoy_universe = [
        track_id
        for track_id in universe
        if track_id not in {case.current_track_id, case.true_next_track_id}
    ]
    actual_size = len(universe) - 1 if pool_size == 0 else pool_size
    decoy_count = actual_size - 1
    if decoy_count > len(decoy_universe):
        raise BenchmarkError(
            f"candidate pool {actual_size} is larger than the available universe "
            f"({len(universe) - 1})"
        )

    rng = _case_rng(seed, case)
    if decoy_count == len(decoy_universe):
        decoys = list(decoy_universe)
    else:
        decoys = rng.sample(decoy_universe, decoy_count)
    if not decoys:
        raise BenchmarkError("candidate pool needs at least one negative candidate")
    random_control = rng.choice(decoys)
    candidates = (case.true_next_track_id, *decoys)
    fingerprint = hashlib.sha256("\n".join(sorted(candidates)).encode()).hexdigest()
    return CandidatePool(
        track_ids=candidates,
        random_control_track_id=random_control,
        fingerprint=fingerprint,
    )


def _finite_feature_mean(
    frames: Sequence[object],
    feature_name: str,
    *,
    catalog_id: str,
) -> float | None:
    values: list[float] = []
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, Mapping):
            raise BenchmarkError(
                f"analysis {catalog_id} has a non-object feature frame at {frame_index}"
            )
        raw_value = frame.get(feature_name)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise BenchmarkError(
                f"analysis {catalog_id} has invalid {feature_name}: {raw_value!r}"
            ) from exc
        if not math.isfinite(value):
            raise BenchmarkError(
                f"analysis {catalog_id} has non-finite {feature_name}: {raw_value!r}"
            )
        values.append(value)
    return statistics.fmean(values) if values else None


def _load_slim_analyses(
    index: Mapping[str, str],
    analysis_dir: Path,
) -> tuple[dict[str, AnalysisResult], str]:
    """Load exactly the information consumed by production pair scoring.

    ``transition_score`` calls mixability without transition windows, so its H
    feature inputs are the four per-track means computed by
    ``precompute_mixability_inputs``.  Representing each mean as one frame is
    exactly equivalent for this code path and avoids retaining ~418 MB of
    unused beat arrays and frame-level curves.  The production scorer and its
    production precomputation function are still called unchanged.
    """

    root = analysis_dir.resolve()
    analyses: dict[str, AnalysisResult] = {}
    internal_ids: dict[str, str] = {}
    catalog_digest = hashlib.sha256()

    for catalog_id, relative_path in index.items():
        path = (root / relative_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise BenchmarkError(
                f"analysis path for {catalog_id} escapes analysis directory: {relative_path}"
            ) from exc
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise BenchmarkError(f"cannot read H analysis for {catalog_id}: {path}") from exc
        try:
            payload = json.loads(raw_bytes)
        except json.JSONDecodeError as exc:
            raise BenchmarkError(f"invalid H analysis JSON for {catalog_id}: {path}") from exc
        if not isinstance(payload, Mapping):
            raise BenchmarkError(f"H analysis for {catalog_id} is not a JSON object")

        raw_frames = payload.get("features", [])
        if not isinstance(raw_frames, list):
            raise BenchmarkError(f"H analysis {catalog_id} has non-list features")
        means = {
            name: _finite_feature_mean(raw_frames, name, catalog_id=catalog_id)
            for name in FEATURE_MEAN_NAMES
        }
        raw_track = payload.get("track")
        if not isinstance(raw_track, Mapping):
            raise BenchmarkError(f"H analysis {catalog_id} has no track object")
        internal_track_id = _clean_id(raw_track.get("track_id"))
        if internal_track_id is None:
            raise BenchmarkError(f"H analysis {catalog_id} has no internal track ID")
        previous_catalog_id = internal_ids.get(internal_track_id)
        if previous_catalog_id is not None:
            raise BenchmarkError(
                f"H analyses {previous_catalog_id} and {catalog_id} share internal track ID "
                f"{internal_track_id}; precomputation would be ambiguous"
            )
        internal_ids[internal_track_id] = catalog_id

        mean_frame = {
            "track_id": internal_track_id,
            "timestamp_sec": 0.0,
            **means,
        }
        slim_payload = {
            "schema_version": payload.get("schema_version", "1.0.0"),
            "engine_version": payload.get("engine_version"),
            "weights_version": payload.get("weights_version"),
            "track": raw_track,
            "features": [mean_frame],
        }
        try:
            analyses[catalog_id] = AnalysisResult.model_validate(slim_payload)
        except Exception as exc:
            raise BenchmarkError(f"invalid score inputs in H analysis {catalog_id}: {exc}") from exc

        catalog_digest.update(catalog_id.encode())
        catalog_digest.update(b"\0")
        catalog_digest.update(relative_path.encode())
        catalog_digest.update(b"\0")
        catalog_digest.update(hashlib.sha256(raw_bytes).digest())

    return analyses, catalog_digest.hexdigest()


def _score_is_tied(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=SCORE_TIE_ABS_TOLERANCE)


def _evaluate(
    cases: Sequence[TransitionCase],
    pools: Mapping[TransitionCase, CandidatePool],
    analyses: Mapping[str, AnalysisResult],
    weights: Any,
    *,
    progress_every: int,
) -> tuple[list[EvaluationRow], dict[str, int]]:
    precomputed = precompute_mixability_inputs(analyses.values())
    energies = {track_id: track_energy(analysis) for track_id, analysis in analyses.items()}
    energy_values = list(energies.values())
    energy_range = max(energy_values) - min(energy_values)
    if not math.isfinite(energy_range) or energy_range <= 0.0:
        raise BenchmarkError("H-analysis energy range is not finite and positive")

    score_cache: dict[tuple[str, str], float] = {}

    def score(current_id: str, candidate_id: str) -> float:
        cache_key = (current_id, candidate_id)
        cached = score_cache.get(cache_key)
        if cached is not None:
            return cached
        value, _relation, _reasoning = transition_score(
            analyses[current_id],
            analyses[candidate_id],
            weights,
            "build",
            energies[current_id],
            energies[candidate_id],
            energy_range,
            planner_mode="smart",
            context=None,
            mixability_precomputation=precomputed,
        )
        value = float(value)
        if not math.isfinite(value):
            raise BenchmarkError(
                f"production scorer returned a non-finite value for "
                f"{current_id} -> {candidate_id}"
            )
        score_cache[cache_key] = value
        return value

    rows: list[EvaluationRow] = []
    for case_index, case in enumerate(cases, start=1):
        pool = pools[case]
        scores = {
            candidate_id: score(case.current_track_id, candidate_id)
            for candidate_id in pool.track_ids
        }
        true_score = scores[case.true_next_track_id]
        better_count = sum(
            candidate_score > true_score
            and not _score_is_tied(candidate_score, true_score)
            for candidate_score in scores.values()
        )
        tie_block_size = sum(
            _score_is_tied(candidate_score, true_score)
            for candidate_score in scores.values()
        )
        midrank = 1.0 + better_count + 0.5 * (tie_block_size - 1)
        pool_size = len(pool.track_ids)
        percentile = 1.0 - (midrank - 1.0) / (pool_size - 1)
        decoy_scores = [
            candidate_score
            for candidate_id, candidate_score in scores.items()
            if candidate_id != case.true_next_track_id
        ]
        rows.append(
            EvaluationRow(
                mix_id=case.mix_id,
                from_position=case.from_position,
                current_track_id=case.current_track_id,
                true_next_track_id=case.true_next_track_id,
                candidate_pool_size=pool_size,
                candidate_pool_sha256=pool.fingerprint,
                midrank=midrank,
                percentile=percentile,
                true_score=true_score,
                random_control_track_id=pool.random_control_track_id,
                random_control_score=scores[pool.random_control_track_id],
                mean_decoy_score=statistics.fmean(decoy_scores),
                tie_block_size=tie_block_size,
                top_5=midrank <= 5.0,
                top_10=midrank <= 10.0,
            )
        )
        if case_index % progress_every == 0 or case_index == len(cases):
            print(
                f"  scoring {case_index}/{len(cases)} | "
                f"unikalne A->B w cache: {len(score_cache)}",
                flush=True,
            )

    return rows, {"unique_scored_pairs": len(score_cache)}


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    if not materialized:
        raise BenchmarkError("cannot summarize an empty metric")
    return statistics.fmean(materialized)


def _estimates(rows: Sequence[EvaluationRow]) -> dict[str, float]:
    return {
        "top_5_rate": _mean(float(row.top_5) for row in rows),
        "top_10_rate": _mean(float(row.top_10) for row in rows),
        "mean_percentile": _mean(row.percentile for row in rows),
        "mean_true_score": _mean(row.true_score for row in rows),
        "mean_random_control_score": _mean(row.random_control_score for row in rows),
        "mean_score_delta_vs_random_control": _mean(
            row.true_score - row.random_control_score for row in rows
        ),
        "mean_decoy_score": _mean(row.mean_decoy_score for row in rows),
        "mean_score_delta_vs_decoy_mean": _mean(
            row.true_score - row.mean_decoy_score for row in rows
        ),
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise BenchmarkError("cannot take a quantile of an empty sequence")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _cluster_bootstrap(
    rows: Sequence[EvaluationRow],
    *,
    samples: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    if samples <= 0:
        return {}
    by_mix: defaultdict[str, list[EvaluationRow]] = defaultdict(list)
    for row in rows:
        by_mix[row.mix_id].append(row)
    mix_ids = sorted(by_mix)
    rng = random.Random(seed ^ 0xB00757A9)
    draws: defaultdict[str, list[float]] = defaultdict(list)

    for _ in range(samples):
        sampled_rows: list[EvaluationRow] = []
        for _mix_slot in mix_ids:
            sampled_rows.extend(by_mix[rng.choice(mix_ids)])
        for metric_name, estimate in _estimates(sampled_rows).items():
            draws[metric_name].append(estimate)

    return {
        metric_name: (_quantile(values, 0.025), _quantile(values, 0.975))
        for metric_name, values in draws.items()
    }


def _metric_payload(
    estimate: float,
    intervals: Mapping[str, tuple[float, float]],
    metric_name: str,
) -> dict[str, object]:
    interval = intervals.get(metric_name)
    return {
        "estimate": round(estimate, 8),
        "ci95": (
            [round(interval[0], 8), round(interval[1], 8)]
            if interval is not None
            else None
        ),
    }


def _build_report(
    *,
    args: argparse.Namespace,
    index: Mapping[str, str],
    audit: Mapping[str, int],
    cases: Sequence[TransitionCase],
    rows: Sequence[EvaluationRow],
    weights: Any,
    analysis_catalog_sha256: str,
    scoring_audit: Mapping[str, int],
) -> dict[str, object]:
    estimates = _estimates(rows)
    intervals = _cluster_bootstrap(
        rows,
        samples=args.bootstrap_samples,
        seed=args.seed,
    )
    pool_sizes = [row.candidate_pool_size for row in rows]
    random_top_5 = _mean(min(5, size) / size for size in pool_sizes)
    random_top_10 = _mean(min(10, size) / size for size in pool_sizes)
    ties = [row.tie_block_size for row in rows]
    priors_path = Path(os.environ.get("DANCELAB_CORPUS_PRIORS", DEFAULT_PRIORS))

    metrics = {
        metric_name: _metric_payload(estimate, intervals, metric_name)
        for metric_name, estimate in estimates.items()
    }
    metrics.update(
        {
            "median_true_score": round(statistics.median(row.true_score for row in rows), 8),
            "median_random_control_score": round(
                statistics.median(row.random_control_score for row in rows), 8
            ),
            "median_midrank": round(statistics.median(row.midrank for row in rows), 6),
            "tie_rate": round(_mean(float(size > 1) for size in ties), 8),
            "mean_tie_block_size": round(_mean(ties), 8),
            "max_tie_block_size": max(ties),
        }
    )

    coverage = dict(audit)
    coverage.update(
        {
            "evaluated_pairs": len(rows),
            "evaluated_mixes": len({row.mix_id for row in rows}),
            "limit_requested": args.limit,
        }
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "configuration": {
            "seed": args.seed,
            "pool_size_requested": args.pool_size,
            "pool_size_zero_means_full_index": True,
            "bootstrap_samples": args.bootstrap_samples,
            "bootstrap_unit": "mix_id",
            "planner_mode": "smart",
            "arc": "build",
            "weights_version": weights.version,
            "corpus_priors_weight": float(weights.corpus_priors_weight),
            "score_tie_policy": (
                "midrank = 1 + count(score > truth) + "
                "0.5 * count(other scores tied with truth)"
            ),
            "score_tie_absolute_tolerance": SCORE_TIE_ABS_TOLERANCE,
            "percentile_definition": "1 - (midrank - 1) / (pool_size - 1); 1=best",
        },
        "inputs": {
            "dataset": str(args.dataset.resolve()),
            "dataset_sha256": _file_sha256(args.dataset),
            "analysis_index": str(args.analysis_index.resolve()),
            "analysis_index_sha256": _file_sha256(args.analysis_index),
            "analysis_index_schema": INDEX_SCHEMA_VERSION,
            "analysis_index_tracks": len(index),
            "analysis_dir": str(args.analysis_dir.resolve()),
            "analysis_catalog_sha256": analysis_catalog_sha256,
            "weights": str(args.weights.resolve()),
            "weights_sha256": _file_sha256(args.weights),
            "corpus_priors": str(priors_path.resolve()),
            "corpus_priors_sha256": _file_sha256(priors_path) if priors_path.is_file() else None,
        },
        "coverage": coverage,
        "candidate_pool": {
            "definition": (
                "true next track plus uniformly sampled H-index decoys; current track "
                "and true next are excluded from the decoy universe"
            ),
            "universe": "all track IDs in frozen analysis_index.json",
            "sampling_without_replacement": True,
            "sampling_uses_features_or_scores": False,
            "target_force_included": True,
            "size_min": min(pool_sizes),
            "size_median": statistics.median(pool_sizes),
            "size_max": max(pool_sizes),
            "nominal_random_baseline": {
                "top_5_rate": round(random_top_5, 8),
                "top_10_rate": round(random_top_10, 8),
                "mean_percentile": 0.5,
            },
        },
        "metrics": metrics,
        "uncertainty": {
            "method": (
                "percentile cluster bootstrap over mix_id"
                if args.bootstrap_samples > 0
                else "disabled by --bootstrap-samples 0"
            ),
            "confidence_level": 0.95 if args.bootstrap_samples > 0 else None,
            "resamples": args.bootstrap_samples,
            "scope": (
                "sampling uncertainty across observed mixes, conditional on this fixed "
                "candidate draw and production model"
            ),
            "does_not_cover": [
                "candidate-pool Monte Carlo variation across seeds",
                "dependence caused by the same track or transition appearing in different mixes",
                "training/evaluation overlap in production corpus priors",
            ],
        },
        "leakage_assessment": {
            "candidate_construction": (
                "No scorer, feature, genre, or future tracklist position is used to choose decoys. "
                "The labelled next track is force-included only so its rank is defined."
            ),
            "direct_adjacency": (
                "Only raw neighbouring positions are used; missing IDs/analyses break a case "
                "instead of being skipped over."
            ),
            "known_model_leakage_risk": (
                "Production corpus priors were estimated from DJ-mix transitions in the same "
                "underlying corpus. This result is in-sample for that component and must not be "
                "claimed as out-of-sample generalization."
            ),
            "availability_proxy_risk": (
                "The corpus does not expose each DJ's real crate at performance time. A random "
                "230-track H-index library matches product-scale difficulty, not historical "
                "ownership, genre, or release-date availability."
            ),
        },
        "scoring_audit": dict(scoring_audit),
        "observations": [row.as_dict() for row in rows],
    }


def _write_report(report: Mapping[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def _format_ci(metric: Mapping[str, object], *, percent: bool = False) -> str:
    multiplier = 100.0 if percent else 1.0
    estimate = float(metric["estimate"]) * multiplier
    interval = metric.get("ci95")
    suffix = "%" if percent else ""
    if not isinstance(interval, list):
        return f"{estimate:.3f}{suffix}"
    return (
        f"{estimate:.3f}{suffix} "
        f"(95% CI {float(interval[0]) * multiplier:.3f}–"
        f"{float(interval[1]) * multiplier:.3f}{suffix})"
    )


def _print_summary(report: Mapping[str, object], output: Path) -> None:
    coverage = report["coverage"]
    pool = report["candidate_pool"]
    metrics = report["metrics"]
    baseline = pool["nominal_random_baseline"]
    assert isinstance(coverage, Mapping)
    assert isinstance(pool, Mapping)
    assert isinstance(metrics, Mapping)
    assert isinstance(baseline, Mapping)

    print("\n══ BENCHMARK PRAWDZIWYCH PRZEJŚĆ KORPUSU ══")
    print(
        f"pary / miksy:          {coverage['evaluated_pairs']} / "
        f"{coverage['evaluated_mixes']}"
    )
    print(
        f"pula kandydatów:       {pool['size_median']} "
        f"(H-index: {report['inputs']['analysis_index_tracks']})"
    )
    print(
        f"top-5:                 {_format_ci(metrics['top_5_rate'], percent=True)} "
        f"| losowo {float(baseline['top_5_rate']) * 100:.2f}%"
    )
    print(
        f"top-10:                {_format_ci(metrics['top_10_rate'], percent=True)} "
        f"| losowo {float(baseline['top_10_rate']) * 100:.2f}%"
    )
    print(
        f"średni percentyl:      {_format_ci(metrics['mean_percentile'])} "
        "| losowo 0.500 | 1 = najlepiej"
    )
    print(
        f"score prawdziwy:       {_format_ci(metrics['mean_true_score'])} "
        f"| mediana {float(metrics['median_true_score']):.3f}"
    )
    print(
        f"score losowy (1/pair): {_format_ci(metrics['mean_random_control_score'])} "
        f"| mediana {float(metrics['median_random_control_score']):.3f}"
    )
    print(
        f"Δ true − mean decoys:  "
        f"{_format_ci(metrics['mean_score_delta_vs_decoy_mean'])}"
    )
    print(
        f"remisy przy truth:     {float(metrics['tie_rate']) * 100:.2f}% par "
        f"| max blok {metrics['max_tie_block_size']}"
    )
    print(
        "\nUWAGA O LEAKAGE: produkcyjne corpus priors powstały częściowo z tego "
        "samego korpusu; wynik nie jest w pełni out-of-sample."
    )
    print(f"JSON: {output.resolve()}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--analysis-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--pool-size",
        type=int,
        default=DEFAULT_POOL_SIZE,
        help="candidate count including truth; 0 uses the full H index (default: 230)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="deterministically sample at most N eligible pairs; 0 evaluates all",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=DEFAULT_BOOTSTRAP_SAMPLES,
    )
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args(argv)

    if args.pool_size == 1 or args.pool_size < 0:
        parser.error("--pool-size must be 0 (full index) or at least 2")
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.bootstrap_samples < 0:
        parser.error("--bootstrap-samples must be non-negative")
    if args.progress_every < 1:
        parser.error("--progress-every must be positive")
    return args


def run(args: argparse.Namespace) -> int:
    index = _load_index(args.analysis_index)
    maximum_pool_size = len(index) - 1
    if args.pool_size > maximum_pool_size:
        raise BenchmarkError(
            f"--pool-size {args.pool_size} exceeds H-index capacity {maximum_pool_size}; "
            "use 0 for the full index"
        )

    all_cases, audit = _build_cases(args.dataset, set(index))
    if not all_cases:
        raise BenchmarkError("no direct adjacent pairs have H analysis at both ends")
    cases = _select_cases(all_cases, args.limit, args.seed)
    print(
        f"dataset: {audit['dataset_mixes']} miksów | "
        f"direct eligible: {audit['eligible_direct_pairs']} par / "
        f"{audit['eligible_mixes']} miksów",
        flush=True,
    )
    if args.limit:
        print(f"--limit: deterministyczna próba {len(cases)} par", flush=True)

    universe = tuple(index)
    pools = {
        case: _candidate_pool(case, universe, args.pool_size, args.seed)
        for case in cases
    }
    actual_pool_size = len(next(iter(pools.values())).track_ids)
    print(
        f"pula: truth + {actual_pool_size - 1} losowych decoys "
        f"z zamrożonego H-index ({len(index)}), seed={args.seed}",
        flush=True,
    )

    analyses, analysis_catalog_sha256 = _load_slim_analyses(index, args.analysis_dir)
    print(f"H analyses: {len(analyses)} poprawnie załadowanych", flush=True)
    weights = load_weights(args.weights)
    if weights.set_builder is None:
        raise BenchmarkError("weights file has no set_builder weights")
    rows, scoring_audit = _evaluate(
        cases,
        pools,
        analyses,
        weights,
        progress_every=args.progress_every,
    )
    report = _build_report(
        args=args,
        index=index,
        audit=audit,
        cases=cases,
        rows=rows,
        weights=weights,
        analysis_catalog_sha256=analysis_catalog_sha256,
        scoring_audit=scoring_audit,
    )
    _write_report(report, args.output)
    _print_summary(report, args.output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return run(args)
    except (BenchmarkError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Leakage-safe ordering dataset derived from aligned DJ mixes.

The public DJ-mix corpus observes performed sequences, not each DJ's complete
library. This module therefore models only:

    P(next track | observed crate, performed history)

It must not be interpreted as a model of:

    P(track selected | DJ's complete library)

The builder is deliberately read-only. It consumes the corpus metadata and
alignment reports, splits each mix at missing or low-confidence tracks, and
creates choices only inside contiguous, confidently aligned runs.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


ORDERING_DATASET_SCHEMA_VERSION = "corpus-ordering-v1"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _fingerprint(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_dataset_path(root: Path) -> Path:
    candidates = (
        root / "djmix-dataset.json",
        root / "dataset" / "dataset.json",
    )
    available = [path for path in candidates if path.is_file()]
    if not available:
        expected = " or ".join(str(path) for path in candidates)
        raise FileNotFoundError(f"corpus metadata not found; expected {expected}")
    if len(available) == 2 and _file_sha256(available[0]) != _file_sha256(available[1]):
        raise ValueError(
            "ambiguous corpus metadata: djmix-dataset.json and "
            "dataset/dataset.json both exist but have different content"
        )
    return available[0]


def _clean_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _finite_number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


@dataclass(frozen=True)
class OrderingObservation:
    """One conditional next-track choice inside an observed mix crate."""

    mix_id: str
    run_id: str
    position: int
    history_track_ids: tuple[str, ...]
    candidate_track_ids: tuple[str, ...]
    selected_track_id: str
    genre_labels: tuple[str, ...] = ()
    dj_id: str | None = None

    def __post_init__(self) -> None:
        if not self.mix_id:
            raise ValueError("mix_id must not be empty")
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        if self.position < 1:
            raise ValueError("position must be at least 1")
        if not self.history_track_ids:
            raise ValueError("history_track_ids must not be empty")
        if len(self.candidate_track_ids) < 2:
            raise ValueError("an ordering observation needs at least two candidates")
        if len(set(self.candidate_track_ids)) != len(self.candidate_track_ids):
            raise ValueError("candidate_track_ids must be unique")
        if tuple(sorted(self.candidate_track_ids)) != self.candidate_track_ids:
            raise ValueError("candidate_track_ids must use canonical sorted order")
        if self.selected_track_id not in self.candidate_track_ids:
            raise ValueError("selected_track_id must be present in candidate_track_ids")

    @property
    def current_track_id(self) -> str:
        return self.history_track_ids[-1]

    def as_dict(self) -> dict[str, object]:
        return {
            "mix_id": self.mix_id,
            "run_id": self.run_id,
            "position": self.position,
            "history_track_ids": list(self.history_track_ids),
            "candidate_track_ids": list(self.candidate_track_ids),
            "selected_track_id": self.selected_track_id,
            "genre_labels": list(self.genre_labels),
            "dj_id": self.dj_id,
        }


@dataclass(frozen=True)
class CorpusOrderingDataset:
    """Immutable dataset plus provenance and quality accounting."""

    observations: tuple[OrderingObservation, ...]
    audit: Mapping[str, object]
    fingerprint: str
    schema_version: str = ORDERING_DATASET_SCHEMA_VERSION

    @property
    def mix_ids(self) -> tuple[str, ...]:
        return tuple(sorted({observation.mix_id for observation in self.observations}))

    @property
    def run_ids(self) -> tuple[str, ...]:
        return tuple(sorted({observation.run_id for observation in self.observations}))

    def as_dict(self, *, include_observations: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "mix_count": len(self.mix_ids),
            "run_count": len(self.run_ids),
            "observation_count": len(self.observations),
            "audit": dict(self.audit),
        }
        if include_observations:
            payload["observations"] = [observation.as_dict() for observation in self.observations]
        return payload


@dataclass(frozen=True)
class OrderingBuildConfig:
    """Quality gates that define the immutable evaluation universe."""

    min_match_rate: float = 0.4
    min_run_tracks: int = 3
    require_reliable_beatgrid: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_match_rate <= 1.0:
            raise ValueError("min_match_rate must be between 0 and 1")
        if self.min_run_tracks < 3:
            raise ValueError("min_run_tracks must be at least 3")

    def as_dict(self) -> dict[str, object]:
        return {
            "min_match_rate": self.min_match_rate,
            "min_run_tracks": self.min_run_tracks,
            "require_reliable_beatgrid": self.require_reliable_beatgrid,
        }


@dataclass(frozen=True)
class _QualifiedTrack:
    catalog_id: str
    audio_source_id: str


def _genre_labels(mix: Mapping[str, object]) -> tuple[str, ...]:
    """Return only source-declared genres, never the general MixesDB tag bag."""

    labels: set[str] = set()
    raw_genres = mix.get("genres", ())
    if not isinstance(raw_genres, list):
        return ()
    for item in raw_genres:
        if isinstance(item, Mapping):
            raw_label = item.get("key")
        else:
            raw_label = item
        label = str(raw_label or "").strip().lower()
        if label:
            labels.add(label)
    return tuple(sorted(labels))


def _qualify_result(
    result: Mapping[str, object],
    config: OrderingBuildConfig,
) -> tuple[_QualifiedTrack | None, str]:
    catalog_id = _clean_identifier(result.get("youtube_id"))
    source_id = _clean_identifier(result.get("track_id"))
    if catalog_id is None or source_id is None:
        return None, "missing_track_identity"

    alignment = result.get("alignment")
    if not isinstance(alignment, Mapping):
        return None, "missing_alignment"
    if alignment.get("matched") is not True:
        return None, "not_matched"

    match_rate = _finite_number(alignment.get("match_rate"))
    if match_rate is None:
        return None, "invalid_match_rate"
    if match_rate < config.min_match_rate:
        return None, "low_match_rate"
    if _finite_number(alignment.get("normalized_cost")) is None:
        return None, "invalid_alignment_cost"

    beatgrid = result.get("track_beatgrid")
    if config.require_reliable_beatgrid:
        if not isinstance(beatgrid, Mapping) or beatgrid.get("reliable") is not True:
            return None, "unreliable_beatgrid"

    return _QualifiedTrack(catalog_id=catalog_id, audio_source_id=source_id), "accepted"


def _emit_run_observations(
    *,
    mix_id: str,
    run_number: int,
    run: list[_QualifiedTrack],
    genre_labels: tuple[str, ...],
    dj_id: str | None,
    config: OrderingBuildConfig,
) -> tuple[list[OrderingObservation], bool]:
    if len(run) < config.min_run_tracks:
        return [], False

    track_ids = tuple(track.catalog_id for track in run)
    observations: list[OrderingObservation] = []
    # The final transition has one remaining candidate and carries no ranking
    # information, so it is intentionally excluded from the loss.
    for selected_index in range(1, len(track_ids) - 1):
        remaining = track_ids[selected_index:]
        observations.append(
            OrderingObservation(
                mix_id=mix_id,
                run_id=f"{mix_id}:run-{run_number}",
                position=selected_index,
                history_track_ids=track_ids[:selected_index],
                candidate_track_ids=tuple(sorted(remaining)),
                selected_track_id=track_ids[selected_index],
                genre_labels=genre_labels,
                dj_id=dj_id,
            )
        )
    return observations, True


def _result_queues(
    report: Mapping[str, object],
) -> tuple[dict[str, deque[Mapping[str, object]]], int]:
    queues: dict[str, deque[Mapping[str, object]]] = defaultdict(deque)
    invalid = 0
    results = report.get("results", ())
    if not isinstance(results, list):
        return queues, invalid
    for item in results:
        if not isinstance(item, Mapping):
            invalid += 1
            continue
        catalog_id = _clean_identifier(item.get("youtube_id"))
        if catalog_id is None:
            invalid += 1
            continue
        queues[catalog_id].append(item)
    return queues, invalid


def _build_mix_observations(
    *,
    mix: Mapping[str, object],
    report: Mapping[str, object],
    config: OrderingBuildConfig,
    dj_id: str | None,
) -> tuple[list[OrderingObservation], Counter[str]]:
    counts: Counter[str] = Counter()
    mix_id = _clean_identifier(mix.get("id"))
    if mix_id is None:
        counts["mix_missing_id"] += 1
        return [], counts

    report_mix_id = _clean_identifier(report.get("mix_id"))
    if report_mix_id != mix_id:
        counts["report_mix_id_mismatch"] += 1
        return [], counts

    tracklist = mix.get("tracklist")
    if not isinstance(tracklist, list):
        counts["mix_invalid_tracklist"] += 1
        return [], counts

    queues, invalid_results = _result_queues(report)
    counts["invalid_report_results"] += invalid_results
    genres = _genre_labels(mix)
    counts["mix_with_explicit_genres" if genres else "mix_without_explicit_genres"] += 1
    observations: list[OrderingObservation] = []
    current_run: list[_QualifiedTrack] = []
    current_catalog_ids: set[str] = set()
    current_source_ids: set[str] = set()
    run_number = 0

    def close_run() -> None:
        nonlocal current_run, current_catalog_ids, current_source_ids, run_number
        if not current_run:
            return
        run_number += 1
        emitted, accepted = _emit_run_observations(
            mix_id=mix_id,
            run_number=run_number,
            run=current_run,
            genre_labels=genres,
            dj_id=dj_id,
            config=config,
        )
        if accepted:
            counts["accepted_runs"] += 1
            counts["accepted_run_tracks"] += len(current_run)
            counts["ordering_observations"] += len(emitted)
            observations.extend(emitted)
        else:
            counts["short_runs"] += 1
            counts["short_run_tracks"] += len(current_run)
        current_run = []
        current_catalog_ids = set()
        current_source_ids = set()

    for raw_track in tracklist:
        counts["metadata_tracks"] += 1
        if not isinstance(raw_track, Mapping):
            counts["invalid_metadata_track"] += 1
            close_run()
            continue

        catalog_id = _clean_identifier(raw_track.get("id"))
        if catalog_id is None:
            counts["metadata_track_missing_id"] += 1
            close_run()
            continue

        if not queues[catalog_id]:
            counts["missing_alignment_result"] += 1
            close_run()
            continue

        result = queues[catalog_id].popleft()
        qualified, reason = _qualify_result(result, config)
        counts[f"quality_{reason}"] += 1
        if qualified is None:
            close_run()
            continue

        # A repeated catalogue ID or byte-identical audio source makes the
        # selected label ambiguous. Start a new contiguous run instead of
        # silently treating the duplicate as a separate candidate.
        if (
            qualified.catalog_id in current_catalog_ids
            or qualified.audio_source_id in current_source_ids
        ):
            counts["duplicate_track_breaks"] += 1
            close_run()

        current_run.append(qualified)
        current_catalog_ids.add(qualified.catalog_id)
        current_source_ids.add(qualified.audio_source_id)

    close_run()
    counts["orphan_alignment_results"] += sum(len(queue) for queue in queues.values())
    return observations, counts


def build_corpus_ordering_dataset(
    corpus_root: str | Path,
    *,
    config: OrderingBuildConfig | None = None,
    dj_by_mix: Mapping[str, str] | None = None,
) -> CorpusOrderingDataset:
    """Build a strict ordering dataset from a frozen corpus snapshot.

    ``dj_by_mix`` must come from trusted metadata. DJ identity is never parsed
    from a title because that would create silent identity errors.
    """

    root = Path(corpus_root).expanduser().resolve()
    dataset_path = _resolve_dataset_path(root)
    alignments_dir = root / "alignments"
    if not alignments_dir.is_dir():
        raise FileNotFoundError(f"alignment directory not found: {alignments_dir}")

    effective_config = config or OrderingBuildConfig()
    raw_dataset = _read_json(dataset_path)
    if not isinstance(raw_dataset, list):
        raise ValueError("corpus dataset.json must contain a list of mixes")

    trusted_dj_ids = {
        str(mix_id): str(dj_id).strip()
        for mix_id, dj_id in (dj_by_mix or {}).items()
        if str(mix_id).strip() and str(dj_id).strip()
    }

    observations: list[OrderingObservation] = []
    totals: Counter[str] = Counter()
    report_digests: list[dict[str, str]] = []
    seen_mix_ids: set[str] = set()

    for raw_mix in raw_dataset:
        totals["metadata_mixes"] += 1
        if not isinstance(raw_mix, Mapping):
            totals["invalid_metadata_mix"] += 1
            continue

        mix_id = _clean_identifier(raw_mix.get("id"))
        if mix_id is None:
            totals["mix_missing_id"] += 1
            continue
        if mix_id in seen_mix_ids:
            totals["duplicate_mix_id"] += 1
            continue
        seen_mix_ids.add(mix_id)

        report_path = alignments_dir / f"{mix_id}.json"
        if not report_path.is_file():
            totals["missing_alignment_report"] += 1
            continue

        try:
            report = _read_json(report_path)
        except (OSError, json.JSONDecodeError):
            totals["invalid_alignment_report_json"] += 1
            continue
        if not isinstance(report, Mapping):
            totals["invalid_alignment_report_shape"] += 1
            continue

        mix_observations, mix_counts = _build_mix_observations(
            mix=raw_mix,
            report=report,
            config=effective_config,
            dj_id=trusted_dj_ids.get(mix_id),
        )
        totals.update(mix_counts)
        if mix_observations:
            totals["accepted_mixes"] += 1
            observations.extend(mix_observations)
            report_digests.append(
                {
                    "mix_id": mix_id,
                    "sha256": _file_sha256(report_path),
                }
            )

    observations.sort(
        key=lambda observation: (
            observation.mix_id,
            observation.run_id,
            observation.position,
        )
    )
    observation_manifest = [observation.as_dict() for observation in observations]
    source_manifest = {
        "schema_version": ORDERING_DATASET_SCHEMA_VERSION,
        "config": effective_config.as_dict(),
        "dataset_sha256": _file_sha256(dataset_path),
        "alignment_reports": sorted(report_digests, key=lambda item: item["mix_id"]),
        "observations": observation_manifest,
    }
    dataset_fingerprint = _fingerprint(source_manifest)
    candidate_sizes = [len(item.candidate_track_ids) for item in observations]
    known_dj_observations = sum(item.dj_id is not None for item in observations)

    audit: dict[str, object] = {
        "scope": "P(next track | observed crate, performed history)",
        "explicitly_not_modeled": "P(track selected | DJ complete library)",
        "config": effective_config.as_dict(),
        "source": {
            "corpus_root": str(root),
            "dataset_path": str(dataset_path),
            "dataset_sha256": source_manifest["dataset_sha256"],
            "accepted_alignment_report_count": len(report_digests),
        },
        "counts": dict(sorted(totals.items())),
        "choice_sets": {
            "minimum_candidates": min(candidate_sizes, default=0),
            "maximum_candidates": max(candidate_sizes, default=0),
            "mean_candidates": (
                sum(candidate_sizes) / len(candidate_sizes) if candidate_sizes else 0.0
            ),
        },
        "identity": {
            "trusted_dj_mapping_count": len(trusted_dj_ids),
            "observations_with_dj_id": known_dj_observations,
            "observations_without_dj_id": len(observations) - known_dj_observations,
            "title_parsing_used": False,
        },
        "leakage_guards": [
            "whole-mix grouping is required during train/validation/test splitting",
            "candidate order is canonical and carries no performed-order position",
            "missing or low-confidence tracks split a run instead of creating fake adjacency",
            "the deterministic final choice with one candidate is excluded",
            "DJ identity is accepted only from explicit trusted metadata",
        ],
        "limitations": [
            "the corpus records performed positives and no rejected full-library candidates",
            "choice sets contain only the remaining tracks in an observed contiguous run",
            "causal reasons for a DJ choice are not observed",
            "alignment confidence is a measurement gate, not proof of artistic intent",
            "genre labels use only an explicit corpus genres field; general tags are not genres",
        ],
    }
    return CorpusOrderingDataset(
        observations=tuple(observations),
        audit=audit,
        fingerprint=dataset_fingerprint,
    )


def write_ordering_dataset_snapshot(
    dataset: CorpusOrderingDataset,
    output_path: str | Path,
) -> Path:
    """Write one immutable JSON snapshot without mutating corpus inputs."""

    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = dataset.as_dict(include_observations=True)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    destination.write_text(encoded, encoding="utf-8")
    return destination


def observation_fingerprint(
    observations: Iterable[OrderingObservation],
) -> str:
    """Hash the exact observations and candidate sets used by an evaluation."""

    manifest = [
        observation.as_dict()
        for observation in sorted(
            observations,
            key=lambda item: (item.mix_id, item.run_id, item.position),
        )
    ]
    return _fingerprint(manifest)

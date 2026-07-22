"""Fail-closed preflight for the five-model DJ ordering experiment.

The gate separates evidence collection from model training. It reports the
exact immutable universe, checks H/E/DJ coverage independently, and creates a
deterministic H-analysis queue without downloading, transcoding, or analyzing
audio.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from dancelab.core.models import AnalysisResult
from dancelab.ingestion.loader import SUPPORTED_EXTENSIONS as ENGINE_AUDIO_EXTENSIONS
from dancelab.ingestion.metadata import make_track_id
from dancelab.validation.djmix.checkpoint import AUDIO_EXTENSIONS as CORPUS_AUDIO_EXTENSIONS
from dancelab.validation.djmix.ordering import CorpusOrderingDataset
from dancelab.validation.djmix.ordering_features import (
    ANALYSIS_INDEX_SCHEMA_VERSION,
    HANDCRAFTED_EXTRACTOR_VERSION,
    handcrafted_features_from_analysis,
    load_frozen_embedding_catalog,
    load_trusted_dj_mapping,
)


MODEL_GATE_SCHEMA_VERSION = "ordering-model-gate-v1"
ANALYSIS_QUEUE_SCHEMA_VERSION = "ordering-analysis-queue-v1"
DISCOVERABLE_AUDIO_EXTENSIONS = frozenset(
    CORPUS_AUDIO_EXTENSIONS | ENGINE_AUDIO_EXTENSIONS
)


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


def _read_object(path: Path, *, label: str) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def _clean_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_track_ids(dataset: CorpusOrderingDataset) -> tuple[str, ...]:
    values: set[str] = set()
    for observation in dataset.observations:
        values.update(observation.history_track_ids)
        values.update(observation.candidate_track_ids)
    return tuple(sorted(values))


@dataclass(frozen=True)
class ComponentCoverage:
    """Coverage of one evidence family over an exact required universe."""

    name: str
    required_count: int
    available_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    invalid_items: Mapping[str, str]
    extra_ids: tuple[str, ...] = ()
    source_fingerprint: str | None = None
    catalog_error: str | None = None
    metadata: Mapping[str, object] | None = None

    @property
    def ready(self) -> bool:
        return (
            self.required_count > 0
            and len(self.available_ids) == self.required_count
            and not self.missing_ids
            and not self.invalid_items
            and self.catalog_error is None
        )

    @property
    def unavailable_count(self) -> int:
        return len(self.missing_ids) + len(self.invalid_items)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ready": self.ready,
            "required_count": self.required_count,
            "available_count": len(self.available_ids),
            "unavailable_count": self.unavailable_count,
            "available_ids": list(self.available_ids),
            "missing_ids": list(self.missing_ids),
            "invalid_items": dict(sorted(self.invalid_items.items())),
            "extra_ids": list(self.extra_ids),
            "source_fingerprint": self.source_fingerprint,
            "catalog_error": self.catalog_error,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class AudioSource:
    catalog_track_id: str
    source_relative_path: str
    source_size_bytes: int
    extension: str
    engine_track_id: str
    engine_decoder_supported: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "catalog_track_id": self.catalog_track_id,
            "source_relative_path": self.source_relative_path,
            "source_size_bytes": self.source_size_bytes,
            "extension": self.extension,
            "engine_track_id": self.engine_track_id,
            "engine_decoder_supported": self.engine_decoder_supported,
        }


@dataclass(frozen=True)
class AudioInventoryReport:
    corpus_root: str
    required_count: int
    real_audio_count: int
    resolved_sources: Mapping[str, AudioSource]
    missing_ids: tuple[str, ...]
    ambiguous_paths: Mapping[str, tuple[str, ...]]
    unsupported_for_engine_ids: tuple[str, ...]
    ignored_appledouble_count: int
    unsafe_entries: tuple[str, ...]
    inventory_fingerprint: str

    @property
    def source_complete(self) -> bool:
        return (
            self.required_count > 0
            and len(self.resolved_sources) == self.required_count
            and not self.missing_ids
            and not self.ambiguous_paths
        )

    @property
    def engine_analysis_ready(self) -> bool:
        return self.source_complete and not self.unsupported_for_engine_ids

    def as_dict(self) -> dict[str, object]:
        return {
            "source_complete": self.source_complete,
            "engine_analysis_ready": self.engine_analysis_ready,
            "corpus_root": self.corpus_root,
            "tracks_relative_root": "tracks",
            "required_count": self.required_count,
            "real_audio_count": self.real_audio_count,
            "resolved_count": len(self.resolved_sources),
            "resolved_sources": {
                key: value.as_dict() for key, value in sorted(self.resolved_sources.items())
            },
            "missing_ids": list(self.missing_ids),
            "ambiguous_paths": {
                key: list(value) for key, value in sorted(self.ambiguous_paths.items())
            },
            "unsupported_for_engine_ids": list(self.unsupported_for_engine_ids),
            "engine_supported_extensions": sorted(ENGINE_AUDIO_EXTENSIONS),
            "discoverable_audio_extensions": sorted(DISCOVERABLE_AUDIO_EXTENSIONS),
            "ignored_appledouble_count": self.ignored_appledouble_count,
            "unsafe_entries": list(self.unsafe_entries),
            "inventory_fingerprint": self.inventory_fingerprint,
            "content_hashing": "deferred to the analysis manifest; no audio bytes hashed here",
        }


@dataclass(frozen=True)
class OrderingAnalysisJob:
    catalog_track_id: str
    source_relative_path: str
    source_size_bytes: int
    source_extension: str
    engine_track_id: str
    expected_analysis_relative_path: str

    def as_dict(self) -> dict[str, object]:
        return {
            "catalog_track_id": self.catalog_track_id,
            "source_relative_path": self.source_relative_path,
            "source_size_bytes": self.source_size_bytes,
            "source_extension": self.source_extension,
            "engine_track_id": self.engine_track_id,
            "expected_analysis_relative_path": self.expected_analysis_relative_path,
        }


@dataclass(frozen=True)
class OrderingAnalysisQueue:
    dataset_fingerprint: str
    required_track_count: int
    already_analyzed_ids: tuple[str, ...]
    jobs: tuple[OrderingAnalysisJob, ...]
    blocked_missing_ids: tuple[str, ...]
    blocked_ambiguous_ids: tuple[str, ...]
    blocked_unsupported_ids: tuple[str, ...]
    fingerprint: str
    schema_version: str = ANALYSIS_QUEUE_SCHEMA_VERSION

    @property
    def remaining_count(self) -> int:
        return self.required_track_count - len(self.already_analyzed_ids)

    @property
    def complete(self) -> bool:
        return self.remaining_count == 0

    @property
    def safe_to_run(self) -> bool:
        return (
            not self.complete
            and len(self.jobs) == self.remaining_count
            and not self.blocked_missing_ids
            and not self.blocked_ambiguous_ids
            and not self.blocked_unsupported_ids
        )

    @property
    def status(self) -> str:
        if self.complete:
            return "complete"
        return "ready" if self.safe_to_run else "blocked"

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "dataset_fingerprint": self.dataset_fingerprint,
            "status": self.status,
            "safe_to_run": self.safe_to_run,
            "complete": self.complete,
            "required_track_count": self.required_track_count,
            "already_analyzed_count": len(self.already_analyzed_ids),
            "already_analyzed_ids": list(self.already_analyzed_ids),
            "remaining_count": self.remaining_count,
            "job_count": len(self.jobs),
            "jobs": [job.as_dict() for job in self.jobs],
            "blocked_missing_ids": list(self.blocked_missing_ids),
            "blocked_ambiguous_ids": list(self.blocked_ambiguous_ids),
            "blocked_unsupported_ids": list(self.blocked_unsupported_ids),
            "execution_policy": {
                "all_or_nothing": True,
                "downloads_allowed": False,
                "transcoding_performed": False,
                "source_audio_mutated": False,
                "partial_queue_execution_allowed": False,
            },
        }


@dataclass(frozen=True)
class OrderingModelGateReport:
    dataset: Mapping[str, object]
    source_audio: AudioInventoryReport
    handcrafted: ComponentCoverage
    embeddings: ComponentCoverage
    dj_identity: ComponentCoverage
    analysis_queue: Mapping[str, object]
    readiness: Mapping[str, bool]
    blockers: tuple[str, ...]
    fingerprint: str
    schema_version: str = MODEL_GATE_SCHEMA_VERSION

    @property
    def ready_for_five_models(self) -> bool:
        return bool(self.readiness.get("five_model_evaluation_ready"))

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "dataset": dict(self.dataset),
            "source_audio": self.source_audio.as_dict(),
            "handcrafted": self.handcrafted.as_dict(),
            "embeddings": self.embeddings.as_dict(),
            "dj_identity": self.dj_identity.as_dict(),
            "analysis_queue": dict(self.analysis_queue),
            "readiness": dict(self.readiness),
            "blockers": list(self.blockers),
            "policies": {
                "scope": "offline validation only",
                "fixed_universe": True,
                "fail_closed": True,
                "silent_track_filtering": False,
                "downloads_allowed": False,
                "source_corpus_mutated": False,
                "dj_identity_from_titles_or_general_tags": False,
            },
        }


def inspect_audio_inventory(
    corpus_root: str | Path,
    required_track_ids: tuple[str, ...],
) -> AudioInventoryReport:
    """Resolve catalogue IDs to exactly one local source file."""

    root = Path(corpus_root).expanduser().resolve()
    tracks_root = root / "tracks"
    if not tracks_root.is_dir():
        raise FileNotFoundError(f"corpus track directory not found: {tracks_root}")

    by_stem: dict[str, list[tuple[Path, int]]] = {}
    ignored_appledouble = 0
    unsafe_entries: list[str] = []
    inventory_rows: list[dict[str, object]] = []
    real_audio_count = 0
    for path in sorted(tracks_root.iterdir(), key=lambda item: item.name):
        if path.name.startswith("._"):
            ignored_appledouble += 1
            continue
        if path.name.startswith(".") or path.suffix.lower() not in DISCOVERABLE_AUDIO_EXTENSIONS:
            continue
        if path.is_symlink():
            unsafe_entries.append(path.name)
            continue
        if not path.is_file():
            continue
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(tracks_root)
            size = resolved.stat().st_size
        except (OSError, ValueError):
            unsafe_entries.append(path.name)
            continue
        real_audio_count += 1
        by_stem.setdefault(path.stem, []).append((resolved, size))
        inventory_rows.append(
            {
                "track_id": path.stem,
                "relative_path": str(resolved.relative_to(root)),
                "bytes": size,
            }
        )

    resolved_sources: dict[str, AudioSource] = {}
    missing: list[str] = []
    ambiguous: dict[str, tuple[str, ...]] = {}
    unsupported: list[str] = []
    for track_id in required_track_ids:
        candidates = by_stem.get(track_id, [])
        if not candidates:
            missing.append(track_id)
            continue
        if len(candidates) != 1:
            ambiguous[track_id] = tuple(
                sorted(str(path.relative_to(root)) for path, _size in candidates)
            )
            continue
        source, size = candidates[0]
        extension = source.suffix.lower()
        supported = extension in ENGINE_AUDIO_EXTENSIONS
        if not supported:
            unsupported.append(track_id)
        resolved_sources[track_id] = AudioSource(
            catalog_track_id=track_id,
            source_relative_path=str(source.relative_to(root)),
            source_size_bytes=size,
            extension=extension,
            engine_track_id=make_track_id(str(source)),
            engine_decoder_supported=supported,
        )

    return AudioInventoryReport(
        corpus_root=str(root),
        required_count=len(required_track_ids),
        real_audio_count=real_audio_count,
        resolved_sources=resolved_sources,
        missing_ids=tuple(missing),
        ambiguous_paths=ambiguous,
        unsupported_for_engine_ids=tuple(unsupported),
        ignored_appledouble_count=ignored_appledouble,
        unsafe_entries=tuple(sorted(unsafe_entries)),
        inventory_fingerprint=_fingerprint(inventory_rows),
    )


def inspect_handcrafted_coverage(
    required_track_ids: tuple[str, ...],
    *,
    analysis_root: str | Path | None,
    analysis_index_path: str | Path | None,
) -> ComponentCoverage:
    required = set(required_track_ids)
    if analysis_root is None and analysis_index_path is None:
        return ComponentCoverage(
            name="H",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_track_ids,
            invalid_items={},
            metadata={
                "status": "not supplied",
                "extractor_version": HANDCRAFTED_EXTRACTOR_VERSION,
            },
        )
    if analysis_root is None or analysis_index_path is None:
        return ComponentCoverage(
            name="H",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_track_ids,
            invalid_items={},
            catalog_error="analysis root and analysis index must be supplied together",
            metadata={"extractor_version": HANDCRAFTED_EXTRACTOR_VERSION},
        )

    root = Path(analysis_root).expanduser().resolve()
    index_source = Path(analysis_index_path).expanduser().resolve()
    try:
        payload = _read_object(index_source, label="analysis index")
        if payload.get("schema_version") != ANALYSIS_INDEX_SCHEMA_VERSION:
            raise ValueError(
                f"analysis index schema must be {ANALYSIS_INDEX_SCHEMA_VERSION}"
            )
        raw_tracks = payload.get("tracks")
        if not isinstance(raw_tracks, Mapping):
            raise ValueError("analysis index tracks must be an object")
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        return ComponentCoverage(
            name="H",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_track_ids,
            invalid_items={},
            catalog_error=str(exc),
            metadata={"extractor_version": HANDCRAFTED_EXTRACTOR_VERSION},
        )

    normalized_tracks = {
        track_id: relative_path
        for raw_track_id, relative_path in raw_tracks.items()
        if (track_id := _clean_identifier(raw_track_id)) is not None
    }
    available: list[str] = []
    missing: list[str] = []
    invalid: dict[str, str] = {}
    for track_id in required_track_ids:
        relative_path = normalized_tracks.get(track_id)
        if relative_path is None:
            missing.append(track_id)
            continue
        try:
            raw_path = str(relative_path or "").strip()
            candidate = Path(raw_path)
            if not raw_path or candidate.is_absolute():
                raise ValueError("analysis path must be non-empty and relative")
            analysis_path = (root / candidate).resolve()
            analysis_path.relative_to(root)
            if not analysis_path.is_file():
                raise FileNotFoundError("analysis file does not exist")
            analysis = AnalysisResult.model_validate_json(
                analysis_path.read_text(encoding="utf-8")
            )
            handcrafted_features_from_analysis(analysis)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid[track_id] = str(exc)
            continue
        available.append(track_id)

    return ComponentCoverage(
        name="H",
        required_count=len(required),
        available_ids=tuple(available),
        missing_ids=tuple(missing),
        invalid_items=invalid,
        extra_ids=tuple(sorted(normalized_tracks.keys() - required)),
        source_fingerprint=_file_sha256(index_source),
        metadata={
            "status": "validated",
            "analysis_root": str(root),
            "extractor_version": HANDCRAFTED_EXTRACTOR_VERSION,
        },
    )


def inspect_embedding_coverage(
    required_track_ids: tuple[str, ...],
    embedding_catalog_path: str | Path | None,
) -> ComponentCoverage:
    required = set(required_track_ids)
    if embedding_catalog_path is None:
        return ComponentCoverage(
            name="E",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_track_ids,
            invalid_items={},
            metadata={"status": "not supplied"},
        )
    source = Path(embedding_catalog_path).expanduser().resolve()
    try:
        catalog = load_frozen_embedding_catalog(source)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        return ComponentCoverage(
            name="E",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_track_ids,
            invalid_items={},
            catalog_error=str(exc),
            metadata={"status": "invalid"},
        )
    available = tuple(sorted(required & catalog.vectors.keys()))
    return ComponentCoverage(
        name="E",
        required_count=len(required),
        available_ids=available,
        missing_ids=tuple(sorted(required - catalog.vectors.keys())),
        invalid_items={},
        extra_ids=tuple(sorted(catalog.vectors.keys() - required)),
        source_fingerprint=catalog.fingerprint,
        metadata={
            "status": "validated",
            "embedding_name": catalog.embedding_name,
            "dimension": catalog.dimension,
            "model": dict(catalog.model),
        },
    )


def inspect_dj_identity_coverage(
    required_mix_ids: tuple[str, ...],
    dj_mapping_path: str | Path | None,
) -> ComponentCoverage:
    required = set(required_mix_ids)
    if dj_mapping_path is None:
        return ComponentCoverage(
            name="DJ",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_mix_ids,
            invalid_items={},
            metadata={"status": "not supplied", "unique_dj_count": 0},
        )
    try:
        mapping, mapping_fingerprint = load_trusted_dj_mapping(dj_mapping_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        return ComponentCoverage(
            name="DJ",
            required_count=len(required),
            available_ids=(),
            missing_ids=required_mix_ids,
            invalid_items={},
            catalog_error=str(exc),
            metadata={"status": "invalid", "unique_dj_count": 0},
        )
    available = tuple(sorted(required & mapping.keys()))
    return ComponentCoverage(
        name="DJ",
        required_count=len(required),
        available_ids=available,
        missing_ids=tuple(sorted(required - mapping.keys())),
        invalid_items={},
        extra_ids=tuple(sorted(mapping.keys() - required)),
        source_fingerprint=mapping_fingerprint,
        metadata={
            "status": "validated",
            "unique_dj_count": len({mapping[mix_id] for mix_id in available}),
        },
    )


def build_ordering_analysis_queue(
    dataset: CorpusOrderingDataset,
    audio: AudioInventoryReport,
    handcrafted: ComponentCoverage,
) -> OrderingAnalysisQueue:
    required_ids = _required_track_ids(dataset)
    already_analyzed = set(handcrafted.available_ids)
    remaining = set(required_ids) - already_analyzed
    missing = tuple(sorted(remaining & set(audio.missing_ids)))
    ambiguous = tuple(sorted(remaining & audio.ambiguous_paths.keys()))
    unsupported = tuple(
        sorted(remaining & set(audio.unsupported_for_engine_ids))
    )
    blocked = set(missing) | set(ambiguous) | set(unsupported)
    jobs = tuple(
        OrderingAnalysisJob(
            catalog_track_id=track_id,
            source_relative_path=source.source_relative_path,
            source_size_bytes=source.source_size_bytes,
            source_extension=source.extension,
            engine_track_id=source.engine_track_id,
            expected_analysis_relative_path=f"{source.engine_track_id}.json",
        )
        for track_id in sorted(remaining - blocked)
        if (source := audio.resolved_sources.get(track_id)) is not None
    )
    canonical = {
        "schema_version": ANALYSIS_QUEUE_SCHEMA_VERSION,
        "dataset_fingerprint": dataset.fingerprint,
        "required_track_count": len(required_ids),
        "already_analyzed_ids": sorted(already_analyzed),
        "jobs": [job.as_dict() for job in jobs],
        "blocked_missing_ids": list(missing),
        "blocked_ambiguous_ids": list(ambiguous),
        "blocked_unsupported_ids": list(unsupported),
    }
    return OrderingAnalysisQueue(
        dataset_fingerprint=dataset.fingerprint,
        required_track_count=len(required_ids),
        already_analyzed_ids=tuple(sorted(already_analyzed)),
        jobs=jobs,
        blocked_missing_ids=missing,
        blocked_ambiguous_ids=ambiguous,
        blocked_unsupported_ids=unsupported,
        fingerprint=_fingerprint(canonical),
    )


def build_ordering_model_gate(
    dataset: CorpusOrderingDataset,
    corpus_root: str | Path,
    *,
    analysis_root: str | Path | None = None,
    analysis_index_path: str | Path | None = None,
    embedding_catalog_path: str | Path | None = None,
    dj_mapping_path: str | Path | None = None,
    expected_dataset_fingerprint: str | None = None,
) -> tuple[OrderingModelGateReport, OrderingAnalysisQueue]:
    """Build the preflight report and H queue without running any model."""

    required_track_ids = _required_track_ids(dataset)
    audio = inspect_audio_inventory(corpus_root, required_track_ids)
    handcrafted = inspect_handcrafted_coverage(
        required_track_ids,
        analysis_root=analysis_root,
        analysis_index_path=analysis_index_path,
    )
    embeddings = inspect_embedding_coverage(
        required_track_ids,
        embedding_catalog_path,
    )
    dj_identity = inspect_dj_identity_coverage(
        dataset.mix_ids,
        dj_mapping_path,
    )
    queue = build_ordering_analysis_queue(dataset, audio, handcrafted)

    unique_dj_count = int((dj_identity.metadata or {}).get("unique_dj_count", 0))
    fingerprint_matches = (
        expected_dataset_fingerprint is None
        or dataset.fingerprint == expected_dataset_fingerprint
    )
    dataset_ready = (
        bool(dataset.observations)
        and len(dataset.mix_ids) >= 3
        and bool(required_track_ids)
        and fingerprint_matches
    )
    identity_ready = dj_identity.ready and unique_dj_count >= 2
    feature_catalog_ready = (
        handcrafted.ready and embeddings.ready and identity_ready
    )
    five_model_ready = dataset_ready and feature_catalog_ready
    readiness = {
        "dataset_ready": dataset_ready,
        "dataset_fingerprint_matches_expected": fingerprint_matches,
        "source_audio_complete": audio.source_complete,
        "handcrafted_complete": handcrafted.ready,
        "handcrafted_queue_safe_to_run": queue.safe_to_run,
        "frozen_embeddings_complete": embeddings.ready,
        "trusted_dj_identity_complete": identity_ready,
        "feature_catalog_ready": feature_catalog_ready,
        "five_model_evaluation_ready": five_model_ready,
    }

    blockers: list[str] = []
    if not dataset.observations:
        blockers.append("dataset has no qualified ordering observations")
    if len(dataset.mix_ids) < 3:
        blockers.append("at least three mixes are required for grouped splitting")
    if not fingerprint_matches:
        blockers.append("dataset fingerprint differs from the pinned expected fingerprint")
    if not handcrafted.ready:
        blockers.append(
            f"H incomplete: {handcrafted.unavailable_count}/{handcrafted.required_count} "
            "required track(s) unavailable"
        )
        if not queue.safe_to_run:
            blockers.append(
                "H queue blocked: "
                f"{len(queue.blocked_missing_ids)} missing, "
                f"{len(queue.blocked_ambiguous_ids)} ambiguous, "
                f"{len(queue.blocked_unsupported_ids)} unsupported by the engine decoder"
            )
    if not embeddings.ready:
        blockers.append(
            f"E incomplete: {embeddings.unavailable_count}/{embeddings.required_count} "
            "required track(s) unavailable"
        )
    if not dj_identity.ready:
        blockers.append(
            f"DJ identity incomplete: {dj_identity.unavailable_count}/"
            f"{dj_identity.required_count} required mix(es) unavailable"
        )
    elif unique_dj_count < 2:
        blockers.append("at least two trusted DJ identities are required for LHEI")

    dataset_summary = {
        "schema_version": dataset.schema_version,
        "fingerprint": dataset.fingerprint,
        "expected_fingerprint": expected_dataset_fingerprint,
        "fingerprint_matches_expected": fingerprint_matches,
        "observation_count": len(dataset.observations),
        "mix_count": len(dataset.mix_ids),
        "run_count": len(dataset.run_ids),
        "required_track_count": len(required_track_ids),
        "required_track_ids": list(required_track_ids),
        "source": dict(dataset.audit.get("source", {})),
    }
    queue_summary = {
        "schema_version": queue.schema_version,
        "fingerprint": queue.fingerprint,
        "status": queue.status,
        "safe_to_run": queue.safe_to_run,
        "complete": queue.complete,
        "remaining_count": queue.remaining_count,
        "job_count": len(queue.jobs),
        "blocked_count": (
            len(queue.blocked_missing_ids)
            + len(queue.blocked_ambiguous_ids)
            + len(queue.blocked_unsupported_ids)
        ),
    }
    canonical = {
        "schema_version": MODEL_GATE_SCHEMA_VERSION,
        "dataset": dataset_summary,
        "source_audio": audio.as_dict(),
        "handcrafted": handcrafted.as_dict(),
        "embeddings": embeddings.as_dict(),
        "dj_identity": dj_identity.as_dict(),
        "analysis_queue": queue_summary,
        "readiness": readiness,
        "blockers": blockers,
    }
    report = OrderingModelGateReport(
        dataset=dataset_summary,
        source_audio=audio,
        handcrafted=handcrafted,
        embeddings=embeddings,
        dj_identity=dj_identity,
        analysis_queue=queue_summary,
        readiness=readiness,
        blockers=tuple(blockers),
        fingerprint=_fingerprint(canonical),
    )
    return report, queue


def _write_json_atomic(payload: Mapping[str, object], output_path: str | Path) -> Path:
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def write_ordering_model_gate(
    report: OrderingModelGateReport,
    output_path: str | Path,
) -> Path:
    return _write_json_atomic(report.as_dict(), output_path)


def write_ordering_analysis_queue(
    queue: OrderingAnalysisQueue,
    output_path: str | Path,
) -> Path:
    return _write_json_atomic(queue.as_dict(), output_path)

"""Source-backed feature preparation for the DJ-mix ordering experiment.

The five-model comparison needs two different audio representations:

* ``H`` is a deterministic vector built from DanceLab ``AnalysisResult`` data.
* ``E`` is supplied by a separately versioned, frozen learned-audio model.

This module never downloads a model and never relabels MFCC/DTW alignment
features as learned embeddings. Catalogue IDs are provided explicitly through
an index; filenames and display titles are not used as identity evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Mapping

import numpy as np

from dancelab.core.models import AnalysisResult, FeatureFrame, SegmentType
from dancelab.decision.harmonic import parse_camelot
from dancelab.validation.djmix.ordering_models import (
    ORDERING_FEATURE_SCHEMA_VERSION,
    OrderingFeatureCatalog,
    feature_catalog_from_payload,
)


ANALYSIS_INDEX_SCHEMA_VERSION = "ordering-analysis-index-v1"
EMBEDDING_CATALOG_SCHEMA_VERSION = "ordering-embeddings-v1"
DJ_MAPPING_SCHEMA_VERSION = "ordering-dj-map-v1"
HANDCRAFTED_EXTRACTOR_VERSION = "ordering-handcrafted-v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEGMENT_TYPES = tuple(SegmentType)
_DESCRIPTOR_SPECS = (
    ("rms", "identity", True),
    ("spectral_flux", "log1p", True),
    ("low_freq_energy_ratio", "identity", True),
    ("onset_density", "log1p", True),
    ("bass_energy", "log1p", True),
    ("pulse_clarity_proxy", "identity", False),
    ("syncopation_proxy", "identity", False),
    ("bass_salience", "identity", False),
    ("microtiming_proxy", "identity", False),
    ("tension_proxy", "identity", False),
    ("release_proxy", "identity", False),
    ("vocal_density_proxy", "identity", False),
)
_SUMMARY_NAMES = ("mean", "std", "p10", "p90", "missing_fraction")


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


def _non_empty(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    return text


def _safe_indexed_path(root: Path, relative_path: object, *, track_id: str) -> Path:
    raw = _non_empty(relative_path, field=f"tracks.{track_id}")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError(f"tracks.{track_id} must be relative to the analysis root")
    resolved_root = root.expanduser().resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"tracks.{track_id} escapes the analysis root") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"analysis file not found for {track_id}: {resolved}")
    return resolved


def _handcrafted_feature_names() -> tuple[str, ...]:
    names = [
        "log_bpm",
        "log_duration_sec",
        "camelot_sin",
        "camelot_cos",
        "camelot_mode_major",
        "key_confidence",
        "key_missing",
    ]
    for field, transform, _required in _DESCRIPTOR_SPECS:
        prefix = f"log1p_{field}" if transform == "log1p" else field
        names.extend(f"{prefix}_{summary}" for summary in _SUMMARY_NAMES)
    names.append("log1p_segment_count")
    names.extend(f"segment_{segment.value}_fraction" for segment in _SEGMENT_TYPES)
    names.append("segments_missing")
    return tuple(names)


HANDCRAFTED_FEATURE_NAMES = _handcrafted_feature_names()


def _descriptor_summary(
    frames: tuple[FeatureFrame, ...],
    *,
    field: str,
    transform: str,
    required: bool,
) -> tuple[float, ...]:
    raw_values = [getattr(frame, field) for frame in frames]
    values = np.asarray(
        [float(value) for value in raw_values if value is not None and math.isfinite(float(value))],
        dtype=np.float64,
    )
    missing_fraction = 1.0 - (len(values) / len(frames))
    if required and missing_fraction > 0.0:
        raise ValueError(
            f"required descriptor {field} is missing in {missing_fraction:.1%} of feature frames"
        )
    if values.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 1.0
    if transform == "log1p":
        if np.any(values < 0.0):
            raise ValueError(f"descriptor {field} contains negative values")
        values = np.log1p(values)
    return (
        float(np.mean(values)),
        float(np.std(values)),
        float(np.quantile(values, 0.10)),
        float(np.quantile(values, 0.90)),
        float(missing_fraction),
    )


def _key_features(analysis: AnalysisResult) -> tuple[float, ...]:
    parsed = parse_camelot(analysis.track.key_estimate)
    if parsed is None:
        return 0.0, 0.0, 0.0, 0.0, 1.0
    number, mode = parsed
    angle = 2.0 * math.pi * (number - 1) / 12.0
    confidence = analysis.track.key_confidence
    if confidence is None or not math.isfinite(confidence):
        confidence = 0.0
    return (
        math.sin(angle),
        math.cos(angle),
        1.0 if mode == "B" else 0.0,
        float(confidence),
        0.0,
    )


def _segment_features(analysis: AnalysisResult) -> tuple[float, ...]:
    if not analysis.segments:
        return (0.0, *(0.0 for _ in _SEGMENT_TYPES), 1.0)
    durations = {
        segment_type: sum(
            max(0.0, segment.end_sec - segment.start_sec)
            for segment in analysis.segments
            if segment.segment_type == segment_type
        )
        for segment_type in _SEGMENT_TYPES
    }
    total = sum(durations.values())
    fractions = (
        tuple(durations[segment_type] / total for segment_type in _SEGMENT_TYPES)
        if total > 0.0
        else tuple(0.0 for _ in _SEGMENT_TYPES)
    )
    return math.log1p(len(analysis.segments)), *fractions, 0.0


def handcrafted_features_from_analysis(
    analysis: AnalysisResult,
) -> tuple[float, ...]:
    """Create one deterministic, interpretable ``H`` vector.

    Required low-level descriptors fail closed. Candidate descriptors use an
    explicit zero plus a missing-fraction feature, so absence is represented
    rather than silently median-imputed from the full dataset.
    """

    beatgrid = analysis.beatgrid
    if beatgrid is None or not beatgrid.reliable:
        raise ValueError("analysis needs a reliable beatgrid")
    bpm = float(beatgrid.bpm)
    duration = analysis.track.duration_sec
    if not math.isfinite(bpm) or bpm <= 0.0:
        raise ValueError("analysis BPM must be finite and positive")
    if duration is None or not math.isfinite(duration) or duration <= 0.0:
        raise ValueError("analysis duration must be finite and positive")
    frames = tuple(analysis.features)
    if not frames:
        raise ValueError("analysis needs at least one feature frame")

    values: list[float] = [math.log(bpm), math.log(float(duration))]
    values.extend(_key_features(analysis))
    for field, transform, required in _DESCRIPTOR_SPECS:
        values.extend(
            _descriptor_summary(
                frames,
                field=field,
                transform=transform,
                required=required,
            )
        )
    values.extend(_segment_features(analysis))
    if len(values) != len(HANDCRAFTED_FEATURE_NAMES):
        raise RuntimeError("handcrafted feature schema and vector are inconsistent")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("handcrafted feature vector contains non-finite values")
    return tuple(values)


@dataclass(frozen=True)
class FrozenEmbeddingCatalog:
    embedding_name: str
    vectors: Mapping[str, tuple[float, ...]]
    model: Mapping[str, object]
    provenance: Mapping[str, object]
    fingerprint: str
    schema_version: str = EMBEDDING_CATALOG_SCHEMA_VERSION

    @property
    def dimension(self) -> int:
        return len(next(iter(self.vectors.values())))


def load_frozen_embedding_catalog(path: str | Path) -> FrozenEmbeddingCatalog:
    """Load precomputed embeddings with a pinned model identity.

    Model execution and downloading are intentionally outside this command.
    """

    source = Path(path).expanduser().resolve()
    payload = _read_object(source, label="embedding catalogue")
    schema = str(payload.get("schema_version") or "")
    if schema != EMBEDDING_CATALOG_SCHEMA_VERSION:
        raise ValueError(
            f"embedding schema must be {EMBEDDING_CATALOG_SCHEMA_VERSION}, "
            f"got {schema or 'missing'}"
        )
    embedding_name = _non_empty(payload.get("embedding_name"), field="embedding_name")
    raw_model = payload.get("model")
    if not isinstance(raw_model, Mapping):
        raise ValueError("model must be an object")
    model = dict(raw_model)
    for field in ("name", "version", "source", "license"):
        _non_empty(model.get(field), field=f"model.{field}")
    model_hash = str(model.get("sha256") or "").lower()
    if not _SHA256_RE.fullmatch(model_hash):
        raise ValueError("model.sha256 must be a lowercase 64-character SHA-256")
    if model.get("frozen") is not True:
        raise ValueError("model.frozen must be true")

    raw_tracks = payload.get("tracks")
    if not isinstance(raw_tracks, Mapping) or not raw_tracks:
        raise ValueError("tracks must be a non-empty object")
    vectors: dict[str, tuple[float, ...]] = {}
    dimensions: set[int] = set()
    for raw_track_id, raw_vector in raw_tracks.items():
        track_id = _non_empty(raw_track_id, field="track ID")
        if not isinstance(raw_vector, list) or not raw_vector:
            raise ValueError(f"tracks.{track_id} must be a non-empty vector")
        vector = tuple(float(value) for value in raw_vector)
        if not all(math.isfinite(value) for value in vector):
            raise ValueError(f"tracks.{track_id} contains non-finite values")
        if np.linalg.norm(np.asarray(vector, dtype=np.float64)) <= 1e-12:
            raise ValueError(f"tracks.{track_id} is an all-zero embedding")
        vectors[track_id] = vector
        dimensions.add(len(vector))
    if len(dimensions) != 1:
        raise ValueError("all embedding vectors must share one dimension")

    provenance = payload.get("provenance", {})
    if not isinstance(provenance, Mapping):
        raise ValueError("provenance must be an object")
    canonical = {
        "schema_version": schema,
        "embedding_name": embedding_name,
        "model": model,
        "tracks": {key: list(value) for key, value in sorted(vectors.items())},
        "provenance": dict(provenance),
    }
    return FrozenEmbeddingCatalog(
        embedding_name=embedding_name,
        vectors=vectors,
        model=model,
        provenance=dict(provenance),
        fingerprint=_fingerprint(canonical),
    )


def load_trusted_dj_mapping(path: str | Path) -> tuple[dict[str, str], str]:
    source = Path(path).expanduser().resolve()
    payload = _read_object(source, label="DJ mapping")
    schema = str(payload.get("schema_version") or "")
    if schema != DJ_MAPPING_SCHEMA_VERSION:
        raise ValueError(
            f"DJ mapping schema must be {DJ_MAPPING_SCHEMA_VERSION}, got {schema or 'missing'}"
        )
    raw_mapping = payload.get("dj_by_mix")
    if not isinstance(raw_mapping, Mapping) or not raw_mapping:
        raise ValueError("dj_by_mix must be a non-empty object")
    mapping = {
        _non_empty(raw_mix_id, field="mix ID"): _non_empty(
            raw_dj_id,
            field=f"dj_by_mix.{raw_mix_id}",
        )
        for raw_mix_id, raw_dj_id in raw_mapping.items()
    }
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping) or not provenance:
        raise ValueError("DJ mapping needs non-empty provenance")
    canonical = {
        "schema_version": schema,
        "dj_by_mix": dict(sorted(mapping.items())),
        "provenance": dict(provenance),
    }
    return mapping, _fingerprint(canonical)


def build_ordering_feature_catalog(
    *,
    analysis_root: str | Path,
    analysis_index_path: str | Path,
    embedding_catalog_path: str | Path,
    dj_mapping_path: str | Path,
) -> OrderingFeatureCatalog:
    """Join explicit analysis, embedding and DJ evidence into one catalogue."""

    root = Path(analysis_root).expanduser().resolve()
    index_source = Path(analysis_index_path).expanduser().resolve()
    index = _read_object(index_source, label="analysis index")
    schema = str(index.get("schema_version") or "")
    if schema != ANALYSIS_INDEX_SCHEMA_VERSION:
        raise ValueError(
            f"analysis index schema must be {ANALYSIS_INDEX_SCHEMA_VERSION}, "
            f"got {schema or 'missing'}"
        )
    raw_tracks = index.get("tracks")
    if not isinstance(raw_tracks, Mapping) or not raw_tracks:
        raise ValueError("analysis index tracks must be a non-empty object")

    embedding_catalog = load_frozen_embedding_catalog(embedding_catalog_path)
    dj_by_mix, dj_mapping_fingerprint = load_trusted_dj_mapping(dj_mapping_path)
    feature_rows: dict[str, dict[str, list[float]]] = {}
    analysis_manifest: list[dict[str, str]] = []
    missing_embeddings: list[str] = []
    for raw_track_id, relative_path in sorted(raw_tracks.items()):
        track_id = _non_empty(raw_track_id, field="track ID")
        analysis_path = _safe_indexed_path(root, relative_path, track_id=track_id)
        analysis = AnalysisResult.model_validate_json(analysis_path.read_text(encoding="utf-8"))
        embedding = embedding_catalog.vectors.get(track_id)
        if embedding is None:
            missing_embeddings.append(track_id)
            continue
        feature_rows[track_id] = {
            "handcrafted": list(handcrafted_features_from_analysis(analysis)),
            "embedding": list(embedding),
        }
        analysis_manifest.append(
            {
                "catalog_track_id": track_id,
                "analysis_track_id": analysis.track.track_id,
                "analysis_sha256": _file_sha256(analysis_path),
            }
        )
    if missing_embeddings:
        preview = ", ".join(missing_embeddings[:5])
        suffix = "..." if len(missing_embeddings) > 5 else ""
        raise ValueError(
            f"{len(missing_embeddings)} indexed track(s) lack frozen embeddings: {preview}{suffix}"
        )
    extra_embeddings = sorted(embedding_catalog.vectors.keys() - feature_rows.keys())
    if extra_embeddings:
        preview = ", ".join(extra_embeddings[:5])
        suffix = "..." if len(extra_embeddings) > 5 else ""
        raise ValueError(
            f"{len(extra_embeddings)} embedding track(s) lack indexed analyses: {preview}{suffix}"
        )

    provenance = {
        "scope": "offline-validation-only",
        "handcrafted_extractor_version": HANDCRAFTED_EXTRACTOR_VERSION,
        "analysis_index_sha256": _file_sha256(index_source),
        "analysis_manifest_fingerprint": _fingerprint(analysis_manifest),
        "embedding_catalog_fingerprint": embedding_catalog.fingerprint,
        "embedding_model": dict(embedding_catalog.model),
        "embedding_provenance": dict(embedding_catalog.provenance),
        "dj_mapping_fingerprint": dj_mapping_fingerprint,
        "identity_policy": "explicit catalogue IDs and trusted DJ mapping only",
        "forbidden_substitutions": [
            "MFCC/DTW alignment scores are not learned embeddings",
            "display titles and filenames are not trusted DJ identities",
        ],
    }
    return feature_catalog_from_payload(
        {
            "schema_version": ORDERING_FEATURE_SCHEMA_VERSION,
            "handcrafted_feature_names": list(HANDCRAFTED_FEATURE_NAMES),
            "embedding_name": embedding_catalog.embedding_name,
            "tracks": feature_rows,
            "dj_by_mix": dj_by_mix,
            "provenance": provenance,
        }
    )


def write_ordering_feature_catalog(
    catalog: OrderingFeatureCatalog,
    output_path: str | Path,
) -> Path:
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            catalog.as_dict(include_vectors=True),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination

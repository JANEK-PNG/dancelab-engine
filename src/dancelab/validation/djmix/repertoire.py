"""Leakage-safe revealed-repertoire proxy for offline DJ-set validation.

The corpus does not expose a DJ's real event crate or rejected candidates.
This module therefore constructs a narrower, explicitly labelled proxy:

    revealed repertoire = tracks identified in earlier approved solo sets

Tracks from the target set are positives. Earlier tracks not used in the
target set are *unlabelled alternatives*, never confirmed negatives. Candidate
identity and date hints may be generated from legacy metadata for human review,
but only a separately approved review file can enter the dataset.

Nothing here is imported by the production planner, host, API or exporters.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterable, Mapping

from dancelab.validation.djmix.model_gate import (
    AudioInventoryReport,
    ComponentCoverage,
    inspect_audio_inventory,
    inspect_embedding_coverage,
    inspect_handcrafted_coverage,
)
from dancelab.validation.djmix.ordering import CorpusOrderingDataset
from dancelab.validation.djmix.ordering_models import OrderingFeatureCatalog


REPERTOIRE_CANDIDATE_SCHEMA_VERSION = "revealed-repertoire-candidates-v1"
REPERTOIRE_REVIEW_SCHEMA_VERSION = "revealed-repertoire-review-v1"
REPERTOIRE_DATASET_SCHEMA_VERSION = "revealed-repertoire-v1"
REPERTOIRE_GATE_SCHEMA_VERSION = "revealed-repertoire-gate-v2"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_PREFIX_RE = re.compile(r"^(?P<date>\d{4}(?:-\d{2}(?:-\d{2})?)?)\s+-\s+(?P<body>.+)$")
_B2B_RE = re.compile(r"\b(?:b2b|back[\s-]+to[\s-]+back)\b", re.IGNORECASE)
_MULTI_ACTOR_RE = re.compile(r"\s(?:&|vs\.?|x)\s|[,;/]", re.IGNORECASE)


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


def _clean_identifier(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_metadata_path(root: Path) -> Path:
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


def _load_metadata(root: Path) -> tuple[Path, dict[str, Mapping[str, object]]]:
    source = _resolve_metadata_path(root)
    payload = _read_json(source)
    if not isinstance(payload, list):
        raise ValueError("corpus metadata must contain a list of mixes")
    mixes: dict[str, Mapping[str, object]] = {}
    for raw_mix in payload:
        if not isinstance(raw_mix, Mapping):
            continue
        mix_id = _clean_identifier(raw_mix.get("id"))
        if mix_id is None:
            continue
        if mix_id in mixes:
            raise ValueError(f"duplicate mix ID in corpus metadata: {mix_id}")
        mixes[mix_id] = raw_mix
    return source, mixes


def _canonical_ids(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _date_precision(raw_value: str | None) -> str:
    if raw_value is None:
        return "missing"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value):
        try:
            date.fromisoformat(raw_value)
        except ValueError:
            return "invalid"
        return "day"
    if re.fullmatch(r"\d{4}-\d{2}", raw_value):
        return "month"
    if re.fullmatch(r"\d{4}", raw_value):
        return "year"
    return "invalid"


def _parse_title_candidate(title: str) -> tuple[str | None, str | None, str]:
    match = _DATE_PREFIX_RE.match(title.strip())
    if match is None:
        return None, None, "missing"
    raw_date = match.group("date")
    body = match.group("body").strip()
    actor = re.split(r"\s+@\s+|\s+-\s+", body, maxsplit=1)[0].strip()
    return raw_date, actor or None, _date_precision(raw_date)


def _category_labels(mix: Mapping[str, object]) -> tuple[str, ...]:
    labels: list[str] = []
    raw_tags = mix.get("tags")
    if not isinstance(raw_tags, list):
        return ()
    for item in raw_tags:
        if not isinstance(item, Mapping):
            continue
        value = _clean_identifier(item.get("key"))
        if value is None:
            continue
        labels.append(value.removeprefix("Category:").strip())
    return tuple(label for label in labels if label)


def _normalized_name(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


def _compact_name(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def _candidate_classification(
    *,
    actor: str | None,
    first_tag: str | None,
) -> str:
    if actor is None:
        return "missing_actor"
    if _B2B_RE.search(actor):
        return "b2b"
    if first_tag is not None and _compact_name(actor) == _compact_name(first_tag):
        return "solo_like"
    if _MULTI_ACTOR_RE.search(actor):
        return "multi_actor"
    if first_tag is None:
        return "missing_first_tag"
    normalized_actor = _normalized_name(actor)
    normalized_tag = _normalized_name(first_tag)
    compact_actor = _compact_name(actor)
    compact_tag = _compact_name(first_tag)
    if (
        normalized_tag not in normalized_actor
        and normalized_actor not in normalized_tag
        and compact_tag not in compact_actor
        and compact_actor not in compact_tag
    ):
        return "tag_not_in_actor"
    return "solo_like"


def _track_summary(mix: Mapping[str, object]) -> dict[str, object]:
    raw_tracklist = mix.get("tracklist")
    if not isinstance(raw_tracklist, list):
        return {
            "track_slot_count": 0,
            "identified_track_count": 0,
            "unique_identified_track_count": 0,
            "unidentified_track_count": 0,
            "duplicate_identified_track_count": 0,
            "identified_fraction": 0.0,
            "identified_track_ids": (),
        }
    track_ids: list[str] = []
    unidentified = 0
    for raw_track in raw_tracklist:
        if not isinstance(raw_track, Mapping):
            unidentified += 1
            continue
        track_id = _clean_identifier(raw_track.get("id"))
        if track_id is None:
            unidentified += 1
        else:
            track_ids.append(track_id)
    unique_ids = _canonical_ids(track_ids)
    slot_count = len(raw_tracklist)
    return {
        "track_slot_count": slot_count,
        "identified_track_count": len(track_ids),
        "unique_identified_track_count": len(unique_ids),
        "unidentified_track_count": unidentified,
        "duplicate_identified_track_count": len(track_ids) - len(unique_ids),
        "identified_fraction": len(track_ids) / slot_count if slot_count else 0.0,
        "identified_track_ids": unique_ids,
    }


@dataclass(frozen=True)
class RepertoireBuildConfig:
    """Pre-registered quality and sample-size gates for the proxy dataset."""

    min_prior_tracks: int = 20
    min_prior_mixes: int = 1
    min_selected_tracks: int = 10
    min_unlabelled_alternatives: int = 10
    min_identified_fraction: float = 0.8
    min_observations: int = 100
    min_djs: int = 20
    history_window_days: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "min_prior_tracks",
            "min_prior_mixes",
            "min_selected_tracks",
            "min_unlabelled_alternatives",
            "min_observations",
            "min_djs",
        ):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be at least 1")
        if not 0.0 < self.min_identified_fraction <= 1.0:
            raise ValueError("min_identified_fraction must be in (0, 1]")
        if self.history_window_days is not None and self.history_window_days < 1:
            raise ValueError("history_window_days must be at least 1 when set")

    def as_dict(self) -> dict[str, object]:
        return {
            "min_prior_tracks": self.min_prior_tracks,
            "min_prior_mixes": self.min_prior_mixes,
            "min_selected_tracks": self.min_selected_tracks,
            "min_unlabelled_alternatives": self.min_unlabelled_alternatives,
            "min_identified_fraction": self.min_identified_fraction,
            "min_observations": self.min_observations,
            "min_djs": self.min_djs,
            "history_window_days": self.history_window_days,
        }


@dataclass(frozen=True)
class RepertoireCandidate:
    mix_id: str
    title: str
    performed_on_candidate: str | None
    date_precision: str
    actor_candidate: str | None
    first_tag_candidate: str | None
    classification: str
    suggested_disposition: str
    track_slot_count: int
    identified_track_count: int
    unique_identified_track_count: int
    unidentified_track_count: int
    duplicate_identified_track_count: int
    identified_fraction: float

    def as_dict(self) -> dict[str, object]:
        return {
            "mix_id": self.mix_id,
            "title": self.title,
            "performed_on_candidate": self.performed_on_candidate,
            "date_precision": self.date_precision,
            "actor_candidate": self.actor_candidate,
            "first_tag_candidate": self.first_tag_candidate,
            "classification": self.classification,
            "suggested_disposition": self.suggested_disposition,
            "track_slot_count": self.track_slot_count,
            "identified_track_count": self.identified_track_count,
            "unique_identified_track_count": self.unique_identified_track_count,
            "unidentified_track_count": self.unidentified_track_count,
            "duplicate_identified_track_count": self.duplicate_identified_track_count,
            "identified_fraction": self.identified_fraction,
        }


@dataclass(frozen=True)
class RepertoireCandidateReport:
    candidates: tuple[RepertoireCandidate, ...]
    source: Mapping[str, object]
    counts: Mapping[str, int]
    fingerprint: str
    schema_version: str = REPERTOIRE_CANDIDATE_SCHEMA_VERSION

    @property
    def eligible_mix_ids(self) -> tuple[str, ...]:
        return tuple(candidate.mix_id for candidate in self.candidates)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "source": dict(self.source),
            "counts": dict(self.counts),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "trust_boundary": {
                "trusted": False,
                "may_enter_dataset_directly": False,
                "purpose": "review queue only",
                "required_review_schema": REPERTOIRE_REVIEW_SCHEMA_VERSION,
                "title_or_tag_identity_is_ground_truth": False,
            },
        }


def build_repertoire_candidate_report(
    corpus_root: str | Path,
    ordering_dataset: CorpusOrderingDataset,
) -> RepertoireCandidateReport:
    """Create untrusted review hints for the frozen ordering mix universe."""

    root = Path(corpus_root).expanduser().resolve()
    metadata_path, mixes = _load_metadata(root)
    eligible_ids = ordering_dataset.mix_ids
    missing = sorted(set(eligible_ids) - mixes.keys())
    if missing:
        preview = ", ".join(missing[:5])
        raise ValueError(f"{len(missing)} ordering mix(es) missing from metadata: {preview}")

    candidates: list[RepertoireCandidate] = []
    counts: Counter[str] = Counter()
    for mix_id in eligible_ids:
        mix = mixes[mix_id]
        title = str(mix.get("title") or "").strip()
        raw_date, actor, precision = _parse_title_candidate(title)
        tags = _category_labels(mix)
        first_tag = tags[0] if tags else None
        classification = _candidate_classification(actor=actor, first_tag=first_tag)
        summary = _track_summary(mix)
        suggested = (
            "review_for_approval"
            if classification == "solo_like"
            and precision == "day"
            and summary["duplicate_identified_track_count"] == 0
            else "review_for_exclusion_or_correction"
        )
        candidates.append(
            RepertoireCandidate(
                mix_id=mix_id,
                title=title,
                performed_on_candidate=raw_date,
                date_precision=precision,
                actor_candidate=actor,
                first_tag_candidate=first_tag,
                classification=classification,
                suggested_disposition=suggested,
                track_slot_count=int(summary["track_slot_count"]),
                identified_track_count=int(summary["identified_track_count"]),
                unique_identified_track_count=int(summary["unique_identified_track_count"]),
                unidentified_track_count=int(summary["unidentified_track_count"]),
                duplicate_identified_track_count=int(summary["duplicate_identified_track_count"]),
                identified_fraction=float(summary["identified_fraction"]),
            )
        )
        counts[f"classification_{classification}"] += 1
        counts[f"date_precision_{precision}"] += 1
        counts[f"suggested_{suggested}"] += 1
        if summary["duplicate_identified_track_count"]:
            counts["mixes_with_duplicate_track_ids"] += 1
        if summary["unidentified_track_count"]:
            counts["mixes_with_unidentified_tracks"] += 1

    source = {
        "corpus_metadata_relative_path": str(metadata_path.relative_to(root)),
        "corpus_metadata_sha256": _file_sha256(metadata_path),
        "ordering_dataset_schema_version": ordering_dataset.schema_version,
        "ordering_dataset_fingerprint": ordering_dataset.fingerprint,
        "eligible_mix_count": len(eligible_ids),
        "eligible_mix_ids_fingerprint": _fingerprint(list(eligible_ids)),
    }
    canonical = {
        "schema_version": REPERTOIRE_CANDIDATE_SCHEMA_VERSION,
        "source": source,
        "counts": dict(sorted(counts.items())),
        "candidates": [candidate.as_dict() for candidate in candidates],
    }
    return RepertoireCandidateReport(
        candidates=tuple(candidates),
        source=source,
        counts=dict(sorted(counts.items())),
        fingerprint=_fingerprint(canonical),
    )


@dataclass(frozen=True)
class ReviewedMix:
    mix_id: str
    dj_id: str
    performed_on: date
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RepertoireReviewInspection:
    required_count: int
    reviewed_count: int
    approved_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    extra_ids: tuple[str, ...]
    invalid_items: Mapping[str, str]
    declared_candidate_fingerprint: str | None
    candidate_fingerprint_matches: bool
    review_fingerprint: str
    provenance: Mapping[str, object]

    @property
    def ready(self) -> bool:
        return (
            self.required_count > 0
            and self.reviewed_count == self.required_count
            and not self.missing_ids
            and not self.extra_ids
            and not self.invalid_items
            and self.candidate_fingerprint_matches
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "required_count": self.required_count,
            "reviewed_count": self.reviewed_count,
            "approved_count": len(self.approved_ids),
            "approved_ids": list(self.approved_ids),
            "excluded_count": len(self.excluded_ids),
            "excluded_ids": list(self.excluded_ids),
            "missing_ids": list(self.missing_ids),
            "extra_ids": list(self.extra_ids),
            "invalid_items": dict(sorted(self.invalid_items.items())),
            "declared_candidate_fingerprint": self.declared_candidate_fingerprint,
            "candidate_fingerprint_matches": self.candidate_fingerprint_matches,
            "review_fingerprint": self.review_fingerprint,
            "provenance": dict(self.provenance),
        }


def inspect_repertoire_review(
    review_path: str | Path,
    candidate_report: RepertoireCandidateReport,
) -> tuple[RepertoireReviewInspection, dict[str, ReviewedMix]]:
    """Validate human-adjudicated identity/date evidence without partial use."""

    source = Path(review_path).expanduser().resolve()
    payload = _read_json(source)
    if not isinstance(payload, Mapping):
        raise ValueError("repertoire review must contain a JSON object")
    schema = str(payload.get("schema_version") or "")
    if schema != REPERTOIRE_REVIEW_SCHEMA_VERSION:
        raise ValueError(
            f"review schema must be {REPERTOIRE_REVIEW_SCHEMA_VERSION}, got {schema or 'missing'}"
        )
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping) or not provenance:
        raise ValueError("review needs non-empty provenance")
    raw_mixes = payload.get("mixes")
    if not isinstance(raw_mixes, Mapping):
        raise ValueError("review mixes must be an object keyed by mix ID")

    required_ids = set(candidate_report.eligible_mix_ids)
    supplied_ids = {
        mix_id for raw_mix_id in raw_mixes if (mix_id := _clean_identifier(raw_mix_id)) is not None
    }
    missing_ids = tuple(sorted(required_ids - supplied_ids))
    extra_ids = tuple(sorted(supplied_ids - required_ids))
    approved: dict[str, ReviewedMix] = {}
    excluded: list[str] = []
    invalid: dict[str, str] = {}

    for mix_id in sorted(required_ids & supplied_ids):
        raw_item = raw_mixes.get(mix_id)
        if not isinstance(raw_item, Mapping):
            invalid[mix_id] = "entry must be an object"
            continue
        status = str(raw_item.get("status") or "").strip()
        if status == "excluded":
            if _clean_identifier(raw_item.get("reason")) is None:
                invalid[mix_id] = "excluded entry needs a non-empty reason"
            else:
                excluded.append(mix_id)
            continue
        if status != "approved":
            invalid[mix_id] = "status must be approved or excluded"
            continue
        dj_id = _clean_identifier(raw_item.get("dj_id"))
        raw_date = _clean_identifier(raw_item.get("performed_on"))
        role = str(raw_item.get("performance_role") or "").strip()
        raw_evidence = raw_item.get("evidence")
        if dj_id is None:
            invalid[mix_id] = "approved entry needs dj_id"
            continue
        if raw_date is None or _date_precision(raw_date) != "day":
            invalid[mix_id] = "approved entry needs an exact ISO performed_on date"
            continue
        if role != "solo":
            invalid[mix_id] = "approved entry performance_role must be solo"
            continue
        if not isinstance(raw_evidence, list):
            invalid[mix_id] = "approved entry needs a non-empty evidence list"
            continue
        evidence = tuple(
            item for raw in raw_evidence if (item := _clean_identifier(raw)) is not None
        )
        if not evidence:
            invalid[mix_id] = "approved entry needs a non-empty evidence list"
            continue
        approved[mix_id] = ReviewedMix(
            mix_id=mix_id,
            dj_id=dj_id,
            performed_on=date.fromisoformat(raw_date),
            evidence=evidence,
        )

    declared_fingerprint = _clean_identifier(payload.get("candidate_report_fingerprint"))
    candidate_matches = declared_fingerprint == candidate_report.fingerprint
    canonical = {
        "schema_version": schema,
        "candidate_report_fingerprint": declared_fingerprint,
        "mixes": {str(key): value for key, value in sorted(raw_mixes.items())},
        "provenance": dict(provenance),
    }
    reviewed_count = len(approved) + len(excluded)
    inspection = RepertoireReviewInspection(
        required_count=len(required_ids),
        reviewed_count=reviewed_count,
        approved_ids=tuple(sorted(approved)),
        excluded_ids=tuple(sorted(excluded)),
        missing_ids=missing_ids,
        extra_ids=extra_ids,
        invalid_items=invalid,
        declared_candidate_fingerprint=declared_fingerprint,
        candidate_fingerprint_matches=candidate_matches,
        review_fingerprint=_fingerprint(canonical),
        provenance=dict(provenance),
    )
    return inspection, approved


@dataclass(frozen=True)
class RevealedRepertoireObservation:
    mix_id: str
    dj_id: str
    performed_on: str
    prior_mix_ids: tuple[str, ...]
    selected_track_ids: tuple[str, ...]
    prior_repertoire_track_ids: tuple[str, ...]
    unlabelled_alternative_track_ids: tuple[str, ...]
    previously_seen_selected_track_ids: tuple[str, ...]
    target_track_slot_count: int
    unidentified_target_track_count: int

    def __post_init__(self) -> None:
        if not self.mix_id or not self.dj_id:
            raise ValueError("mix_id and dj_id must not be empty")
        if _date_precision(self.performed_on) != "day":
            raise ValueError("performed_on must be an exact ISO date")
        if not self.prior_mix_ids:
            raise ValueError("prior_mix_ids must not be empty")
        for field_name in (
            "selected_track_ids",
            "prior_repertoire_track_ids",
            "unlabelled_alternative_track_ids",
            "previously_seen_selected_track_ids",
        ):
            values = getattr(self, field_name)
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{field_name} must be unique and canonically sorted")
        selected = set(self.selected_track_ids)
        prior = set(self.prior_repertoire_track_ids)
        if set(self.unlabelled_alternative_track_ids) != prior - selected:
            raise ValueError("unlabelled alternatives must equal prior repertoire minus selected")
        if set(self.previously_seen_selected_track_ids) != prior & selected:
            raise ValueError("previously seen selected tracks must equal prior/selected overlap")
        if self.target_track_slot_count < len(self.selected_track_ids):
            raise ValueError("target track slots cannot be smaller than selected IDs")
        if self.unidentified_target_track_count < 0:
            raise ValueError("unidentified target track count must not be negative")

    @property
    def available_track_ids(self) -> tuple[str, ...]:
        return _canonical_ids((*self.selected_track_ids, *self.unlabelled_alternative_track_ids))

    @property
    def identified_fraction(self) -> float:
        if self.target_track_slot_count == 0:
            return 0.0
        identified = self.target_track_slot_count - self.unidentified_target_track_count
        return identified / self.target_track_slot_count

    def as_dict(self) -> dict[str, object]:
        return {
            "mix_id": self.mix_id,
            "dj_id": self.dj_id,
            "performed_on": self.performed_on,
            "prior_mix_ids": list(self.prior_mix_ids),
            "selected_track_ids": list(self.selected_track_ids),
            "prior_repertoire_track_ids": list(self.prior_repertoire_track_ids),
            "unlabelled_alternative_track_ids": list(self.unlabelled_alternative_track_ids),
            "previously_seen_selected_track_ids": list(self.previously_seen_selected_track_ids),
            "available_track_ids": list(self.available_track_ids),
            "selection_size": len(self.selected_track_ids),
            "available_size": len(self.available_track_ids),
            "target_track_slot_count": self.target_track_slot_count,
            "unidentified_target_track_count": self.unidentified_target_track_count,
            "identified_fraction": self.identified_fraction,
        }


@dataclass(frozen=True)
class RevealedRepertoireDataset:
    observations: tuple[RevealedRepertoireObservation, ...]
    audit: Mapping[str, object]
    fingerprint: str
    schema_version: str = REPERTOIRE_DATASET_SCHEMA_VERSION

    @property
    def mix_ids(self) -> tuple[str, ...]:
        return tuple(observation.mix_id for observation in self.observations)

    @property
    def dj_ids(self) -> tuple[str, ...]:
        return _canonical_ids(observation.dj_id for observation in self.observations)

    @property
    def track_ids(self) -> tuple[str, ...]:
        return _canonical_ids(
            track_id
            for observation in self.observations
            for track_id in observation.available_track_ids
        )

    def as_dict(self, *, include_observations: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "observation_count": len(self.observations),
            "mix_count": len(self.mix_ids),
            "dj_count": len(self.dj_ids),
            "track_count": len(self.track_ids),
            "audit": dict(self.audit),
        }
        if include_observations:
            payload["observations"] = [observation.as_dict() for observation in self.observations]
        return payload


@dataclass(frozen=True)
class _ApprovedMixData:
    mix_id: str
    dj_id: str
    performed_on: date
    track_ids: tuple[str, ...]
    track_slot_count: int
    unidentified_track_count: int
    duplicate_track_count: int


def build_revealed_repertoire_dataset(
    corpus_root: str | Path,
    *,
    ordering_dataset: CorpusOrderingDataset,
    candidate_report: RepertoireCandidateReport,
    review: RepertoireReviewInspection,
    approved_mixes: Mapping[str, ReviewedMix],
    config: RepertoireBuildConfig | None = None,
) -> RevealedRepertoireDataset:
    """Build the proxy only after complete, fingerprint-matched adjudication."""

    if not review.ready:
        raise ValueError("repertoire review is incomplete or does not match candidates")
    root = Path(corpus_root).expanduser().resolve()
    metadata_path, mixes = _load_metadata(root)
    effective_config = config or RepertoireBuildConfig()
    records: list[_ApprovedMixData] = []
    counts: Counter[str] = Counter()

    for mix_id, reviewed in sorted(approved_mixes.items()):
        mix = mixes.get(mix_id)
        if mix is None:
            raise ValueError(f"approved mix is missing from corpus metadata: {mix_id}")
        summary = _track_summary(mix)
        records.append(
            _ApprovedMixData(
                mix_id=mix_id,
                dj_id=reviewed.dj_id,
                performed_on=reviewed.performed_on,
                track_ids=tuple(summary["identified_track_ids"]),
                track_slot_count=int(summary["track_slot_count"]),
                unidentified_track_count=int(summary["unidentified_track_count"]),
                duplicate_track_count=int(summary["duplicate_identified_track_count"]),
            )
        )

    by_dj: dict[str, list[_ApprovedMixData]] = defaultdict(list)
    for record in records:
        by_dj[record.dj_id].append(record)

    observations: list[RevealedRepertoireObservation] = []
    for dj_id, dj_records in sorted(by_dj.items()):
        ordered = sorted(dj_records, key=lambda item: (item.performed_on, item.mix_id))
        for target in ordered:
            counts["approved_target_candidates"] += 1
            if target.duplicate_track_count:
                counts["excluded_duplicate_target_tracks"] += 1
                continue
            if target.track_slot_count == 0:
                counts["excluded_empty_target_tracklist"] += 1
                continue
            identified_fraction = len(target.track_ids) / target.track_slot_count
            if identified_fraction < effective_config.min_identified_fraction:
                counts["excluded_low_identified_fraction"] += 1
                continue
            if len(target.track_ids) < effective_config.min_selected_tracks:
                counts["excluded_too_few_selected_tracks"] += 1
                continue

            prior_records = [
                item
                for item in ordered
                if item.performed_on < target.performed_on
                and (
                    effective_config.history_window_days is None
                    or (target.performed_on - item.performed_on).days
                    <= effective_config.history_window_days
                )
                and item.track_ids
            ]
            if len(prior_records) < effective_config.min_prior_mixes:
                counts["excluded_too_few_prior_mixes"] += 1
                continue
            prior_track_ids = _canonical_ids(
                track_id for item in prior_records for track_id in item.track_ids
            )
            if len(prior_track_ids) < effective_config.min_prior_tracks:
                counts["excluded_too_few_prior_tracks"] += 1
                continue
            alternatives = _canonical_ids(set(prior_track_ids) - set(target.track_ids))
            if len(alternatives) < effective_config.min_unlabelled_alternatives:
                counts["excluded_too_few_unlabelled_alternatives"] += 1
                continue
            seen_selected = _canonical_ids(set(prior_track_ids) & set(target.track_ids))
            observations.append(
                RevealedRepertoireObservation(
                    mix_id=target.mix_id,
                    dj_id=dj_id,
                    performed_on=target.performed_on.isoformat(),
                    prior_mix_ids=tuple(sorted(item.mix_id for item in prior_records)),
                    selected_track_ids=target.track_ids,
                    prior_repertoire_track_ids=prior_track_ids,
                    unlabelled_alternative_track_ids=alternatives,
                    previously_seen_selected_track_ids=seen_selected,
                    target_track_slot_count=target.track_slot_count,
                    unidentified_target_track_count=target.unidentified_track_count,
                )
            )
            counts["observations"] += 1
            counts["selected_tracks"] += len(target.track_ids)
            counts["unlabelled_alternatives"] += len(alternatives)
            counts["previously_seen_selected_tracks"] += len(seen_selected)

    observations.sort(key=lambda item: (item.performed_on, item.dj_id, item.mix_id))
    source = {
        "corpus_metadata_relative_path": str(metadata_path.relative_to(root)),
        "corpus_metadata_sha256": _file_sha256(metadata_path),
        "ordering_dataset_fingerprint": ordering_dataset.fingerprint,
        "candidate_report_fingerprint": candidate_report.fingerprint,
        "review_fingerprint": review.review_fingerprint,
    }
    audit = {
        "scope": (
            "P(identified target subset | tracks revealed in earlier approved "
            "solo sets by the same DJ)"
        ),
        "explicitly_not_modelled": "P(track selected | DJ true event crate)",
        "config": effective_config.as_dict(),
        "source": source,
        "counts": dict(sorted(counts.items())),
        "label_semantics": {
            "selected_track_ids": "observed positives in the target mix",
            "unlabelled_alternative_track_ids": (
                "earlier revealed tracks not observed in target; not confirmed negatives"
            ),
            "target_mix_used_as_its_own_history": False,
        },
        "leakage_guards": [
            "only exact reviewed dates are accepted",
            "only reviewed solo performances are accepted",
            "history is strictly earlier than the target date",
            "same-day and future mixes never enter target history",
            "the target mix contributes positives only, never alternatives",
            "candidate title and tag parsing cannot enter the dataset directly",
            "all eligible ordering mixes require explicit approval or exclusion",
        ],
        "limitations": [
            "revealed repertoire is a lower-bound proxy, not the DJ's real crate",
            "unlabelled historical tracks may have been unavailable at the target event",
            "track release dates are not verified",
            "unknown catalogue IDs make the identified target subset incomplete",
            "DJ intent, venue constraints and causal rejection reasons are unobserved",
            "the proxy should be treated as positive-unlabelled evidence",
        ],
    }
    canonical = {
        "schema_version": REPERTOIRE_DATASET_SCHEMA_VERSION,
        "source": source,
        "config": effective_config.as_dict(),
        "observations": [observation.as_dict() for observation in observations],
    }
    return RevealedRepertoireDataset(
        observations=tuple(observations),
        audit=audit,
        fingerprint=_fingerprint(canonical),
    )


@dataclass(frozen=True)
class RepertoireFeatureCoverage:
    required_count: int
    available_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    extra_ids: tuple[str, ...]
    source_fingerprint: str | None

    @property
    def ready(self) -> bool:
        return (
            self.required_count > 0
            and len(self.available_ids) == self.required_count
            and not self.missing_ids
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "required_count": self.required_count,
            "available_count": len(self.available_ids),
            "available_ids": list(self.available_ids),
            "missing_ids": list(self.missing_ids),
            "extra_ids": list(self.extra_ids),
            "source_fingerprint": self.source_fingerprint,
            "required_families": ["H", "E"],
        }


def inspect_repertoire_feature_coverage(
    dataset: RevealedRepertoireDataset | None,
    feature_catalog: OrderingFeatureCatalog | None,
) -> RepertoireFeatureCoverage:
    required = set(dataset.track_ids if dataset is not None else ())
    available_source = set(feature_catalog.tracks if feature_catalog is not None else ())
    available = tuple(sorted(required & available_source))
    return RepertoireFeatureCoverage(
        required_count=len(required),
        available_ids=available,
        missing_ids=tuple(sorted(required - available_source)),
        extra_ids=tuple(sorted(available_source - required)),
        source_fingerprint=feature_catalog.fingerprint if feature_catalog is not None else None,
    )


def _component_coverage_from_feature_catalog(
    dataset: RevealedRepertoireDataset | None,
    feature_catalog: OrderingFeatureCatalog | None,
    *,
    family: str,
) -> ComponentCoverage:
    required_ids = dataset.track_ids if dataset is not None else ()
    required = set(required_ids)
    available_source = set(feature_catalog.tracks if feature_catalog is not None else ())
    available = tuple(sorted(required & available_source))
    metadata: dict[str, object] = {
        "status": "not supplied",
        "coverage_source": "combined ordering feature catalogue",
    }
    source_fingerprint: str | None = None
    if feature_catalog is not None:
        source_fingerprint = feature_catalog.fingerprint
        metadata = {
            "status": "validated",
            "coverage_source": "combined ordering feature catalogue",
            "catalog_provenance": dict(feature_catalog.provenance),
        }
        if family == "H":
            metadata.update(
                {
                    "dimension": feature_catalog.handcrafted_dimension,
                    "feature_names": list(feature_catalog.handcrafted_feature_names),
                }
            )
        else:
            metadata.update(
                {
                    "dimension": feature_catalog.embedding_dimension,
                    "embedding_name": feature_catalog.embedding_name,
                }
            )
    return ComponentCoverage(
        name=family,
        required_count=len(required),
        available_ids=available,
        missing_ids=tuple(sorted(required - available_source)),
        invalid_items={},
        extra_ids=tuple(sorted(available_source - required)),
        source_fingerprint=source_fingerprint,
        metadata=metadata,
    )


def inspect_repertoire_evidence_coverage(
    corpus_root: str | Path,
    dataset: RevealedRepertoireDataset | None,
    feature_catalog: OrderingFeatureCatalog | None,
    *,
    analysis_root: str | Path | None = None,
    analysis_index_path: str | Path | None = None,
    embedding_catalog_path: str | Path | None = None,
) -> tuple[AudioInventoryReport | None, ComponentCoverage, ComponentCoverage]:
    """Inspect source audio, H and E over the exact proxy universe.

    Explicit H/E sources take precedence. A validated combined model catalogue
    is also accepted because every row in that schema necessarily contains
    both feature families.
    """

    required_ids = dataset.track_ids if dataset is not None else ()
    source_audio = (
        inspect_audio_inventory(corpus_root, required_ids) if dataset is not None else None
    )
    if analysis_root is not None or analysis_index_path is not None:
        handcrafted = inspect_handcrafted_coverage(
            required_ids,
            analysis_root=analysis_root,
            analysis_index_path=analysis_index_path,
        )
    else:
        handcrafted = _component_coverage_from_feature_catalog(
            dataset,
            feature_catalog,
            family="H",
        )
    if embedding_catalog_path is not None:
        embeddings = inspect_embedding_coverage(required_ids, embedding_catalog_path)
    else:
        embeddings = _component_coverage_from_feature_catalog(
            dataset,
            feature_catalog,
            family="E",
        )
    return source_audio, handcrafted, embeddings


@dataclass(frozen=True)
class RevealedRepertoireGateReport:
    ordering_dataset: Mapping[str, object]
    candidate_report: Mapping[str, object]
    review: RepertoireReviewInspection
    proxy_dataset: Mapping[str, object]
    source_audio: AudioInventoryReport | None
    handcrafted: ComponentCoverage
    embeddings: ComponentCoverage
    features: RepertoireFeatureCoverage
    readiness: Mapping[str, bool]
    blockers: tuple[str, ...]
    config: RepertoireBuildConfig
    fingerprint: str
    schema_version: str = REPERTOIRE_GATE_SCHEMA_VERSION

    @property
    def ready_for_proxy_evaluation(self) -> bool:
        return bool(self.readiness.get("proxy_evaluation_ready"))

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "ordering_dataset": dict(self.ordering_dataset),
            "candidate_report": dict(self.candidate_report),
            "review": self.review.as_dict(),
            "proxy_dataset": dict(self.proxy_dataset),
            "source_audio": (
                self.source_audio.as_dict()
                if self.source_audio is not None
                else {
                    "inspected": False,
                    "reason": "proxy dataset was not built",
                }
            ),
            "handcrafted": self.handcrafted.as_dict(),
            "embeddings": self.embeddings.as_dict(),
            "features": self.features.as_dict(),
            "readiness": dict(self.readiness),
            "blockers": list(self.blockers),
            "config": self.config.as_dict(),
            "policies": {
                "scope": "offline validation only",
                "production_engine_mutated": False,
                "fail_closed": True,
                "full_frozen_universe_adjudication_required": True,
                "candidate_hints_are_trusted_identity": False,
                "future_sets_allowed_in_history": False,
                "unlabelled_alternatives_are_negatives": False,
                "calibrated_real_crate_probability_claimed": False,
            },
        }


def build_revealed_repertoire_gate(
    corpus_root: str | Path,
    *,
    ordering_dataset: CorpusOrderingDataset,
    review_path: str | Path,
    feature_catalog: OrderingFeatureCatalog | None = None,
    analysis_root: str | Path | None = None,
    analysis_index_path: str | Path | None = None,
    embedding_catalog_path: str | Path | None = None,
    config: RepertoireBuildConfig | None = None,
    expected_ordering_dataset_fingerprint: str | None = None,
) -> tuple[
    RepertoireCandidateReport,
    RevealedRepertoireGateReport,
    RevealedRepertoireDataset | None,
]:
    """Build the complete fail-closed gate and optional immutable proxy."""

    effective_config = config or RepertoireBuildConfig()
    candidates = build_repertoire_candidate_report(corpus_root, ordering_dataset)
    review, approved = inspect_repertoire_review(review_path, candidates)
    ordering_matches = (
        expected_ordering_dataset_fingerprint is None
        or ordering_dataset.fingerprint == expected_ordering_dataset_fingerprint
    )
    proxy: RevealedRepertoireDataset | None = None
    if review.ready and ordering_matches:
        proxy = build_revealed_repertoire_dataset(
            corpus_root,
            ordering_dataset=ordering_dataset,
            candidate_report=candidates,
            review=review,
            approved_mixes=approved,
            config=effective_config,
        )

    source_audio, handcrafted, embeddings = inspect_repertoire_evidence_coverage(
        corpus_root,
        proxy,
        feature_catalog,
        analysis_root=analysis_root,
        analysis_index_path=analysis_index_path,
        embedding_catalog_path=embedding_catalog_path,
    )
    features = inspect_repertoire_feature_coverage(proxy, feature_catalog)
    sample_size_ready = (
        proxy is not None
        and len(proxy.observations) >= effective_config.min_observations
        and len(proxy.dj_ids) >= effective_config.min_djs
    )
    readiness = {
        "ordering_dataset_fingerprint_ready": ordering_matches,
        "review_ready": review.ready,
        "proxy_dataset_built": proxy is not None,
        "sample_size_ready": sample_size_ready,
        "source_audio_complete": bool(
            source_audio is not None and source_audio.source_complete
        ),
        "handcrafted_complete": handcrafted.ready,
        "frozen_embeddings_complete": embeddings.ready,
        "model_feature_catalog_complete": features.ready,
        "feature_evidence_ready": (
            handcrafted.ready and embeddings.ready and features.ready
        ),
        "proxy_evaluation_ready": (
            ordering_matches
            and review.ready
            and sample_size_ready
            and handcrafted.ready
            and embeddings.ready
            and features.ready
        ),
    }
    blockers: list[str] = []
    if not ordering_matches:
        blockers.append("ordering dataset fingerprint differs from the pre-registered fingerprint")
    if not review.candidate_fingerprint_matches:
        blockers.append("review was not made against this exact candidate report")
    if review.missing_ids:
        blockers.append(f"{len(review.missing_ids)} eligible mix(es) are not reviewed")
    if review.extra_ids:
        blockers.append(f"{len(review.extra_ids)} review mix(es) are outside the universe")
    if review.invalid_items:
        blockers.append(f"{len(review.invalid_items)} review entry/entries are invalid")
    if proxy is not None and len(proxy.observations) < effective_config.min_observations:
        blockers.append(
            f"proxy has {len(proxy.observations)} observations; "
            f"{effective_config.min_observations} required"
        )
    if proxy is not None and len(proxy.dj_ids) < effective_config.min_djs:
        blockers.append(f"proxy has {len(proxy.dj_ids)} DJs; {effective_config.min_djs} required")
    if proxy is not None and not handcrafted.ready:
        blockers.append(
            f"H incomplete: {handcrafted.unavailable_count}/"
            f"{handcrafted.required_count} proxy track(s) unavailable"
        )
        if source_audio is not None and not source_audio.source_complete:
            blockers.append(
                "proxy source audio incomplete: "
                f"{len(source_audio.missing_ids)} missing, "
                f"{len(source_audio.ambiguous_paths)} ambiguous"
            )
        if source_audio is not None and source_audio.unsupported_for_engine_ids:
            blockers.append(
                f"H extraction blocked for "
                f"{len(source_audio.unsupported_for_engine_ids)} resolved source(s) "
                "unsupported by the engine decoder"
            )
    if proxy is not None and not embeddings.ready:
        blockers.append(
            f"E incomplete: {embeddings.unavailable_count}/"
            f"{embeddings.required_count} proxy track(s) unavailable"
        )
    if proxy is not None and not features.ready:
        blockers.append(
            "combined H/E model catalogue incomplete for "
            f"{len(features.missing_ids)}/{features.required_count} proxy track(s)"
        )

    ordering_summary = {
        "schema_version": ordering_dataset.schema_version,
        "fingerprint": ordering_dataset.fingerprint,
        "expected_fingerprint": expected_ordering_dataset_fingerprint,
        "fingerprint_matches_expected": ordering_matches,
        "mix_count": len(ordering_dataset.mix_ids),
        "observation_count": len(ordering_dataset.observations),
    }
    candidate_summary = {
        "schema_version": candidates.schema_version,
        "fingerprint": candidates.fingerprint,
        "eligible_mix_count": len(candidates.candidates),
        "counts": dict(candidates.counts),
    }
    proxy_summary = (
        proxy.as_dict(include_observations=False)
        if proxy is not None
        else {
            "schema_version": REPERTOIRE_DATASET_SCHEMA_VERSION,
            "built": False,
        }
    )
    canonical = {
        "schema_version": REPERTOIRE_GATE_SCHEMA_VERSION,
        "ordering_dataset": ordering_summary,
        "candidate_report": candidate_summary,
        "review": review.as_dict(),
        "proxy_dataset": proxy_summary,
        "source_audio": (
            source_audio.as_dict()
            if source_audio is not None
            else {"inspected": False, "reason": "proxy dataset was not built"}
        ),
        "handcrafted": handcrafted.as_dict(),
        "embeddings": embeddings.as_dict(),
        "features": features.as_dict(),
        "readiness": readiness,
        "blockers": blockers,
        "config": effective_config.as_dict(),
    }
    report = RevealedRepertoireGateReport(
        ordering_dataset=ordering_summary,
        candidate_report=candidate_summary,
        review=review,
        proxy_dataset=proxy_summary,
        source_audio=source_audio,
        handcrafted=handcrafted,
        embeddings=embeddings,
        features=features,
        readiness=readiness,
        blockers=tuple(blockers),
        config=effective_config,
        fingerprint=_fingerprint(canonical),
    )
    return candidates, report, proxy


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


def write_repertoire_candidate_report(
    report: RepertoireCandidateReport,
    output_path: str | Path,
) -> Path:
    return _write_json_atomic(report.as_dict(), output_path)


def write_repertoire_review_template(
    report: RepertoireCandidateReport,
    output_path: str | Path,
) -> Path:
    """Write a deliberately non-runnable review worksheet.

    ``pending`` is not accepted by :func:`inspect_repertoire_review`. A human
    must replace every entry with an explicit approved or excluded decision.
    """

    payload = {
        "schema_version": REPERTOIRE_REVIEW_SCHEMA_VERSION,
        "candidate_report_fingerprint": report.fingerprint,
        "mixes": {
            candidate.mix_id: {
                "status": "pending",
                "candidate": {
                    "actor": candidate.actor_candidate,
                    "performed_on": candidate.performed_on_candidate,
                    "date_precision": candidate.date_precision,
                    "classification": candidate.classification,
                    "suggested_disposition": candidate.suggested_disposition,
                },
            }
            for candidate in report.candidates
        },
        "provenance": {
            "status": "template-not-reviewed",
            "generated_from_candidate_report": report.fingerprint,
            "instructions": (
                "replace every pending entry with approved plus evidence or excluded plus reason"
            ),
        },
    }
    return _write_json_atomic(payload, output_path)


def write_revealed_repertoire_dataset(
    dataset: RevealedRepertoireDataset,
    output_path: str | Path,
) -> Path:
    return _write_json_atomic(dataset.as_dict(include_observations=True), output_path)


def write_revealed_repertoire_gate(
    report: RevealedRepertoireGateReport,
    output_path: str | Path,
) -> Path:
    return _write_json_atomic(report.as_dict(), output_path)

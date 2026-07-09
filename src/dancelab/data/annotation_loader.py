"""Annotation CSV loaders (Data Contracts - Annotation Files).

Six contract files under data/annotations/:
    track_metadata.csv, segment_annotations.csv,
    transition_window_annotations.csv, mixability_pair_annotations.csv,
    set_function_labels.csv, context_profiles.csv

Rules from the contract:
- stable ids (track_id, segment_id, window_id, pair_id, context_profile_id),
  never file-name based logic;
- missing data = empty field or "unknown" — NEVER fabricated values.

Loaders are strict on structure (missing columns fail) and lenient on empty
optional values (parsed as None). Cross-record validation lives in
annotation_validator.py.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, Field

from dancelab.core.errors import DanceLabError


class AnnotationFileError(DanceLabError):
    """Annotation CSV is missing, unreadable, or has a broken header."""


# ------------------------------------------------------------------ row models

RATING = Field(default=None, ge=1, le=5)


class TrackMetadata(BaseModel):
    track_id: str
    title: str | None = None
    artist: str | None = None
    duration_sec: float | None = Field(default=None, gt=0)
    bpm: float | None = Field(default=None, gt=0)
    style: str | None = None
    key: str | None = None
    source: str | None = None


class SegmentAnnotation(BaseModel):
    segment_id: str
    track_id: str
    start_sec: float = Field(ge=0)
    end_sec: float
    segment_type: str = "unknown"
    phrase_length_bars: int | None = Field(default=None, gt=0)
    energy_level: int | None = RATING
    tension_level: int | None = RATING
    vocal_presence: int | None = RATING
    bass_intensity: int | None = RATING
    comment: str | None = None


class TransitionWindowAnnotation(BaseModel):
    window_id: str
    track_id: str
    window_type: str = "unknown"
    start_sec: float = Field(ge=0)
    end_sec: float
    dj_rating: int | None = RATING
    engine_candidate: bool = False
    reason_good: str | None = None
    risk_notes: str | None = None


class MixabilityPairAnnotation(BaseModel):
    pair_id: str
    track_id_a: str
    track_id_b: str
    window_a_id: str | None = None
    window_b_id: str | None = None
    dj_mixability_rating: int | None = RATING
    tempo_fit_rating: int | None = RATING
    phrase_fit_rating: int | None = RATING
    bass_conflict_rating: int | None = RATING
    vocal_conflict_rating: int | None = RATING
    tension_fit_rating: int | None = RATING
    comment: str | None = None


class SetFunctionLabel(BaseModel):
    track_id: str
    context_profile_id: str | None = None
    primary_function: str
    secondary_functions: list[str] = Field(default_factory=list)
    dj_confidence: int | None = RATING
    reasoning: str | None = None
    risk_notes: str | None = None


class ContextProfileRow(BaseModel):
    context_profile_id: str
    venue_type: str | None = None
    set_role: str | None = None
    time_of_night: str | None = None
    crowd_energy: str | None = None
    style_focus: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------- loading

_LIST_SEPARATOR = ";"


def _read_rows(path: str | Path, required: set[str]) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise AnnotationFileError(f"Annotation file not found: {p}")
    with p.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = set(reader.fieldnames or [])
        missing = required - header
        if missing:
            raise AnnotationFileError(f"{p.name}: missing columns {sorted(missing)}")
        return [
            {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            for row in reader
            if any((v or "").strip() for v in row.values())
        ]


def _clean(row: dict, list_fields: tuple[str, ...] = (), bool_fields: tuple[str, ...] = ()) -> dict:
    # list/bool fields checked FIRST so an empty value becomes [] / False,
    # not None (which would fail typed-list / bool validation).
    out: dict = {}
    for k, v in row.items():
        if k in list_fields:
            out[k] = [s.strip() for s in (v or "").split(_LIST_SEPARATOR) if s.strip()]
        elif k in bool_fields:
            out[k] = str(v or "").strip().lower() in ("1", "true", "yes")
        elif v in ("", None, "unknown") and k not in ("segment_type", "window_type"):
            out[k] = None
        else:
            out[k] = v
    return out


def load_track_metadata(path: str | Path) -> list[TrackMetadata]:
    rows = _read_rows(path, {"track_id"})
    return [TrackMetadata.model_validate(_clean(r)) for r in rows]


def load_segment_annotations(path: str | Path) -> list[SegmentAnnotation]:
    rows = _read_rows(path, {"segment_id", "track_id", "start_sec", "end_sec"})
    return [SegmentAnnotation.model_validate(_clean(r)) for r in rows]


def load_transition_windows(path: str | Path) -> list[TransitionWindowAnnotation]:
    rows = _read_rows(path, {"window_id", "track_id", "start_sec", "end_sec"})
    return [
        TransitionWindowAnnotation.model_validate(_clean(r, bool_fields=("engine_candidate",)))
        for r in rows
    ]


def load_mixability_pairs(path: str | Path) -> list[MixabilityPairAnnotation]:
    rows = _read_rows(path, {"pair_id", "track_id_a", "track_id_b"})
    return [MixabilityPairAnnotation.model_validate(_clean(r)) for r in rows]


def load_set_function_labels(path: str | Path) -> list[SetFunctionLabel]:
    rows = _read_rows(path, {"track_id", "primary_function"})
    return [
        SetFunctionLabel.model_validate(_clean(r, list_fields=("secondary_functions",)))
        for r in rows
    ]


def load_context_profiles(path: str | Path) -> list[ContextProfileRow]:
    rows = _read_rows(path, {"context_profile_id"})
    return [
        ContextProfileRow.model_validate(_clean(r, list_fields=("style_focus",)))
        for r in rows
    ]

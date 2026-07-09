"""Cross-record validation of the annotation dataset (Engineering Ticket).

Rules:
- no empty track_id (loaders enforce),
- start_sec < end_sec,
- segments within track duration,
- ratings in 1–5 (loaders enforce via Pydantic),
- mixability pairs reference existing tracks,
- transition windows reference existing tracks,
- set function labels use known roles,
- context profile references exist.

Works WITHOUT audio files (ticket DoD) — duration checks use track_metadata.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from dancelab.data import annotation_loader as al

KNOWN_ROLES = {
    "opener", "builder", "bridge", "peak", "reset", "closer",
    "tool", "transition_tool", "tension_builder", "release_moment",
    "depends",  # honest uncertainty is a legal label (Annotation Schema rule)
}

FILES = {
    "track_metadata": "track_metadata.csv",
    "segments": "segment_annotations.csv",
    "transition_windows": "transition_window_annotations.csv",
    "mixability_pairs": "mixability_pair_annotations.csv",
    "set_function_labels": "set_function_labels.csv",
    "context_profiles": "context_profiles.csv",
}


class DatasetValidationReport(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


def validate_annotation_dataset(root: str | Path) -> DatasetValidationReport:
    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    def try_load(key: str, loader):
        path = root / FILES[key]
        if not path.exists():
            warnings.append(f"{FILES[key]} missing — {key} not validated")
            counts[key] = 0
            return []
        try:
            rows = loader(path)
            counts[key] = len(rows)
            return rows
        except Exception as exc:
            errors.append(f"{FILES[key]}: {exc}")
            counts[key] = 0
            return []

    tracks = try_load("track_metadata", al.load_track_metadata)
    segments = try_load("segments", al.load_segment_annotations)
    windows = try_load("transition_windows", al.load_transition_windows)
    pairs = try_load("mixability_pairs", al.load_mixability_pairs)
    labels = try_load("set_function_labels", al.load_set_function_labels)
    contexts = try_load("context_profiles", al.load_context_profiles)

    track_ids = {t.track_id for t in tracks}
    durations = {t.track_id: t.duration_sec for t in tracks if t.duration_sec}
    context_ids = {c.context_profile_id for c in contexts}

    def check_span(kind: str, rid: str, tid: str, start: float, end: float):
        if start >= end:
            errors.append(f"{kind} {rid}: start_sec {start} >= end_sec {end}")
        dur = durations.get(tid)
        if dur and end > dur + 1.0:  # 1 s tolerance for rounding
            errors.append(f"{kind} {rid}: end_sec {end} beyond track duration {dur}")

    for s in segments:
        if track_ids and s.track_id not in track_ids:
            errors.append(f"segment {s.segment_id}: unknown track_id '{s.track_id}'")
        check_span("segment", s.segment_id, s.track_id, s.start_sec, s.end_sec)

    for wnd in windows:
        if track_ids and wnd.track_id not in track_ids:
            errors.append(f"window {wnd.window_id}: unknown track_id '{wnd.track_id}'")
        check_span("window", wnd.window_id, wnd.track_id, wnd.start_sec, wnd.end_sec)

    window_ids = {wnd.window_id for wnd in windows}
    for p in pairs:
        for side, tid in (("a", p.track_id_a), ("b", p.track_id_b)):
            if track_ids and tid not in track_ids:
                errors.append(f"pair {p.pair_id}: unknown track_id_{side} '{tid}'")
        for side, wid in (("a", p.window_a_id), ("b", p.window_b_id)):
            if wid and window_ids and wid not in window_ids:
                errors.append(f"pair {p.pair_id}: unknown window_{side}_id '{wid}'")

    for lbl in labels:
        if track_ids and lbl.track_id not in track_ids:
            errors.append(f"set_function label: unknown track_id '{lbl.track_id}'")
        if lbl.primary_function not in KNOWN_ROLES:
            errors.append(
                f"set_function label {lbl.track_id}: unknown role '{lbl.primary_function}' "
                f"(known: {sorted(KNOWN_ROLES)})"
            )
        for sec in lbl.secondary_functions:
            if sec not in KNOWN_ROLES:
                errors.append(f"set_function label {lbl.track_id}: unknown secondary role '{sec}'")
        if lbl.context_profile_id and context_ids and lbl.context_profile_id not in context_ids:
            errors.append(
                f"set_function label {lbl.track_id}: unknown context '{lbl.context_profile_id}'"
            )

    # contract: extreme ratings should carry a comment
    for p in pairs:
        if p.dj_mixability_rating in (1, 5) and not p.comment:
            warnings.append(f"pair {p.pair_id}: rating {p.dj_mixability_rating} without comment")
    for wnd in windows:
        if wnd.dj_rating in (1, 5) and not (wnd.reason_good or wnd.risk_notes):
            warnings.append(f"window {wnd.window_id}: rating {wnd.dj_rating} without comment")

    return DatasetValidationReport(
        valid=not errors, errors=errors, warnings=warnings, counts=counts
    )

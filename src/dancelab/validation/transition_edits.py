"""Append-only DJ corrections captured by the transition review waveform.

The engine suggestion is never overwritten.  Each row stores a reference
value and the DJ's corrected value so validation can measure both direction
and magnitude of the correction later.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dancelab.security import spreadsheet_safe_value


TRANSITION_EDIT_SCHEMA_VERSION = "1.0"
ALLOWED_ACTIONS = {"transition_region_set", "hot_cue_moved", "hot_cue_set"}
ALLOWED_DECKS = {"A", "B"}


@dataclass(frozen=True)
class TransitionEditEvent:
    pair_id: str
    track_id_a: str
    track_id_b: str
    deck: str
    track_id: str
    action: str
    marker_type: str
    user_start_sec: float
    user_end_sec: float | None = None
    marker_label: str = ""
    marker_name: str = ""
    reference_source: str = ""
    reference_start_sec: float | None = None
    reference_end_sec: float | None = None
    reference_start_beat: int | None = None
    reference_end_beat: int | None = None
    user_start_beat: int | None = None
    user_end_beat: int | None = None
    track_duration_sec: float | None = None
    quantize_grid_beats: int = 0
    beatgrid_reliable: bool = False
    engine_pair_score: float | None = None
    annotator: str = "anonymous"
    recorded_at_utc: str = ""
    event_id: str = ""
    schema_version: str = TRANSITION_EDIT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.pair_id or not self.track_id_a or not self.track_id_b or not self.track_id:
            raise ValueError("transition edit identifiers cannot be empty")
        if self.deck not in ALLOWED_DECKS:
            raise ValueError(f"deck must be one of {sorted(ALLOWED_DECKS)}")
        if self.action not in ALLOWED_ACTIONS:
            raise ValueError(f"unsupported transition edit action: {self.action}")
        if self.user_start_sec < 0:
            raise ValueError("user_start_sec cannot be negative")
        if self.user_end_sec is not None and self.user_end_sec < self.user_start_sec:
            raise ValueError("user_end_sec cannot precede user_start_sec")
        if self.action == "transition_region_set":
            if self.user_end_sec is None or self.user_end_sec <= self.user_start_sec:
                raise ValueError("transition region must have a positive duration")
        if self.quantize_grid_beats < 0:
            raise ValueError("quantize_grid_beats cannot be negative")

    def stamped(self) -> "TransitionEditEvent":
        values = asdict(self)
        values["event_id"] = self.event_id or str(uuid4())
        values["recorded_at_utc"] = self.recorded_at_utc or datetime.now(timezone.utc).isoformat()
        values["annotator"] = self.annotator.strip() or "anonymous"
        return TransitionEditEvent(**values)


TRANSITION_EDIT_FIELDS = [field.name for field in fields(TransitionEditEvent)]


def transition_edits_path(cache_root: str | Path, annotator: str) -> Path:
    safe_annotator = "_".join((annotator.strip() or "anonymous").split())
    safe_annotator = "".join(
        char for char in safe_annotator if char.isalnum() or char in {"_", "-"}
    ) or "anonymous"
    root = Path(cache_root).expanduser() / "validation"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe_annotator}_transition_edits.csv"


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return spreadsheet_safe_value(value)


def append_transition_edit(path: str | Path, event: TransitionEditEvent) -> TransitionEditEvent:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stamped = event.stamped()
    is_new = not destination.exists() or destination.stat().st_size == 0
    with destination.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRANSITION_EDIT_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({key: _csv_value(value) for key, value in asdict(stamped).items()})
        handle.flush()
    return stamped


def read_transition_edits(
    path: str | Path,
    *,
    pair_id: str | None = None,
) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if pair_id is None:
        return rows
    return [row for row in rows if row.get("pair_id") == pair_id]


def latest_transition_edits(
    path: str | Path,
    pair_id: str,
) -> dict[tuple[str, str, str], dict[str, str]]:
    """Latest row keyed by ``(deck, action, marker_label)`` for restoration."""
    latest: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in read_transition_edits(path, pair_id=pair_id):
        key = (row.get("deck", ""), row.get("action", ""), row.get("marker_label", ""))
        latest[key] = row
    return latest

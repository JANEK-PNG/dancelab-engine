"""Strict extraction of adjacent transitions from a local Raveform archive."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from dancelab.validation.raveform.models import (
    DURATION_BUCKETS_BEATS,
    TransitionObservation,
    normalize_context_label,
)


MATCH_RATE_MIN = 0.4
MAX_OVERLAP_BEATS = 256.0
ARCHIVE_ROOT = "raveform/"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def quantize_duration_beats(
    overlap_beats: float,
    buckets: tuple[int, ...] = DURATION_BUCKETS_BEATS,
) -> int:
    """Map observed overlap to the nearest supported 32-beat product duration."""

    if not np.isfinite(overlap_beats) or overlap_beats <= 0.0:
        raise ValueError("overlap_beats must be finite and positive")
    if not buckets or any(value <= 0 for value in buckets):
        raise ValueError("duration buckets must be positive")
    return min(buckets, key=lambda value: (abs(value - overlap_beats), value))


def _section_at(structure: dict[str, object] | None, time_sec: float) -> str | None:
    if not structure or not np.isfinite(time_sec):
        return None
    aliases = {"altintro": "alt-intro", "altoutro": "alt-outro"}
    for section in structure.get("sections", []):
        if float(section["start"]) <= time_sec < float(section["end"]):
            label = normalize_context_label(str(section["name"]))
            return aliases.get(label, label)
    return None


def _track_id_from_beat_member(member: str) -> str:
    filename = member.rsplit("/", 1)[-1]
    return filename.removesuffix(".beat.json")


def load_raveform_observations(
    archive_path: str | Path,
) -> tuple[tuple[TransitionObservation, ...], dict[str, object]]:
    """Load the public archive without downloading audio or mutating engine state."""

    path = Path(archive_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Raveform archive is not a file: {path}")

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        beat_track_ids = {
            _track_id_from_beat_member(name)
            for name in names
            if name.startswith(f"{ARCHIVE_ROOT}beats/tracks/")
            and name.endswith(".beat.json")
        }
        mixes = [
            json.loads(line)
            for line in archive.read(f"{ARCHIVE_ROOT}mixes.jsonl").splitlines()
            if line.strip()
        ]
        structures_payload = json.loads(
            archive.read(f"{ARCHIVE_ROOT}structures/segments.json")
        )
        structures = {str(item["id"]): item for item in structures_payload}
        mix_by_id = {str(mix["id"]): mix for mix in mixes}

        plays_by_mix: dict[str, list[dict[str, object]]] = defaultdict(list)
        raw_alignments = 0
        qualified_alignments = 0
        alignment_members = sorted(
            name
            for name in names
            if name.startswith(f"{ARCHIVE_ROOT}alignments/")
            and name.endswith(".align.jsonl")
        )
        for member in alignment_members:
            for raw_line in archive.open(member):
                if not raw_line.strip():
                    continue
                raw_alignments += 1
                play = json.loads(raw_line)
                if float(play["match_rate"]) <= MATCH_RATE_MIN:
                    continue
                if str(play["track_id"]) not in beat_track_ids:
                    continue
                qualified_alignments += 1
                plays_by_mix[str(play["mix_id"])].append(play)

    adjacent_pairs = 0
    observations: list[TransitionObservation] = []
    for mix_id, mix in mix_by_id.items():
        tracklist = [entry.get("id") for entry in mix["tracklist"]]
        plays_by_track: dict[str, list[dict[str, object]]] = defaultdict(list)
        for play in plays_by_mix.get(mix_id, []):
            plays_by_track[str(play["track_id"])].append(play)
        for plays in plays_by_track.values():
            plays.sort(
                key=lambda item: (
                    float(item["mixin_beat_mix"]),
                    float(item["mixout_beat_mix"]),
                )
            )

        aligned_tracklist: list[dict[str, object] | None] = []
        for track_id in tracklist:
            candidates = plays_by_track.get(str(track_id), []) if track_id else []
            aligned_tracklist.append(candidates.pop(0) if candidates else None)

        genres = tuple(
            dict.fromkeys(normalize_context_label(str(value)) for value in mix.get("genres", []))
        )
        for position, (previous, following) in enumerate(
            zip(aligned_tracklist, aligned_tracklist[1:], strict=False)
        ):
            if previous is None or following is None:
                continue
            adjacent_pairs += 1
            overlap = float(previous["mixout_beat_mix"]) - float(following["mixin_beat_mix"])
            if not 0.0 < overlap <= MAX_OVERLAP_BEATS:
                continue
            previous_track_id = str(previous["track_id"])
            next_track_id = str(following["track_id"])
            observations.append(TransitionObservation(
                mix_id=mix_id,
                previous_track_id=previous_track_id,
                next_track_id=next_track_id,
                overlap_beats=overlap,
                duration_bucket_beats=quantize_duration_beats(overlap),
                tracklist_position=position,
                genres=genres,
                outgoing_section=_section_at(
                    structures.get(previous_track_id),
                    float(previous["mixout_time_track"]),
                ),
                incoming_section=_section_at(
                    structures.get(next_track_id),
                    float(following["mixin_time_track"]),
                ),
                previous_match_rate=float(previous["match_rate"]),
                next_match_rate=float(following["match_rate"]),
            ))

    overlap_values = np.asarray([item.overlap_beats for item in observations], dtype=np.float64)
    target_counts = Counter(item.duration_bucket_beats for item in observations)
    structured_count = sum(item.section_pair is not None for item in observations)
    genre_count = sum(bool(item.genres) for item in observations)
    primary_keys = Counter((item.mix_id, item.tracklist_position) for item in observations)
    duplicate_primary_rows = sum(count - 1 for count in primary_keys.values() if count > 1)
    rows_per_mix = Counter(item.mix_id for item in observations)
    match_rates = np.asarray([
        rate
        for item in observations
        for rate in (item.previous_match_rate, item.next_match_rate)
    ])
    audit = {
        "archive_path": str(path),
        "archive_sha256": _sha256(path),
        "source": "taejunkim/raveform public archive",
        "filters": {
            "match_rate": f"> {MATCH_RATE_MIN}",
            "pairing": "strict adjacent identified tracklist entries; missing rows are not skipped",
            "positive_overlap_beats": f"0 < overlap <= {MAX_OVERLAP_BEATS}",
            "duration_quantization": "nearest supported 32-beat bucket; lower bucket wins ties",
        },
        "inventory": {
            "archive_members": len(names),
            "mixes": len(mixes),
            "track_beat_files": len(beat_track_ids),
            "alignment_files": len(alignment_members),
            "raw_alignments": raw_alignments,
            "qualified_alignments": qualified_alignments,
            "qualified_adjacent_pairs": adjacent_pairs,
            "positive_overlap_observations": len(observations),
            "genre_context_observations": genre_count,
            "section_pair_observations": structured_count,
        },
        "target_bucket_counts": {str(key): target_counts[key] for key in sorted(target_counts)},
        "quality": {
            "grain": "one qualified positive-overlap transition per mix tracklist position",
            "duplicate_primary_rows": duplicate_primary_rows,
            "same_track_on_both_sides": sum(
                item.previous_track_id == item.next_track_id for item in observations
            ),
            "genre_context_coverage": round(genre_count / len(observations), 8),
            "section_pair_coverage": round(structured_count / len(observations), 8),
            "distinct_genres": len({genre for item in observations for genre in item.genres}),
            "distinct_section_pairs": len(
                {item.section_pair for item in observations if item.section_pair}
            ),
            "match_rate_min": round(float(match_rates.min()), 8),
            "match_rate_max": round(float(match_rates.max()), 8),
            "transitions_per_mix_quantiles": {
                str(percentile): round(float(value), 3)
                for percentile, value in zip(
                    (0, 25, 50, 75, 100),
                    np.percentile(tuple(rows_per_mix.values()), (0, 25, 50, 75, 100)),
                    strict=True,
                )
            },
        },
        "overlap_quantiles_beats": {
            str(percentile): round(float(value), 3)
            for percentile, value in zip(
                (10, 25, 50, 75, 90),
                np.percentile(overlap_values, (10, 25, 50, 75, 90)),
                strict=True,
            )
        },
    }
    return tuple(observations), audit

"""Data contracts for the offline DJ-mix validation add-on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class BeatFeatureSequence:
    """Beat-synchronous feature blocks for one local audio source.

    Every feature block has shape ``(dimensions, beat_intervals)``. The time at
    index ``i`` is the start of feature column ``i``.
    """

    beat_times_sec: tuple[float, ...]
    blocks: Mapping[str, np.ndarray]
    beatgrid_reliable: bool | None = None
    beatgrid_quality: float | None = None
    warnings: tuple[str, ...] = ()

    @property
    def beat_count(self) -> int:
        if not self.blocks:
            return 0
        return int(next(iter(self.blocks.values())).shape[1])


@dataclass(frozen=True)
class AlignmentResult:
    """Best mix-to-track alignment across the evaluated chroma shifts."""

    feature_names: tuple[str, ...]
    normalization: str
    key_invariant: bool
    key_shift_semitones: int
    normalized_cost: float
    shift_costs: tuple[float, ...]
    match_rate: float
    match_threshold: float
    matched: bool
    # Forward path points are ``(track_beat_index, mix_beat_index)``.
    path: tuple[tuple[int, int], ...]
    source_basis: tuple[str, ...] = (
        "DLASOT-13",
        "mir-aidj/djmix-analysis@a2ae903",
    )

    def as_dict(self, *, include_path: bool = False) -> dict[str, object]:
        result: dict[str, object] = {
            "feature_names": list(self.feature_names),
            "normalization": self.normalization,
            "key_invariant": self.key_invariant,
            "key_shift_semitones": self.key_shift_semitones,
            "normalized_cost": self.normalized_cost,
            "shift_costs": list(self.shift_costs),
            "match_rate": self.match_rate,
            "match_threshold": self.match_threshold,
            "matched": self.matched,
            "path_length": len(self.path),
            "source_basis": list(self.source_basis),
        }
        if include_path:
            result["path"] = [list(point) for point in self.path]
        return result


@dataclass(frozen=True)
class CueCandidate:
    """Entry/exit evidence from diagonal runs at one phrase tier."""

    tier_beats: int
    mix_cue_in_beat: int
    mix_cue_out_beat: int
    track_cue_in_beat: int
    track_cue_out_beat: int
    mix_cue_in_sec: float | None = None
    mix_cue_out_sec: float | None = None
    track_cue_in_sec: float | None = None
    track_cue_out_sec: float | None = None

    def as_dict(self) -> dict[str, int | float | None]:
        return {
            "tier_beats": self.tier_beats,
            "mix_cue_in_beat": self.mix_cue_in_beat,
            "mix_cue_out_beat": self.mix_cue_out_beat,
            "track_cue_in_beat": self.track_cue_in_beat,
            "track_cue_out_beat": self.track_cue_out_beat,
            "mix_cue_in_sec": self.mix_cue_in_sec,
            "mix_cue_out_sec": self.mix_cue_out_sec,
            "track_cue_in_sec": self.track_cue_in_sec,
            "track_cue_out_sec": self.track_cue_out_sec,
        }

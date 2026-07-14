"""Data contracts for the offline DJ-mix validation add-on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


M11_FORMULA_VERSION = "m11-dlasot13-v1"
M11_CODE_VERSION = "dancelab-djmix-validation-v2"
M11_SOURCE_BASIS = (
    "DLASOT-13",
    "mir-aidj/djmix-analysis@a2ae903",
)


@dataclass(frozen=True)
class AudioIdentity:
    """Immutable file identity used to prevent track/title/audio cross-linking."""

    source_id: str
    display_name: str
    resolved_path: str
    byte_size: int
    sha256: str
    fingerprint_algorithm: str = "sha256-file-v1"

    def as_dict(self) -> dict[str, str | int]:
        return {
            "source_id": self.source_id,
            "display_name": self.display_name,
            "resolved_path": self.resolved_path,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "fingerprint_algorithm": self.fingerprint_algorithm,
        }


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
    track_beat_count: int
    mix_beat_count: int
    track_path_coverage: float
    feature_coverage: float
    # Forward path points are ``(track_beat_index, mix_beat_index)``.
    path: tuple[tuple[int, int], ...]
    formula_version: str = M11_FORMULA_VERSION
    code_version: str = M11_CODE_VERSION
    source_basis: tuple[str, ...] = M11_SOURCE_BASIS

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
            "track_beat_count": self.track_beat_count,
            "mix_beat_count": self.mix_beat_count,
            "track_path_coverage": self.track_path_coverage,
            "feature_coverage": self.feature_coverage,
            "path_length": len(self.path),
            "track_start_beat": self.path[0][0] if self.path else None,
            "track_end_beat": self.path[-1][0] if self.path else None,
            "mix_start_beat": self.path[0][1] if self.path else None,
            "mix_end_beat": self.path[-1][1] if self.path else None,
            "formula_version": self.formula_version,
            "code_version": self.code_version,
            "source_basis": list(self.source_basis),
        }
        if include_path:
            result["path"] = [list(point) for point in self.path]
        return result


@dataclass(frozen=True)
class BoundaryConfidence:
    """Transparent, deliberately untuned evidence summary for one boundary."""

    score: float
    components: tuple[tuple[str, float], ...]
    weights: tuple[tuple[str, float], ...]
    complete: bool
    calibrated: bool = False
    formula_version: str = "m11-cue-confidence-equal-v1-untuned"
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "components": dict(self.components),
            "weights": dict(self.weights),
            "complete": self.complete,
            "calibrated": self.calibrated,
            "formula_version": self.formula_version,
            "warnings": list(self.warnings),
        }


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
    cue_in_run_beats: int | None = None
    cue_out_run_beats: int | None = None
    cue_in_confidence: BoundaryConfidence | None = None
    cue_out_confidence: BoundaryConfidence | None = None
    formula_version: str = M11_FORMULA_VERSION
    code_version: str = M11_CODE_VERSION

    def as_dict(self) -> dict[str, object]:
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
            "cue_in_run_beats": self.cue_in_run_beats,
            "cue_out_run_beats": self.cue_out_run_beats,
            "cue_in_confidence": (
                self.cue_in_confidence.as_dict() if self.cue_in_confidence else None
            ),
            "cue_out_confidence": (
                self.cue_out_confidence.as_dict() if self.cue_out_confidence else None
            ),
            "formula_version": self.formula_version,
            "code_version": self.code_version,
        }


@dataclass(frozen=True)
class TransitionEvidence:
    """Paired cue-out/cue-in evidence for one performed transition region."""

    transition_id: str
    mix_source_id: str
    previous_source_id: str
    next_source_id: str
    tier_beats: int
    mix_cue_out_beat: int
    mix_cue_in_beat: int
    mix_cue_mid_beat: int
    transition_length_beats: int
    mix_cue_out_sec: float | None
    mix_cue_in_sec: float | None
    mix_cue_mid_sec: float | None
    transition_length_sec: float | None
    confidence: float | None
    valid: bool
    warnings: tuple[str, ...] = ()
    formula_version: str = M11_FORMULA_VERSION
    code_version: str = M11_CODE_VERSION
    source_basis: tuple[str, ...] = M11_SOURCE_BASIS

    def as_dict(self) -> dict[str, object]:
        return {
            "transition_id": self.transition_id,
            "mix_source_id": self.mix_source_id,
            "previous_source_id": self.previous_source_id,
            "next_source_id": self.next_source_id,
            "tier_beats": self.tier_beats,
            "mix_cue_out_beat": self.mix_cue_out_beat,
            "mix_cue_in_beat": self.mix_cue_in_beat,
            "mix_cue_mid_beat": self.mix_cue_mid_beat,
            "transition_length_beats": self.transition_length_beats,
            "mix_cue_out_sec": self.mix_cue_out_sec,
            "mix_cue_in_sec": self.mix_cue_in_sec,
            "mix_cue_mid_sec": self.mix_cue_mid_sec,
            "transition_length_sec": self.transition_length_sec,
            "confidence": self.confidence,
            "valid": self.valid,
            "warnings": list(self.warnings),
            "formula_version": self.formula_version,
            "code_version": self.code_version,
            "source_basis": list(self.source_basis),
        }

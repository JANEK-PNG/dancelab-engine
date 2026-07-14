"""Pair adjacent M11 alignments into performed-transition evidence."""

from __future__ import annotations

import hashlib
from typing import Iterable

from dancelab.validation.djmix.models import (
    AlignmentResult,
    AudioIdentity,
    CueCandidate,
    TransitionEvidence,
)


def _transition_id(
    mix_source_id: str,
    previous_source_id: str,
    next_source_id: str,
    tier_beats: int,
) -> str:
    payload = "\0".join((mix_source_id, previous_source_id, next_source_id, str(tier_beats)))
    return "m11:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def assemble_transition_evidence(
    *,
    mix: AudioIdentity,
    previous_track: AudioIdentity,
    next_track: AudioIdentity,
    previous_alignment: AlignmentResult,
    next_alignment: AlignmentResult,
    previous_cues: Iterable[CueCandidate],
    next_cues: Iterable[CueCandidate],
) -> tuple[TransitionEvidence, ...]:
    """Combine previous cue-out and next cue-in at every shared phrase tier."""

    if previous_track.source_id == next_track.source_id:
        raise ValueError("adjacent transition tracks must have different audio fingerprints")

    previous_by_tier = {candidate.tier_beats: candidate for candidate in previous_cues}
    next_by_tier = {candidate.tier_beats: candidate for candidate in next_cues}
    common_tiers = sorted(set(previous_by_tier) & set(next_by_tier), reverse=True)
    evidence: list[TransitionEvidence] = []
    for tier in common_tiers:
        previous = previous_by_tier[tier]
        following = next_by_tier[tier]
        cue_out_beat = previous.mix_cue_out_beat
        cue_in_beat = following.mix_cue_in_beat
        length_beats = cue_in_beat - cue_out_beat
        cue_mid_beat = cue_out_beat + length_beats // 2

        cue_out_sec = previous.mix_cue_out_sec
        cue_in_sec = following.mix_cue_in_sec
        if cue_out_sec is not None and cue_in_sec is not None:
            length_sec = cue_in_sec - cue_out_sec
            cue_mid_sec = cue_out_sec + length_sec / 2.0
        else:
            length_sec = None
            cue_mid_sec = None

        warnings: list[str] = []
        if not previous_alignment.matched:
            warnings.append("previous_alignment_below_match_threshold")
        if not next_alignment.matched:
            warnings.append("next_alignment_below_match_threshold")
        if length_beats < 0:
            warnings.append("cue_order_reversed")
        if length_sec is not None and length_sec < 0.0:
            warnings.append("cue_time_order_reversed")

        previous_confidence = previous.cue_out_confidence
        next_confidence = following.cue_in_confidence
        if previous_confidence is None or next_confidence is None:
            confidence = None
            warnings.append("unscored_boundary_confidence")
        else:
            # A transition is no stronger than its weakest boundary.
            confidence = round(min(previous_confidence.score, next_confidence.score), 8)
            if not previous_confidence.complete or not next_confidence.complete:
                warnings.append("incomplete_confidence_inputs")

        valid = (
            previous_alignment.matched
            and next_alignment.matched
            and length_beats >= 0
            and (length_sec is None or length_sec >= 0.0)
        )
        evidence.append(TransitionEvidence(
            transition_id=_transition_id(
                mix.source_id,
                previous_track.source_id,
                next_track.source_id,
                tier,
            ),
            mix_source_id=mix.source_id,
            previous_source_id=previous_track.source_id,
            next_source_id=next_track.source_id,
            tier_beats=tier,
            mix_cue_out_beat=cue_out_beat,
            mix_cue_in_beat=cue_in_beat,
            mix_cue_mid_beat=cue_mid_beat,
            transition_length_beats=length_beats,
            mix_cue_out_sec=cue_out_sec,
            mix_cue_in_sec=cue_in_sec,
            mix_cue_mid_sec=cue_mid_sec,
            transition_length_sec=length_sec,
            confidence=confidence,
            valid=valid,
            warnings=tuple(warnings),
        ))
    return tuple(evidence)

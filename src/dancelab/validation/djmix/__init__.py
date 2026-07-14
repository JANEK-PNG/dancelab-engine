"""Offline DJ-mix validation based on mix-to-track subsequence alignment.

This package is a measurement add-on. It consumes local audio and emits
validation results; it does not alter engine analyses, rankings, BPM values, or
Rekordbox exports.
"""

from dancelab.validation.djmix.alignment import align_feature_sequences, diagonal_match_rate
from dancelab.validation.djmix.cues import extract_cue_candidates
from dancelab.validation.djmix.features import (
    combine_feature_blocks,
    extract_beat_synchronous_features,
)
from dancelab.validation.djmix.models import (
    AlignmentResult,
    BeatFeatureSequence,
    CueCandidate,
)

__all__ = [
    "AlignmentResult",
    "BeatFeatureSequence",
    "CueCandidate",
    "align_feature_sequences",
    "combine_feature_blocks",
    "diagonal_match_rate",
    "extract_beat_synchronous_features",
    "extract_cue_candidates",
]

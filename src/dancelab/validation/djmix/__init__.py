"""Offline DJ-mix validation based on mix-to-track subsequence alignment.

This package is a measurement add-on. It consumes local audio and emits
validation results; it does not alter engine analyses, rankings, BPM values, or
Rekordbox exports.
"""

from dancelab.validation.djmix.alignment import align_feature_sequences, diagonal_match_rate
from dancelab.validation.djmix.confidence import (
    assess_boundary_confidence,
    score_cue_candidates,
)
from dancelab.validation.djmix.cues import extract_cue_candidates
from dancelab.validation.djmix.evaluation import evaluate_boundary_predictions
from dancelab.validation.djmix.features import (
    combine_feature_blocks,
    extract_beat_synchronous_features,
)
from dancelab.validation.djmix.identity import identify_audio_file
from dancelab.validation.djmix.models import (
    AlignmentResult,
    AudioIdentity,
    BeatFeatureSequence,
    BoundaryConfidence,
    CueCandidate,
    TransitionEvidence,
)
from dancelab.validation.djmix.transitions import assemble_transition_evidence

__all__ = [
    "AlignmentResult",
    "AudioIdentity",
    "BeatFeatureSequence",
    "BoundaryConfidence",
    "CueCandidate",
    "TransitionEvidence",
    "align_feature_sequences",
    "assemble_transition_evidence",
    "assess_boundary_confidence",
    "combine_feature_blocks",
    "diagonal_match_rate",
    "evaluate_boundary_predictions",
    "extract_beat_synchronous_features",
    "extract_cue_candidates",
    "identify_audio_file",
    "score_cue_candidates",
]

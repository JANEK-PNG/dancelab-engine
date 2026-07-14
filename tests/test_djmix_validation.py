from __future__ import annotations

import numpy as np
import pytest

from dancelab.core.audio_types import AudioSignal
from dancelab.validation.djmix.alignment import align_feature_sequences, diagonal_match_rate
from dancelab.validation.djmix.cues import extract_cue_candidates
from dancelab.validation.djmix.features import (
    combine_feature_blocks,
    extract_beat_synchronous_features,
)
from dancelab.validation.djmix.models import BeatFeatureSequence


def _sequence(*, chroma: np.ndarray | None = None, mfcc: np.ndarray | None = None):
    blocks = {}
    if chroma is not None:
        blocks["chroma"] = np.asarray(chroma, dtype=np.float32)
    if mfcc is not None:
        blocks["mfcc"] = np.asarray(mfcc, dtype=np.float32)
    beat_count = next(iter(blocks.values())).shape[1]
    return BeatFeatureSequence(
        beat_times_sec=tuple(float(index) for index in range(beat_count)),
        blocks=blocks,
    )


def test_diagonal_match_rate_is_explicit_and_safe():
    assert diagonal_match_rate(np.array([[0, 2], [1, 3], [2, 4], [3, 5]])) == 1.0
    assert diagonal_match_rate(np.array([[0, 2]])) == 0.0
    assert diagonal_match_rate(np.array([[0, 2], [1, 3], [1, 4], [2, 5]])) == pytest.approx(2 / 3)


def test_key_invariant_subsequence_alignment_recovers_shift_and_offset():
    pytest.importorskip("librosa")
    beat_count = 24
    track_chroma = np.zeros((12, beat_count), dtype=np.float32)
    track_chroma[np.arange(beat_count) % 12, np.arange(beat_count)] = 1.0
    expected_shift = 3
    shifted = np.roll(track_chroma, expected_shift, axis=0)
    mix_chroma = np.concatenate([
        np.full((12, 7), 0.05, dtype=np.float32),
        shifted,
        np.full((12, 5), 0.02, dtype=np.float32),
    ], axis=1)

    result = align_feature_sequences(
        _sequence(chroma=track_chroma),
        _sequence(chroma=mix_chroma),
        feature_names=("chroma",),
        key_invariant=True,
    )

    assert result.key_shift_semitones == expected_shift
    assert result.match_rate == 1.0
    assert result.path[0] == (0, 7)
    assert result.path[-1] == (beat_count - 1, 7 + beat_count - 1)
    assert result.matched


def test_cue_candidates_return_32_16_8_tiers_without_falling_below_eight():
    path = np.column_stack([np.arange(41), np.arange(41) + 10])
    mix_times = tuple(index * 0.5 for index in range(60))
    track_times = tuple(index * 0.5 for index in range(50))

    cues = extract_cue_candidates(
        path,
        mix_beat_times_sec=mix_times,
        track_beat_times_sec=track_times,
    )

    assert [candidate.tier_beats for candidate in cues] == [32, 16, 8]
    assert cues[0].mix_cue_in_beat == 10
    assert cues[0].mix_cue_out_beat == 50
    assert cues[0].track_cue_in_beat == 0
    assert cues[0].track_cue_out_beat == 40
    assert cues[0].mix_cue_in_sec == 5.0


def test_cue_candidates_omit_tiers_not_supported_by_path():
    first = np.column_stack([np.arange(11), np.arange(11)])
    # Break the path, then add another ten-beat diagonal run.
    second = np.column_stack([np.arange(10, 21), np.arange(11, 22)])
    path = np.vstack([first, second[1:]])

    cues = extract_cue_candidates(path)

    assert [candidate.tier_beats for candidate in cues] == [8]


def test_feature_combination_preserves_chroma_location_and_zero_variance_guard():
    sequence = _sequence(
        mfcc=np.vstack([np.arange(6), np.arange(6) * 2]),
        chroma=np.ones((12, 6), dtype=np.float32),
    )
    combined = combine_feature_blocks(
        sequence,
        feature_names=("mfcc", "chroma"),
        normalization="per_dimension",
    )

    assert combined.matrix.shape == (14, 6)
    assert combined.chroma_slice == slice(2, 14)
    assert np.all(combined.matrix[combined.chroma_slice] == 0.0)
    assert np.all(np.isfinite(combined.matrix))


def test_audio_feature_extraction_aggregates_between_supplied_beats():
    pytest.importorskip("librosa")
    sample_rate = 22050
    duration = 4.0
    time = np.arange(int(sample_rate * duration)) / sample_rate
    samples = (0.2 * np.sin(2 * np.pi * 220.0 * time)).astype(np.float32)
    signal = AudioSignal(samples=samples, sample_rate=sample_rate)

    sequence = extract_beat_synchronous_features(
        signal,
        beat_times_sec=(0.0, 1.0, 2.0, 3.0, 4.0),
        feature_names=("chroma", "mfcc"),
    )

    assert sequence.beat_count == 4
    assert sequence.blocks["chroma"].shape == (12, 4)
    assert sequence.blocks["mfcc"].shape == (12, 4)
    assert sequence.beat_times_sec == (0.0, 1.0, 2.0, 3.0)

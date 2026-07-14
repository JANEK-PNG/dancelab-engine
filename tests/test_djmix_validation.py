from __future__ import annotations

import numpy as np
import pytest

from dancelab.core.audio_types import AudioSignal
from dancelab.validation.djmix.alignment import align_feature_sequences, diagonal_match_rate
from dancelab.validation.djmix.confidence import score_cue_candidates
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
)
from dancelab.validation.djmix.transitions import assemble_transition_evidence


def _sequence(
    *,
    chroma: np.ndarray | None = None,
    mfcc: np.ndarray | None = None,
    beatgrid_reliable: bool | None = None,
    beatgrid_quality: float | None = None,
):
    blocks = {}
    if chroma is not None:
        blocks["chroma"] = np.asarray(chroma, dtype=np.float32)
    if mfcc is not None:
        blocks["mfcc"] = np.asarray(mfcc, dtype=np.float32)
    beat_count = next(iter(blocks.values())).shape[1]
    return BeatFeatureSequence(
        beat_times_sec=tuple(float(index) for index in range(beat_count)),
        blocks=blocks,
        beatgrid_reliable=beatgrid_reliable,
        beatgrid_quality=beatgrid_quality,
    )


def _alignment(path: np.ndarray, *, matched: bool = True) -> AlignmentResult:
    points = np.asarray(path, dtype=np.int64)
    return AlignmentResult(
        feature_names=("chroma", "mfcc"),
        normalization="source_global",
        key_invariant=True,
        key_shift_semitones=0,
        normalized_cost=0.25,
        shift_costs=(0.25,),
        match_rate=0.9 if matched else 0.2,
        match_threshold=0.4,
        matched=matched,
        track_beat_count=int(points[:, 0].max()) + 1,
        mix_beat_count=int(points[:, 1].max()) + 1,
        track_path_coverage=1.0,
        feature_coverage=1.0,
        path=tuple((int(track), int(mix_)) for track, mix_ in points),
    )


def _identity(name: str, marker: str) -> AudioIdentity:
    digest = marker * 64
    return AudioIdentity(
        source_id=f"sha256:{digest}",
        display_name=name,
        resolved_path=f"/audio/{name}.wav",
        byte_size=1024,
        sha256=digest,
    )


def test_diagonal_match_rate_is_explicit_and_safe():
    assert diagonal_match_rate(np.array([[0, 2], [1, 3], [2, 4], [3, 5]])) == 1.0
    assert diagonal_match_rate(np.array([[0, 2]])) == 0.0
    assert diagonal_match_rate(np.array([[0, 2], [1, 3], [1, 4], [2, 5]])) == pytest.approx(2 / 3)


def test_diagonal_match_rate_counts_duplicate_points_as_non_diagonal_steps():
    path = np.array([[0, 2], [1, 3], [1, 3], [2, 4]])

    assert diagonal_match_rate(path) == pytest.approx(2 / 3)


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


def test_audio_pipeline_recovers_tempo_changed_key_shifted_subsequence():
    pytest.importorskip("librosa")
    sample_rate = 22050
    track_period = 0.5
    mix_period = 0.4
    pitch_classes = np.array([0, 7, 2, 9, 4, 11, 5, 1, 8, 3, 10, 6] * 2)

    def synth(sequence: np.ndarray, period: float, *, shift: int = 0) -> np.ndarray:
        sample_count = int(round(period * sample_rate))
        time = np.arange(sample_count) / sample_rate
        edge = np.arange(sample_count)
        envelope = np.minimum(1.0, np.minimum(edge / 180.0, edge[::-1] / 180.0))
        chunks = []
        for pitch_class in sequence:
            frequency = 261.625565 * 2 ** (((int(pitch_class) + shift) % 12) / 12)
            chunks.append(
                (0.35 * np.sin(2 * np.pi * frequency * time) * envelope).astype(np.float32)
            )
        return np.concatenate(chunks)

    track_audio = synth(pitch_classes, track_period)
    prefix = np.array([1, 1, 6, 6, 10, 10])
    suffix = np.array([3, 3, 8, 8])
    mix_audio = np.concatenate([
        synth(prefix, mix_period),
        synth(pitch_classes, mix_period, shift=3),
        synth(suffix, mix_period),
    ])
    track = extract_beat_synchronous_features(
        AudioSignal(track_audio, sample_rate),
        np.arange(len(pitch_classes) + 1) * track_period,
        feature_names=("chroma",),
    )
    mix = extract_beat_synchronous_features(
        AudioSignal(mix_audio, sample_rate),
        np.arange(len(prefix) + len(pitch_classes) + len(suffix) + 1) * mix_period,
        feature_names=("chroma",),
    )

    result = align_feature_sequences(
        track,
        mix,
        feature_names=("chroma",),
        key_invariant=True,
    )

    assert result.key_shift_semitones == 3
    assert result.path[0] == (0, len(prefix))
    assert result.path[-1] == (len(pitch_classes) - 1, len(prefix) + len(pitch_classes) - 1)
    assert result.match_rate == 1.0
    assert result.track_path_coverage == 1.0


def test_unrelated_flat_feature_fixture_fails_match_rate_gate():
    pytest.importorskip("librosa")
    beat_count = 32
    track_chroma = np.zeros((12, beat_count), dtype=np.float32)
    track_chroma[np.arange(beat_count) % 12, np.arange(beat_count)] = 1.0
    unrelated_mix = np.ones((12, 48), dtype=np.float32)

    result = align_feature_sequences(
        _sequence(chroma=track_chroma),
        _sequence(chroma=unrelated_mix),
        feature_names=("chroma",),
        key_invariant=True,
    )

    assert result.match_rate == 0.0
    assert not result.matched


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
    assert cues[0].cue_in_run_beats == 40
    assert cues[0].cue_out_run_beats == 40


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


def test_audio_identity_is_content_backed_and_path_independent(tmp_path):
    first = tmp_path / "first.wav"
    second = tmp_path / "renamed.wav"
    first.write_bytes(b"same-audio-bytes")
    second.write_bytes(b"same-audio-bytes")

    first_identity = identify_audio_file(first, chunk_bytes=3)
    second_identity = identify_audio_file(second, chunk_bytes=4)

    assert first_identity.source_id == second_identity.source_id
    assert first_identity.sha256 == second_identity.sha256
    assert first_identity.display_name != second_identity.display_name
    assert first_identity.byte_size == len(b"same-audio-bytes")


def test_cue_confidence_is_visible_untuned_and_missing_inputs_do_not_improve_it():
    path = np.column_stack([np.arange(41), np.arange(41) + 10])
    alignment = _alignment(path)
    complete_track = _sequence(
        chroma=np.ones((12, 41)),
        beatgrid_reliable=True,
        beatgrid_quality=0.8,
    )
    complete_mix = _sequence(
        chroma=np.ones((12, 60)),
        beatgrid_reliable=True,
        beatgrid_quality=0.9,
    )
    missing_quality_track = _sequence(chroma=np.ones((12, 41)))
    candidate = extract_cue_candidates(path, tiers=(32,))[0]

    complete = score_cue_candidates(
        (candidate,),
        alignment,
        track=complete_track,
        mix=complete_mix,
    )[0].cue_in_confidence
    incomplete = score_cue_candidates(
        (candidate,),
        alignment,
        track=missing_quality_track,
        mix=complete_mix,
    )[0].cue_in_confidence

    assert complete is not None and incomplete is not None
    assert not complete.calibrated
    assert complete.formula_version.endswith("untuned")
    assert complete.complete
    assert not incomplete.complete
    assert incomplete.score < complete.score
    assert "missing_beatgrid_quality" in incomplete.warnings


def test_adjacent_alignments_form_a_versioned_transition_region():
    previous_path = np.column_stack([np.arange(33), np.arange(33)])
    next_path = np.column_stack([np.arange(33), np.arange(33) + 40])
    previous_alignment = _alignment(previous_path)
    next_alignment = _alignment(next_path)
    previous_track = _sequence(
        chroma=np.ones((12, 33)),
        beatgrid_reliable=True,
        beatgrid_quality=0.9,
    )
    next_track = _sequence(
        chroma=np.ones((12, 33)),
        beatgrid_reliable=True,
        beatgrid_quality=0.85,
    )
    mix = _sequence(
        chroma=np.ones((12, 73)),
        beatgrid_reliable=True,
        beatgrid_quality=0.95,
    )
    previous_cues = score_cue_candidates(
        extract_cue_candidates(previous_path, tiers=(32,)),
        previous_alignment,
        track=previous_track,
        mix=mix,
    )
    next_cues = score_cue_candidates(
        extract_cue_candidates(next_path, tiers=(32,)),
        next_alignment,
        track=next_track,
        mix=mix,
    )

    evidence = assemble_transition_evidence(
        mix=_identity("mix", "a"),
        previous_track=_identity("previous", "b"),
        next_track=_identity("next", "c"),
        previous_alignment=previous_alignment,
        next_alignment=next_alignment,
        previous_cues=previous_cues,
        next_cues=next_cues,
    )

    assert len(evidence) == 1
    transition = evidence[0]
    assert transition.valid
    assert transition.mix_cue_out_beat == 32
    assert transition.mix_cue_in_beat == 40
    assert transition.mix_cue_mid_beat == 36
    assert transition.transition_length_beats == 8
    assert transition.confidence is not None
    assert transition.transition_id.startswith("m11:")


def test_transition_identity_rejects_same_audio_on_both_sides():
    path = np.column_stack([np.arange(9), np.arange(9)])
    alignment = _alignment(path)
    identity = _identity("same", "d")

    with pytest.raises(ValueError, match="different audio fingerprints"):
        assemble_transition_evidence(
            mix=_identity("mix", "a"),
            previous_track=identity,
            next_track=identity,
            previous_alignment=alignment,
            next_alignment=alignment,
            previous_cues=extract_cue_candidates(path, tiers=(8,)),
            next_cues=extract_cue_candidates(path, tiers=(8,)),
        )


def test_boundary_evaluation_reports_coverage_and_both_hit_rate_denominators():
    result = evaluate_boundary_predictions(
        (10.0, None, 80.0),
        (12.0, 30.0, 70.0),
        tolerances_sec=(5.0, 15.0),
    )

    assert result.total == 3
    assert result.evaluated == 2
    assert result.coverage == pytest.approx(2 / 3)
    assert result.mean_absolute_error_sec == 6.0
    assert dict(result.hit_rate_evaluated) == {5.0: 0.5, 15.0: 1.0}
    assert dict(result.hit_rate_all) == pytest.approx({5.0: 1 / 3, 15.0: 2 / 3})

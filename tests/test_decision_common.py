"""Shared tempo primitives (AUD-M8): one octave-folding convention everywhere."""

import pytest

from dancelab.decision._common import (
    BPM_OCTAVE_FACTORS,
    bpm_octave_variants,
    min_relative_bpm_distance,
    nearest_bpm_variant,
    tempo_proximity_score,
)


def test_octave_factors_are_direct_double_half():
    assert BPM_OCTAVE_FACTORS == (1.0, 2.0, 0.5)
    assert bpm_octave_variants(128.0) == (128.0, 256.0, 64.0)


def test_nearest_variant_folds_half_and_double_time():
    # 70 vs 140 → half-time of 140 (70) is exact
    assert nearest_bpm_variant(70.0, 140.0) == pytest.approx(70.0)
    # 174 vs 87 → double-time of 87 (174) is exact
    assert nearest_bpm_variant(174.0, 87.0) == pytest.approx(174.0)
    assert nearest_bpm_variant(None, 120.0) is None
    assert nearest_bpm_variant(120.0, None) is None


def test_tempo_proximity_score_is_neutral_when_unknown_and_1_when_equal():
    assert tempo_proximity_score(None, 128.0) == 0.5
    assert tempo_proximity_score(128.0, None) == 0.5
    assert tempo_proximity_score(128.0, 128.0) == pytest.approx(1.0)
    # half-time counts as a match, not a mismatch
    assert tempo_proximity_score(128.0, 64.0) == pytest.approx(1.0)


def test_min_relative_distance_matches_score_denominator():
    # a 6% gap at tolerance 0.06 → distance/(2*0.06) = 0.5 → score 0.5
    dist = min_relative_bpm_distance(100.0, 106.0)
    assert dist == pytest.approx(0.06)
    assert tempo_proximity_score(100.0, 106.0, tolerance_pct=0.06) == pytest.approx(0.5)

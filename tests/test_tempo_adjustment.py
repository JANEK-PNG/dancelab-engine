"""Source-faithful M8-M10 preview tempo mathematics."""

import pytest

from dancelab.decision.tempo_adjustment import (
    M9_OCTAVE_EXPONENTS,
    build_balanced_tempo_plan,
    nearest_octave_candidate,
    octave_tempo_candidates,
    shared_target_tempo,
    tempo_discomfort,
)


def test_m8_discomfort_is_asymmetric_and_zero_at_native_rate():
    assert tempo_discomfort(1.0) == 0.0
    assert tempo_discomfort(1.1) == pytest.approx(0.0765)
    assert tempo_discomfort(0.9) == pytest.approx((1.0 / 0.9) - 1.0)
    with pytest.raises(ValueError):
        tempo_discomfort(0.0)


def test_m9_enumerates_full_family_but_preview_selector_stays_bounded():
    candidates = octave_tempo_candidates(100.0)
    assert tuple(candidate.octave_exponent for candidate in candidates) == M9_OCTAVE_EXPONENTS
    assert tuple(candidate.bpm for candidate in candidates) == (25.0, 50.0, 100.0, 200.0, 400.0)
    assert nearest_octave_candidate(174.0, 87.0).octave_exponent == 1
    assert nearest_octave_candidate(70.0, 140.0).octave_exponent == -1


def test_m10_numeric_reference_and_interval_guarantee():
    target = shared_target_tempo(120.0, 130.0)
    assert target == pytest.approx(125.554, abs=0.001)
    assert 120.0 <= target <= 130.0
    assert shared_target_tempo(128.0, 128.0) == 128.0


def test_balanced_plan_equalizes_source_model_discomfort():
    plan = build_balanced_tempo_plan(
        120.0,
        130.0,
        beatgrid_reliable_a=True,
        beatgrid_reliable_b=True,
        beatgrid_quality_a=0.91,
        beatgrid_quality_b=0.84,
    )
    assert plan is not None
    assert plan.rate_a == pytest.approx(plan.target_bpm / 120.0)
    assert plan.rate_b == pytest.approx(plan.target_bpm / 130.0)
    assert plan.discomfort_a == pytest.approx(plan.discomfort_b)
    assert plan.confidence == pytest.approx(0.84)
    assert plan.within_review_band is True
    assert plan.formula_ids == ("M8", "M9", "M10")
    assert plan.source_ids == ("DLASOT-12",)


def test_balanced_plan_is_symmetric_under_deck_swap():
    first = build_balanced_tempo_plan(
        120.0,
        130.0,
        beatgrid_reliable_a=True,
        beatgrid_reliable_b=True,
    )
    swapped = build_balanced_tempo_plan(
        130.0,
        120.0,
        beatgrid_reliable_a=True,
        beatgrid_reliable_b=True,
    )
    assert first is not None and swapped is not None
    assert first.target_bpm == pytest.approx(swapped.target_bpm)
    assert first.rate_a == pytest.approx(swapped.rate_b)
    assert first.rate_b == pytest.approx(swapped.rate_a)


def test_balanced_plan_respects_selected_half_time_relation():
    candidate_b = nearest_octave_candidate(88.0, 176.0)
    plan = build_balanced_tempo_plan(
        88.0,
        176.0,
        selected_b_bpm=candidate_b.bpm,
        octave_b=candidate_b.octave_exponent,
        beatgrid_reliable_a=True,
        beatgrid_reliable_b=True,
    )
    assert plan is not None
    assert plan.selected_b_bpm == 88.0
    assert plan.target_bpm == 88.0
    assert plan.rate_a == pytest.approx(1.0)
    assert plan.rate_b == pytest.approx(1.0)


def test_balanced_plan_refuses_unreliable_grid_and_flags_large_adjustment():
    assert build_balanced_tempo_plan(
        120.0,
        130.0,
        beatgrid_reliable_a=False,
        beatgrid_reliable_b=True,
    ) is None

    plan = build_balanced_tempo_plan(
        80.0,
        120.0,
        beatgrid_reliable_a=True,
        beatgrid_reliable_b=True,
        max_rate_delta=0.05,
    )
    assert plan is not None
    assert plan.within_review_band is False
    assert any("preview band" in warning for warning in plan.warnings)

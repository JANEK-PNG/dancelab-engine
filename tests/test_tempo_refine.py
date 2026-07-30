"""A tempo may only be pulled onto the musical grid when the beats agree."""

import numpy as np
import pytest

from dancelab.core.tempo_refine import refine_tempo


def beats_at(bpm: float, count: int = 240, jitter: float = 0.0, seed: int = 3):
    rng = np.random.default_rng(seed)
    grid = np.arange(count) * (60.0 / bpm)
    return grid + rng.normal(0.0, jitter, count) if jitter else grid


def test_a_clean_integer_tempo_is_recovered_exactly():
    got = refine_tempo(beats_at(136.0))
    assert got.snapped and got.bpm == pytest.approx(136.0)


def test_scatter_that_drags_the_free_fit_off_is_pulled_back():
    # the failure this exists for: a tracker's noise moved the estimate a tenth of
    # a BPM, which is half a second of slip across a long blend
    beats = beats_at(136.0, jitter=0.030)
    got = refine_tempo(beats)
    assert got.snapped
    assert got.bpm == pytest.approx(136.0)
    assert abs(got.free_bpm - 136.0) > 0.0


def test_a_record_that_is_not_on_a_round_tempo_keeps_its_own():
    got = refine_tempo(beats_at(133.4))
    assert not got.snapped
    assert got.bpm == pytest.approx(133.4, abs=0.01)


def test_half_bpm_tempos_are_musical_too():
    got = refine_tempo(beats_at(129.5))
    assert got.snapped and got.bpm == pytest.approx(129.5)


def test_a_far_away_round_number_cannot_capture_the_estimate():
    # a badly folded or half-time estimate must not be dragged onto a neighbour
    got = refine_tempo(beats_at(137.0), max_shift_bpm=0.1)
    assert got.bpm == pytest.approx(137.0, abs=0.01)


def test_too_few_beats_is_refused_rather_than_guessed():
    assert refine_tempo(beats_at(128.0, count=8)) is None


def test_the_free_fit_uses_least_squares_not_the_median_gap():
    # beat times rounded to an analysis frame: the median gap quantises to the
    # frame and lands on the wrong tempo, the fit across all beats does not
    frame = 0.0116
    beats = np.round(beats_at(136.0) / frame) * frame
    got = refine_tempo(beats)
    assert got.free_bpm == pytest.approx(136.0, abs=0.05)
    assert got.snapped

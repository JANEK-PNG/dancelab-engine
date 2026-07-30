"""A rigid grid must find the pulse, survive the noise, and admit when there is none."""

import numpy as np
import pytest

from dancelab.core.rigid_grid import fit_rigid_grid

SR = 22050


def click_track(bpm, seconds=60.0, sr=SR, jitter=0.0, offbeat=0.0,
                hats=0.0, seed=5, start=0.11):
    """A kick on every beat, optionally with hats, an offbeat, and timing noise."""
    rng = np.random.default_rng(seed)
    y = rng.normal(0.0, 0.002, int(seconds * sr))
    period = 60.0 / bpm

    def hit(at, amp, length, freq):
        i = int(at * sr)
        n = int(length * sr)
        if i < 0 or i + n > y.size:
            return
        t = np.arange(n) / sr
        y[i:i + n] += amp * np.sin(2 * np.pi * freq * t) * np.exp(-t / (length / 4))

    for k in range(int(seconds / period)):
        at = start + k * period + (rng.normal(0, jitter) if jitter else 0.0)
        hit(at, 1.0, 0.09, 55)
        if offbeat:
            hit(at + period / 2, offbeat, 0.05, 3000)
        if hats:
            for sub in (0.25, 0.5, 0.75):
                hit(at + period * sub, hats, 0.02, 8000)
    return y


def test_a_plain_four_four_pulse_is_found_exactly():
    got = fit_rigid_grid(click_track(128.0), SR)
    assert got.bpm == pytest.approx(128.0)


def test_the_phase_lands_on_the_kick_not_between_them():
    got = fit_rigid_grid(click_track(130.0, start=0.37), SR)
    period = 60.0 / 130.0
    offset = (got.first_beat_sec - 0.37) % period
    assert min(offset, period - offset) < 0.03


def test_half_tempo_is_not_preferred_when_it_looks_sharper():
    # the failure this guards: folding at half tempo piles the strong beats into one
    # narrower peak, and a sharpness score picks it — a 135 record read as 67.5
    got = fit_rigid_grid(click_track(135.0, offbeat=0.35), SR)
    assert got.bpm == pytest.approx(135.0)


def test_hats_on_every_sixteenth_do_not_double_the_tempo():
    got = fit_rigid_grid(click_track(128.0, hats=0.5), SR)
    assert got.bpm == pytest.approx(128.0)


def test_timing_noise_that_derails_a_tracker_leaves_the_grid_alone():
    # a tracker following beat to beat accumulates this into a wandering tempo;
    # a rigid fit averages it away
    got = fit_rigid_grid(click_track(136.0, jitter=0.012), SR)
    assert got.bpm == pytest.approx(136.0)


def test_music_with_no_steady_pulse_scores_low_rather_than_guessing():
    rng = np.random.default_rng(11)
    noise = rng.normal(0.0, 0.1, SR * 40)
    got = fit_rigid_grid(noise, SR)
    assert got is None or got.contrast < 2.0


def test_a_clip_too_short_to_judge_is_refused():
    assert fit_rigid_grid(click_track(128.0, seconds=4.0), SR) is None


def test_downbeats_are_every_fourth_beat():
    got = fit_rigid_grid(click_track(128.0), SR)
    bars = got.downbeats()
    assert bars[1] - bars[0] == pytest.approx(4 * 60.0 / 128.0)

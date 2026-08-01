"""A rigid grid must find the pulse, survive the noise, and admit when there is none."""

import numpy as np
import pytest

pytest.importorskip("librosa")  # onset extraction belongs to the [audio] profile

from dancelab.core.rigid_grid import (
    _onset_envelope,
    _settle_relatives,
    fit_rigid_grid,
)

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


def test_an_off_grid_tempo_is_not_quantised_to_a_half_bpm():
    # The coarse scan only offers whole and half BPM. Taking its winner as the
    # answer put every record on a 0.5 grid — a quarter of a BPM is 337 ms of walk
    # across a three-minute slot at 136, three times the quarter-beat where tight
    # becomes a stumble. A record that sits at 128.3 has to be able to say so.
    got = fit_rigid_grid(click_track(128.3, seconds=90.0), SR)
    assert not got.snapped_to_musical
    assert got.bpm == pytest.approx(128.3, abs=0.05)


def test_a_round_tempo_is_still_reported_exactly_round():
    # and the snap has to survive: a record made at 128 should come back at 128,
    # not at 127.99 because the fine scan found a hundredth more energy there
    got = fit_rigid_grid(click_track(128.0, seconds=90.0), SR)
    assert got.snapped_to_musical
    assert got.bpm == 128.0


def test_the_free_fit_is_reported_either_way():
    got = fit_rigid_grid(click_track(130.0, seconds=90.0), SR)
    assert got.free_bpm > 0
    assert abs(got.free_bpm - 130.0) < 0.75


def test_a_dotted_reading_is_demoted_when_the_kick_band_prefers_the_slower_grid():
    # Bicep's Glue fitted at 195 against Rekordbox's 130 and then fell out of a set
    # as "32 % away from the tempo" while sitting two percent from it. Captured
    # energy settles 2x on its own — half tempo can only catch half the beats — but
    # a 1.5x grid lands on every second real beat and stays sharp enough to win.
    env, times = _onset_envelope(click_track(130.0, seconds=90.0), SR, 128, True)
    assert _settle_relatives(195.0, env, times) == pytest.approx(130.0)


def test_a_record_really_at_the_faster_tempo_keeps_it():
    # the other half of the same rule, and the one that keeps it honest: demotion
    # must need the kick band to explain the slower grid distinctly better, not
    # merely as well. Measured across 184 records, the nearest false alarm reaches
    # 1.210 and the nearest true demotion 1.323.
    env, times = _onset_envelope(click_track(195.0, seconds=90.0), SR, 128, True)
    assert _settle_relatives(195.0, env, times) == pytest.approx(195.0)


def test_the_demotion_cannot_walk_a_record_below_the_searched_range():
    env, times = _onset_envelope(click_track(130.0, seconds=90.0), SR, 128, True)
    assert _settle_relatives(70.0, env, times) >= 60.0


def test_a_record_off_the_whole_bpm_grid_is_not_demoted_to_three_quarters():
    # The demotion has to be judged against the record's real tempo, not against the
    # coarse candidate. Daphni's Waiting So Long sits at 133.30; the coarse grid
    # offers 133.5, which smears across a whole record down to 1.202 where the truth
    # scores 3.496 — and 100.00 cleared the margin against the smear and took it.
    got = fit_rigid_grid(click_track(133.3, seconds=90.0), SR)
    assert got.bpm == pytest.approx(133.3, abs=0.05)

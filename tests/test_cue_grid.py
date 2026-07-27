"""Canonical cue grid: one snapping rule shared by every cue writer."""

from dancelab.core.models import BeatGrid
from dancelab.decision.cue_grid import snap_cue_start, usable_beat_grid


def _grid(**kw):
    base = dict(bpm=120.0, reliable=True, beat_times_sec=[300.0, 300.5, 301.0])
    base.update(kw)
    return BeatGrid(**base)


def test_unreliable_grid_is_never_snapped_to():
    """An unreliable beatgrid's beat times are noise — snapping to them invents precision."""
    bg = _grid(reliable=False)
    assert snap_cue_start(bg, 300.3) == 300.3  # position left untouched
    assert usable_beat_grid(bg) is None


def test_missing_grid_returns_position_unchanged():
    assert snap_cue_start(None, 300.3) == 300.3
    assert snap_cue_start(_grid(beat_times_sec=[]), 300.3) == 300.3


def test_reliable_grid_snaps_to_nearest_beat():
    assert snap_cue_start(_grid(), 300.3) == 300.5
    assert snap_cue_start(_grid(), 300.1) == 300.0


def test_verified_phase_snaps_to_phrase_boundary_not_just_nearest_beat():
    """With verified bar phase the cue lands on a countable phrase division."""
    beats = [i * 0.5 for i in range(65)]  # 120 BPM, 65 beats from 0.0
    bg = BeatGrid(bpm=120.0, reliable=True, beat_times_sec=beats,
                  downbeats_sec=[0.0, 2.0, 4.0], downbeat_phase_verified=True)
    # 3.4s = beat 6.8; nearest beat would be beat 7 (3.5s), but the phrase grid
    # pulls it to a countable boundary instead.
    snapped = snap_cue_start(bg, 3.4)
    beat_index = round(snapped / 0.5)
    assert beat_index % 2 == 0, f"expected a phrase boundary, got beat {beat_index}"

"""Pair-review helpers: beat sync, quantize, window pick — headless math."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from dancelab.core.config import load_config
from dancelab.core.models import AnalysisResult, BeatGrid, Track, TransitionWindow, WindowType
from dancelab.host.pair_review import Deck, beat_sync_rate, best_window, snap_to_grid
from dancelab.host.preview_timing import quantized_cue_and_start

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication


def test_beat_sync_rate_matches_master_tempo():
    # 126 master, 133 incoming → slow the incoming down
    assert beat_sync_rate(126.0, 133.0) == pytest.approx(126.0 / 133.0)
    # equal tempo → 1.0
    assert beat_sync_rate(128.0, 128.0) == pytest.approx(1.0)


def test_beat_sync_rate_is_half_double_time_aware():
    # 130 master, 65 read: half-time — sync at ~1.0, not 2.0
    assert beat_sync_rate(130.0, 65.0) == pytest.approx(1.0)
    # 87 read vs 174 master: double-time of 87 is 174 → rate ~1.0
    assert beat_sync_rate(174.0, 87.0) == pytest.approx(1.0)


def test_beat_sync_rate_honest_none_and_clamped():
    assert beat_sync_rate(None, 128.0) is None
    assert beat_sync_rate(128.0, None) is None
    assert beat_sync_rate(128.0, 0.0) is None
    # absurd mismatch clamps into the usable preview range
    assert 0.5 <= beat_sync_rate(60.0, 100.0) <= 2.0


def test_snap_to_grid_defaults_to_eight_beat_boundaries():
    beats = [index * 0.5 for index in range(33)]  # 120 BPM, 16 seconds
    downbeats = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0]
    assert snap_to_grid(0.61, beats, downbeats) == 0.0
    assert snap_to_grid(3.1, beats, downbeats) == 4.0
    assert snap_to_grid(6.2, beats, downbeats) == 8.0
    # nearest-beat mode still exists, but only when explicitly requested for diagnostics
    assert snap_to_grid(0.61, beats, downbeats, grid_beats=1) == 0.5
    # no grid → position unchanged, never invented
    assert snap_to_grid(3.3, [], []) == 3.3


def test_quantized_cue_and_start_stays_on_eight_beat_grid():
    beats = [index * 0.5 for index in range(81)]  # 40 seconds at 120 BPM
    downbeats = [index * 2.0 for index in range(21)]

    cue, start, lead = quantized_cue_and_start(20.1, beats, downbeats)

    assert cue == 20.0       # beat 40, divisible by 8
    assert start == 12.0     # beat 24, 16-beat lead and still divisible by 8
    assert lead == 16


def test_best_window_picks_highest_scoring_of_type():
    windows = [
        TransitionWindow(
            transition_window_id="w1", window_type=WindowType.mix_out,
            start_sec=100.0, end_sec=116.0, score=0.6,
        ),
        TransitionWindow(
            transition_window_id="w2", window_type=WindowType.mix_out,
            start_sec=200.0, end_sec=216.0, score=0.9,
        ),
        TransitionWindow(
            transition_window_id="w3", window_type=WindowType.mix_in,
            start_sec=0.0, end_sec=16.0, score=0.8,
        ),
    ]
    assert best_window(windows, WindowType.mix_out).transition_window_id == "w2"
    assert best_window(windows, WindowType.mix_in).transition_window_id == "w3"
    assert best_window(windows, WindowType.bridge) is None


def test_deck_set_track_clears_previous_player_source():
    QApplication.instance() or QApplication([])

    class FakePlayer:
        def __init__(self):
            self.sources = [QUrl.fromLocalFile("/tmp/old-track.mp3")]
            self.positions = []
            self.stopped = False

        def stop(self):
            self.stopped = True

        def setSource(self, source):
            self.sources.append(source)

        def setPosition(self, position):
            self.positions.append(position)

    deck = Deck("Deck")
    fake = FakePlayer()
    deck._player = fake
    analysis = AnalysisResult(
        engine_version="test",
        track=Track(
            track_id="new",
            title="New Track",
            source_path="/tmp/new-track.mp3",
            duration_sec=180.0,
            bpm_estimate=128.0,
        ),
    )

    deck.set_track(analysis, load_config("configs/default.yaml"), [], WindowType.mix_in)

    assert fake.stopped is True
    assert fake.sources[-1].isEmpty()
    assert fake.positions[-1] == 0


def test_deck_quantize_ignores_unreliable_beatgrid():
    QApplication.instance() or QApplication([])

    class FakePlayer:
        def __init__(self):
            self.positions = []

        def source(self):
            return QUrl.fromLocalFile("/tmp/source.mp3")

        def setPosition(self, position):
            self.positions.append(position)

    deck = Deck("Deck")
    fake = FakePlayer()
    deck._player = fake
    deck.quantize = True
    deck.analysis = AnalysisResult(
        engine_version="test",
        track=Track(
            track_id="new",
            title="New Track",
            source_path="/tmp/new-track.mp3",
            duration_sec=180.0,
            bpm_estimate=120.0,
        ),
        beatgrid=BeatGrid(
            bpm=120.0,
            beat_times_sec=[0.0, 0.5, 1.0],
            downbeats_sec=[0.0],
            reliable=False,
            diagnostic_flags=["grid_drift"],
        ),
    )

    deck.seek(0.61)

    assert fake.positions[-1] == 610


def test_preview_transition_states_problem_instead_of_silent_failure(tmp_path):
    QApplication.instance() or QApplication([])
    from dancelab.host.pair_review import TransitionReviewWidget
    from dancelab.core.models import SetTransition

    widget = TransitionReviewWidget()
    missing = AnalysisResult(
        engine_version="t",
        track=Track(track_id="gone", title="Gone", source_path=str(tmp_path / "gone.wav"),
                    duration_sec=180.0, bpm_estimate=128.0),
    )
    transition = SetTransition(from_track_id="gone", to_track_id="gone",
                               transition_score=0.5, harmonic_relation="exact")
    widget.set_transition(missing, missing, transition, load_config("configs/default.yaml"), [], [])
    widget.preview_transition()
    assert "file missing" in widget.sync_status.text()  # loud, not silent
    assert widget.deck_a._player is None                # nothing half-started

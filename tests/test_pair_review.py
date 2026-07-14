"""Pair-review helpers: beat sync, quantize, window pick — headless math."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from dancelab.core.config import load_config
from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    SetTransition,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.host.pair_review import (
    Deck,
    StructureStrip,
    TransitionReviewWidget,
    WaveformCueMarker,
    beat_sync_rate,
    best_window,
    snap_to_grid,
)
from dancelab.host.preview_timing import quantized_cue_and_start

from PySide6.QtCore import QUrl
from PySide6.QtCore import QPointF, Qt
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


def test_best_outgoing_window_prefers_enough_runway_for_the_preview():
    analysis = AnalysisResult(
        engine_version="test",
        track=Track(
            track_id="track",
            duration_sec=200.0,
            bpm_estimate=120.0,
        ),
    )
    windows = [
        TransitionWindow(
            transition_window_id="late-high",
            window_type=WindowType.mix_out,
            start_sec=170.0,
            end_sec=186.0,
            score=0.95,
        ),
        TransitionWindow(
            transition_window_id="safe-earlier",
            window_type=WindowType.mix_out,
            start_sec=120.0,
            end_sec=136.0,
            score=0.70,
        ),
    ]

    selected = best_window(
        windows,
        WindowType.mix_out,
        analysis=analysis,
        transition_beats=64,
    )

    assert selected.transition_window_id == "safe-earlier"


def test_waveform_drag_selects_quantized_transition_and_moves_hot_cue():
    QApplication.instance() or QApplication([])

    class Event:
        def __init__(self, x, button=Qt.LeftButton, modifiers=Qt.NoModifier):
            self._position = QPointF(float(x), 70.0)
            self._button = button
            self._modifiers = modifiers

        def position(self):
            return self._position

        def button(self):
            return self._button

        def modifiers(self):
            return self._modifiers

    strip = StructureStrip()
    strip.resize(1000, 160)
    beats = [index * 0.5 for index in range(201)]
    strip.set_data(
        duration_sec=100.0,
        segments=[],
        windows=[],
        waveform=[0.5] * 100,
        beat_times=beats,
        downbeats=[index * 2.0 for index in range(51)],
        beatgrid_reliable=True,
    )

    selections = []
    strip.selectionCommitted.connect(lambda start, end: selections.append((start, end)))
    strip.mousePressEvent(Event(83))
    strip.mouseMoveEvent(Event(281))
    strip.mouseReleaseEvent(Event(281))
    assert selections == [(8.0, 28.0)]

    strip.set_cue_markers([
        WaveformCueMarker("A", "Mix In", 8.0, "engine_transition_window", 8.0, "#38D996")
    ])
    cue_changes = []
    strip.cueMoved.connect(cue_changes.append)
    strip.mousePressEvent(Event(80))
    strip.mouseMoveEvent(Event(401))
    strip.mouseReleaseEvent(Event(401))
    assert strip.cue_markers["A"].time_sec == 40.0
    assert cue_changes[0]["reference_time_sec"] == 8.0
    assert cue_changes[0]["user_time_sec"] == 40.0

    strip.zoom_at(500, 0.5)
    assert strip.view_end_sec - strip.view_start_sec == pytest.approx(50.0)
    strip.fit_to_track()
    assert (strip.view_start_sec, strip.view_end_sec) == (0.0, 100.0)


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


def test_transition_preview_uses_latest_manual_region_before_imported_cue():
    QApplication.instance() or QApplication([])
    deck = Deck("Deck")
    deck.analysis = AnalysisResult(
        engine_version="test",
        track=Track(
            track_id="track",
            title="Track",
            source_path="/tmp/track.wav",
            duration_sec=180.0,
            bpm_estimate=120.0,
        ),
        beatgrid=BeatGrid(
            bpm=120.0,
            beat_times_sec=[index * 0.5 for index in range(361)],
            downbeats_sec=[index * 2.0 for index in range(91)],
            reliable=True,
        ),
    )
    deck.user_cue_sec = 16.0
    deck.strip.set_data(
        duration_sec=180.0,
        segments=[],
        windows=[],
        beat_times=deck.analysis.beatgrid.beat_times_sec,
        downbeats=deck.analysis.beatgrid.downbeats_sec,
        beatgrid_reliable=True,
    )
    deck.strip.set_user_selection(23.1, 39.0)

    assert deck.preview_cue_sec() == 24.0


def test_preview_transition_states_problem_instead_of_silent_failure(tmp_path):
    QApplication.instance() or QApplication([])
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


def test_transition_lab_exposes_phrase_locked_profiles_and_single_mix_view():
    QApplication.instance() or QApplication([])
    widget = TransitionReviewWidget()

    profile_ids = [widget.profile_combo.itemData(index) for index in range(widget.profile_combo.count())]
    assert profile_ids == ["linear", "plain_blend", "bass_swap", "tops_swap", "contour_blend"]
    assert widget.profile_combo.currentData() == "plain_blend"
    duration_values = [
        widget.duration_combo.itemData(index)
        for index in range(widget.duration_combo.count())
    ]
    assert duration_values == ["auto", 32, 64, 96, 128, 160, 192, 224, 256]
    assert widget.simulation_view.envelope.grid_beats == 8
    assert widget.simulation_view.envelope.duration_beats == 64
    assert "not a claim" in widget.profile_description.text()
    assert widget._preview_animation_timer.interval() == 33
    strategy_ids = [
        widget.tempo_strategy_combo.itemData(index)
        for index in range(widget.tempo_strategy_combo.count())
    ]
    assert strategy_ids == ["follow_outgoing", "balanced_m10"]
    assert widget.tempo_strategy_combo.currentData() == "follow_outgoing"


def test_transition_lab_shortens_manual_length_when_source_would_end(tmp_path):
    QApplication.instance() or QApplication([])
    source_a = tmp_path / "a.wav"
    source_b = tmp_path / "b.wav"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")
    widget = TransitionReviewWidget()
    config = load_config("configs/default.yaml")
    widget.deck_a.analysis = AnalysisResult(
        engine_version="test",
        track=Track(
            track_id="a",
            source_path=str(source_a),
            duration_sec=100.0,
            bpm_estimate=120.0,
        ),
    )
    widget.deck_b.analysis = AnalysisResult(
        engine_version="test",
        track=Track(
            track_id="b",
            source_path=str(source_b),
            duration_sec=180.0,
            bpm_estimate=120.0,
        ),
    )
    widget.deck_a.config = config
    widget.deck_b.config = config
    widget.deck_a.windows = [
        TransitionWindow(
            window_type=WindowType.mix_out,
            start_sec=60.0,
            end_sec=76.0,
            score=0.9,
        )
    ]
    widget.deck_b.windows = [
        TransitionWindow(
            window_type=WindowType.mix_in,
            start_sec=0.0,
            end_sec=16.0,
            score=0.9,
        )
    ]
    widget.deck_b.cue_window_type = WindowType.mix_in
    widget.duration_combo.setCurrentIndex(widget.duration_combo.findData(128))

    inputs = widget._preview_inputs()

    assert not isinstance(inputs, str)
    _, render_args, _, plan = inputs
    assert plan.requested_beats == 128
    assert plan.selected_beats == 64
    assert render_args["duration_beats"] == 64


def _tempo_review_analysis(track_id: str, bpm: float, *, reliable: bool = True):
    beat_period = 60.0 / bpm
    return AnalysisResult(
        engine_version="test",
        track=Track(
            track_id=track_id,
            title=track_id,
            source_path=f"/tmp/{track_id}.wav",
            duration_sec=180.0,
            bpm_estimate=bpm,
        ),
        beatgrid=BeatGrid(
            bpm=bpm,
            beat_times_sec=[index * beat_period for index in range(361)],
            downbeats_sec=[index * beat_period * 4 for index in range(91)],
            quality_score=0.9 if reliable else 0.2,
            reliable=reliable,
        ),
    )


def test_transition_lab_m10_stays_shadow_and_preserves_validated_preview_clock():
    QApplication.instance() or QApplication([])
    widget = TransitionReviewWidget()
    analysis_a = _tempo_review_analysis("a", 120.0)
    analysis_b = _tempo_review_analysis("b", 130.0)
    transition = SetTransition(
        from_track_id="a",
        to_track_id="b",
        transition_score=0.7,
        harmonic_relation="exact",
    )
    widget.set_transition(
        analysis_a,
        analysis_b,
        transition,
        load_config("configs/default.yaml"),
        [],
        [],
    )
    validated_rates = (widget.deck_a.playback_rate, widget.deck_b.playback_rate)
    widget.tempo_strategy_combo.setCurrentIndex(
        widget.tempo_strategy_combo.findData("balanced_m10")
    )

    assert widget._tempo_plan is not None
    assert widget._tempo_plan.target_bpm == pytest.approx(125.554, abs=0.001)
    assert validated_rates == pytest.approx((1.0, 120.0 / 130.0))
    assert (widget.deck_a.playback_rate, widget.deck_b.playback_rate) == pytest.approx(
        validated_rates
    )
    # A 64-beat phrase has exactly the same duration on both playback clocks.
    duration_a = 64.0 * 60.0 / 120.0
    duration_b = 64.0 * 60.0 / (130.0 * widget.deck_b.playback_rate)
    assert duration_b == pytest.approx(duration_a)
    assert "Stable sync active" in widget.sync_status.text()
    assert "M8-M10 shadow target 125.554 BPM" in widget.sync_status.text()


def test_transition_lab_blocks_balanced_target_for_unreliable_grid():
    QApplication.instance() or QApplication([])
    widget = TransitionReviewWidget()
    analysis_a = _tempo_review_analysis("a", 120.0)
    analysis_b = _tempo_review_analysis("b", 130.0, reliable=False)
    transition = SetTransition(
        from_track_id="a",
        to_track_id="b",
        transition_score=0.7,
        harmonic_relation="exact",
    )
    widget.set_transition(
        analysis_a,
        analysis_b,
        transition,
        load_config("configs/default.yaml"),
        [],
        [],
    )
    widget.tempo_strategy_combo.setCurrentIndex(
        widget.tempo_strategy_combo.findData("balanced_m10")
    )

    assert widget._tempo_plan is None
    assert widget.deck_a.playback_rate == 1.0
    assert widget.deck_b.playback_rate == pytest.approx(120.0 / 130.0)
    assert "Stable sync active" in widget.sync_status.text()
    assert "M8-M10 shadow unavailable" in widget.sync_status.text()
    assert "reliable beatgrids are required" in widget.sync_status.text()


def test_transition_lab_knobs_follow_bass_swap_playhead():
    QApplication.instance() or QApplication([])
    widget = TransitionReviewWidget()
    widget.profile_combo.setCurrentIndex(widget.profile_combo.findData("bass_swap"))
    widget.simulation_view.set_playhead_fraction(0.5)

    values = widget.simulation_view.current_mixer_values()

    assert values["low_a"] == pytest.approx(0.05, abs=1e-6)
    assert values["low_b"] == pytest.approx(1.0)
    assert values["fader_a"] == pytest.approx(2**-0.5, abs=0.01)
    assert values["fader_b"] == pytest.approx(2**-0.5, abs=0.01)


def test_transition_lab_ignores_render_from_previous_pair():
    QApplication.instance() or QApplication([])
    widget = TransitionReviewWidget()
    widget._preview_token = 7
    widget._current_pair_key = ("current-a", "current-b")
    widget._pending_signatures[7] = ("old-signature",)

    widget._on_transition_rendered(
        {"token": 7, "pair_key": ("old-a", "old-b"), "result": object()}
    )

    assert widget._preview_result is None
    assert widget._preview_signature is None

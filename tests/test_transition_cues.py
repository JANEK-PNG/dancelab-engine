"""Edge-level TransitionCue (§13) — verified B-start or manual listen."""

from __future__ import annotations

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    SetTransition,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.decision.transition_cues import build_transition_cue
from dancelab.ingestion.rekordbox_device import DeviceCue


def _analysis(tid: str, reliable: bool = True) -> AnalysisResult:
    return AnalysisResult(
        engine_version="t",
        track=Track(track_id=tid, bpm_estimate=128.0),
        beatgrid=BeatGrid(
            bpm=128.0, beat_times_sec=[0.0, 0.5], downbeats_sec=[0.0], reliable=reliable
        ),
    )


def _win(wtype: WindowType, start: float, end: float, score: float = 0.8) -> TransitionWindow:
    return TransitionWindow(window_type=wtype, start_sec=start, end_sec=end, score=score)


TRANSITION = SetTransition(
    from_track_id="a", to_track_id="b", transition_score=0.82,
    harmonic_relation="adjacent_same_mode",
)


def test_user_hotcue_near_window_becomes_verified_b_start():
    cue = build_transition_cue(
        TRANSITION,
        analysis_a=_analysis("a"),
        analysis_b=_analysis("b"),
        windows_a=[_win(WindowType.mix_out, 240.0, 270.0)],
        windows_b=[_win(WindowType.mix_in, 60.0, 90.0)],
        user_cues_b=[DeviceCue("hot", 1, "point", 65_000, None)],  # hot A @ 65 s
    )
    assert cue.b_cue_source == "rekordbox_hotcue"
    assert cue.b_cue_slot == 1
    assert cue.b_in_start_sec == 65.0
    assert cue.requires_manual_listen is False
    # 30 s window at 128 BPM = 64 beats, grids reliable → claimed
    assert cue.mix_duration_beats == 64
    assert any("YOUR hot cue A" in r for r in cue.reasoning)


def test_window_only_requires_manual_listen():
    cue = build_transition_cue(
        TRANSITION,
        analysis_a=_analysis("a"),
        analysis_b=_analysis("b"),
        windows_a=[_win(WindowType.mix_out, 240.0, 270.0)],
        windows_b=[_win(WindowType.mix_in, 60.0, 90.0)],
        user_cues_b=None,
    )
    assert cue.b_cue_source == "window_only"
    assert cue.requires_manual_listen is True  # hard rule: no unverified claim


def test_far_user_cue_is_not_matched():
    cue = build_transition_cue(
        TRANSITION,
        analysis_a=_analysis("a"),
        analysis_b=_analysis("b"),
        windows_a=[_win(WindowType.mix_out, 240.0, 270.0)],
        windows_b=[_win(WindowType.mix_in, 60.0, 90.0)],
        user_cues_b=[DeviceCue("hot", 3, "point", 290_000, None)],  # 290 s ≫ window
    )
    assert cue.b_cue_source == "window_only"
    assert cue.requires_manual_listen is True


def test_unreliable_grid_never_claims_beats():
    cue = build_transition_cue(
        TRANSITION,
        analysis_a=_analysis("a", reliable=False),
        analysis_b=_analysis("b"),
        windows_a=[_win(WindowType.mix_out, 240.0, 270.0)],
        windows_b=[_win(WindowType.mix_in, 60.0, 90.0)],
        user_cues_b=[DeviceCue("hot", 1, "point", 65_000, None)],
    )
    assert cue.mix_duration_beats is None          # never fabricated
    assert cue.requires_manual_listen is True      # unreliable grid → listen
    assert any("beatgrid unreliable" in r for r in cue.reasoning)


def test_loop_cues_are_not_b_start_candidates():
    cue = build_transition_cue(
        TRANSITION,
        analysis_a=_analysis("a"),
        analysis_b=_analysis("b"),
        windows_a=[_win(WindowType.mix_out, 240.0, 270.0)],
        windows_b=[_win(WindowType.mix_in, 60.0, 90.0)],
        user_cues_b=[DeviceCue("hot", 2, "loop", 62_000, 70_000)],  # loop ≠ start point
    )
    assert cue.b_cue_source == "window_only"


def test_earliest_hotcue_without_a_mix_in_window_still_needs_a_listen():
    """A hot cue picked with no engine window to corroborate it is a guess at
    the DJ's intent, not a verified handoff. The code's own comment on that
    branch says as much, so the flag must agree."""
    cue = build_transition_cue(
        TRANSITION,
        analysis_a=_analysis("a"),
        analysis_b=_analysis("b"),
        windows_a=[_win(WindowType.mix_out, 240.0, 270.0)],
        windows_b=[],                                    # no mix-in window on B
        user_cues_b=[DeviceCue("hot", 1, "point", 12_000, None)],
    )
    assert cue.b_cue_source == "rekordbox_hotcue"        # timestamp is real
    assert cue.requires_manual_listen is True            # but nothing corroborates it

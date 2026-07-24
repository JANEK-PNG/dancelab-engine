"""Pure planner: in-out mode placement + honesty flags."""

from dancelab.core.models import (
    SetPlan,
    SetTransition,
    TransitionWindow,
    WindowType,
    AnalysisResult,
    BeatGrid,
    Track,
)
from dancelab.decision.cue_plan import plan_cues
from dancelab.decision.cue_labels import DEFAULT_CUE_LABELS
from dancelab.decision.cue_export_models import CueContentMode


def _analysis(track_id, *, reliable=True, title=""):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title),
        beatgrid=BeatGrid(bpm=120.0, reliable=reliable),
    )


def _set():
    return SetPlan(
        track_order=["A", "B"],
        transitions=[
            SetTransition(
                from_track_id="A", to_track_id="B",
                transition_score=0.8, harmonic_relation="adjacent",
            )
        ],
    )


def _plan(windows, analyses=None, mode=CueContentMode.in_out):
    analyses = analyses or {"A": _analysis("A"), "B": _analysis("B")}
    return plan_cues(
        _set(), analyses=analyses, windows_by_track=windows,
        labels=DEFAULT_CUE_LABELS, mode=mode,
    )


def test_in_out_places_mixout_on_A_and_mixin_on_B():
    windows = {
        "A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
        "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9, window_type=WindowType.mix_in)],
    }
    plan = _plan(windows)
    by_track = {t.content_id: t for t in plan.tracks}
    a_out = [c for c in by_track["A"].cues if c.cue_type == "mix_out"]
    b_in = [c for c in by_track["B"].cues if c.cue_type == "mix_in"]
    assert a_out and a_out[0].pad_label == "B" and a_out[0].position_ms == 300000
    assert b_in and b_in[0].pad_label == "A" and b_in[0].position_ms == 30000


def test_weak_window_is_flagged_unverified_not_dropped():
    windows = {
        "A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
        "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.5, window_type=WindowType.mix_in)],
    }
    plan = _plan(windows)
    b_in = [c for c in next(t for t in plan.tracks if t.content_id == "B").cues if c.cue_type == "mix_in"][0]
    assert b_in.confident is False
    assert "check by ear" in b_in.comment  # placed, not dropped


def test_unreliable_beatgrid_makes_cue_unverified_and_no_beats():
    windows = {
        "A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.95, window_type=WindowType.mix_out)],
        "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.95, window_type=WindowType.mix_in)],
    }
    analyses = {"A": _analysis("A", reliable=False), "B": _analysis("B", reliable=False)}
    plan = _plan(windows, analyses=analyses)
    a_out = [c for c in next(t for t in plan.tracks if t.content_id == "A").cues if c.cue_type == "mix_out"][0]
    assert a_out.confident is False
    assert "beats" not in a_out.comment  # no fabricated beat-count


def test_none_mode_writes_nothing():
    plan = _plan({"A": [], "B": []}, mode=CueContentMode.none)
    assert plan.tracks == []


def test_missing_analysis_warns_and_skips():
    windows = {"A": [], "B": []}
    plan = _plan(windows, analyses={"A": _analysis("A")})  # B missing
    assert any("missing analysis" in w for w in plan.warnings)

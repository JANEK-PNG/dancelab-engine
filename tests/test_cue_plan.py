"""Pure planner: in-out mode placement + honesty flags."""

from dancelab.core.models import (
    SetPlan,
    SetTransition,
    TransitionWindow,
    WindowType,
    AnalysisResult,
    BeatGrid,
    Track,
    Segment,
    SegmentType,
)
from dancelab.decision.cue_plan import plan_cues
from dancelab.decision.cue_labels import DEFAULT_CUE_LABELS
from dancelab.decision.cue_export_models import CueContentMode


def _seg(track_id, seg_type, start, end):
    return Segment(
        segment_id=f"{track_id}-{seg_type}-{int(start)}", track_id=track_id,
        start_sec=start, end_sec=end, segment_type=seg_type,
    )


def _analysis(track_id, *, reliable=True, title="", segments=None):
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=track_id, title=title),
        beatgrid=BeatGrid(bpm=120.0, reliable=reliable),
        segments=segments or [],
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
    assert "⚠" in b_in.comment          # marked uncertain
    assert "MIX IN" in b_in.comment     # but TYPE stays visible, not hidden
    assert b_in.cue_type == "mix_in"


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


def test_structural_adds_drop_and_breakdown_on_pads_C_and_D():
    windows = {
        "A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
        "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9, window_type=WindowType.mix_in)],
    }
    analyses = {
        "A": _analysis("A"),
        "B": _analysis("B", segments=[
            _seg("B", SegmentType.drop, 60.0, 90.0),
            _seg("B", SegmentType.breakdown, 120.0, 150.0),
        ]),
    }
    plan = plan_cues(_set(), analyses=analyses, windows_by_track=windows,
                     labels=DEFAULT_CUE_LABELS, mode=CueContentMode.structural)
    b = next(t for t in plan.tracks if t.content_id == "B")
    drop = [c for c in b.cues if c.cue_type == "drop"]
    brk = [c for c in b.cues if c.cue_type == "breakdown"]
    mix_in = [c for c in b.cues if c.cue_type == "mix_in"]
    assert mix_in and mix_in[0].pad_label == "A"          # in-out still present
    assert drop and drop[0].pad_label == "C" and drop[0].position_ms == 60000
    assert brk and brk[0].pad_label == "D" and brk[0].position_ms == 120000


def test_in_out_mode_has_no_structural_cues():
    windows = {"A": [], "B": []}
    analyses = {"A": _analysis("A"),
                "B": _analysis("B", segments=[_seg("B", SegmentType.drop, 60.0, 90.0)])}
    plan = plan_cues(_set(), analyses=analyses, windows_by_track=windows,
                     labels=DEFAULT_CUE_LABELS, mode=CueContentMode.in_out)
    b = next(t for t in plan.tracks if t.content_id == "B")
    assert all(c.cue_type != "drop" for c in b.cues)


def test_cue_snaps_to_nearest_beat():
    from dancelab.decision.cue_plan import snap_to_grid
    bg = BeatGrid(bpm=120.0, reliable=True,
                  beat_times_sec=[30.0, 30.5, 31.0, 300.0, 300.5, 301.0])
    assert snap_to_grid(300.3, bg) == 300.5  # nearest beat
    assert snap_to_grid(30.1, bg) == 30.0


def test_snap_prefers_verified_downbeat():
    from dancelab.decision.cue_plan import snap_to_grid
    bg = BeatGrid(bpm=120.0, reliable=True,
                  beat_times_sec=[300.0, 300.5, 301.0],
                  downbeats_sec=[300.0, 302.0], downbeat_phase_verified=True)
    assert snap_to_grid(300.4, bg) == 300.0  # downbeat wins when phase-verified


def test_snap_falls_back_to_raw_without_grid_times():
    from dancelab.decision.cue_plan import snap_to_grid
    bg = BeatGrid(bpm=120.0, reliable=True)  # no beat_times
    assert snap_to_grid(300.3, bg) == 300.3


def test_plan_snaps_mixout_to_beat():
    windows = {
        "A": [TransitionWindow(start_sec=300.3, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
        "B": [],
    }
    analyses = {
        "A": AnalysisResult(engine_version="t", track=Track(track_id="A"),
                            beatgrid=BeatGrid(bpm=120.0, reliable=True,
                                              beat_times_sec=[300.0, 300.5, 301.0])),
        "B": _analysis("B"),
    }
    plan = plan_cues(_set(), analyses=analyses, windows_by_track=windows,
                     labels=DEFAULT_CUE_LABELS, mode=CueContentMode.in_out)
    a_out = [c for c in next(t for t in plan.tracks if t.content_id == "A").cues
             if c.cue_type == "mix_out"][0]
    assert a_out.position_ms == 300500  # snapped to 300.5s, not 300.3


def test_structural_ignores_non_landmark_segments():
    windows = {"A": [], "B": []}
    analyses = {"A": _analysis("A"),
                "B": _analysis("B", segments=[
                    _seg("B", SegmentType.groove, 40.0, 60.0),
                    _seg("B", SegmentType.intro, 0.0, 10.0),
                ])}
    plan = plan_cues(_set(), analyses=analyses, windows_by_track=windows,
                     labels=DEFAULT_CUE_LABELS, mode=CueContentMode.structural)
    b = next(t for t in plan.tracks if t.content_id == "B")
    assert b.cues == [] or all(c.cue_type in ("mix_in", "mix_out") for c in b.cues)

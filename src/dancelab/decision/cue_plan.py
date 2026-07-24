"""Pure cue planner: an ordered set -> a CuePlan (no I/O).

Reuses `decision.transition_cues.build_transition_cue` for the honest mix-in /
mix-out points and beat-counts, then maps them onto hot-cue pads. Honesty
(ADR-005): a cue is `confident` only when its transition window is strong AND
both beatgrids are reliable (or a verified DJ hot cue backs it). Otherwise the
cue is still placed, but flagged unverified ("check by ear") — never dropped,
never faked. Beat-counts appear only when confident.
"""

from __future__ import annotations

from dancelab.core.models import (
    AnalysisResult,
    SegmentType,
    SetPlan,
    TransitionWindow,
    WindowType,
)
from dancelab.decision.transition_cues import build_transition_cue
from dancelab.decision.cue_labels import render_comment
from dancelab.decision.cue_export_models import (
    CuePlan,
    TrackCuePlan,
    PlannedCue,
    CueContentMode,
    pad_index_to_kind,
    PAD_NAMES,
)

# A window must clear this score (and grids must be reliable) for its cue to be
# treated as confident rather than "check by ear".
CONFIDENT_SCORE = 0.7

# Segment types that become structural landmark cues, mapped to cue_type/label.
# "phrase" is intentionally absent: phrase markers need a verified downbeat
# grid we do not claim here (ADR-005).
STRUCTURAL_SEGMENTS: dict[SegmentType, str] = {
    SegmentType.drop: "drop",
    SegmentType.breakdown: "breakdown",
}
FIRST_STRUCTURAL_PAD = 3  # pads A/B reserved for in-out; structural starts at C
MAX_PAD = 8


def _best_window(windows: list[TransitionWindow], wtype: WindowType) -> TransitionWindow | None:
    matching = [w for w in windows if w.window_type == wtype]
    return max(matching, key=lambda w: w.score) if matching else None


def _grids_reliable(an_a: AnalysisResult, an_b: AnalysisResult) -> bool:
    return bool(
        an_a.beatgrid and an_a.beatgrid.reliable
        and an_b.beatgrid and an_b.beatgrid.reliable
    )


def _mk_cue(content_id, position_sec, pad_index, cue_type, labels, confident, beats=None):
    if confident:
        label = labels.get(cue_type, {})
        comment = render_comment(label.get("comment", cue_type), beats)
        color = label.get("color", -1)
    else:
        unv = labels.get("unverified", {})
        comment = unv.get("comment", "⚠ check by ear")
        color = unv.get("color", -1)
    return PlannedCue(
        content_id=str(content_id),
        position_ms=int(round(position_sec * 1000)),
        kind=pad_index_to_kind(pad_index),
        pad_label=PAD_NAMES[pad_index - 1],
        color=color,
        comment=comment,
        cue_type=cue_type,
        confident=confident,
    )


def _add_structural(track_id, analysis, labels, cues: list, warnings: list) -> None:
    """Append drop/breakdown landmark cues on the next free pads (C onward)."""
    landmarks = [
        (seg.start_sec, STRUCTURAL_SEGMENTS[seg.segment_type])
        for seg in sorted(analysis.segments, key=lambda s: s.start_sec)
        if seg.segment_type in STRUCTURAL_SEGMENTS
    ]
    if not landmarks:
        return
    used = {c.kind for c in cues}
    grid_ok = bool(analysis.beatgrid and analysis.beatgrid.reliable)
    pad_index = FIRST_STRUCTURAL_PAD
    for position_sec, cue_type in landmarks:
        while pad_index <= MAX_PAD and pad_index_to_kind(pad_index) in used:
            pad_index += 1
        if pad_index > MAX_PAD:
            warnings.append(f"{track_id}: pads exhausted, dropped {cue_type} @ {position_sec:.0f}s")
            continue
        cues.append(_mk_cue(track_id, position_sec, pad_index, cue_type, labels, confident=grid_ok))
        used.add(pad_index_to_kind(pad_index))
        pad_index += 1


def plan_cues(
    set_plan: SetPlan,
    *,
    analyses: dict[str, AnalysisResult],
    windows_by_track: dict[str, list[TransitionWindow]],
    labels: dict,
    mode: CueContentMode,
) -> CuePlan:
    plan = CuePlan(mode=mode, tracks=[], warnings=[])
    if mode == CueContentMode.none:
        return plan

    cues_by_track: dict[str, list[PlannedCue]] = {tid: [] for tid in set_plan.track_order}

    for tr in set_plan.transitions:
        a, b = tr.from_track_id, tr.to_track_id
        an_a, an_b = analyses.get(a), analyses.get(b)
        if an_a is None or an_b is None:
            plan.warnings.append(f"missing analysis for {a}->{b}; transition skipped")
            continue

        wa = windows_by_track.get(a, [])
        wb = windows_by_track.get(b, [])
        tc = build_transition_cue(
            tr, analysis_a=an_a, analysis_b=an_b,
            windows_a=wa, windows_b=wb, user_cues_b=None,
        )
        grids = _grids_reliable(an_a, an_b)
        out_w = _best_window(wa, WindowType.mix_out)
        in_w = _best_window(wb, WindowType.mix_in)

        if tc.a_out_start_sec is not None:
            confident = bool(grids and out_w is not None and out_w.score >= CONFIDENT_SCORE)
            cues_by_track.setdefault(a, []).append(
                _mk_cue(a, tc.a_out_start_sec, 2, "mix_out", labels,
                        confident, beats=tc.mix_duration_beats if confident else None)
            )
        if tc.b_in_start_sec is not None:
            verified_cue = tc.b_cue_source == "rekordbox_hotcue"
            confident = verified_cue or bool(
                grids and in_w is not None and in_w.score >= CONFIDENT_SCORE
            )
            cues_by_track.setdefault(b, []).append(
                _mk_cue(b, tc.b_in_start_sec, 1, "mix_in", labels, confident)
            )

    if mode == CueContentMode.structural:
        for tid in set_plan.track_order:
            an = analyses.get(tid)
            if an is None:
                continue
            _add_structural(tid, an, labels, cues_by_track.setdefault(tid, []), plan.warnings)

    for tid in set_plan.track_order:
        an = analyses.get(tid)
        title = (an.track.title if an and an.track else "") or ""
        plan.tracks.append(
            TrackCuePlan(content_id=str(tid), track_title=title, cues=cues_by_track.get(tid, []))
        )
    return plan

"""Edge-level transition cues (SPEC §13) — verified handoff points.

Combines engine transition windows with the DJ's own Rekordbox hot cues
(read byte-verified from a device export). Honesty rules enforced here:
- a B-side start is only "claimed" when backed by a real cue timestamp
  (the DJ's hot cue near the mix-in window); otherwise the edge stays
  window_only and requires a manual listen;
- mix_duration_beats is computed only when BOTH beatgrids are reliable —
  never a fabricated number.
"""

from __future__ import annotations

from dancelab.core.models import (
    AnalysisResult,
    SetTransition,
    TransitionCue,
    TransitionWindow,
    WindowType,
)
from dancelab.ingestion.rekordbox_device import DeviceCue

# a user cue counts as "at the mix-in" when within this many seconds of the
# engine's best mix-in window (generous: windows are 16-32 s constructs)
CUE_MATCH_TOLERANCE_SEC = 45.0


def _best(windows: list[TransitionWindow], window_type: WindowType) -> TransitionWindow | None:
    matching = [w for w in windows if w.window_type == window_type]
    return max(matching, key=lambda w: w.score) if matching else None


def _nearest_user_cue(
    cues: list[DeviceCue], target_sec: float
) -> DeviceCue | None:
    points = [c for c in cues if c.list_type == "hot" and c.cue_type == "point"]
    if not points:
        return None
    nearest = min(points, key=lambda c: abs(c.time_ms / 1000.0 - target_sec))
    if abs(nearest.time_ms / 1000.0 - target_sec) <= CUE_MATCH_TOLERANCE_SEC:
        return nearest
    return None


def build_transition_cue(
    transition: SetTransition,
    *,
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    windows_a: list[TransitionWindow],
    windows_b: list[TransitionWindow],
    user_cues_b: list[DeviceCue] | None = None,
) -> TransitionCue:
    reasoning: list[str] = []

    out_window = _best(windows_a, WindowType.mix_out)
    a_out = out_window.start_sec if out_window else None
    if out_window is None:
        reasoning.append("no mix-out window detected on A — manual placement needed")

    in_window = _best(windows_b, WindowType.mix_in)
    b_in: float | None = in_window.start_sec if in_window else None
    b_source = "window_only"
    b_slot: int | None = None

    if user_cues_b:
        if b_in is not None:
            user_cue = _nearest_user_cue(user_cues_b, b_in)
        else:
            # no engine window: the DJ's earliest hot point cue IS their
            # chosen entry point — verified timestamp, still needs a listen
            points = [
                c for c in user_cues_b
                if c.list_type == "hot" and c.cue_type == "point"
            ]
            user_cue = min(points, key=lambda c: c.time_ms) if points else None
        if user_cue is not None:
            b_in = user_cue.time_ms / 1000.0
            b_source = "rekordbox_hotcue"
            b_slot = user_cue.hot_slot
            slot_name = chr(ord("A") + user_cue.hot_slot - 1) if user_cue.hot_slot else "?"
            reasoning.append(
                f"B start = YOUR hot cue {slot_name} @ {b_in:.1f}s "
                "(verified from Rekordbox device export)"
            )
    if b_source == "window_only" and in_window is not None:
        reasoning.append(
            "B start is an engine window estimate — no verified cue; listen first"
        )

    grids_reliable = bool(
        analysis_a.beatgrid and analysis_a.beatgrid.reliable
        and analysis_b.beatgrid and analysis_b.beatgrid.reliable
    )
    mix_beats: int | None = None
    if grids_reliable and out_window is not None and analysis_a.beatgrid.bpm > 0:
        window_len = max(out_window.end_sec - out_window.start_sec, 0.0)
        mix_beats = int(round(window_len * analysis_a.beatgrid.bpm / 60.0))
    elif not grids_reliable:
        reasoning.append("beatgrid unreliable on one side — no beat-count claimed")

    return TransitionCue(
        from_track_id=transition.from_track_id,
        to_track_id=transition.to_track_id,
        transition_type=transition.harmonic_relation,
        a_out_start_sec=a_out,
        b_in_start_sec=b_in,
        b_cue_source=b_source,
        b_cue_slot=b_slot,
        mix_duration_beats=mix_beats,
        confidence=max(0.0, min(1.0, transition.transition_score)),
        # HARD RULE: only a verified cue with usable windows and reliable
        # grids releases the manual-listen requirement. Both windows must be
        # present: a hot cue chosen with no mix-in window to corroborate it
        # (the earliest-cue branch above) is a guess at the DJ's intent, and
        # that branch's own comment says it still needs a listen.
        requires_manual_listen=not (
            b_source == "rekordbox_hotcue"
            and in_window is not None
            and out_window is not None
            and grids_reliable
        ),
        reasoning=reasoning,
    )

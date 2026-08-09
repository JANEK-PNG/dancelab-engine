"""Where a hot cue is allowed to land — one rule, shared by every cue writer.

Both cue paths (the Rekordbox XML exporter and the master.db writer) need the
same answer to "given a raw window time, where does the cue actually go?".
Keeping that answer in one place stops the two paths from drifting apart and
from re-deriving a weaker version of it.

Honesty (ADR-005) is enforced by the grid guards rather than by convention:
an unreliable beatgrid snaps nothing (its beat times are noise, and snapping to
noise invents precision), and a phrase grid is only claimed when the bar phase
was actually verified. Without verified phase we snap to the nearest beat and
make no phrase claim.
"""

from __future__ import annotations

from dancelab.core.models import BeatGrid

# Phrase divisions a DJ can actually count, largest first. All are whole BARS
# (multiples of 4 beats): a hot cue must land on beat 1 of a bar — the red bar
# line in Rekordbox — never mid-bar (Janek 09.08: "68.1, not 68.2"). The old
# 2-beat division put cues on beat 3 and was the source of that complaint.
CUE_PHRASE_DIVISIONS_BEATS = (64, 32, 16, 8, 4)
# How far a cue may be pulled to reach each division.
CUE_PHRASE_SNAP_TOLERANCE_BEATS = {64: 4.0, 32: 4.0, 16: 4.0, 8: 2.0, 4: 2.0}


def usable_beat_grid(beatgrid: BeatGrid | None) -> BeatGrid | None:
    """A reliable beat sequence may snap cues to beats without claiming phrases."""
    if beatgrid is None or not beatgrid.reliable or not beatgrid.beat_times_sec:
        return None
    return beatgrid


def usable_export_grid(beatgrid: BeatGrid | None) -> BeatGrid | None:
    """Only grids with verified bar phase may become Rekordbox TEMPO data."""
    if (
        beatgrid is None
        or not beatgrid.reliable
        or not beatgrid.downbeat_phase_verified
        or not beatgrid.beat_times_sec
    ):
        return None
    return beatgrid


def grid_anchor_sec(beatgrid: BeatGrid) -> float:
    return float((beatgrid.downbeats_sec or beatgrid.beat_times_sec)[0])


def cue_phrase_division(beatgrid: BeatGrid, cue_sec: float) -> int | None:
    """Largest phrase division the cue sits on, measured from the grid anchor."""
    if beatgrid.bpm <= 0:
        return None
    beat_period = 60.0 / beatgrid.bpm
    beat_index = int(round((cue_sec - grid_anchor_sec(beatgrid)) / beat_period))
    if beat_index < 0:
        return None
    for division in CUE_PHRASE_DIVISIONS_BEATS:
        if beat_index % division == 0:
            return division
    return None


def snap_to_phrase_grid(beatgrid: BeatGrid, target_sec: float) -> float:
    """Snap hot cues to phrase-aware beat boundaries, not arbitrary beats.

    Cues should land on musically countable positions: 64/32/16/8/4/2-beat
    boundaries from the first exported downbeat. This prevents cues landing on
    e.g. beat 3 when the usable phrase point is beat 4.
    """
    if beatgrid.bpm <= 0:
        return target_sec

    beat_period = 60.0 / beatgrid.bpm
    anchor = grid_anchor_sec(beatgrid)
    target_beat = (target_sec - anchor) / beat_period
    if target_beat < 0:
        return anchor

    for division in CUE_PHRASE_DIVISIONS_BEATS:
        boundary = max(0, round(target_beat / division) * division)
        offset_beats = abs(target_beat - boundary)
        if boundary == 0 and target_beat > CUE_PHRASE_SNAP_TOLERANCE_BEATS[4]:
            continue
        if offset_beats <= CUE_PHRASE_SNAP_TOLERANCE_BEATS[division]:
            return anchor + boundary * beat_period

    # Last-resort safety: the nearest BAR rather than a random off-count.
    # Rare, because the 4-beat division above is already lenient.
    boundary = max(0, round(target_beat / 4) * 4)
    return anchor + boundary * beat_period


def snap_cue_start(beatgrid: BeatGrid | None, start_sec: float) -> float:
    """Snap to a phrase only with verified phase; otherwise to the nearest beat.

    Returns `start_sec` unchanged when the grid cannot be trusted at all.
    """
    grid = usable_beat_grid(beatgrid)
    if grid is None:
        return start_sec
    if grid.downbeat_phase_verified:
        return snap_to_phrase_grid(grid, start_sec)
    return float(min(grid.beat_times_sec, key=lambda beat: abs(beat - start_sec)))

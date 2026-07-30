"""Phrase-alignment helpers shared across transition and pair decisions."""

from __future__ import annotations

import numpy as np

from dancelab.core.models import BeatGrid, Segment

_EPS = 1e-9


def phrase_anchor_times(
    beatgrid: BeatGrid | None,
    segments: list[Segment] | None = None,
    *,
    phrase_beats: int = 32,
) -> np.ndarray:
    """Candidate phrase anchors from beatgrid plus structural boundaries.

    Beat-derived anchors keep the regular 32-beat phrasing baseline. Segment
    boundaries are snapped to the nearest beat/downbeat when available, so the
    phrase map can follow detected section changes instead of a rigid grid only.
    """
    anchors: list[float] = []
    beat_times = np.asarray(beatgrid.beat_times_sec if beatgrid is not None else [], dtype=np.float64)
    downbeats = np.asarray(beatgrid.downbeats_sec if beatgrid is not None else [], dtype=np.float64)

    if downbeats.size:
        bars_per_phrase = max(1, phrase_beats // 4)
        anchors.extend(float(value) for value in downbeats[::bars_per_phrase])
    elif beat_times.size:
        anchors.extend(float(value) for value in beat_times[::phrase_beats])

    boundaries = sorted(
        {
            float(segment.start_sec)
            for segment in (segments or [])
        }
        | {
            float(segment.end_sec)
            for segment in (segments or [])
        }
    )
    if boundaries:
        snap_targets = downbeats if downbeats.size else beat_times
        if snap_targets.size:
            for boundary in boundaries:
                idx = int(np.argmin(np.abs(snap_targets - boundary)))
                anchors.append(float(snap_targets[idx]))
        else:
            anchors.extend(boundaries)

    if beat_times.size:
        anchors.append(float(beat_times[0]))

    if not anchors:
        return np.array([], dtype=np.float64)
    return np.array(sorted({round(anchor, 4) for anchor in anchors}), dtype=np.float64)


def phrase_alignment_curve(
    times_sec: np.ndarray,
    beatgrid: BeatGrid | None,
    segments: list[Segment] | None = None,
    *,
    phrase_beats: int = 32,
    width_beats: float = 4.0,
) -> np.ndarray | None:
    """Alignment score in [0,1] for each time point against phrase anchors."""
    times = np.asarray(times_sec, dtype=np.float64)
    if times.size == 0:
        return np.array([], dtype=np.float64)

    anchors = phrase_anchor_times(beatgrid, segments, phrase_beats=phrase_beats)
    if anchors.size == 0:
        return None

    beat_len = None
    if beatgrid is not None and beatgrid.bpm > 0:
        beat_len = 60.0 / beatgrid.bpm
    elif anchors.size > 1:
        beat_len = max(float(np.median(np.diff(anchors))) / 8.0, _EPS)
    else:
        beat_len = 0.5

    dist = np.min(np.abs(times[:, None] - anchors[None, :]), axis=1)
    width_sec = max(width_beats * beat_len, _EPS)
    return np.exp(-dist / width_sec)


# Phrase multiples a DJ counts out by hand. These are structural, not measured.
CLASSIC_TRANSITION_BEATS: tuple[float, ...] = (8.0, 16.0, 32.0)


def preferred_transition_beats() -> tuple[float, ...]:
    """Transition lengths that score full marks.

    These are the phrase multiples a DJ counts out. They are structural, not
    measured, and they are deliberately NOT extended with the corpus figure.

    The priors file carries transition_length_beats_median = 94, and that value
    was briefly wired in here. Auditing the source field killed it: across 11,405
    corpus transitions, 14.3% of transition_length_beats are NEGATIVE (down to
    -14526) and 28.7% exceed four minutes (up to 15771). The field measures the
    gap between two aligned regions — negative when alignments overlap, enormous
    when unaligned material sits between them — not how long a DJ blended. The
    median was taken over that contaminated distribution.

    A trustworthy blend length has to be measured from the mix audio around the
    seam, or from a set whose transitions we actually know. Until then, no number
    from that field shapes scoring (ADR-005).
    """
    return CLASSIC_TRANSITION_BEATS


def window_phrase_score(
    start_sec: float,
    end_sec: float,
    beatgrid: BeatGrid | None,
    segments: list[Segment] | None = None,
    *,
    phrase_beats: int = 32,
) -> float | None:
    """Phrase suitability of one candidate window."""
    alignment = phrase_alignment_curve(
        np.array([start_sec, end_sec], dtype=np.float64),
        beatgrid,
        segments,
        phrase_beats=phrase_beats,
    )
    if alignment is None:
        return None

    boundary_score = float(alignment.mean())
    if beatgrid is None or beatgrid.bpm <= 0:
        return boundary_score

    beat_len = 60.0 / beatgrid.bpm
    duration_beats = max((end_sec - start_sec) / max(beat_len, _EPS), 0.0)
    length_score = max(
        0.0,
        max(
            1.0 - abs(duration_beats - preferred) / max(preferred, 1.0)
            for preferred in preferred_transition_beats()
        ),
    )
    return float(np.clip(0.65 * boundary_score + 0.35 * length_score, 0.0, 1.0))

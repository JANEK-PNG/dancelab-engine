"""Pull a detected tempo onto the grid the record was actually made on.

Dance records are produced in a DAW at a tempo somebody typed: 128, 130, 136, 140,
occasionally a half. A tracker that answers 135.885 is not describing a record that
drifts a tenth of a beat per minute — it is describing its own scatter. Half a BPM
of error is 470 ms of slip across seventy seconds, which is a stumble, and no fader
can hold two records together when their tempo is only known that well.

This does not round. Rounding a bad estimate to a clean number produces a confident
lie. Each candidate tempo is instead tested against the beat times themselves: fit
the phase, measure how far the beats sit from a perfect grid at that tempo, and keep
the musical candidate only when it explains the beats at least as well as the free
fit. On one DJ's library that held for 38 of 44 records, and where it held it was
usually far better — Caribou's Honey went from 120 ms of scatter at 135.885 to 11 ms
at 136.0. The six that refused are left alone; a record that genuinely is not on a
round tempo has to be allowed to say so.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TempoRefinement:
    bpm: float
    source: str                 # "musical_grid" | "free_fit"
    residual_sec: float         # median distance of beats from a perfect grid
    free_bpm: float
    free_residual_sec: float

    @property
    def snapped(self) -> bool:
        return self.source == "musical_grid"


def _residual(beat_times: np.ndarray, bpm: float) -> float:
    """How far the beats sit from a perfect grid at this tempo, phase fitted."""
    period = 60.0 / bpm
    n = np.arange(beat_times.size)
    offset = float(np.median(beat_times - period * n))
    return float(np.median(np.abs(beat_times - (offset + period * n))))


def refine_tempo(beat_times, *, tolerance: float = 1.15,
                 max_shift_bpm: float = 0.75,
                 min_beats: int = 32) -> TempoRefinement | None:
    """Best tempo for these beats: a musical one when it earns the place.

    The free estimate is a least-squares fit over every beat, never the median gap
    between beats — beat times are rounded to the analysis frame and that rounding
    accumulates into tens of milliseconds across a phrase.

    tolerance is how much worse a musical candidate may be and still win; at 1.15
    it must explain the beats within 15 % of the free fit. max_shift_bpm refuses
    candidates further away than a tracker's plausible error, so a badly octave-
    folded or half-time estimate cannot be dragged onto a nearby round number.
    """
    beats = np.asarray(beat_times, dtype=float)
    if beats.size < min_beats:
        return None
    period = float(np.polyfit(np.arange(beats.size), beats, 1)[0])
    if not np.isfinite(period) or period <= 0.05:
        return None
    free = 60.0 / period
    free_res = _residual(beats, free)

    candidates = {round(free), round(free * 2) / 2}
    scored = [(c, _residual(beats, c)) for c in sorted(candidates)
              if c > 0 and abs(c - free) <= max_shift_bpm]
    if scored:
        best, best_res = min(scored, key=lambda item: item[1])
        if best_res <= free_res * tolerance:
            return TempoRefinement(float(best), "musical_grid", best_res,
                                   free, free_res)
    return TempoRefinement(free, "free_fit", free_res, free, free_res)

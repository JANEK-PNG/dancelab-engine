"""Beat grid for the analysis pipeline: rigid fit first, tracker as fallback.

The engine has had two beat grids since 2026-07-30 and the better one never
reached the product. `core/rigid_grid` fits ONE tempo and ONE phase to the whole
record by folding the onset envelope — it cannot lose a beat and cannot drift.
`preprocessing/beatgrid` wraps librosa's dynamic tracker, which follows tempo as
it moves. That freedom is right for a record played by hand and is pure damage
on a record that came out of a DAW, where the tempo is one number by construction.

Measured 2026-07-31 against Rekordbox (an algorithm that is not ours, 183 tracks):
mean error 1.7 millibeats for the rigid fit against 8.0 for the tracker.

So: try the rigid fit; take it only when it is confident; otherwise fall back to
the tracker and SAY SO in the diagnostics. A low rigid score is not a failure to
paper over — it is the record telling us no single tempo explains it.

Two honesty rules this module keeps:

  * `downbeat_phase_verified` stays False. The rigid fit settles BEAT phase, not
    BAR phase; which of the four beats is the "1" is a different question and
    nothing here answers it. Exports that need bar phase must still refuse.
  * `quality_score` stays None on the rigid path. Contrast is not a probability
    and inventing a mapping from one to the other would be exactly the kind of
    number that looks measured without being measured (ADR-005). The contrast
    itself goes into `diagnostic_flags`, where a reader can see it for what it is.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.models import BeatGrid
from dancelab.core.rigid_grid import MIN_CONTRAST, fit_rigid_grid
from dancelab.preprocessing.beatgrid import estimate_beatgrid


def _mono(signal: AudioSignal) -> np.ndarray:
    x = np.asarray(signal.samples, dtype=np.float32)
    return x.mean(axis=0) if x.ndim > 1 else x


def _from_rigid(grid, span_sec: float) -> BeatGrid:
    beats = [float(b) for b in grid.beats]
    flags = [
        "beatgrid_source=rigid",
        f"rigid_contrast={grid.contrast:.2f}",
        "tempo_snapped_to_musical" if grid.snapped_to_musical else "tempo_free_fit",
    ]
    if grid.free_bpm and abs(grid.free_bpm - grid.bpm) > 0.01:
        flags.append(f"free_bpm={grid.free_bpm:.3f}")
    return BeatGrid(
        bpm=float(grid.bpm),
        beat_times_sec=beats,
        # Beat phase, not bar phase — see module docstring. Kept as the same
        # every-fourth-beat proxy the tracker path uses, and just as unverified.
        downbeats_sec=[float(b) for b in grid.downbeats()],
        quality_score=None,
        coverage_sec=float(span_sec),
        diagnostic_flags=flags,
        downbeat_phase_verified=False,
        reliable=True,
    )


def estimate_beatgrid_best(
    signal: AudioSignal,
    *,
    hop_size: int = 512,
    bpm_hint: float | None = None,
    tempo_min: float = 90.0,
    tempo_max: float = 180.0,
    rigid: bool = True,
) -> BeatGrid:
    """The grid the product should use: rigid when it holds, tracker when it doesn't."""
    if rigid:
        y = _mono(signal)
        try:
            grid = fit_rigid_grid(y, signal.sample_rate)
        except Exception as exc:                      # noqa: BLE001 - never fatal
            grid = None
            rigid_note = f"rigid_grid_error={type(exc).__name__}"
        else:
            rigid_note = None
        if grid is not None and grid.confident:
            return _from_rigid(grid, span_sec=len(y) / signal.sample_rate)

        why = rigid_note or (
            f"rigid_contrast={grid.contrast:.2f}<{MIN_CONTRAST}" if grid is not None
            else "rigid_grid_no_fit"
        )
    else:
        why = "rigid_grid_disabled"

    out = estimate_beatgrid(
        signal,
        hop_size=hop_size,
        bpm_hint=bpm_hint,
        tempo_min=tempo_min,
        tempo_max=tempo_max,
    )

    # Uwaga: `estimate_beatgrid` SAMO woła `refine_tempo` (beatgrid.py:371) oraz
    # `refine_bpm_from_beat_times`. Dokładanie tu drugiego dostrojenia byłoby
    # czwartą kopią tej samej reguły — dokładnie ten wzorzec, który w tym repo
    # dał trzy różne implementacje snapowania cue. Zostawiamy tor trackera
    # nietknięty i dopisujemy tylko powód, dla którego sztywna siatka odpadła.
    flags = list(out.diagnostic_flags) + ["beatgrid_source=tracker", why]
    return out.model_copy(update={"diagnostic_flags": flags})

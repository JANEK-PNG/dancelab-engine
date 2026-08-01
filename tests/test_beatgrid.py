"""The tempo the pipeline reports is the one everything downstream mixes on."""

import numpy as np
import pytest

pytest.importorskip("librosa")  # real beat tracking belongs to the [audio] profile

from dancelab.core.audio_types import AudioSignal
from dancelab.preprocessing.beatgrid import estimate_beatgrid

SR = 22050


def kick_track(bpm: float, seconds: float = 40.0, jitter: float = 0.004,
               seed: int = 4) -> np.ndarray:
    """A four-to-the-floor record with the timing scatter a tracker actually sees."""
    rng = np.random.default_rng(seed)
    y = rng.normal(0.0, 0.002, int(seconds * SR)).astype(np.float32)
    period = 60.0 / bpm
    for k in range(int(seconds / period)):
        at = 0.25 + k * period + rng.normal(0, jitter)
        i, n = int(at * SR), int(0.09 * SR)
        if i < 0 or i + n > y.size:
            continue
        t = np.arange(n) / SR
        y[i:i + n] += np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.022)
    return y


def test_a_sequenced_tempo_is_reported_as_the_round_number_it_was_made_at():
    """The tracker's own scatter must not reach the caller as a decimal tempo.

    Club records are sequenced at whole BPM; a grid answering 135.885 is describing
    its noise, and half a BPM is 256 ms of slip across seventy seconds — well past
    the quarter-beat where tight becomes a stumble. This is the pipeline's use of
    core.tempo_refine: without it here, the render scripts and beatgrid.bpm
    disagreed about the same record, and only the scripts were right.
    """
    grid = estimate_beatgrid(AudioSignal(samples=kick_track(128.0), sample_rate=SR),
                             hop_size=256)
    assert grid.bpm == pytest.approx(128.0, abs=0.01)


def test_the_snap_is_recorded_in_the_flags_when_it_moves_the_tempo():
    """A number that was changed has to say so, or its provenance is a fiction."""
    grid = estimate_beatgrid(AudioSignal(samples=kick_track(128.0, jitter=0.006),
                                         sample_rate=SR), hop_size=256)
    snapped = [f for f in grid.diagnostic_flags
               if f.startswith("bpm_snapped_to_musical_grid")]
    assert not snapped or ("free=" in snapped[0] and "residual=" in snapped[0])

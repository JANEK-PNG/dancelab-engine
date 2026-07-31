"""Fit one rigid beat grid to a record that never changes tempo.

A general beat tracker follows the music: it is built for players who breathe, so
it is allowed to bend, and on a fixed-tempo record that freedom is pure damage. On
one DJ's library the tracked beats scattered 60-270 ms about a straight line and
the tempo read differently from the first half of a track than the second — not
because the record drifts, but because the tracker did.

Club records do not drift. They are sequenced against a DAW's grid at a tempo
somebody typed, which means the whole problem is two numbers: a period and a phase.
So nothing is tracked here. Every candidate tempo is scored by folding the onset
envelope onto a single beat phase and asking how sharply the energy piles up — the
same epoch folding used to find a pulsar in noisy counts. A tempo that is right
concentrates every kick in the record into one narrow peak; a tempo that is wrong
smears them evenly, however locally convincing it looked.

Because the grid is rigid, it cannot lose a beat, gain one, or wander — the failure
modes that made the tracked grids unusable are unreachable by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FOLD_BINS = 96
BPM_LO, BPM_HI = 60.0, 200.0
# Below this, no rigid grid explains the record — it was not made to a fixed tempo.
# The threshold lives beside the fit rather than in whichever caller happens to
# remember it, so a future engine caller cannot get a confident grid for
# arrhythmic material by forgetting to check.
MIN_CONTRAST = 2.0


@dataclass(frozen=True)
class RigidGrid:
    bpm: float
    first_beat_sec: float
    contrast: float          # how far the folded peak stands above the rest
    beats: np.ndarray

    @property
    def confident(self) -> bool:
        """Whether this grid should be believed at all."""
        return self.contrast >= MIN_CONTRAST

    def downbeats(self, per_bar: int = 4) -> np.ndarray:
        return self.beats[::per_bar]


KICK_HZ = 160.0


def _onset_envelope(y: np.ndarray, sr: int, hop: int,
                    kick_only: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Onsets to fold. By default only what happens under 160 Hz.

    Taking the whole spectrum lets every hat, clap, vocal consonant and reverb tail
    vote on where the beat is, and on breaks-driven records they outvote the kick —
    a 135 BPM record read as 169, a jungle tune as 131. The pulse a DJ beatmatches
    to is the kick, so the kick is what gets asked. This is the one idea in the
    references that the fold was missing (Joe Sullivan via realtime-bpm-analyzer:
    low-pass first, then look for peaks).
    """
    import librosa

    if kick_only:
        from scipy.signal import butter, sosfiltfilt

        sos = butter(4, KICK_HZ / (sr / 2), btype="lowpass", output="sos")
        y = sosfiltfilt(sos, y).astype(np.float32)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    env = np.maximum(env - np.median(env), 0.0)
    times = np.arange(env.size) * hop / sr
    return env, times


def _fold(env: np.ndarray, times: np.ndarray, bpm: float,
          window_frac: float = 0.10) -> tuple[float, float]:
    """Score a tempo by how much of the record's onset energy its grid catches.

    Returns (score, phase in beats). Score is the share of all onset energy landing
    within a narrow window of a beat, divided by the share of time that window
    occupies — how much better than spreading the energy evenly this grid does.

    Sharpness alone cannot be the score, and that mistake is what this replaces.
    At half the true tempo every second beat folds onto the same phase and the peak
    comes out *sharper* than the truth, so a contrast measure prefers it: the first
    version read a 135 BPM record as 67.5. Asking about captured energy settles the
    octave without a rule about ranges: half tempo can only ever catch half the beats,
    which is the decisive case (3.84 against 7.46 on a synthetic 85 BPM record).
    Doubling loses too, but narrowly — 7.31 against 7.46 — because the absolute
    window halves and transient tails fall outside it, not because coverage changes.
    """
    phase = np.mod(times * bpm / 60.0, 1.0)
    idx = np.minimum((phase * FOLD_BINS).astype(int), FOLD_BINS - 1)
    profile = np.bincount(idx, weights=env, minlength=FOLD_BINS)
    total = profile.sum()
    if total <= 1e-12:
        return 0.0, 0.0
    half = max(1, int(round(window_frac * FOLD_BINS / 2)))
    peak = int(np.argmax(np.convolve(np.r_[profile, profile],
                                     np.ones(2 * half + 1), mode="same")[:FOLD_BINS]))
    window = np.arange(peak - half, peak + half + 1) % FOLD_BINS
    captured = profile[window].sum() / total
    coverage = window.size / FOLD_BINS
    return float(captured / coverage), (peak + 0.5) / FOLD_BINS


def _fit_one(y, sr, hop, musical_only, kick_only) -> RigidGrid | None:

    env, times = _onset_envelope(y, sr, hop, kick_only)
    if env.sum() <= 0:
        return None
    if musical_only:
        candidates = np.arange(BPM_LO * 2, BPM_HI * 2 + 1) / 2.0
    else:
        candidates = np.arange(BPM_LO, BPM_HI + 0.01, 0.05)
    scored = [(bpm, *_fold(env, times, bpm)) for bpm in candidates]

    bpm, contrast, phase = max(scored, key=lambda item: item[1])

    period = 60.0 / bpm
    first = phase * period
    count = int((times[-1] - first) / period) + 1
    if count < 8:
        return None
    return RigidGrid(float(bpm), float(first), float(contrast),
                     first + np.arange(count) * period)


def fit_rigid_grid(y: np.ndarray, sr: int, *, hop: int = 128,
                   musical_only: bool = True) -> RigidGrid | None:
    """The tempo and phase that best explain a record, from whichever view is clearer.

    The fit is run twice, once on the kick band and once on the whole spectrum, and
    the more confident answer wins. Neither view is better everywhere: filtering to
    the kick rescued the records where breaks and hats were outvoting it (a jungle
    tune went from 2.24 to 3.06, Overmono from 2.40 to 3.32) and cost confidence on
    the ones whose broadband onsets were already clean. Both agreed on every tempo
    in this library, so what is really being chosen is the sharper phase.

    A low score is not a failure to report as a number — it means no rigid grid
    explains this record, which is the true answer for anything played by hand.
    """
    if y.size < sr * 8:
        return None
    fits = [f for f in (_fit_one(y, sr, hop, musical_only, True),
                        _fit_one(y, sr, hop, musical_only, False)) if f]
    return max(fits, key=lambda g: g.contrast) if fits else None

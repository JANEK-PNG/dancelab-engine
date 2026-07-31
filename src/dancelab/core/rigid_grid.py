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
# Measured, not chosen: across a 49-record sample of one DJ's library the scores
# fall in two groups with a clear gap. Stems and spoken material land at 1.09-1.99;
# every actual club record from 2.42 up, to 4.08. The threshold sits in the gap.
# It had been 2.0, which was calibrated before a fine tempo scan was added — that
# scan can only raise a score, and it lifted Burial's Archangel to 2.06, letting a
# record made without a metronome through a gate that had correctly refused it.
#
# The threshold lives beside the fit rather than in whichever caller happens to
# remember it, so a future engine caller cannot get a confident grid for
# arrhythmic material by forgetting to check.
MIN_CONTRAST = 2.2
# The coarse scan only settles the octave; the period is then found to a hundredth
# of a BPM, and the round number is kept only if it explains the onsets within this
# much of the free fit. Same bargain as core.tempo_refine, different evidence.
FINE_SPAN_BPM = 0.75
FINE_STEP_BPM = 0.01
SNAP_ABS_BPM = 0.05
MUSICAL_TOLERANCE = 0.995
# The octave is settled on a shorter stretch. On the whole record the coarse grid's
# own 0.5 BPM step is the problem it exists to fix: at 128.3 the nearest candidate
# is 128.5, which drifts a third of a beat across ninety seconds and smears its
# peak, while 192.5 sits 0.05 from 1.5x the truth, stays sharp, and wins on half
# the energy. Over a minute a 0.25 BPM error moves a quarter of a beat, too little
# to flip that comparison.
OCTAVE_WINDOW_SEC = 60.0


@dataclass(frozen=True)
class RigidGrid:
    bpm: float
    first_beat_sec: float
    contrast: float          # how far the folded peak stands above the rest
    beats: np.ndarray
    snapped_to_musical: bool = True
    free_bpm: float = 0.0    # the unconstrained best fit, before any snapping

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


def _fit_one(y, sr, hop, kick_only, tolerance=MUSICAL_TOLERANCE) -> RigidGrid | None:
    """Coarse musical scan to settle the octave, then a fine scan for the period.

    Scanning whole and half BPM alone is robust — those are the tempos records are
    made at, and the wide net cannot settle on a neighbour a hundredth away for no
    musical reason. But taking the winner as the answer quantises every tempo to
    0.5 BPM, and a quarter of a BPM is 337 ms of walk across a three-minute slot at
    136 — three times the quarter-beat where tight becomes a stumble. A record that
    genuinely sits at 133.4 has to be allowed to say so.

    So the musical winner names the neighbourhood, a fine scan finds the period
    inside it, and the musical value is kept only when it explains the onsets about
    as well — the same bargain `tempo_refine` strikes on beat times, made here on
    the fold score because that is the evidence this module has.
    """
    env, times = _onset_envelope(y, sr, hop, kick_only)
    if env.sum() <= 0:
        return None

    musical = np.arange(BPM_LO * 2, BPM_HI * 2 + 1) / 2.0
    n = min(env.size, int(OCTAVE_WINDOW_SEC * sr / hop))
    o_env, o_times = env[:n], times[:n]
    coarse_bpm = max(musical, key=lambda bpm: _fold(o_env, o_times, bpm)[0])
    # scored on the whole record once the octave is known
    m_bpm, m_score, m_phase = coarse_bpm, *_fold(env, times, coarse_bpm)

    fine = np.arange(m_bpm - FINE_SPAN_BPM, m_bpm + FINE_SPAN_BPM + 1e-9, FINE_STEP_BPM)
    f_bpm, f_score, f_phase = max(((bpm, *_fold(env, times, bpm)) for bpm in fine),
                                  key=lambda item: item[1])

    # A hundredth of a BPM apart is not a disagreement about tempo, it is noise in
    # the score; prefer the number somebody could have typed.
    snapped = (m_score >= f_score * tolerance
               or abs(f_bpm - m_bpm) <= SNAP_ABS_BPM)
    bpm, score, phase = ((m_bpm, m_score, m_phase) if snapped
                         else (f_bpm, f_score, f_phase))

    period = 60.0 / bpm
    first = phase * period
    count = int((times[-1] - first) / period) + 1
    if count < 8:
        return None
    return RigidGrid(float(bpm), float(first), float(score),
                     first + np.arange(count) * period,
                     snapped_to_musical=bool(snapped), free_bpm=float(f_bpm))


def fit_rigid_grid(y: np.ndarray, sr: int, *, hop: int = 128,
                   tolerance: float = MUSICAL_TOLERANCE) -> RigidGrid | None:
    """The tempo and phase that best explain a record, from whichever view is clearer.

    The fit is run twice, once on the kick band and once on the whole spectrum, and
    the more confident answer wins. Neither view is better everywhere: filtering to
    the kick rescued the records where breaks and hats were outvoting it (a jungle
    tune went from 2.24 to 3.06, Overmono from 2.40 to 3.32) and cost confidence on
    the ones whose broadband onsets were already clean. Both agreed on every tempo
    in this library, so what is really being chosen is the sharper phase.

    A low score is not a failure to report as a number — it means no rigid grid
    explains this record, which is the true answer for anything played by hand.

    `snapped_to_musical` says whether the answer is a tempo somebody could have
    typed into a DAW or a measured one; `free_bpm` carries the unconstrained fit
    either way, so a caller can see how far the snap moved it.
    """
    if y.size < sr * 8:
        return None
    fits = [f for f in (_fit_one(y, sr, hop, True, tolerance),
                        _fit_one(y, sr, hop, False, tolerance)) if f]
    if not fits:
        return None
    # A confident view beats a merely loud one: the kick band and the full spectrum
    # can disagree about whether the record has a fixed tempo at all.
    confident = [g for g in fits if g.confident]
    return max(confident or fits, key=lambda g: g.contrast)

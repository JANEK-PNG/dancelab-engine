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
# Captured-energy-per-coverage settles 2x by itself — half tempo can only ever catch
# half the beats. It does not settle 1.5x or 4/3x, where the faster grid still lands
# on a real beat often enough to stay sharp: Bicep's Glue fitted at 195 against 130,
# COIDO at 184 against 138, Ahoona at 160 against 120, and all three then fell out of
# a set as "32 % away from the tempo" while sitting two percent from it.
#
# The kick band decides, not the full spectrum, and the margin is measured. Across
# 184 records checked against Rekordbox's independent analysis there are 1074 cases
# where the slower relative is wrong and 3 where it is right, and on the kick band
# they separate: wrong tops out at 1.210, right starts at 1.323. On the full spectrum
# the same two groups overlap completely (0.880 to 1.097 against a 0.873 95th
# percentile), which is the same reason the low-pass exists at all — hats, claps and
# reverb tails vote on the beat and outvote the kick.
#
# So this only demotes a tempo when the kick band says the slower grid explains the
# kicks distinctly better, not merely as well. Three positive examples is thin
# evidence for the exact number; the thousand negatives below it are not.
OCTAVE_RELATIVES = (2.0, 1.5, 4.0 / 3.0)
OCTAVE_MARGIN = 1.27
# ...but every record behind that number sits between 120 and 140, and the margin
# was measured on the dotted and triplet relations. Applying it to plain doubling
# as well left slow material reading at twice its tempo, and the map says how much:
# against full-track Rekordbox analyses, 38.3% of records whose true tempo is 80-99
# came out doubled, and 20.6% of those at 60-79, against 1.2-1.5% above 120. Fast
# records are safe only by accident — their double lands past BPM_HI and is never
# scanned, so nothing had to decide.
#
# Doubling is a different question from a dotted or triplet relation, and it
# separates cleanly: folding at half the truth can only ever catch every other
# beat. Measured on synthetic material of both kinds, records we wrongly doubled
# score 0.99-1.06 for the slower grid — ambient and rock, where long low notes
# smear the envelope until both grids look alike — while genuine jungle at 174,
# drum and bass at 160 and house at 128 all score 0.51-0.55. The threshold sits in
# that gap, so a real fast record is never demoted and the smeared slow one is.
DOUBLE_MARGIN = 0.80


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


def _refine(env: np.ndarray, times: np.ndarray, around: float,
            tolerance: float) -> tuple[float, float, float, bool, float]:
    """The period near `around`, keeping the round number when it explains as well.

    Returns (bpm, score, phase, snapped, free_bpm). Scanning whole and half BPM alone
    is robust — those are the tempos records are made at — but taking that winner as
    the answer quantises every tempo to 0.5 BPM, and a quarter of a BPM is 337 ms of
    walk across a three-minute slot at 136, three times the quarter-beat where tight
    becomes a stumble. A record that genuinely sits at 133.30 has to say so.
    """
    m_score, m_phase = _fold(env, times, around)
    fine = np.arange(around - FINE_SPAN_BPM, around + FINE_SPAN_BPM + 1e-9,
                     FINE_STEP_BPM)
    f_bpm, f_score, f_phase = max(((bpm, *_fold(env, times, bpm)) for bpm in fine),
                                  key=lambda item: item[1])
    # A hundredth of a BPM apart is not a disagreement about tempo, it is noise in
    # the score; prefer the number somebody could have typed.
    snapped = m_score >= f_score * tolerance or abs(f_bpm - around) <= SNAP_ABS_BPM
    bpm, score, phase = ((around, m_score, m_phase) if snapped
                         else (f_bpm, f_score, f_phase))
    return bpm, score, phase, snapped, f_bpm


def _settle_relatives(bpm: float, env: np.ndarray, times: np.ndarray) -> float:
    """Demote a tempo to a slower relative when the kick band clearly prefers it.

    `env` is the arbiter — always the kick band, whichever view is being fitted — and
    `bpm` must already be refined, not the winner of the coarse scan. Comparing
    against a coarse candidate demotes records that are simply not at a whole tempo:
    Daphni's Waiting So Long sits at 133.30, the coarse grid offers 133.5, and 0.2 BPM
    across a whole record smears that reading down to 1.202 while the true tempo
    scores 3.496. A relative measured against the smear cleared the margin at 1.362
    and the record came out at 100. Against the real fit it is 0.47.
    """
    base = _fold(env, times, bpm)[0]
    if base <= 0:
        return bpm
    for div in sorted(OCTAVE_RELATIVES, reverse=True):
        cand = bpm / div
        if cand < BPM_LO:
            continue
        margin = DOUBLE_MARGIN if div == 2.0 else OCTAVE_MARGIN
        if _fold(env, times, cand)[0] >= margin * base:
            return cand
    return bpm


def _fit_one(y, sr, hop, kick_only, tolerance=MUSICAL_TOLERANCE,
             arbiter: tuple[np.ndarray, np.ndarray] | None = None) -> RigidGrid | None:
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
    bpm, score, phase, snapped, f_bpm = _refine(env, times, coarse_bpm, tolerance)

    # The window settles which end of the octave range this record lives in; the
    # dotted and triplet relations are settled on the whole record, by the kick band,
    # because a minute is not enough evidence and the full spectrum is the wrong
    # witness. COIDO's full-spectrum view scored its own answer 2.32 and the true
    # tempo 2.55 — the window had simply misled it.
    #
    # It runs on the refined tempo, not the coarse winner, and the record that
    # proved why is in `_settle_relatives`. A demotion then earns its own refinement,
    # because a phase and a period found around 195 say nothing about 130.
    a_env, a_times = arbiter if arbiter is not None else (env, times)
    slower = _settle_relatives(bpm, a_env, a_times)
    if slower != bpm:
        bpm, score, phase, snapped, f_bpm = _refine(env, times, slower, tolerance)

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
    # The kick band arbitrates the octave for both views, so it is computed once here
    # and handed to the full-spectrum fit as well. Without that the full view kept
    # answering 1.5x and 4/3x and, being marginally sharper, won the choice below:
    # 2.70 against 2.37 on Glue, 2.75 against 2.64 on Ahoona.
    arbiter = _onset_envelope(y, sr, hop, kick_only=True)
    fits = [f for f in (_fit_one(y, sr, hop, True, tolerance, arbiter),
                        _fit_one(y, sr, hop, False, tolerance, arbiter)) if f]
    if not fits:
        return None
    # A confident view beats a merely loud one: the kick band and the full spectrum
    # can disagree about whether the record has a fixed tempo at all.
    confident = [g for g in fits if g.confident]
    return max(confident or fits, key=lambda g: g.contrast)

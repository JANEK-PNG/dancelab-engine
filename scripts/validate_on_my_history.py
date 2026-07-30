#!/usr/bin/env python
"""Does the engine rank what Janek actually plays?

Rekordbox logs every performance: DjmdHistory sessions, DjmdSongHistory plays in
order. That is ground truth nobody had to record or align — his own choices, not
800 strangers' mixes whose seams the corpus alignment lost.

For each consecutive pair A -> B in a session, we score every candidate in the
library as a follow-up to A and ask where the track he really picked landed.
Percentile rank: 0.0 = the engine put it first, 0.5 = no better than chance,
1.0 = last. The metric is candidate-count independent, so no observation is
discarded for having a small pool.

HONEST SCOPE — read before quoting a number:
- Only the components with data are scored: harmonic relation, tempo, and the
  corpus priors. There are no per-frame features here, so mixability, energy and
  context contribute nothing. This measures the harmonic/tempo core, not the
  whole engine.
- The candidate pool is the whole library with usable metadata. In reality he
  played from a prepared crate, so the true pool was smaller and the engine's
  task here is harder than his was.
- History rows record when a track was loaded, so TrackNo order is taken as play
  order. Sessions shorter than MIN_TRACKS are skipped.
"""

from __future__ import annotations

import random
import statistics as st
from collections import defaultdict

MIN_TRACKS = 5
CONTROL_PAIRS = 600
CONTROL_SEED = 20260728


def _library(db, tables):
    """ContentID -> (bpm, camelot) for tracks the engine can actually score."""
    keys = {k.ID: k.ScaleName for k in db.session.query(tables.DjmdKey).all()}
    out = {}
    for row in db.session.query(tables.DjmdContent).all():
        bpm = float(row.BPM or 0)
        if bpm > 300:  # Rekordbox stores BPM x100
            bpm /= 100.0
        camelot = keys.get(row.KeyID)
        if bpm > 0 and camelot:
            out[str(row.ID)] = (bpm, camelot)
    return out


def _sessions(db, tables):
    """[(session_name, [ContentID in play order])] for real sets only."""
    by_history = defaultdict(list)
    for row in (db.session.query(tables.DjmdSongHistory)
                .order_by(tables.DjmdSongHistory.TrackNo).all()):
        by_history[row.HistoryID].append(str(row.ContentID))
    names = {h.ID: h.Name for h in db.session.query(tables.DjmdHistory).all()}
    return [(names.get(hid, str(hid)), ids)
            for hid, ids in by_history.items() if len(ids) >= MIN_TRACKS]


def _score(a, b, weights):
    """Engine score for A -> B from tempo, harmony and the corpus priors."""
    from dancelab.decision.harmonic import harmonic_compatibility
    from dancelab.decision.set_builder import bpm_score
    from dancelab.decision.corpus_priors import transition_prior_lift

    bpm_a, key_a = a
    bpm_b, key_b = b
    harm = harmonic_compatibility(key_a, key_b)
    base = 0.5 * harm.harmonic_compatibility_score + 0.5 * bpm_score(bpm_a, bpm_b)
    lift, _ = transition_prior_lift(harm.harmonic_relation, bpm_a, bpm_b)
    prior_weight = float(getattr(weights, "corpus_priors_weight", 0.0) or 0.0)
    return base * (lift ** prior_weight) if prior_weight else base


def main() -> None:
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    from dancelab.core.config import load_weights

    weights = load_weights("configs/descriptor_weights.yaml")
    db = Rekordbox6Database()
    lib = _library(db, tables)
    sessions = _sessions(db, tables)
    db.close()

    ranks: list[float] = []
    top1 = top10 = 0
    observations = 0
    for _name, ids in sessions:
        for current, actual in zip(ids, ids[1:]):
            if current not in lib or actual not in lib:
                continue
            pool = [t for t in lib if t != current]
            if len(pool) < 2:
                continue
            here = _score(lib[current], lib[actual], weights)
            better = sum(1 for t in pool
                         if t != actual and _score(lib[current], lib[t], weights) > here)
            rank = better / (len(pool) - 1)
            ranks.append(rank)
            observations += 1
            if rank == 0.0:
                top1 += 1
            if rank <= 0.10:
                top10 += 1

    print(f"sesje uzyte:        {len(sessions)}")
    print(f"obserwacje A->B:    {observations}")
    print(f"pula kandydatow:    {len(lib)} utworow z BPM+tonacja")
    if not observations:
        print("brak obserwacji — nie ma czego mierzyc")
        return
    print()
    print(f"sredni percentyl trafnego wyboru: {st.mean(ranks):.3f}   (0.5 = jak losowo, mniej = lepiej)")
    print(f"mediana:                          {st.median(ranks):.3f}")
    print(f"trafiony jako #1:                 {top1} ({100*top1/observations:.1f}%)")
    print(f"w gornych 10%:                    {top10} ({100*top10/observations:.1f}%)")
    print(f"losowo w gornych 10% byloby:      ~{0.10*observations:.0f} (10.0%)")

    # Control on the same procedure with random pairs. Ties in scoring pull the
    # rank slightly below 0.5, so without this the bias would be read as engine
    # skill. The signal is the gap between the two, not the distance from 0.5.
    rng = random.Random(CONTROL_SEED)
    ids = list(lib)
    control: list[float] = []
    for _ in range(CONTROL_PAIRS):
        current = rng.choice(ids)
        actual = rng.choice([t for t in ids if t != current])
        pool = [t for t in ids if t != current]
        here = _score(lib[current], lib[actual], weights)
        better = sum(1 for t in pool
                     if t != actual and _score(lib[current], lib[t], weights) > here)
        control.append(better / (len(pool) - 1))
    baseline = st.mean(control)
    print()
    print(f"KONTROLA (losowe pary, ta sama procedura): {baseline:.3f}")
    print(f"REALNY SYGNAL (kontrola - wybory Janka):   {baseline - st.mean(ranks):+.3f}")


if __name__ == "__main__":
    main()

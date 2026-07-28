"""The measured transition length must reach the engine.

scripts/corpus_priors.py measured a median transition of 94 beats across 6,144
real DJ transitions. core/phrasing rewarded windows near 8, 16 or 32 beats —
hand-picked phrase multiples — so a window at the measured median scored zero
for length. The engine was tuned against its own corpus.
"""

from dancelab.core.models import BeatGrid
from dancelab.core.phrasing import preferred_transition_beats, window_phrase_score
from dancelab.decision.corpus_priors import transition_length_beats


def _grid(bpm=120.0):
    # 120 BPM -> 0.5 s per beat, 300 beats of runway
    return BeatGrid(bpm=bpm, reliable=True,
                    beat_times_sec=[i * 0.5 for i in range(300)],
                    downbeats_sec=[i * 2.0 for i in range(75)])


def test_corpus_median_is_readable_from_the_priors_file():
    assert transition_length_beats() == 94


def test_preferred_lengths_include_the_measured_median():
    preferred = preferred_transition_beats()
    assert 94 in preferred, f"corpus median missing from {preferred}"
    # short blends stay legitimate — this adds a length, it does not replace them
    assert {8.0, 16.0, 32.0} <= set(preferred)


def test_a_transition_at_the_measured_median_is_no_longer_scored_worthless():
    grid = _grid()
    beat = 0.5
    short = window_phrase_score(0.0, 32 * beat, grid)      # 32 beats
    median = window_phrase_score(0.0, 94 * beat, grid)     # 94 beats, the real median
    assert median is not None and short is not None
    assert median > 0.5, f"measured-median transition scored {median}"

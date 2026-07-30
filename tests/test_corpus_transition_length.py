"""The corpus transition length is NOT trustworthy enough to shape scoring.

priors_v1.json carries transition_length_beats_median = 94 and it was briefly
wired into core/phrasing. Auditing the source field killed it: across 11,405
corpus transitions, 14.3% of transition_length_beats are negative (to -14526)
and 28.7% exceed four minutes (to 15771). The field measures the gap between two
aligned regions, not how long a DJ blended, and the median was taken over that.

These tests pin the retreat: the value stays readable and documented, but no
number derived from that field reaches the scoring path (ADR-005).
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


def test_the_contaminated_corpus_median_does_not_shape_scoring():
    """Readable for provenance, but never a scoring input until re-measured."""
    preferred = preferred_transition_beats()
    assert set(preferred) == {8.0, 16.0, 32.0}, (
        f"a corpus-derived length leaked into scoring: {preferred}"
    )

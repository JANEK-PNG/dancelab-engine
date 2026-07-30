"""The DJ's word about a seam has to reach the next proposal."""

from dancelab.decision.verdicts import VerdictStore


def test_an_unjudged_pair_is_left_alone():
    store = VerdictStore()
    assert store.score_adjustment("a", "b") == 0.0
    assert store.preferred_beats("a", "b", 64) == 64


def test_acceptance_lifts_and_rejection_sinks_that_pair():
    store = VerdictStore()
    store.record("a", "b", "yes")
    store.record("a", "c", "no")
    assert store.score_adjustment("a", "b") > 0
    assert store.score_adjustment("a", "c") < 0
    # and nothing leaks to other pairs — one listen is not a law
    assert store.score_adjustment("a", "d") == 0.0
    assert store.score_adjustment("b", "a") == 0.0


def test_the_latest_word_wins():
    store = VerdictStore()
    store.record("a", "b", "no")
    store.record("a", "b", "yes")
    assert store.score_adjustment("a", "b") > 0


def test_length_feedback_steps_through_renderable_phrases():
    store = VerdictStore()
    store.record("a", "b", "longer", beats=64)
    assert store.preferred_beats("a", "b", 64) == 96
    store.record("a", "b", "shorter", beats=96)
    assert store.preferred_beats("a", "b", 96) == 64


def test_length_feedback_does_not_decide_whether_to_play_the_pair():
    store = VerdictStore()
    store.record("a", "b", "longer", beats=64)
    assert store.score_adjustment("a", "b") == 0.0


def test_length_feedback_stops_at_the_ends_of_the_range():
    store = VerdictStore()
    store.record("a", "b", "shorter", beats=32)
    assert store.preferred_beats("a", "b", 32) == 32
    store.record("c", "d", "longer", beats=256)
    assert store.preferred_beats("c", "d", 256) == 256


def test_verdicts_survive_a_restart(tmp_path):
    path = tmp_path / "verdicts.json"
    store = VerdictStore()
    store.record("a", "b", "yes", beats=96)
    store.save(path)

    reloaded = VerdictStore.load(path)
    assert reloaded.score_adjustment("a", "b") > 0
    assert reloaded.latest_for("a", "b").beats == 96
    assert reloaded.counts()["yes"] == 1


def test_a_corrupt_store_does_not_block_the_session_or_get_overwritten(tmp_path):
    path = tmp_path / "verdicts.json"
    path.write_text("{ this is not json")
    store = VerdictStore.load(path)
    assert store.verdicts == []
    assert path.read_text().startswith("{ this")   # left on disk for inspection

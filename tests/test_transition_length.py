"""Stability runway — Janek's craft rule for how long a seam can carry a blend."""

from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track
from dancelab.decision.transition_length import (
    stability_runway_beats,
    suggest_transition_beats,
)


def _analysis(tid, rms_series, *, bpm=120.0, hop=0.5):
    """120 BPM -> 1 beat = 0.5 s = one frame; frame index == beat index."""
    return AnalysisResult(
        engine_version="t",
        track=Track(track_id=tid, bpm_estimate=bpm),
        beatgrid=BeatGrid(bpm=bpm, reliable=True),
        features=[FeatureFrame(track_id=tid, timestamp_sec=i * hop, rms=v)
                  for i, v in enumerate(rms_series)],
    )


def test_flat_material_runs_to_the_horizon():
    a = _analysis("a", [0.4] * 300)
    runway, why = stability_runway_beats(a, 0.0)
    assert runway == 256.0
    assert "horizon" in why


def test_a_drop_ends_the_runway_where_it_happens():
    # stable for 64 beats, then the level collapses (a break)
    a = _analysis("a", [0.4] * 64 + [0.05] * 100)
    runway, why = stability_runway_beats(a, 0.0)
    assert 60 <= runway <= 64
    assert "jump" in why or "drift" in why


def test_slow_drift_away_from_the_cue_level_also_ends_it():
    # no single jump, but the level walks away ~1.2%/beat
    series = [0.4 * (1 - 0.012 * i) for i in range(200)]
    runway, _ = stability_runway_beats(_analysis("a", series), 0.0)
    assert runway < 64


def test_no_tempo_or_no_frames_is_none_not_a_guess():
    no_tempo = AnalysisResult(engine_version="t", track=Track(track_id="x"),
                              features=[FeatureFrame(track_id="x", timestamp_sec=0.0, rms=0.4)])
    assert stability_runway_beats(no_tempo, 0.0)[0] is None
    no_frames = _analysis("y", [0.4] * 10)
    assert stability_runway_beats(no_frames, 100.0)[0] is None  # cue past all frames


def test_pair_length_is_governed_by_the_weaker_side():
    long_side = _analysis("a", [0.4] * 300)
    short_side = _analysis("b", [0.4] * 40 + [0.05] * 100)   # breaks near beat 40
    s = suggest_transition_beats(long_side, 0.0, short_side, 0.0)
    assert s.beats == 32                                     # largest option under ~40
    assert "B governs" in " ".join(s.reasoning)


def test_missing_side_yields_none_with_reasons():
    ok = _analysis("a", [0.4] * 300)
    broken = AnalysisResult(engine_version="t", track=Track(track_id="b"))
    s = suggest_transition_beats(ok, 0.0, broken, 0.0)
    assert s.beats is None
    assert any("B in:" in r for r in s.reasoning)


def test_thin_runway_still_suggests_the_shortest_option():
    a = _analysis("a", [0.4] * 10 + [0.05] * 50)   # ~10 beats of runway
    s = suggest_transition_beats(a, 0.0, a, 0.0)
    assert s.beats == 32
    assert "shortest option" in " ".join(s.reasoning)


def test_incoming_side_tolerates_growth():
    """Janek 2026-07-28: an incoming track that BUILDS is a classic mix-in.
    For side B only jumps and downward collapses end the runway."""
    # steady build: +2%/beat for 150 beats, no jumps, no collapse
    series = [0.1 * (1.02 ** i) for i in range(150)]
    grow = _analysis("b", series)
    out_r, _ = stability_runway_beats(grow, 0.0, side="outgoing")
    in_r, why = stability_runway_beats(grow, 0.0, side="incoming")
    assert out_r < 40                      # outgoing rule still calls this unstable
    assert in_r > 100, why                 # incoming rule rides the build


def test_incoming_collapse_after_growth_ends_the_runway():
    # builds for 60 beats, then breakdown: level falls to 30% of the peak
    series = [0.1 * (1.02 ** i) for i in range(60)]
    series += [series[-1] * 0.3] * 80
    r, why = stability_runway_beats(_analysis("b", series), 0.0, side="incoming")
    assert 55 <= r <= 62
    assert "collapse" in why or "jump" in why


def test_pair_uses_incoming_rule_for_b():
    stable = _analysis("a", [0.4] * 300)
    build = _analysis("b", [0.1 * (1.02 ** i) for i in range(150)] + [0.4] * 100)
    s = suggest_transition_beats(stable, 0.0, build, 0.0)
    assert s.beats is not None and s.beats >= 96   # no longer strangled to 32

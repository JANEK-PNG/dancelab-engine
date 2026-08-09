"""Set Builder v0.2 - harmonic rules, set-level energy shape, provenance."""

import pytest

from dancelab.core.config import load_weights
from dancelab.core.models import DANCELAB_SCHEMA_VERSION, AnalysisResult, FeatureFrame, Track
from dancelab.decision.set_builder import (
    MODEL_VERSION,
    bpm_score,
    build_set,
    harmonic_relation,
    parse_camelot,
)


@pytest.fixture
def weights():
    return load_weights("configs/descriptor_weights.yaml")


def track(tid, camelot, bpm, rms, *, title=None, artist=None, style=None):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=tid,
            title=title,
            artist=artist,
            key_estimate=camelot,
            bpm_estimate=bpm,
            style_label=style,
        ),
        features=[FeatureFrame(track_id=tid, timestamp_sec=float(t), rms=rms,
                               low_freq_energy_ratio=0.5, bass_energy=50.0) for t in range(30)],
    )


# ------------------------------------------------------------- harmonic rules


def test_parse_camelot():
    assert parse_camelot("8A") == (8, "A")
    assert parse_camelot("12B") == (12, "B")
    assert parse_camelot("bad") is None
    assert parse_camelot(None) is None


def test_harmonic_relations():
    # Sprint 5.1 taxonomy: exact / relative_major_minor / adjacent_same_mode / cautious / risky
    assert harmonic_relation("8A", "8A") == "exact"
    assert harmonic_relation("8A", "9A") == "adjacent_same_mode"
    assert harmonic_relation("8A", "7A") == "adjacent_same_mode"
    assert harmonic_relation("12A", "1A") == "adjacent_same_mode"   # wheel wrap
    assert harmonic_relation("8A", "8B") == "relative_major_minor"
    assert harmonic_relation("8A", "10A") == "cautious"
    assert harmonic_relation("8A", "3B") == "risky"
    assert harmonic_relation("8A", None) == "unknown"


def test_harmonic_distance2_is_symmetric():
    """AUD-H1: ±2 same-mode moves must classify identically — the old code
    tagged only +2 as cautious and let −2 fall through to risky."""
    from dancelab.decision.harmonic import harmonic_compatibility

    assert harmonic_relation("8A", "6A") == "cautious"   # −2 (energy drop)
    assert harmonic_relation("6A", "8A") == "cautious"   # +2 (energy lift)
    assert harmonic_relation("1A", "11A") == "cautious"  # −2 across the wrap
    down = harmonic_compatibility("8A", "6A", 0.9, 0.9)
    up = harmonic_compatibility("6A", "8A", 0.9, 0.9)
    assert down.harmonic_compatibility_score == up.harmonic_compatibility_score
    assert down.harmonic_risk == up.harmonic_risk


def test_bpm_score_halftime():
    assert bpm_score(128, 128) == 1.0       # same octave, no penalty
    assert bpm_score(128, 100) == 0.0       # too far
    # Same-octave preference: corpus shows DJs keep one tempo family in 99.1%
    # of transitions, so 140<->70 is technically syncable but strongly
    # dispreferred (SAME_OCTAVE_PREFERENCE=0.9 → 1.0 * 0.1).
    assert bpm_score(140, 70) == pytest.approx(0.1)


# ------------------------------------------------------------------- ordering


def test_build_set_orders_harmonically(weights):
    # a harmonic chain 8A->9A->10A plus a dissonant outlier
    tracks = [
        track("t_8a", "8A", 128, 0.20),
        track("t_9a", "9A", 128, 0.25),
        track("t_10a", "10A", 128, 0.30),
        track("t_diss", "3B", 128, 0.35),
    ]
    plan = build_set(tracks, weights, arc="build")
    assert plan.schema_version == DANCELAB_SCHEMA_VERSION
    assert plan.model_version == MODEL_VERSION
    assert len(plan.track_order) == 4
    assert set(plan.track_order) == {"t_8a", "t_9a", "t_10a", "t_diss"}
    # opener = lowest energy (t_8a); early transitions should be harmonic, not dissonant
    assert plan.track_order[0] == "t_8a"
    assert plan.transitions[0].harmonic_relation in (
        "exact", "adjacent_same_mode", "relative_major_minor", "cautious")
    # the risky (dissonant) track gets pushed toward the end
    assert plan.track_order.index("t_diss") >= 2


def test_energy_build_arc_rises(weights):
    tracks = [track(f"t{i}", "8A", 128, 0.1 + 0.05 * i) for i in range(5)]
    plan = build_set(tracks, weights, arc="build")
    energies = [next(f.rms for f in t.features)
                for tid in plan.track_order
                for t in tracks if t.track.track_id == tid]
    # build arc should not start at the highest-energy track
    assert energies[0] == min(energies)


def test_build_arc_uses_one_broad_climb_instead_of_repeated_large_drops(weights):
    tracks = [
        track("low_8a", "8A", 128, 0.10),
        track("high_9a", "9A", 128, 0.85),
        track("low_3b", "3B", 128, 0.20),
        track("high_10a", "10A", 128, 0.75),
        track("low_4b", "4B", 128, 0.30),
        track("high_11a", "11A", 128, 0.65),
        track("mid_5b", "5B", 128, 0.40),
        track("mid_12a", "12A", 128, 0.55),
    ]

    plan = build_set(tracks, weights, arc="build")
    energy_by_id = {
        analysis.track.track_id: analysis.features[0].rms
        for analysis in tracks
    }
    ordered = [energy_by_id[track_id] for track_id in plan.track_order]
    energy_range = max(ordered) - min(ordered)
    relative_deltas = [
        (right - left) / energy_range
        for left, right in zip(ordered, ordered[1:], strict=False)
    ]

    assert min(relative_deltas) >= -0.08
    assert not any("build arc relaxed" in warning for warning in plan.warnings)


def test_locked_tracks_can_break_build_shape_but_surface_a_warning(weights):
    tracks = [
        track("low", "8A", 128, 0.10),
        track("high", "9A", 128, 0.90),
        track("forced_low", "10A", 128, 0.20),
        track("middle", "11A", 128, 0.50),
    ]

    plan = build_set(
        tracks,
        weights,
        arc="build",
        locked_positions={2: "high", 3: "forced_low"},
    )

    assert plan.track_order[1:3] == ["high", "forced_low"]
    assert any("build arc relaxed" in warning for warning in plan.warnings)


def test_start_track_override(weights):
    tracks = [track("a", "8A", 128, 0.3), track("b", "9A", 128, 0.1)]
    plan = build_set(tracks, weights, start_track_id="a")
    assert plan.track_order[0] == "a"


def test_build_set_respects_locked_positions(weights):
    tracks = [
        track("a", "8A", 128, 0.10),
        track("b", "9A", 128, 0.20),
        track("c", "10A", 128, 0.30),
        track("locked", "8B", 128, 0.40),
    ]

    plan = build_set(tracks, weights, locked_positions={2: "locked"})

    assert plan.track_order[1] == "locked"
    assert plan.locked_positions == {2: "locked"}
    assert {t.from_track_id for t in plan.transitions} == set(plan.track_order[:-1])
    assert {t.to_track_id for t in plan.transitions} == set(plan.track_order[1:])


def test_build_set_pins_required_tracks_when_selecting_subset(weights):
    tracks = [
        track("opener", "8A", 128, 0.10),
        track("optional_a", "9A", 128, 0.20),
        track("must_play", "3B", 130, 0.30),
        track("optional_b", "10A", 128, 0.40),
        track("closer", "8B", 126, 0.50),
    ]

    plan = build_set(
        tracks,
        weights,
        target_track_count=3,
        locked_positions={1: "opener"},
        pinned_track_ids=["must_play"],
    )

    assert len(plan.track_order) == 3
    assert plan.track_order[0] == "opener"
    assert "must_play" in plan.track_order
    assert plan.pinned_track_ids == ["must_play"]
    assert len(plan.dropped_track_ids) == 2
    assert not set(plan.dropped_track_ids) & {"opener", "must_play"}


def test_build_set_prefers_unique_artists_when_library_allows_it(weights):
    tracks = [
        track("daphni_a", "8A", 128, 0.10, title="Daphni - Waiting So Long"),
        track("daphni_b", "8A", 128, 0.20, title="Daphni, Sofia Kourtesis - Unidos"),
        track("ploy", "8A", 128, 0.30, title="Ploy - When In Room"),
        track("mercy", "8A", 128, 0.40, title="Mercy System - If I Were You"),
    ]

    plan = build_set(tracks, weights, target_track_count=3)

    assert len(plan.track_order) == 3
    assert not {"daphni_a", "daphni_b"} <= set(plan.track_order)
    assert not any("repeated artist" in warning for warning in plan.warnings)


def test_build_set_separates_repeated_artists_when_repeat_is_unavoidable(weights):
    tracks = [
        track("daphni_a", "8A", 128, 0.10, title="Daphni - Waiting So Long"),
        track("daphni_b", "8A", 128, 0.20, title="Daphni, Sofia Kourtesis - Unidos"),
        track("ploy", "8A", 128, 0.30, title="Ploy - When In Room"),
        track("mercy", "8A", 128, 0.40, title="Mercy System - If I Were You"),
    ]

    plan = build_set(tracks, weights, target_track_count=4)

    assert {"daphni_a", "daphni_b"} <= set(plan.track_order)
    assert abs(plan.track_order.index("daphni_a") - plan.track_order.index("daphni_b")) > 1
    assert any("artist diversity relaxed" in warning for warning in plan.warnings)
    assert not any("adjacent repeated artist" in warning for warning in plan.warnings)


def test_build_set_planner_mode_prefers_harmonic_or_bpm(weights):
    tracks = [
        track("opener", "8A", 128, 0.10, title="Open Artist - Open"),
        track("key_fit", "8A", 168, 0.20, title="Key Artist - Wide Tempo"),
        track("bpm_fit", "3B", 128, 0.20, title="Tempo Artist - Risky Key"),
    ]

    harmonic_plan = build_set(
        tracks,
        weights,
        target_track_count=2,
        start_track_id="opener",
        planner_mode="harmonic",
    )
    bpm_plan = build_set(
        tracks,
        weights,
        target_track_count=2,
        start_track_id="opener",
        planner_mode="bpm",
    )

    assert harmonic_plan.planner_mode == "harmonic"
    assert harmonic_plan.track_order == ["opener", "key_fit"]
    assert "planner mode harmonic" in harmonic_plan.transitions[0].reasoning[0]
    assert bpm_plan.planner_mode == "bpm"
    assert bpm_plan.track_order == ["opener", "bpm_fit"]
    assert "planner mode bpm" in bpm_plan.transitions[0].reasoning[0]


def test_build_set_applies_style_and_bpm_brief(weights):
    tracks = [
        track("uk_a", "8A", 130, 0.20, style="uk-bass"),
        track("uk_b", "9A", 134, 0.22, style="bass"),
        track("hard", "10A", 142, 0.70, style="bass"),
        track("house", "11A", 124, 0.25, style="deep-house"),
    ]

    plan = build_set(
        tracks,
        weights,
        target_track_count=2,
        preferred_styles=["uk bass", "bass"],
        bpm_max=135,
    )

    assert set(plan.track_order) == {"uk_a", "uk_b"}
    assert "hard" in plan.dropped_track_ids
    assert any("style preference applied" in warning for warning in plan.warnings)
    assert any("BPM range applied" in warning for warning in plan.warnings)


def test_build_set_reports_constraint_conflicts(weights):
    tracks = [track("a", "8A", 128, 0.2), track("b", "9A", 128, 0.25)]

    with pytest.raises(ValueError, match="multiple positions"):
        build_set(tracks, weights, locked_positions={1: "a", 2: "a"})
    with pytest.raises(ValueError, match="exceed target_track_count"):
        build_set(tracks, weights, target_track_count=1, pinned_track_ids=["a", "b"])
    with pytest.raises(ValueError, match="unknown tracks"):
        build_set(tracks, weights, pinned_track_ids=["ghost"])
    with pytest.raises(ValueError, match="cannot exceed"):
        build_set([track("solo", "8A", 128, 0.2)], weights, target_track_count=2)


def test_single_track_is_honest(weights):
    plan = build_set([track("solo", "8A", 128, 0.2)], weights)
    assert plan.track_order == ["solo"]
    assert any("need >=2" in w for w in plan.warnings)


def test_dissonant_transition_warns(weights):
    tracks = [track("a", "8A", 128, 0.2), track("b", "3B", 128, 0.2)]
    plan = build_set(tracks, weights)
    assert plan.transitions[0].harmonic_relation == "risky"
    assert any("risky" in w for w in plan.transitions[0].warnings)


# ----------------------------------------------------------------- provenance


def test_set_plan_provenance(weights):
    plan = build_set([track("a", "8A", 128, 0.2), track("b", "9A", 128, 0.25)], weights)
    assert plan.provenance is not None
    assert plan.provenance.model_card_id == "set_builder_model_card_v0.2"
    assert "this is the best possible set order" in plan.provenance.cannot_claim


def test_json_roundtrip(weights):
    from dancelab.core.models import SetPlan
    plan = build_set([track("a", "8A", 128, 0.2), track("b", "9A", 128, 0.25)], weights)
    assert SetPlan.model_validate_json(plan.model_dump_json()) == plan


def test_build_set_deterministic_on_ties(weights, monkeypatch):
    """AUD-M5 / T-4: identical candidates (guaranteed score ties) must yield
    the same order regardless of hash seed — ties break by track_id."""
    tracks = [track(f"tie_{c}", "8A", 128, 0.2) for c in "dbca"]
    orders = {tuple(build_set(tracks, weights).track_order) for _ in range(5)}
    assert len(orders) == 1
    # tie-break is lexicographic by id after the opener
    order = orders.pop()
    assert list(order[1:]) == sorted(order[1:])


# ---------------------------------------------------------- §14 novelty


def _tie_library(n=8):
    # identical musical profile → every transition ties → ε tie-breaks decide
    return [track(f"t{i}", "8A", 126.0, 0.30) for i in range(n)]


def test_deterministic_mode_is_byte_stable(weights):
    lib = _tie_library()
    a = build_set(lib, weights)  # default novelty_mode="deterministic"
    b = build_set(lib, weights)
    assert a.track_order == b.track_order


def test_seeded_variation_reproducible_and_varies(weights):
    lib = _tie_library()
    one = build_set(lib, weights, novelty_mode="balanced", seed=1)
    one_again = build_set(lib, weights, novelty_mode="balanced", seed=1)
    two = build_set(lib, weights, novelty_mode="balanced", seed=2)
    assert one.track_order == one_again.track_order  # same seed → reproducible
    assert one.track_order != two.track_order        # different seed → varies
    # relevance intact: all-tie library, so any order has the same mean score
    assert one.mean_transition_score == two.mean_transition_score


def test_history_penalty_avoids_repeating_previous_sequence(weights):
    from dancelab.decision.history import fingerprint_plan

    lib = _tie_library()
    first = build_set(lib, weights, novelty_mode="balanced", seed=7)
    fp = fingerprint_plan(
        first.track_order, ctx_hash="ctx", seed=7, novelty_mode="balanced"
    )
    second = build_set(
        lib, weights, novelty_mode="balanced", seed=7, history=[fp]
    )
    # same seed, but history edge penalties push away from the previous run
    assert second.track_order != first.track_order


def test_tiny_library_returns_honest_identical_warning(weights):
    from dancelab.decision.history import fingerprint_plan

    lib = _tie_library(2)  # 2 tracks → only one possible order per opener
    first = build_set(lib, weights, novelty_mode="fresh", seed=1,
                      start_track_id="t0")
    fp = fingerprint_plan(first.track_order, ctx_hash="c", seed=1, novelty_mode="fresh")
    second = build_set(lib, weights, novelty_mode="fresh", seed=1,
                       start_track_id="t0", history=[fp])
    assert second.track_order == first.track_order
    assert any("library too small to vary" in w for w in second.warnings)


def test_pinned_tracks_exempt_from_overuse_penalty():
    from dancelab.decision.history import NoveltyContext, fingerprint_plan

    history = [
        fingerprint_plan([f"x{j}", "pinme"], ctx_hash="c", seed=None, novelty_mode="fresh")
        for j in range(6)  # "pinme" appeared 6× — over any allowance
    ]
    ctx = NoveltyContext.build(
        mode="fresh", history=history, seed=None, exempt_ids={"pinme"}
    )
    assert ctx.penalty("prev", "pinme") == 0.0          # §15.10 exemption
    ctx_no_pin = NoveltyContext.build(mode="fresh", history=history, seed=None)
    assert ctx_no_pin.penalty("prev", "pinme") > 0.0    # penalized without pin


def _no_features(tid, camelot, bpm):
    """A track the analysis produced no RMS frames for — energy is unknown."""
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=tid, key_estimate=camelot, bpm_estimate=bpm),
        features=[],
    )


def test_track_without_rms_does_not_anchor_the_energy_scale():
    """A missing measurement must not become the quietest track in the pool.

    Substituting 0.0 makes it the floor of e_min, which rescales every other
    track's normalized energy and, under a build arc, drags it toward the opener.
    """
    from dancelab.core.config import load_weights
    weights = load_weights("configs/descriptor_weights.yaml")
    tracks = [
        track("t1", "8A", 128, 0.40),
        track("t2", "9A", 129, 0.42),
        track("t3", "8B", 128, 0.44),
        _no_features("ghost", "9A", 128),
    ]
    plan = build_set(tracks, weights, arc="build")
    assert any("energy" in w.lower() and "ghost" in w for w in plan.warnings), plan.warnings
    assert plan.track_order[0] != "ghost", "unmeasured track was treated as the quietest"


def test_slot_przed_filarem_liczy_krawedz_mostowa(weights):
    """Badanie tripletów (09.08.2026): most potrzebuje drugiego brzegu.
    Slot bezpośrednio przed zablokowanym filarem ocenia kandydata za OBIE
    krawędzie (wejście z poprzednika + wejście W filar, wagi równe α=1).
    Tu: z 8A oba pomosty wychodzą tak samo dobrze (9A vs 7A — sąsiedzi),
    ale filar stoi w 10A: 9A wchodzi w niego gładko (sąsiad), 7A ryzykownie.
    Parowy builder nie widzi różnicy; mostowy musi wybrać 9A."""
    tracks = [
        track("start", "8A", 128.0, 0.5),
        track("most_dobry", "9A", 128.0, 0.5),
        track("most_slepy", "7A", 128.0, 0.5),
        track("filar", "10A", 128.0, 0.5),
    ]
    plan = build_set(tracks, weights, start_track_id="start",
                     locked_positions={3: "filar"})
    assert plan.track_order[0] == "start"
    assert plan.track_order[2] == "filar"
    assert plan.track_order[1] == "most_dobry", \
        "przed filarem wygrywa kandydat, który umie w filar wejść"

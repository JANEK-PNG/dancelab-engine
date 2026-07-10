"""Set Builder v0.1 — harmonic rules, ordering, provenance."""

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


def track(tid, camelot, bpm, rms):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=tid, key_estimate=camelot, bpm_estimate=bpm),
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
    assert bpm_score(128, 128) == 1.0
    assert bpm_score(140, 70) == 1.0        # half-time compatible
    assert bpm_score(128, 100) == 0.0       # too far


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
    assert plan.provenance.model_card_id == "set_builder_model_card_v0.1"
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

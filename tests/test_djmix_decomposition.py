from __future__ import annotations

from itertools import combinations
import math

import numpy as np
import pytest

from dancelab.validation.djmix.decomposition import (
    MeasuredLoss,
    ModelLosses,
    assess_crate_overlap,
    block_bootstrap_set_ids,
    combine_joint_losses,
    decompose_losses,
    evaluation_fingerprint,
    fixed_size_selection_nll,
    log_fixed_size_partition,
    random_selection_baseline_nll,
)


def _losses(
    *,
    l0: float = 100.0,
    lh: float = 80.0,
    le: float = 70.0,
    lhe: float = 60.0,
    lhei: float = 55.0,
    fingerprint: str = "fixture-hash",
    scope: str = "ordering-given-crate",
) -> ModelLosses:
    return ModelLosses.from_values(
        baseline=l0,
        handcrafted=lh,
        embedding=le,
        combined=lhe,
        combined_dj=lhei,
        evaluation_hash=fingerprint,
        scope=scope,
    )


def test_shapley_decomposition_is_order_independent_and_sums_to_one():
    result = decompose_losses(_losses())

    assert result.c_rule == pytest.approx(0.15)
    assert result.c_similarity == pytest.approx(0.25)
    assert result.identity == pytest.approx(0.05)
    assert result.residual == pytest.approx(0.55)
    assert result.total == pytest.approx(1.0)
    assert result.flags == ()


def test_negative_out_of_sample_contributions_are_preserved_and_flagged():
    result = decompose_losses(
        _losses(lh=110.0, le=90.0, lhe=105.0, lhei=110.0),
    )

    assert result.c_rule < 0.0
    assert result.identity < 0.0
    assert any(flag.startswith("LH>L0") for flag in result.flags)
    assert "C_rule<0: negative out-of-sample contribution" in result.flags
    assert "I<0: DJ effect does not generalize" in result.flags
    assert result.total == pytest.approx(1.0)


def test_positive_dj_effect_with_low_overlap_is_not_labeled_as_identity():
    result = decompose_losses(_losses(), q_d=0.1)

    assert result.identity > 0.0
    assert any("not separable from crate" in flag for flag in result.flags)


def test_decomposition_rejects_only_invalid_numeric_baseline_and_hash_mismatch():
    with pytest.raises(ValueError, match="positive"):
        decompose_losses(_losses(l0=0.0))
    with pytest.raises(ValueError, match="finite"):
        MeasuredLoss(math.inf, "fixture")

    losses = _losses()
    mismatched = ModelLosses(
        baseline=losses.baseline,
        handcrafted=MeasuredLoss(losses.handcrafted.value, "different"),
        embedding=losses.embedding,
        combined=losses.combined,
        combined_dj=losses.combined_dj,
        scope=losses.scope,
    )
    with pytest.raises(ValueError, match="same evaluation_hash"):
        decompose_losses(mismatched)


def test_joint_losses_require_and_preserve_one_evaluation_universe():
    selection = _losses(
        l0=20.0,
        lh=18.0,
        le=17.0,
        lhe=16.0,
        lhei=15.0,
        scope="selection",
    )
    ordering = _losses(scope="ordering-given-crate")

    joint = combine_joint_losses(selection, ordering)

    assert joint.values() == {
        "L0": 120.0,
        "LH": 98.0,
        "LE": 87.0,
        "LHE": 76.0,
        "LHEI": 70.0,
    }
    assert joint.evaluation_hash == "fixture-hash"
    with pytest.raises(ValueError, match="same evaluation_hash"):
        combine_joint_losses(selection, _losses(fingerprint="other"))


def test_evaluation_fingerprint_is_canonical_and_rejects_nan():
    left = evaluation_fingerprint({"sets": ["a"], "pool": {"b": 2, "a": 1}})
    right = evaluation_fingerprint({"pool": {"a": 1, "b": 2}, "sets": ["a"]})

    assert left == right
    with pytest.raises(ValueError, match="finite"):
        evaluation_fingerprint({"loss": math.nan})


def test_log_partition_matches_brute_force_subset_enumeration():
    log_weights = np.log(np.array([1.0, 2.0, 4.0, 8.0]))
    selection_size = 2
    brute_force = sum(
        math.prod(math.exp(log_weights[index]) for index in subset)
        for subset in combinations(range(len(log_weights)), selection_size)
    )

    actual = log_fixed_size_partition(log_weights, selection_size)

    assert actual == pytest.approx(math.log(brute_force))


def test_fixed_size_selection_nll_is_exact_and_stable_for_large_scores():
    assert fixed_size_selection_nll([1000.0, 1000.0, 1000.0], [0, 1]) == pytest.approx(
        math.log(3.0)
    )
    assert random_selection_baseline_nll(4, 2) == pytest.approx(math.log(6.0))
    with pytest.raises(ValueError, match="duplicates"):
        fixed_size_selection_nll([0.0, 1.0], [0, 0])


def test_audio_space_overlap_separates_similar_and_distant_crates():
    report = assess_crate_overlap(
        {
            "dj-a": np.array([[0.0, 0.0], [0.1, 0.0]]),
            "dj-b": np.array([[0.02, 0.0], [0.12, 0.0]]),
            "dj-c": np.array([[10.0, 0.0], [10.1, 0.0]]),
        },
        set_counts={"dj-a": 2, "dj-b": 3, "dj-c": 1},
    )

    assert report.q_by_dj["dj-a"] == pytest.approx(1.0)
    assert report.q_by_dj["dj-b"] == pytest.approx(1.0)
    assert report.q_by_dj["dj-c"] == pytest.approx(0.0)
    assert report.weighted_q == pytest.approx(5 / 6)


def test_audio_space_overlap_marks_unidentifiable_crates_instead_of_guessing():
    report = assess_crate_overlap(
        {
            "single": np.array([[0.0, 0.0]]),
            "collapsed": np.array([[1.0, 1.0], [1.0, 1.0]]),
        }
    )

    assert report.q_by_dj == {"single": None, "collapsed": None}
    assert report.weighted_q is None
    assert len(report.warnings) >= 2


def test_bootstrap_samples_whole_set_blocks_deterministically():
    first = block_bootstrap_set_ids(("set-a", "set-b", "set-c"), replicates=4, seed=7)
    second = block_bootstrap_set_ids(("set-a", "set-b", "set-c"), replicates=4, seed=7)

    assert first == second
    assert len(first) == 4
    assert all(len(replica) == 3 for replica in first)
    assert all(set(replica) <= {"set-a", "set-b", "set-c"} for replica in first)

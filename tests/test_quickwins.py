"""Sprint-3 quick wins: BPM octave-fold, robust normalization, extra validation
metrics (kappa/tau/spearman), per-formula-term metadata (no anonymous variables)."""

import numpy as np
import pytest

from dancelab.core.normalization import minmax_01, robust_01, robust_norm_0_100
from dancelab.core.provenance import load_formula_terms
from dancelab.preprocessing.beatgrid import _refit_beats, octave_fold_factor
from dancelab.validation.dj_decision_metrics import (
    cohen_kappa,
    kendall_tau,
    spearman_rho,
)


# ------------------------------------------------------------- octave folding


def test_octave_fold_doubles_half_time():
    assert octave_fold_factor(62.0, 90.0, 180.0) == 2.0   # house 124 tracked as 62
    assert octave_fold_factor(88.0, 90.0, 180.0) == 2.0   # dnb 176 tracked as 88


def test_octave_fold_halves_double_time():
    assert octave_fold_factor(280.0, 90.0, 180.0) == 0.5  # → 140


def test_octave_fold_leaves_in_range():
    assert octave_fold_factor(128.0, 90.0, 180.0) == 1.0
    assert octave_fold_factor(174.0, 90.0, 180.0) == 1.0  # real DnB tempo stays


def test_octave_fold_degenerate_range():
    assert octave_fold_factor(120.0, 180.0, 90.0) == 1.0  # bad range → no-op
    assert octave_fold_factor(0.0, 90.0, 180.0) == 1.0


def test_refit_beats_subdivides_and_preserves_phase():
    beats = np.array([0.0, 1.0, 2.0, 3.0])  # 60 BPM tracked; fold ×2 → 120 BPM
    refit = _refit_beats(beats, 2.0)
    assert np.allclose(refit, [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    assert refit[0] == beats[0] and refit[-1] == beats[-1]  # phase kept


def test_refit_beats_decimates():
    beats = np.arange(0.0, 8.0, 1.0)  # fold ×0.5 → keep every 2nd
    assert np.allclose(_refit_beats(beats, 0.5), [0.0, 2.0, 4.0, 6.0])


# ---------------------------------------------------------------- normalization


def test_minmax_and_robust_01():
    z = np.array([0.0, 5.0, 10.0])
    assert np.allclose(minmax_01(z), [0.0, 0.5, 1.0])
    assert np.allclose(robust_01(z), [0.0, 0.5, 1.0], atol=0.05)


def test_robust_ignores_outlier():
    # realistic time series: ~100 values in [1,4] plus a few extreme spikes.
    # Robust P5–P95 excludes the spikes; min-max lets them crush the scale.
    rng = np.random.default_rng(0)
    base = rng.uniform(1.0, 4.0, size=100)
    z = np.concatenate([base, [1000.0, 1000.0, 1000.0]])
    mm = minmax_01(z)
    rb = robust_01(z)
    # a mid-range value ~2.5 → near zero under min-max, meaningful under robust
    idx = int(np.argmin(np.abs(base - 2.5)))
    assert mm[idx] < 0.01
    assert rb[idx] > 0.2


def test_constant_input_is_neutral():
    z = np.array([7.0, 7.0, 7.0])
    assert np.allclose(minmax_01(z), 0.5)
    assert np.allclose(robust_01(z), 0.5)
    assert np.allclose(robust_norm_0_100(z), 50.0)


# ------------------------------------------------------------ validation metrics


def test_kendall_tau_perfect_and_reverse():
    assert kendall_tau([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert kendall_tau([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_with_ties():
    r = spearman_rho([1, 2, 2, 3], [1, 2, 2, 3])
    assert r == pytest.approx(1.0)


def test_cohen_kappa_agreement_and_chance():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == pytest.approx(1.0)
    # total disagreement → negative kappa
    assert cohen_kappa(["a", "a", "b", "b"], ["b", "b", "a", "a"]) < 0
    assert cohen_kappa([], []) is None
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None  # p_e == 1 → undefined


def test_metrics_none_on_short_input():
    assert kendall_tau([1, 2], [1, 2]) is None
    assert spearman_rho([1], [1]) is None


# ---------------------------------------------------------------- formula terms


def test_every_transition_component_has_a_term():
    from dancelab.decision.transition_windows import (
        PENALTY_COMPONENTS,
        POSITIVE_COMPONENTS,
    )

    terms = load_formula_terms("configs/formula_terms.yaml")
    for key in (*POSITIVE_COMPONENTS, *PENALTY_COMPONENTS):
        assert key in terms, f"transition component '{key}' has no formula-term metadata"
        assert terms[key].cannot_claim and terms[key].formula_symbol


def test_every_mixability_component_has_a_term():
    from dancelab.decision.mixability import COMPONENTS

    terms = load_formula_terms("configs/formula_terms.yaml")
    for key in COMPONENTS:
        assert key in terms, f"mixability component '{key}' has no formula-term metadata"


def test_formula_terms_endpoint():
    from fastapi.testclient import TestClient

    from dancelab.api.main import app

    body = TestClient(app).get("/formula-terms").json()
    assert "phrase" in body
    assert body["phrase"]["scientific_status"] == "candidate"
    assert body["phrase"]["cannot_claim"]

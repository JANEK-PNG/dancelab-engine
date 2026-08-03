"""Brzmienie w ocenie przejścia — i granice, w których wolno mu działać."""

import numpy as np
import pytest

from dancelab.decision.sound_affinity import blend, cosine_affinity


def test_identical_sound_is_full_affinity():
    v = [0.3, -0.7, 0.1, 0.9]
    assert cosine_affinity(v, v) == pytest.approx(1.0, abs=1e-6)


def test_opposite_sound_is_zero_not_negative():
    # kosinus żyje w [-1,1], ocena przejścia w [0,1] — bez przeskalowania
    # przeciwne brzmienie wnosiłoby ujemny wkład i wywracało sumę wag
    v = [1.0, 0.0, 0.0]
    assert cosine_affinity(v, [-1.0, 0.0, 0.0]) == pytest.approx(0.0, abs=1e-6)


def test_missing_embedding_is_none_not_zero():
    """ADR-005 w praktyce: nieznane wychodzi jako None, nigdy jako 0.

    Zero znaczyłoby „brzmi maksymalnie niepodobnie" i karałoby każdy utwór
    bez osadzenia. W bibliotece, gdzie CLAP ma tylko część płyt, to
    przesunęłoby cały ranking na te nieliczne, które go mają.
    """
    assert cosine_affinity(None, [1.0, 0.0]) is None
    assert cosine_affinity([1.0, 0.0], None) is None
    assert cosine_affinity([0.0, 0.0], [1.0, 0.0]) is None      # wektor zerowy
    assert cosine_affinity([1.0, 0.0], [1.0, 0.0, 0.0]) is None  # inny wymiar


def test_without_affinity_the_core_score_passes_through_untouched():
    score, note = blend(0.42, None, weight=0.6)
    assert score == 0.42
    assert "unavailable" in note


def test_weight_zero_leaves_the_core_alone():
    score, _ = blend(0.42, 0.99, weight=0.0)
    assert score == 0.42


def test_affinity_moves_the_score_toward_itself():
    low, _ = blend(0.8, 0.0, weight=0.5)
    high, _ = blend(0.8, 1.0, weight=0.5)
    assert low < 0.8 < high
    assert low == pytest.approx(0.4)
    assert high == pytest.approx(0.9)


def test_the_blend_stays_inside_the_score_range():
    for core in (0.0, 0.5, 1.0):
        for aff in (0.0, 0.5, 1.0):
            s, _ = blend(core, aff, weight=0.6)
            assert 0.0 <= s <= 1.0


def test_the_reason_names_the_weight_so_a_score_can_be_audited():
    _, note = blend(0.5, 0.75, weight=0.6)
    assert "0.75" in note and "0.60" in note


def test_the_scorer_uses_sound_only_in_smart_mode():
    """Czyste tryby harmonic/bpm to jawna wola DJ-a i mają nią zostać.

    To ta sama granica, którą trzymają lifty korpusu: user, który prosi
    o „tylko harmonia", nie ma dostać po cichu wmieszanego brzmienia.
    """
    from dancelab.core.config import load_config, load_weights
    from dancelab.core.models import AnalysisResult, Track
    from dancelab.decision.set_builder import transition_score

    weights = load_weights(load_config("configs/default.yaml").weights_file)
    weights = weights.model_copy(update={"sound_affinity_weight": 0.6})

    def t(tid, key, bpm, emb):
        return AnalysisResult(engine_version="t", track=Track(
            track_id=tid, key_estimate=key, key_confidence=0.9,
            bpm_estimate=bpm, sound_embedding=emb))

    a = t("a", "8A", 124.0, [1.0, 0.0, 0.0])
    near = t("b", "8A", 124.0, [1.0, 0.0, 0.0])
    far = t("c", "8A", 124.0, [-1.0, 0.0, 0.0])

    s_near, _, why = transition_score(a, near, weights, "build", 0.1, 0.1, 0.2)
    s_far, _, _ = transition_score(a, far, weights, "build", 0.1, 0.1, 0.2)
    assert s_near > s_far, "brzmienie ma wpływać w trybie smart"
    assert any("sound affinity" in line for line in why)

    h_near, _, _ = transition_score(a, near, weights, "build", 0.1, 0.1, 0.2,
                                    planner_mode="harmonic")
    h_far, _, _ = transition_score(a, far, weights, "build", 0.1, 0.1, 0.2,
                                   planner_mode="harmonic")
    assert h_near == h_far, "tryb harmonic nie ma słyszeć brzmienia"


def test_a_library_without_embeddings_scores_exactly_as_before():
    """Włączenie wagi nie może ruszyć wyniku tam, gdzie nie ma osadzeń."""
    from dancelab.core.config import load_config, load_weights
    from dancelab.core.models import AnalysisResult, Track
    from dancelab.decision.set_builder import transition_score

    base = load_weights(load_config("configs/default.yaml").weights_file)
    loud = base.model_copy(update={"sound_affinity_weight": 0.6})

    def t(tid, key, bpm):
        return AnalysisResult(engine_version="t", track=Track(
            track_id=tid, key_estimate=key, key_confidence=0.9, bpm_estimate=bpm))

    a, b = t("a", "8A", 124.0), t("b", "9A", 126.0)
    off, _, _ = transition_score(a, b, base, "build", 0.1, 0.12, 0.2)
    on, _, _ = transition_score(a, b, loud, "build", 0.1, 0.12, 0.2)
    assert off == on

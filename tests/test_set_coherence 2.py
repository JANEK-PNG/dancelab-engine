"""Whole-set coherence report (compute_set_coherence + SetPlan.set_coherence)."""

from __future__ import annotations

from dancelab.decision.set_builder import compute_set_coherence


def test_coherent_build_scores_higher_than_chaotic():
    order = ["a", "b", "c", "d"]
    # rising energy, tight tempo → coherent build
    energy = {"a": 0.1, "b": 0.3, "c": 0.6, "d": 0.9}
    tight_bpm = {"a": 128.0, "b": 129.0, "c": 130.0, "d": 131.0}
    target = [0.1, 0.37, 0.63, 0.9]  # a matching build target
    good = compute_set_coherence(
        order, arc="build", energy=energy, e_min=0.1, e_range=0.8,
        target_profile=target, bpm_by_id=tight_bpm,
    )
    # jagged energy + wild tempo → incoherent
    chaotic_energy = {"a": 0.9, "b": 0.1, "c": 0.8, "d": 0.2}
    wild_bpm = {"a": 128.0, "b": 90.0, "c": 175.0, "d": 100.0}
    bad = compute_set_coherence(
        order, arc="build", energy=chaotic_energy, e_min=0.1, e_range=0.8,
        target_profile=target, bpm_by_id=wild_bpm,
    )
    assert good.overall > bad.overall
    assert good.arc_adherence > bad.arc_adherence
    assert good.tempo_continuity > bad.tempo_continuity
    assert 0.0 <= bad.overall <= 1.0 and 0.0 <= good.overall <= 1.0


def test_coherence_none_for_trivial_set():
    assert compute_set_coherence(
        ["a"], arc="build", energy={"a": 0.5}, e_min=0.0, e_range=1.0,
        target_profile=[0.5], bpm_by_id={"a": 128.0},
    ) is None

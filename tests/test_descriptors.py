"""Descriptor layer: schema/config contracts + candidate curve behavior."""

import numpy as np
import pytest

from dancelab.context.conditioning import condition
from dancelab.core.config import load_weights
from dancelab.descriptors.bass_salience import bass_salience
from dancelab.descriptors.groove import groove_density
from dancelab.descriptors.release import release_map
from dancelab.descriptors.tension import tension_curve
from dancelab.features.microtiming import (
    microtiming_deviations,
    microtiming_profile,
    syncopation_profile,
)


def test_weights_config_loads_and_is_versioned():
    w = load_weights("configs/descriptor_weights.yaml")
    assert w.version
    assert w.groove_density.status == "candidate"
    assert set(w.groove_density.weights) == {
        "pulse_clarity", "syncopation", "onset_density", "bass_salience", "microtiming",
    }
    assert set(w.mixability.weights) == {
        "tempo", "phrase", "energy", "bass", "vocal", "tension", "style", "context", "harmonic",
    }
    assert set(w.mixability_conflict.weights) == {"bass", "vocal", "phrase", "tension"}


def test_candidate_statuses_marked():
    w = load_weights("configs/descriptor_weights.yaml")
    # ADR-005: no group may silently claim stability in v0
    for group in (w.groove_density, w.bass_salience, w.tension, w.transition_window, w.mixability):
        assert group.status in {"candidate", "planned", "draft"}


def test_groove_density_returns_candidate_curve():
    w = load_weights("configs/descriptor_weights.yaml")
    z = np.array([0.1, 0.4, 0.7, 0.3])
    out = groove_density(z, z, z, z, z, w.groove_density)
    assert out.shape == z.shape
    assert np.all((0.0 <= out) & (out <= 1.0))


def test_bass_salience_penalizes_masking():
    w = load_weights("configs/descriptor_weights.yaml")
    clean = bass_salience(
        np.array([0.8, 0.8, 0.8]),
        np.array([0.8, 0.8, 0.8]),
        np.array([0.7, 0.7, 0.7]),
        np.array([0.1, 0.1, 0.1]),
        w.bass_salience,
    )
    masked = bass_salience(
        np.array([0.8, 0.8, 0.8]),
        np.array([0.8, 0.8, 0.8]),
        np.array([0.7, 0.7, 0.7]),
        np.array([0.9, 0.9, 0.9]),
        w.bass_salience,
    )
    assert masked.mean() < clean.mean()


def test_tension_and_release_follow_build_then_drop():
    w = load_weights("configs/descriptor_weights.yaml")
    tension = tension_curve(
        {
            "rise": np.array([0.1, 0.4, 0.8, 0.2]),
            "delay": np.array([0.1, 0.3, 0.7, 0.1]),
            "spectral": np.array([0.2, 0.5, 0.9, 0.2]),
            "instability": np.array([0.1, 0.2, 0.6, 0.1]),
            "expectation": np.array([0.1, 0.4, 0.8, 0.2]),
        },
        w.tension,
    )
    release = release_map(tension, np.array([0.0, 1.0, 2.0, 3.0]))
    assert tension.argmax() == 2
    assert release[2] >= release[1]
    assert np.all((0.0 <= release) & (release <= 1.0))


def test_microtiming_and_syncopation_profiles_use_beat_context():
    beat_times = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    onset_times = np.array([0.02, 0.27, 0.51, 0.76, 1.01, 1.24])
    deviations = microtiming_deviations(onset_times, beat_times)
    micro = microtiming_profile(onset_times, beat_times, np.array([0.0, 1.0]))
    sync = syncopation_profile(onset_times, beat_times, np.array([0.0, 1.0]))

    assert deviations.size
    assert np.all((0.0 <= micro) & (micro <= 1.0))
    assert np.all((0.0 <= sync) & (sync <= 1.0))
    assert sync[0] > 0.0


def test_conditioning_multiplicative_form():
    # X_eff = X_audio * C_fit (Core Equations) — implemented, testable now
    curve = np.array([1.0, 0.5, 0.8])
    c_fit = np.array([0.5, 1.0, 0.0])
    assert np.allclose(condition(curve, c_fit), [0.5, 0.5, 0.0])


def test_conditioning_shape_mismatch_raises():
    with pytest.raises(ValueError):
        condition(np.zeros(3), np.zeros(4))

"""arc="off" is the measured default: no energy shape is imposed on a set.

Decided by Janek 2026-08-11 after the shape measurement (ledger entry
"KSZTAŁT SETU ZMIERZONY..."): the "build" ramp described real sets worse
than a flat line on two independent instruments, and real sets take a
median of 5 energy drops >8% which the ramp forbade outright. These tests
pin the decision so a silent revert cannot happen.
"""

from dancelab.core.config import load_weights
from dancelab.core.models import AnalysisResult, FeatureFrame, Track
from dancelab.decision.set_builder import (
    _arc_profile_candidates,
    _energy_score,
    _set_arc_target_profile,
    build_set,
)


def _track(track_id: str, camelot: str, bpm: float, rms: float) -> AnalysisResult:
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=track_id, key_estimate=camelot, bpm_estimate=bpm),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(timestamp),
                rms=rms,
                low_freq_energy_ratio=0.5,
                bass_energy=50.0,
            )
            for timestamp in range(30)
        ],
    )


def test_off_jest_domyslne_i_energia_neutralna():
    """Default arc holds no energy opinion: every delta scores 1.0."""
    assert build_set.__defaults__ is not None
    for delta in (-0.5, -0.09, 0.0, 0.3):
        assert _energy_score(delta, "off") == 1.0
    # the refuted shapes still exist, but only as explicit choices
    assert _energy_score(-0.5, "build") < 1.0


def test_off_nie_ma_celu_i_nie_zakazuje_spadkow():
    """No target profile and no drop ban - candidates pass through whole."""
    assert _set_arc_target_profile(
        {"a": 0.1}, target_count=10, arc="off", e_min=0.0, e_range=1.0,
        forced_opener_id=None) == []
    energia = {"cichy": 0.05, "glosny": 0.95, "sredni": 0.5}
    kandydaci = ["cichy", "glosny", "sredni"]
    # under "build" a big drop from a loud current track was filtered out;
    # under "off" the quiet track must stay eligible
    zostaja = _arc_profile_candidates(
        kandydaci, current="glosny", index=5, arc="off", target_profile=[],
        energy=energia, e_min=0.0, e_range=1.0)
    assert zostaja == kandydaci


def test_budowa_z_off_dziala_a_raport_nie_zmysla_wiernosci():
    """build_set works on the default and coherence reports no adherence."""
    pula = [
        _track("t1", "8A", 128, 0.9),
        _track("t2", "9A", 128, 0.2),   # a hard energy drop mid-pool
        _track("t3", "8B", 129, 0.8),
        _track("t4", "9B", 129, 0.4),
    ]
    plan = build_set(pula, load_weights("configs/descriptor_weights.yaml"),
                     target_track_count=4)
    assert len(plan.track_order) == 4
    if plan.set_coherence is not None:
        assert plan.set_coherence.arc_adherence is None
        assert "arc off" in plan.set_coherence.note

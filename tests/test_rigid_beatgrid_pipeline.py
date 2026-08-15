"""Siatka sztywna w pipelinie analizy — i granice, których nie wolno przekroczyć.

Dług z 2026-07-30: `core/rigid_grid` i `core/tempo_refine` istniały, ale pipeline
analizy ich NIE używał — korzystały z nich tylko skrypty renderu. Te testy
pilnują, że produkt dostaje lepszą siatkę i że przy okazji nie zaczyna
twierdzić rzeczy, których nie zmierzył.
"""

from __future__ import annotations

import numpy as np
import pytest

# Ten plik potrzebuje profilu [audio]. Bez tej bramki wywracał ZBIERANIE
# testów w bezdźwiękowym profilu CI, czyli padał nie jeden test, tylko
# cały plik. Wzorzec taki sam jak w test_preprocessing i test_beatgrid.
pytest.importorskip("librosa")

from dancelab.core.audio_types import AudioSignal
from dancelab.preprocessing.rigid_beatgrid import estimate_beatgrid_best

SR = 22050


def _click_track(bpm: float, seconds: float = 24.0, sr: int = SR) -> AudioSignal:
    """Perkusja na sztywnym tempie — dokładnie ten materiał, pod który jest fold."""
    n = int(seconds * sr)
    y = np.zeros(n, dtype=np.float32)
    period = 60.0 / bpm
    rng = np.random.default_rng(7)
    t = 0.0
    while t < seconds:
        i = int(t * sr)
        env = np.exp(-np.linspace(0, 12, int(0.05 * sr)))
        click = (rng.standard_normal(env.size) * env).astype(np.float32)
        y[i: i + click.size] += click[: max(0, n - i)]
        t += period
    y += 0.001 * rng.standard_normal(n).astype(np.float32)
    return AudioSignal(samples=y, sample_rate=sr)


def test_rigid_grid_used_and_tempo_correct():
    sig = _click_track(128.0)
    g = estimate_beatgrid_best(sig, rigid=True)
    assert "beatgrid_source=rigid" in g.diagnostic_flags, g.diagnostic_flags
    assert g.bpm == pytest.approx(128.0, abs=0.6)
    assert len(g.beat_times_sec) > 20


def test_rigid_path_does_not_claim_bar_phase():
    """Fold ustala fazę BITU, nie TAKTU. Gdyby to kiedyś zaczęło zwracać True,
    eksport fraz i hot cue dostałyby zgodę, której nikt nie zmierzył."""
    g = estimate_beatgrid_best(_click_track(124.0), rigid=True)
    assert g.downbeat_phase_verified is False


def test_rigid_path_does_not_invent_quality_score():
    """Kontrast to nie prawdopodobieństwo. Zamiana jednego na drugie byłaby
    liczbą wyglądającą na zmierzoną (ADR-005) — ma zostać None, a kontrast
    ma być czytelny w diagnostyce."""
    g = estimate_beatgrid_best(_click_track(130.0), rigid=True)
    assert g.quality_score is None
    assert any(f.startswith("rigid_contrast=") for f in g.diagnostic_flags)


def test_switch_off_falls_back_and_says_so():
    g = estimate_beatgrid_best(_click_track(126.0), rigid=False)
    assert "beatgrid_source=tracker" in g.diagnostic_flags
    assert "rigid_grid_disabled" in g.diagnostic_flags


def test_unfittable_material_falls_back_with_reason():
    """Szum nie ma tempa. Ma wrócić tracker Z POWODEM, a nie sztywna siatka
    zmyślona z niczego."""
    rng = np.random.default_rng(3)
    n = int(20 * SR)
    sig = AudioSignal(samples=rng.standard_normal(n).astype(np.float32) * 0.1,
                      sample_rate=SR)
    g = estimate_beatgrid_best(sig, rigid=True)
    assert "beatgrid_source=tracker" in g.diagnostic_flags
    assert any("rigid_" in f for f in g.diagnostic_flags), g.diagnostic_flags

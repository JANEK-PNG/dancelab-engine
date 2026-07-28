"""Mixability Engine v0.1 — tests per ticket: tempo fit, bass risk,
pair window scoring, JSON schema, API, edge cases (no key, very different BPM)."""

import pytest

import dancelab.decision.mixability as mixability_module
from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    ContextProfile,
    FeatureFrame,
    MixabilityInput,
    MixabilityOutput,
    ModelStatus,
    Segment,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.decision.mixability import (
    MODEL_VERSION,
    bass_conflict,
    compute_mixability,
    pair_window_score,
    precompute_mixability_inputs,
    tempo_fit,
)


@pytest.fixture
def weights():
    return load_weights("configs/descriptor_weights.yaml")


def make_analysis(track_id, bpm=None, rms=0.3, lfer=0.5, style=None, n=30):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=track_id, bpm_estimate=bpm, style_label=style),
        features=[FeatureFrame(track_id=track_id, timestamp_sec=float(t),
                               rms=rms, low_freq_energy_ratio=lfer) for t in range(n)],
    )


def make_phrase_analysis(track_id, bpm, tension_start=0.3, tension_end=0.7):
    beat_times = [i * (60.0 / bpm) for i in range(160)]
    downbeats = beat_times[::4]
    features = []
    for t in range(40):
        progress = t / 39 if 39 else 0.0
        tension = tension_start + (tension_end - tension_start) * progress
        features.append(
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=0.35 + 0.01 * progress,
                low_freq_energy_ratio=0.45,
                bass_energy=40.0,
                onset_density=0.6,
                pulse_clarity_proxy=0.7,
                vocal_density_proxy=0.1,
                tension_proxy=tension,
                release_proxy=max(0.0, tension - 0.08),
            )
        )
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=track_id, bpm_estimate=bpm, style_label="techno"),
        beatgrid=BeatGrid(bpm=bpm, beat_times_sec=beat_times, downbeats_sec=downbeats),
        segments=[
            Segment(segment_id=f"{track_id}_seg0", track_id=track_id, start_sec=0.0, end_sec=16.0, segment_type="build"),
            Segment(segment_id=f"{track_id}_seg1", track_id=track_id, start_sec=16.0, end_sec=32.0, segment_type="groove"),
            Segment(segment_id=f"{track_id}_seg2", track_id=track_id, start_sec=32.0, end_sec=39.0, segment_type="outro"),
        ],
        features=features,
    )


# ------------------------------------------------------------------- tempo fit


def test_tempo_fit_equal_bpm():
    assert tempo_fit(128.0, 128.0) == 1.0


def test_tempo_fit_within_pitch_range():
    assert tempo_fit(128.0, 132.0) > 0.5


def test_tempo_fit_edge_very_different_bpm():
    assert tempo_fit(128.0, 95.0) == 0.0


def test_tempo_fit_halftime_recognized():
    # 140 vs 70 = half-time, DJ-compatible — must NOT score 0
    assert tempo_fit(140.0, 70.0) == 1.0


def test_tempo_fit_unknown_bpm_is_none():
    assert tempo_fit(None, 128.0) is None  # never guessed


# ------------------------------------------------------------------- bass risk


def test_bass_conflict_high_when_both_bass_heavy():
    a, b = make_analysis("a", lfer=0.7), make_analysis("b", lfer=0.65)
    assert bass_conflict(a, b) == pytest.approx(0.65)


def test_bass_conflict_defused_by_light_track():
    a, b = make_analysis("a", lfer=0.7), make_analysis("b", lfer=0.1)
    assert bass_conflict(a, b) == pytest.approx(0.1)


# ------------------------------------------------------- pair window scoring


def test_pair_window_score_formula(weights):
    wa = TransitionWindow(start_sec=100, end_sec=116, score=0.8,
                          window_type=WindowType.mix_out, risk_score=0.2)
    wb = TransitionWindow(start_sec=10, end_sec=26, score=0.7,
                          window_type=WindowType.mix_in, risk_score=0.4)
    s = pair_window_score(0.5, wa, wb, weights.mixability_conflict)
    w = weights.mixability_conflict.weights
    expected = 0.5 + 0.8 + 0.7 - (w["bass"] + w["vocal"]) * 0.3
    assert s == pytest.approx(expected)


# ------------------------------------------------------------------ end-to-end


def test_compute_mixability_basic(weights):
    out = compute_mixability(
        MixabilityInput(track_a=make_analysis("a", bpm=128, lfer=0.7),
                        track_b=make_analysis("b", bpm=129, lfer=0.68)),
        weights.mixability, weights.mixability_conflict,
    )
    assert out.model_version == MODEL_VERSION
    assert out.status == ModelStatus.candidate
    assert 0 <= out.mixability_score <= 1.001
    assert any("bass conflict" in r for r in out.risks)  # both bass-heavy
    assert out.bass_conflict_risk is not None
    assert any("bass conflict risk" in flag for flag in out.rule_flags)
    assert out.standard_blend_allowed is True
    assert out.recommendation_policy.value == "suppress"
    assert out.policy_reasons
    assert out.reasoning


def test_edge_missing_bpm_warns_not_guesses(weights):
    out = compute_mixability(
        MixabilityInput(track_a=make_analysis("a"), track_b=make_analysis("b")),
        weights.mixability, weights.mixability_conflict,
    )
    assert any("tempo fit unavailable" in w for w in out.warnings)


def test_pair_windows_ranked(weights):
    wa = [TransitionWindow(start_sec=200, end_sec=216, score=0.9, window_type=WindowType.mix_out),
          TransitionWindow(start_sec=100, end_sec=116, score=0.5, window_type=WindowType.mix_out)]
    wb = [TransitionWindow(start_sec=10, end_sec=26, score=0.8, window_type=WindowType.mix_in)]
    out = compute_mixability(
        MixabilityInput(track_a=make_analysis("a", bpm=128), track_b=make_analysis("b", bpm=128),
                        transition_windows_a=wa, transition_windows_b=wb),
        weights.mixability, weights.mixability_conflict,
    )
    assert len(out.best_pair_windows) == 2
    assert out.best_pair_windows[0].pair_score >= out.best_pair_windows[1].pair_score
    assert out.best_pair_windows[0].track_a_window == (200.0, 216.0)


def test_context_component_activates_when_profile_present(weights):
    out = compute_mixability(
        MixabilityInput(
            track_a=make_analysis("a", bpm=128, rms=0.7, lfer=0.65, style="techno"),
            track_b=make_analysis("b", bpm=129, rms=0.72, lfer=0.62, style="techno"),
            context=ContextProfile(
                context_id="club_peak",
                venue_type="club",
                set_role="peak",
                style_focus=["techno"],
            ),
        ),
        weights.mixability,
        weights.mixability_conflict,
    )
    assert not any("context fit unavailable" in w for w in out.warnings)
    assert any("context fit" in r for r in out.reasoning)
    assert out.context_fit_score is not None


def test_precomputation_preserves_complete_mixability_payload(weights):
    a = make_phrase_analysis("a", 128, tension_start=0.45, tension_end=0.65)
    b = make_phrase_analysis("b", 129, tension_start=0.42, tension_end=0.62)
    context = ContextProfile(
        context_id="club_peak",
        venue_type="club",
        set_role="peak",
        style_focus=["techno"],
    )
    inp = MixabilityInput(track_a=a, track_b=b, context=context)

    baseline = compute_mixability(
        inp,
        weights.mixability,
        weights.mixability_conflict,
    )
    cached = compute_mixability(
        inp,
        weights.mixability,
        weights.mixability_conflict,
        precomputed=precompute_mixability_inputs([a, b], context=context),
    )

    assert cached.model_dump(mode="json") == baseline.model_dump(mode="json")


def test_precomputation_scores_context_once_per_track(weights, monkeypatch):
    a = make_analysis("a", bpm=128, style="techno")
    b = make_analysis("b", bpm=129, style="techno")
    context = ContextProfile(
        context_id="club_peak",
        venue_type="club",
        set_role="peak",
        style_focus=["techno"],
    )
    calls: list[str] = []
    original = mixability_module.track_context_score

    def counting_context_score(analysis, profile):
        calls.append(analysis.track.track_id)
        return original(analysis, profile)

    monkeypatch.setattr(mixability_module, "track_context_score", counting_context_score)
    precomputed = precompute_mixability_inputs([a, b], context=context)
    assert calls == ["a", "b"]

    for _ in range(3):
        compute_mixability(
            MixabilityInput(track_a=a, track_b=b, context=context),
            weights.mixability,
            weights.mixability_conflict,
            precomputed=precomputed,
        )

    assert calls == ["a", "b"]


def test_precomputation_does_not_reuse_a_different_context(weights, monkeypatch):
    a = make_analysis("a", bpm=128, style="techno")
    b = make_analysis("b", bpm=129, style="techno")
    cached_context = ContextProfile(context_id="club", venue_type="club", set_role="peak")
    requested_context = ContextProfile(context_id="cafe", venue_type="cafe", set_role="opener")
    precomputed = precompute_mixability_inputs([a, b], context=cached_context)
    calls: list[str] = []
    original = mixability_module.track_context_score

    def counting_context_score(analysis, profile):
        calls.append(analysis.track.track_id)
        return original(analysis, profile)

    monkeypatch.setattr(mixability_module, "track_context_score", counting_context_score)
    compute_mixability(
        MixabilityInput(track_a=a, track_b=b, context=requested_context),
        weights.mixability,
        weights.mixability_conflict,
        precomputed=precomputed,
    )

    assert calls == ["a", "b"]


def test_phrase_and_tension_components_activate_with_descriptor_coverage(weights):
    a = make_phrase_analysis("a", 128, tension_start=0.45, tension_end=0.65)
    b = make_phrase_analysis("b", 128, tension_start=0.42, tension_end=0.62)
    out = compute_mixability(
        MixabilityInput(
            track_a=a,
            track_b=b,
            transition_windows_a=[
                TransitionWindow(start_sec=24.0, end_sec=32.0, score=0.8, window_type=WindowType.mix_out),
            ],
            transition_windows_b=[
                TransitionWindow(start_sec=0.0, end_sec=8.0, score=0.8, window_type=WindowType.mix_in),
            ],
        ),
        weights.mixability,
        weights.mixability_conflict,
    )
    assert out.phrase_fit is not None
    assert out.tension_fit is not None
    assert not any("phrase fit unavailable" in warning for warning in out.warnings)
    assert not any("tension fit unavailable" in warning for warning in out.warnings)


def test_output_json_roundtrip(weights):
    out = compute_mixability(
        MixabilityInput(track_a=make_analysis("a"), track_b=make_analysis("b")),
        weights.mixability, weights.mixability_conflict,
    )
    assert MixabilityOutput.model_validate_json(out.model_dump_json()) == out


def test_example_mixability_json_validates():
    import json
    from pathlib import Path
    out = MixabilityOutput.model_validate(
        json.loads(Path("data/examples/example_mixability.json").read_text())
    )
    assert out.model_version == MODEL_VERSION and out.reasoning


# ------------------------------------------------------------------------- API


def test_api_mixability_endpoint(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from dancelab.api.main import app
    from dancelab.storage.repositories import FileAnalysisRepository

    monkeypatch.setenv("DANCELAB_PROCESSED_DIR", str(tmp_path))
    repo = FileAnalysisRepository(tmp_path)
    repo.save(make_analysis("mixa", bpm=128, n=60))
    repo.save(make_analysis("mixb", bpm=126, n=60))

    client = TestClient(app)
    r = client.post("/pairs/mixability", json={"track_id_a": "mixa", "track_id_b": "mixb"})
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == MODEL_VERSION
    assert "mixability_score" in body and body["reasoning"]

    assert client.post("/pairs/mixability",
                       json={"track_id_a": "mixa", "track_id_b": "nope"}).status_code == 404


def test_phrase_fit_does_not_trust_an_unreliable_beatgrid():
    """An unreliable grid's beat times are noise. Building phrase scores on them
    invents precision and, worse, counts as a present component."""
    from dancelab.core.models import AnalysisResult, BeatGrid, Track, TransitionWindow, WindowType
    from dancelab.decision.mixability import phrase_fit

    def _unreliable(tid):
        return AnalysisResult(
            engine_version="t",
            track=Track(track_id=tid, bpm_estimate=128.0),
            beatgrid=BeatGrid(bpm=128.0, reliable=False,
                              beat_times_sec=[float(i) * 0.469 for i in range(64)],
                              downbeats_sec=[0.0, 1.875, 3.75]),
            segments=[],           # no fallback anchors either
        )

    out_w = [TransitionWindow(window_type=WindowType.mix_out, start_sec=10.0, end_sec=20.0, score=0.8)]
    in_w = [TransitionWindow(window_type=WindowType.mix_in, start_sec=0.0, end_sec=10.0, score=0.8)]
    assert phrase_fit(_unreliable("a"), _unreliable("b"), out_w, in_w) is None

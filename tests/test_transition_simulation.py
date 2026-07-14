"""Transition Lab envelope and sample-accurate rendering tests."""

from __future__ import annotations

import numpy as np
import pytest

from dancelab.host.transition_simulation import (
    PROFILE_OPTIONS,
    TRANSITION_DURATION_OPTIONS,
    build_transition_envelope,
    plan_transition_duration,
    render_transition_preview,
    sample_transition_envelope,
    transition_preview_cache_path,
)


def test_duration_plan_keeps_phrase_choice_when_source_runway_is_safe():
    plan = plan_transition_duration(
        128,
        available_a_beats=160.0,
        available_b_beats=256.0,
    )

    assert plan.selected_beats == 128
    assert plan.shortened is False
    assert plan.outgoing_guard_beats == 8


def test_duration_plan_shortens_only_to_supported_32_beat_multiple():
    plan = plan_transition_duration(
        192,
        available_a_beats=137.0,
        available_b_beats=180.0,
    )

    assert plan.selected_beats == 128
    assert plan.shortened is True
    assert plan.selected_beats in TRANSITION_DURATION_OPTIONS


def test_duration_plan_rejects_cue_with_less_than_one_safe_phrase():
    plan = plan_transition_duration(
        64,
        available_a_beats=36.0,
        available_b_beats=200.0,
    )

    assert plan.selected_beats is None


@pytest.mark.parametrize("profile_id", [profile_id for profile_id, _ in PROFILE_OPTIONS])
def test_preview_profiles_are_bounded_and_phrase_locked(profile_id):
    envelope = build_transition_envelope(profile_id)

    assert envelope.beat_positions[0] == 0.0
    assert envelope.beat_positions[-1] == 64.0
    assert np.diff(envelope.beat_positions).tolist() == [8.0] * 8
    for curve in envelope.curves().values():
        assert len(curve) == len(envelope.beat_positions)
        assert min(curve) >= 0.0
        assert max(curve) <= 1.0
    assert np.all(np.diff(envelope.fader_a) <= 1e-9)
    assert np.all(np.diff(envelope.fader_b) >= -1e-9)


def test_bass_swap_hands_low_band_over_on_middle_eight_beat_boundary():
    envelope = build_transition_envelope("bass_swap")
    middle = envelope.beat_positions.index(32.0)

    assert envelope.low_a[middle - 1] > envelope.low_b[middle - 1]
    assert envelope.low_a[middle] <= 0.05
    assert envelope.low_b[middle] == pytest.approx(1.0)
    assert envelope.low_b[middle + 1] == pytest.approx(1.0)


def test_sampled_envelope_preserves_exact_endpoints():
    envelope = build_transition_envelope("contour_blend")
    sampled = sample_transition_envelope(envelope, 1001)

    for name, values in envelope.curves().items():
        assert sampled[name][0] == pytest.approx(values[0])
        assert sampled[name][-1] == pytest.approx(values[-1])


def test_preview_cache_identity_includes_pair_cues_rate_and_profile(tmp_path):
    source_a = tmp_path / "a.wav"
    source_b = tmp_path / "b.wav"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")
    common = dict(
        cache_dir=tmp_path / "cache",
        source_a=source_a,
        source_b=source_b,
        track_id_a="track-a",
        track_id_b="track-b",
        cue_a_sec=10.0,
        cue_b_sec=2.0,
        playback_rate_b=1.0,
    )

    baseline = transition_preview_cache_path(**common, profile_id="plain_blend")
    changed_profile = transition_preview_cache_path(**common, profile_id="bass_swap")
    changed_cue = transition_preview_cache_path(
        **{**common, "cue_b_sec": 4.0}, profile_id="plain_blend"
    )
    changed_balanced_plan = transition_preview_cache_path(
        **common,
        profile_id="plain_blend",
        playback_rate_a=1.02,
        preview_bpm=130.0,
        tempo_strategy="balanced_m10",
    )

    assert baseline != changed_profile
    assert baseline != changed_cue
    assert baseline != changed_balanced_plan
    assert baseline.parent.name == "transition_previews"


def test_renderer_writes_one_bounded_sample_accurate_mix(tmp_path):
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    pytest.importorskip("scipy")
    sample_rate = 8000
    duration_sec = 12.0
    time = np.arange(int(sample_rate * duration_sec), dtype=np.float32) / sample_rate
    outgoing = 0.32 * np.sin(2.0 * np.pi * 110.0 * time)
    incoming = 0.28 * np.sin(2.0 * np.pi * 660.0 * time)
    source_a = tmp_path / "outgoing.wav"
    source_b = tmp_path / "incoming.wav"
    output = tmp_path / "rendered.wav"
    sf.write(source_a, outgoing, sample_rate)
    sf.write(source_b, incoming, sample_rate)

    result = render_transition_preview(
        source_a=source_a,
        source_b=source_b,
        cue_a_sec=1.0,
        cue_b_sec=1.0,
        bpm_master=120.0,
        playback_rate_a=1.02,
        playback_rate_b=1.0,
        tempo_strategy="balanced_m10",
        profile_id="bass_swap",
        output_path=output,
        sample_rate=sample_rate,
        duration_beats=16,
        grid_beats=8,
    )
    rendered, rendered_rate = sf.read(output, dtype="float32")

    assert rendered_rate == sample_rate
    assert rendered.shape == (int(8.0 * sample_rate), 2)
    assert len(rendered) == int(8.0 * sample_rate)
    assert sf.info(output).subtype == "PCM_24"
    assert result.duration_sec == pytest.approx(8.0)
    assert result.preview_bpm == pytest.approx(120.0)
    assert result.playback_rate_a == pytest.approx(1.02)
    assert result.playback_rate_b == pytest.approx(1.0)
    assert result.tempo_strategy == "balanced_m10"
    assert result.channels == 2
    assert result.output_subtype == "PCM_24"
    assert result.time_stretch_backend == "librosa_phase_vocoder"
    assert result.envelope.beat_positions == (0.0, 8.0, 16.0)
    assert np.max(np.abs(rendered)) <= 0.981
    assert np.sqrt(np.mean(rendered**2)) > 0.02
    assert len(result.outgoing.minimum) == 360
    assert len(result.mixed.minimum) == 360
    assert len(result.incoming.minimum) == 360


def test_renderer_preserves_stereo_channel_information(tmp_path):
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    pytest.importorskip("scipy")
    sample_rate = 8000
    duration_sec = 10.0
    time = np.arange(int(sample_rate * duration_sec), dtype=np.float32) / sample_rate
    source_a = tmp_path / "stereo-a.wav"
    source_b = tmp_path / "stereo-b.wav"
    output = tmp_path / "stereo-render.wav"
    sf.write(
        source_a,
        np.column_stack(
            (
                0.30 * np.sin(2.0 * np.pi * 110.0 * time),
                0.12 * np.sin(2.0 * np.pi * 330.0 * time),
            )
        ),
        sample_rate,
    )
    sf.write(
        source_b,
        np.column_stack(
            (
                0.08 * np.sin(2.0 * np.pi * 550.0 * time),
                0.26 * np.sin(2.0 * np.pi * 770.0 * time),
            )
        ),
        sample_rate,
    )

    result = render_transition_preview(
        source_a=source_a,
        source_b=source_b,
        cue_a_sec=0.5,
        cue_b_sec=0.5,
        bpm_master=120.0,
        playback_rate_a=1.0,
        playback_rate_b=1.0,
        profile_id="plain_blend",
        output_path=output,
        sample_rate=sample_rate,
        duration_beats=16,
        grid_beats=8,
    )
    rendered, _ = sf.read(output, dtype="float32", always_2d=True)

    assert rendered.shape == (int(8.0 * sample_rate), 2)
    assert not np.allclose(rendered[:, 0], rendered[:, 1], atol=1e-4)
    assert np.sqrt(np.mean((rendered[:, 0] - rendered[:, 1]) ** 2)) > 0.02
    assert sf.info(output).subtype == "PCM_24"
    assert result.channels == 2
    assert result.time_stretch_backend == "none"


def test_renderer_rejects_source_that_ends_before_requested_phrase(tmp_path):
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    sample_rate = 8000
    source = np.zeros(sample_rate * 2, dtype=np.float32)
    source_a = tmp_path / "short-outgoing.wav"
    source_b = tmp_path / "incoming.wav"
    sf.write(source_a, source, sample_rate)
    sf.write(source_b, np.zeros(sample_rate * 10, dtype=np.float32), sample_rate)

    with pytest.raises(ValueError, match="choose an earlier cue or a shorter transition"):
        render_transition_preview(
            source_a=source_a,
            source_b=source_b,
            cue_a_sec=0.0,
            cue_b_sec=0.0,
            bpm_master=120.0,
            playback_rate_a=1.0,
            playback_rate_b=1.0,
            profile_id="plain_blend",
            output_path=tmp_path / "must-not-exist.wav",
            sample_rate=sample_rate,
            duration_beats=16,
            grid_beats=8,
        )

    assert not (tmp_path / "must-not-exist.wav").exists()

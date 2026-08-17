"""Pipeline orchestration: audio -> features -> descriptors -> conditioning -> decisions.

This is the single entry point used by both CLI and API, so both surfaces
return byte-identical results for the same input (Repo Blueprint DoD:
"API zwraca ten sam wynik").
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from dancelab import __version__
from dancelab.core.config import EngineConfig, load_weights
from dancelab.core.models import AnalysisResult, DescriptorCurve, ModelStatus, StemType, Track
from dancelab.core.normalization import minmax_01, robust_01
from dancelab.descriptors.bass_salience import bass_salience
from dancelab.descriptors.breakdown_drop import (
    breakdown_drop_curves,
    relabel_breakdown_drop_segments,
)
from dancelab.descriptors.groove import groove_density
from dancelab.descriptors.release import release_map
from dancelab.descriptors.tension import tension_curve
from dancelab.features.extract import extract_features
from dancelab.features.key import estimate_key
from dancelab.features.microtiming import microtiming_profile, syncopation_profile
from dancelab.features.onset_density import detect_onsets
from dancelab.features.vocals import _demucs_available, vocal_activity
from dancelab.ingestion.loader import load_audio
from dancelab.ingestion.metadata import build_track
from dancelab.ingestion.tags import read_audio_tags
from dancelab.preprocessing.rigid_beatgrid import estimate_beatgrid_best
from dancelab.preprocessing.segmentation import segment_track
from dancelab.stems import (
    StemBundle,
    build_stem_window_features,
    extract_stems,
    stem_energy_ratio_per_frame,
)


def _column_or_default(result: list, name: str, default: float) -> np.ndarray:
    return np.array(
        [
            float(value) if value is not None else default
            for value in (getattr(frame, name) for frame in result)
        ],
        dtype=np.float64,
    )


def _rolling_mean(values: np.ndarray, window: int = 8) -> np.ndarray:
    if len(values) == 0:
        return values
    radius = max(window // 2, 1)
    padded = np.pad(values, (radius, radius), mode="edge")
    kernel = np.ones(2 * radius + 1, dtype=np.float64) / (2 * radius + 1)
    return np.convolve(padded, kernel, mode="valid")


def _descriptor_curve(name: str, times: np.ndarray, values: np.ndarray) -> DescriptorCurve:
    return DescriptorCurve(
        name=name,
        status=ModelStatus.candidate,
        times_sec=[round(float(value), 4) for value in times],
        values=[round(float(value), 4) for value in values],
    )


def _enrich_descriptor_features(
    features: list,
    *,
    onset_times: np.ndarray,
    beat_times: list[float],
    weights,
) -> tuple[list, list[DescriptorCurve], dict[str, np.ndarray]]:
    if not features:
        return features, [], {}
    if not all(hasattr(weights, name) for name in ("groove_density", "bass_salience", "tension")):
        return features, [], {}

    times = np.array([frame.timestamp_sec for frame in features], dtype=np.float64)
    onset_density = _column_or_default(features, "onset_density", 0.0)
    pulse = _column_or_default(features, "pulse_clarity_proxy", 0.5)
    vocal = np.clip(_column_or_default(features, "vocal_density_proxy", 0.0), 0.0, 1.0)
    rms = _column_or_default(features, "rms", 0.0)
    flux = _column_or_default(features, "spectral_flux", 0.0)
    bass = _column_or_default(features, "bass_energy", 0.0)

    beat_array = np.asarray(beat_times, dtype=np.float64)
    sync = syncopation_profile(onset_times, beat_array, times) if beat_array.size else np.zeros_like(times)
    micro = microtiming_profile(onset_times, beat_array, times) if beat_array.size else np.zeros_like(times)

    rms_norm = robust_01(rms)
    flux_norm = robust_01(flux)
    onset_norm = robust_01(onset_density)
    bass_norm = robust_01(bass)
    rhythm_clarity = (
        1.0 - minmax_01(np.abs(np.gradient(flux_norm)))
        if len(flux_norm) > 1
        else np.full_like(flux_norm, 0.5)
    )
    masking_penalty = np.clip(0.6 * flux_norm + 0.4 * vocal, 0.0, 1.0)

    bass_curve = bass_salience(
        bass_norm,
        pulse,
        rhythm_clarity,
        masking_penalty,
        weights.bass_salience,
    )

    rise = np.clip(np.gradient(rms_norm), 0.0, None) if len(rms_norm) > 1 else np.zeros_like(rms_norm)
    delay = np.clip(rms_norm - _rolling_mean(rms_norm), 0.0, None)
    spectral_rise = np.clip(np.gradient(flux_norm), 0.0, None) if len(flux_norm) > 1 else np.zeros_like(flux_norm)
    spectral = np.clip(0.6 * flux_norm + 0.4 * spectral_rise, 0.0, 1.0)
    instability = np.clip(0.5 * (1.0 - pulse) + 0.5 * micro, 0.0, 1.0)
    onset_rise = np.clip(np.gradient(onset_norm), 0.0, None) if len(onset_norm) > 1 else np.zeros_like(onset_norm)
    expectation = np.clip(0.5 * sync + 0.5 * onset_rise, 0.0, 1.0)

    tension = tension_curve(
        {
            "rise": rise,
            "delay": delay,
            "spectral": spectral,
            "instability": instability,
            "expectation": expectation,
        },
        weights.tension,
    )
    release = release_map(tension, times)
    groove = groove_density(
        pulse,
        sync,
        onset_density,
        bass_curve,
        micro,
        weights.groove_density,
    )
    breakdown_curve, drop_curve = breakdown_drop_curves(
        rms_norm,
        bass_curve,
        onset_density,
        tension,
        release,
        groove,
    )

    enriched = [
        frame.model_copy(
            update={
                "syncopation_proxy": round(float(sync[idx]), 4),
                "bass_salience": round(float(bass_curve[idx]), 4),
                "microtiming_proxy": round(float(micro[idx]), 4),
                "tension_proxy": round(float(tension[idx]), 4),
                "release_proxy": round(float(release[idx]), 4),
            }
        )
        for idx, frame in enumerate(features)
    ]
    curves = [
        _descriptor_curve("bass_salience", times, bass_curve),
        _descriptor_curve("tension", times, tension),
        _descriptor_curve("release", times, release),
        _descriptor_curve("groove_density", times, groove),
        _descriptor_curve("breakdown_likelihood", times, breakdown_curve),
        _descriptor_curve("drop_likelihood", times, drop_curve),
    ]
    return enriched, curves, {
        "times": times,
        "energy": rms_norm,
        "release": release,
        "breakdown": breakdown_curve,
        "drop": drop_curve,
    }


def _analyze_track_impl(
    path: str | Path,
    config: EngineConfig,
    style_label: str | None = None,
    bpm_hint: float | None = None,
    title: str | None = None,
    artist: str | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> tuple[AnalysisResult, StemBundle | None]:
    """Analyze a single audio file with everything implemented so far.

    Computes beatgrid, onsets, per-second features, candidate descriptor
    proxies, descriptor curves, and structural segments. Decision outputs still
    stay empty here - they are produced on demand by the decision endpoints,
    never fabricated in storage (ADR-005). The `notes` field states exactly
    what is and isn't covered.

    AUD-M9: the old `context_id` parameter was accepted and silently ignored
    (conditioning happens at decision time, not analyze time) — removed rather
    than kept as a lying knob. title/artist overrides now actually apply.
    """
    # AUD-M9: engine.random_seed was an advertised-but-unused knob. The engine
    # is seed-free by design, but seeding the global RNG here guards against
    # any dependency (librosa/torch paths) quietly introducing randomness.
    def _stage(name: str) -> None:
        # real progress hook for UIs — fires at each actual pipeline stage,
        # never simulated
        if on_stage is not None:
            on_stage(name)

    def _formula_hash_or_none(weights_file) -> str | None:  # noqa: ANN001
        """Odcisk pliku wag, albo None gdy nie da się go policzyć.

        None znaczy „nie wiem, czym to policzono" i taka analiza NIE zostanie
        ponownie użyta w innym katalogu — przeliczy się. Lepiej zapłacić
        analizą niż podać wynik z nieznanych wag (ADR-005).
        """
        from dancelab.storage.library_manifest import formula_hash

        try:
            return formula_hash(weights_file)
        except Exception:                                          # noqa: BLE001
            return None

    np.random.seed(config.engine.random_seed)
    weights = load_weights(config.weights_file)
    _stage("Loading audio")
    signal = load_audio(path, config)
    tags = read_audio_tags(path)
    effective_style = style_label or tags.genre
    effective_bpm_hint = bpm_hint or tags.bpm
    track: Track = build_track(
        signal,
        title=title or tags.title,
        artist=artist or tags.artist,
        style_label=effective_style,
        bpm_estimate=bpm_hint,
    )
    _stage("Extracting stems")
    stem_bundle = extract_stems(signal, track.track_id, config)
    vocal_stem = stem_bundle.channels.get(StemType.vocals) if stem_bundle is not None else None

    hop = config.audio.hop_size
    _stage("Key detection")
    key_name, camelot, key_conf = estimate_key(signal.samples, signal.sample_rate, hop_size=hop)
    track = track.model_copy(
        update={"key_estimate": camelot, "key_name": key_name, "key_confidence": key_conf}
    )
    _stage("Beat tracking (BPM)")
    beatgrid = estimate_beatgrid_best(
        signal,
        hop_size=hop,
        bpm_hint=effective_bpm_hint,
        tempo_min=config.analysis.tempo_min,
        tempo_max=config.analysis.tempo_max,
        rigid=config.analysis.rigid_grid,
    )
    _stage("Onset detection")
    onset_times = detect_onsets(signal.samples, signal.sample_rate, hop_size=hop)
    _stage("Vocal activity")
    if vocal_stem is not None:
        vocal_proxy = stem_energy_ratio_per_frame(
            vocal_stem.samples,
            signal.samples,
            config.audio.frame_size,
            hop,
        )
        vocal_note = (
            "vocal_density_proxy is a source-separated vocal-energy ratio (candidate) - "
            "separation artifacts can bias it; not proof of vocals or vocal clash"
        )
    else:
        # stem layer off (or no vocal stem): use the configured vocal backend.
        # Default "hpss" keeps a plain analyze fast; opt into demucs for quality.
        fallback_method = "hpss" if stem_bundle is not None else config.analysis.vocal_method
        vocal_proxy = vocal_activity(
            signal.samples,
            signal.sample_rate,
            frame_size=config.audio.frame_size,
            hop_size=hop,
            method=fallback_method,
        )
        demucs_used = fallback_method == "demucs" or (
            fallback_method == "auto" and _demucs_available()
        )
        vocal_note = (
            "vocal_density_proxy is a demucs vocal-energy ratio (candidate) - "
            "separation artifacts can bias it; not proof of vocals"
            if demucs_used else
            "vocal_density_proxy is an HPSS mid-band VAD proxy (candidate) - "
            "melodic instruments can raise it; not proof of vocals"
        )
    _stage("Feature extraction")
    features = extract_features(
        signal,
        config,
        track.track_id,
        onset_times_sec=onset_times,
        beat_times_sec=beatgrid.beat_times_sec,
        vocal_proxy=vocal_proxy,
    )
    stem_window_features = []
    if stem_bundle is not None and stem_bundle.channels:
        stem_window_features = build_stem_window_features(
            track_id=track.track_id,
            mix_signal=signal,
            channels=stem_bundle.channels,
            summary=stem_bundle.result,
            frame_size=config.audio.frame_size,
            hop_size=hop,
        )
    _stage("Segmentation")
    segments = segment_track(
        signal,
        track.track_id,
        hop_size=hop,
        min_len_sec=config.analysis.segment_min_len_sec,
    )
    _stage("Descriptor proxies")
    features, descriptor_curves, detector_curves = _enrich_descriptor_features(
        features,
        onset_times=onset_times,
        beat_times=beatgrid.beat_times_sec,
        weights=weights,
    )
    if detector_curves:
        segments = relabel_breakdown_drop_segments(
            segments,
            detector_curves["times"],
            detector_curves["breakdown"],
            detector_curves["drop"],
            detector_curves["energy"],
            detector_curves["release"],
        )

    # BPM from beatgrid unless the user supplied a hint (their value wins)
    if track.bpm_estimate is None:
        track = track.model_copy(update={"bpm_estimate": beatgrid.bpm})

    notes = [
        "features computed: rms, spectral_flux, low_freq_energy_ratio, "
        "bass_energy, onset_density, pulse_clarity_proxy, "
        "vocal_density_proxy; beatgrid + segments included",
        "pulse_clarity_proxy is a beat-aligned novelty autocorrelation ratio "
        "(candidate) - useful as a rhythmic regularity signal, not a validated groove score",
        vocal_note,
        "segment TYPE labels are heuristic (unvalidated); boundaries more reliable, "
        "and breakdown/drop labels are candidate detectors rather than validated structure truth",
    ]
    if descriptor_curves:
        notes.append(
            "descriptor proxies computed: syncopation_proxy, bass_salience, "
            "microtiming_proxy, tension_proxy, release_proxy; descriptor_curves include "
            "groove_density, bass_salience, tension, release, breakdown_likelihood, "
            "and drop_likelihood (candidate, not DJ-validated)"
        )
    if tags.genre and style_label is None:
        notes.append(f"style_label source: file genre tag `{tags.genre}`")
    if tags.bpm is not None and bpm_hint is None:
        notes.append(f"file BPM tag used only as beat-tracker hint ({tags.bpm:.2f})")
    if stem_bundle is not None:
        notes.extend(
            [
                "stem-aware layer attempted: candidate vocals/bass/drums/other preprocessing; "
                "fallback suppresses stem outputs when separation quality is insufficient",
                *stem_bundle.result.warnings,
            ]
        )

    return AnalysisResult(
        engine_version=__version__,
        weights_version=weights.version,
        formula_version=_formula_hash_or_none(config.weights_file),
        track=track,
        beatgrid=beatgrid,
        segments=segments,
        features=features,
        stem_extraction=stem_bundle.result if stem_bundle is not None else None,
        stem_window_features=stem_window_features,
        descriptor_curves=descriptor_curves,
        notes=notes,
    ), stem_bundle


def analyze_track(
    path: str | Path,
    config: EngineConfig,
    style_label: str | None = None,
    bpm_hint: float | None = None,
    title: str | None = None,
    artist: str | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> AnalysisResult:
    result, _ = _analyze_track_impl(
        path,
        config,
        style_label=style_label,
        bpm_hint=bpm_hint,
        title=title,
        artist=artist,
        on_stage=on_stage,
    )
    return result


def analyze_track_with_stems(
    path: str | Path,
    config: EngineConfig,
    style_label: str | None = None,
    bpm_hint: float | None = None,
    title: str | None = None,
    artist: str | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> tuple[AnalysisResult, StemBundle | None]:
    """Analyze a track and return the in-memory stem bundle for artifact export."""
    return _analyze_track_impl(
        path,
        config,
        style_label=style_label,
        bpm_hint=bpm_hint,
        title=title,
        artist=artist,
        on_stage=on_stage,
    )


def engine_versions(config: EngineConfig) -> dict:
    weights = load_weights(config.weights_file)
    return {
        "engine_version": __version__,
        "config_version": config.engine.version,
        "weights_version": weights.version,
    }

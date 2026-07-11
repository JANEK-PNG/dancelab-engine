"""Optional stem-aware preprocessing adapter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.backend import preferred_torch_device
from dancelab.core.config import EngineConfig
from dancelab.core.models import (
    ArtifactFlag,
    DurationMatchStatus,
    ModelStatus,
    SourceStatus,
    StemChannelSummary,
    StemExtractionResult,
    StemExtractionStatus,
    StemProvenance,
    StemType,
    ValidationStatus,
    WarningLevel,
)
from dancelab.core.provenance import stem_cannot_claim_note
from dancelab.features.vocals import _demucs_available, _get_demucs
from dancelab.stems.quality import (
    artifact_flag_from_residual,
    confidence_from_energy_shares,
    energy_share,
    should_fallback,
)


@dataclass
class StemBundle:
    channels: dict[StemType, AudioSignal]
    result: StemExtractionResult


def _mono(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float32)
    return arr.mean(axis=0) if arr.ndim > 1 else arr


def _config_hash(config: EngineConfig) -> str:
    payload = json.dumps(config.stems.model_dump(), sort_keys=True).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:12]


def _provenance_id(track_id: str, config: EngineConfig) -> str:
    base = f"{track_id}:{_config_hash(config)}".encode("utf-8")
    return hashlib.sha1(base).hexdigest()[:16]


def _stem_id(track_id: str, stem_type: StemType) -> str:
    return f"{track_id}:{stem_type.value}"


def _empty_summary(
    *,
    track_id: str,
    config: EngineConfig,
    model_name: str,
    model_variant: str | None,
    model_signature: str | None,
    processing_command: str | None,
    extraction_status: StemExtractionStatus,
    source_status: SourceStatus,
    warning_level: WarningLevel,
    warnings: list[str],
    fallback_used: bool,
    artifact_flag: ArtifactFlag = ArtifactFlag.none,
) -> StemExtractionResult:
    provenance = StemProvenance(
        provenance_id=_provenance_id(track_id, config),
        model_name=model_name,
        model_variant=model_variant,
        model_signature=model_signature,
        processing_command=processing_command,
        config_hash=_config_hash(config),
        input_audio_id=track_id,
        output_sample_rate=config.audio.sample_rate,
        duration_match_status=DurationMatchStatus.match,
        extraction_status=extraction_status,
        artifact_flag=artifact_flag,
        fallback_used=fallback_used,
    )
    channels = [
        StemChannelSummary(
            stem_type=stem_type,
            stem_id=_stem_id(track_id, stem_type),
            available=False,
            source_status=source_status,
            warning_level=warning_level,
            confidence=0.0,
        )
        for stem_type in StemType
    ]
    return StemExtractionResult(
        status=ModelStatus.candidate,
        source_status=source_status,
        warning_level=warning_level,
        validation_status=ValidationStatus.to_validate,
        cannot_claim=stem_cannot_claim_note(),
        provenance=provenance,
        channels=channels,
        warnings=warnings,
    )


def _extract_demucs_channels(signal: AudioSignal) -> tuple[dict[StemType, AudioSignal], DurationMatchStatus]:
    import torch
    from demucs.apply import apply_model

    model = _get_demucs()
    stereo = np.asarray(signal.samples, dtype=np.float32)
    if stereo.ndim == 1:
        stereo = np.stack([stereo, stereo])

    duration_status = DurationMatchStatus.match
    if signal.sample_rate != model.samplerate:
        import librosa

        stereo = librosa.resample(
            stereo, orig_sr=signal.sample_rate, target_sr=model.samplerate
        )
        duration_status = DurationMatchStatus.resampled

    wav = torch.tensor(stereo[None], dtype=torch.float32)
    with torch.no_grad():
        raw = apply_model(model, wav, device=preferred_torch_device())[0]

    channels: dict[StemType, AudioSignal] = {}
    for stem_type in StemType:
        if stem_type.value not in model.sources:
            continue
        stem = raw[model.sources.index(stem_type.value)].cpu().numpy().mean(axis=0)
        if signal.sample_rate != model.samplerate:
            import librosa

            stem = librosa.resample(
                stem, orig_sr=model.samplerate, target_sr=signal.sample_rate
            )
        channels[stem_type] = AudioSignal(
            samples=stem.astype(np.float32),
            sample_rate=signal.sample_rate,
            source_path=signal.source_path,
            metadata={"stem_type": stem_type.value},
        )

    if any(abs(ch.duration_sec - signal.duration_sec) > 0.05 for ch in channels.values()):
        duration_status = DurationMatchStatus.mismatch
    return channels, duration_status


def extract_stems(signal: AudioSignal, track_id: str, config: EngineConfig) -> StemBundle | None:
    """Attempt source separation and return a JSON-safe summary plus in-memory stems."""
    if not config.stems.enabled:
        return None

    warnings: list[str] = []
    requested_method = config.stems.method
    method = requested_method
    if method == "auto":
        method = "demucs" if _demucs_available() else "none"
    if method not in {"demucs", "none"}:
        warnings.append(
            f"unknown stem method '{requested_method}' - using full-mix fallback"
        )
        return StemBundle(
            channels={},
            result=_empty_summary(
                track_id=track_id,
                config=config,
                model_name="stem_fallback",
                model_variant=requested_method,
                model_signature=None,
                processing_command=None,
                extraction_status=StemExtractionStatus.unavailable,
                source_status=SourceStatus.fallback_full_mix,
                warning_level=WarningLevel.warning,
                warnings=warnings,
                fallback_used=True,
            ),
        )

    if method == "none":
        if requested_method == "none":
            warnings.append("stem-aware layer disabled by method=none, using full-mix fallback")
        else:
            warnings.append(
                "stem-aware layer unavailable - demucs not installed, using full-mix fallback"
            )
        return StemBundle(
            channels={},
            result=_empty_summary(
                track_id=track_id,
                config=config,
                model_name="stem_fallback",
                model_variant=method,
                model_signature=None,
                processing_command=None,
                extraction_status=StemExtractionStatus.unavailable,
                source_status=SourceStatus.fallback_full_mix,
                warning_level=WarningLevel.warning,
                warnings=warnings,
                fallback_used=True,
            ),
        )

    try:
        channels, duration_status = _extract_demucs_channels(signal)
    except Exception as exc:  # pragma: no cover - exercised by integration paths
        warnings.append(f"stem extraction failed - {exc}")
        return StemBundle(
            channels={},
            result=_empty_summary(
                track_id=track_id,
                config=config,
                model_name="htdemucs",
                model_variant=method,
                model_signature="demucs.apply_model.cpu",
                processing_command="demucs.apply_model(device=cpu)",
                extraction_status=StemExtractionStatus.failed,
                source_status=SourceStatus.fallback_full_mix,
                warning_level=WarningLevel.error,
                warnings=warnings,
                fallback_used=True,
            ),
        )

    mix = _mono(np.asarray(signal.samples, dtype=np.float32))
    shares = {stem_type: energy_share(ch.samples, mix) for stem_type, ch in channels.items()}
    confidence = confidence_from_energy_shares(shares)
    residual = abs(sum(shares.values()) - 1.0)
    artifact_flag = artifact_flag_from_residual(residual)
    fallback = should_fallback(
        confidence=confidence,
        artifact_flag=artifact_flag,
        confidence_threshold=config.stems.fallback_confidence_threshold,
        max_artifact_flag=config.stems.max_artifact_flag,
        available_stems=len(channels),
        min_required_stems=config.stems.min_required_stems,
    )

    if len(channels) < len(StemType):
        warnings.append(
            f"stem extraction returned {len(channels)}/{len(StemType)} expected stems"
        )
    if residual > 0.15:
        warnings.append(
            f"stem energy-balance residual {residual:.2f} -> artifact flag {artifact_flag.value}"
        )
    if fallback:
        warnings.append("stem-aware outputs suppressed - full-mix fallback selected")

    extraction_status = StemExtractionStatus.success
    if fallback:
        extraction_status = StemExtractionStatus.fallback
    elif len(channels) < len(StemType):
        extraction_status = StemExtractionStatus.partial

    provenance = StemProvenance(
        provenance_id=_provenance_id(track_id, config),
        model_name="htdemucs",
        model_variant=method,
        model_signature="demucs.apply_model.cpu",
        processing_command="demucs.apply_model(device=cpu)",
        config_hash=_config_hash(config),
        input_audio_id=track_id,
        output_stem_ids={stem_type: _stem_id(track_id, stem_type) for stem_type in channels},
        output_sample_rate=signal.sample_rate,
        duration_match_status=duration_status,
        extraction_status=extraction_status,
        artifact_flag=artifact_flag,
        fallback_used=fallback,
    )

    source_status = SourceStatus.fallback_full_mix if fallback else SourceStatus.source_backed
    warning_level = (
        WarningLevel.error
        if fallback and not channels
        else WarningLevel.warning
        if fallback or artifact_flag != ArtifactFlag.none
        else WarningLevel.info
    )
    channel_summaries = []
    for stem_type in StemType:
        share = shares.get(stem_type)
        channel_summaries.append(
            StemChannelSummary(
                stem_type=stem_type,
                stem_id=_stem_id(track_id, stem_type),
                available=(stem_type in channels) and not fallback,
                source_status=source_status if stem_type in channels else SourceStatus.unavailable,
                warning_level=warning_level if stem_type in channels else WarningLevel.warning,
                activity_mean=round(float(np.clip(share, 0.0, 1.0)), 4) if share is not None else None,
                confidence=round(confidence, 4) if stem_type in channels else 0.0,
            )
        )

    result = StemExtractionResult(
        status=ModelStatus.candidate,
        source_status=source_status,
        warning_level=warning_level,
        validation_status=ValidationStatus.to_validate,
        cannot_claim=stem_cannot_claim_note(),
        provenance=provenance,
        channels=channel_summaries,
        warnings=warnings,
    )
    return StemBundle(channels={} if fallback else channels, result=result)

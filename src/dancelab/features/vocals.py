"""Vocal activity (System Architecture §3).

Two backends behind one interface returning a per-STFT-frame proxy in [0,1]:

- **demucs** (STATUS: candidate, preferred): htdemucs source separation →
  isolated vocals stem → per-frame fraction of mix energy that is vocal.
  This is real vocal separation, not a mid-band heuristic (the Vocal Density
  Card's `validation_required`). Heavy: ~0.34× realtime on CPU; needs the
  `[vocals]` extra + a one-time 80 MB model download.
- **hpss** (STATUS: candidate, fallback): harmonic mid-band energy ratio.
  Cheap, no extra deps, but melodic synths inflate it — kept so tests/CI and
  demucs-less installs still produce a (weaker) signal.

`vocal_activity` auto-selects demucs when importable, else hpss. Even with
demucs, this stays `candidate` / to-validate: separation is imperfect and no DJ
vocal-clash validation exists yet (cannot_claim on the model card holds).
Deterministic for a fixed signal.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.errors import MissingDependencyError
from dancelab.core.backend import preferred_torch_device

VOCAL_BAND_HZ = (200.0, 3400.0)
_EPS = 1e-9


def _demucs_available() -> bool:
    try:
        import demucs.pretrained  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def vocal_activity(
    x: np.ndarray,
    sample_rate: int,
    frame_size: int = 2048,
    hop_size: int = 512,
    band_hz: tuple[float, float] = VOCAL_BAND_HZ,
    method: str = "auto",
) -> np.ndarray:
    """Per-STFT-frame vocal-activity proxy in [0,1].

    method: "auto" (demucs if available else hpss) | "demucs" | "hpss".
    """
    if method == "auto":
        method = "demucs" if _demucs_available() else "hpss"
    if method == "demucs":
        return _vocal_activity_demucs(x, sample_rate, frame_size, hop_size)
    if method == "hpss":
        return _vocal_activity_hpss(x, sample_rate, frame_size, hop_size, band_hz)
    raise ValueError(f"unknown vocal method '{method}'")


# ---------------------------------------------------------------- demucs backend

_MODEL = None  # cached across calls in one process


def _get_demucs():
    global _MODEL
    if _MODEL is None:
        try:
            from demucs.pretrained import get_model
        except ImportError as exc:  # pragma: no cover
            raise MissingDependencyError(
                "demucs is required for vocal separation. Install: pip install 'dancelab-engine[vocals]'"
            ) from exc
        _MODEL = get_model("htdemucs")
        _MODEL.eval()
    return _MODEL


def _vocal_activity_demucs(
    x: np.ndarray, sample_rate: int, frame_size: int, hop_size: int
) -> np.ndarray:
    import torch
    from demucs.apply import apply_model

    model = _get_demucs()
    x = np.asarray(x, dtype=np.float32)
    stereo = np.stack([x, x]) if x.ndim == 1 else x

    # demucs runs at its own sample rate; resample if needed
    if sample_rate != model.samplerate:
        import librosa
        stereo = librosa.resample(stereo, orig_sr=sample_rate, target_sr=model.samplerate)

    wav = torch.tensor(stereo[None], dtype=torch.float32)
    with torch.no_grad():
        stems = apply_model(model, wav, device=preferred_torch_device())[0]
    vocals = stems[model.sources.index("vocals")].cpu().numpy().mean(axis=0)  # → mono
    mix = stereo.mean(axis=0)

    # resample stems back to the analysis sample rate for frame alignment
    if sample_rate != model.samplerate:
        import librosa
        vocals = librosa.resample(vocals, orig_sr=model.samplerate, target_sr=sample_rate)
        mix = librosa.resample(mix, orig_sr=model.samplerate, target_sr=sample_rate)

    return _energy_ratio_per_frame(vocals, mix, frame_size, hop_size)


def _energy_ratio_per_frame(
    vocals: np.ndarray, mix: np.ndarray, frame_size: int, hop_size: int
) -> np.ndarray:
    """Fraction of per-frame mix energy carried by the vocals stem, in [0,1].

    Silence gate: frames whose mix energy is below 5% of the track's typical
    (nonzero-frame median) energy are set to 0 — in near-silent gaps vocal/mix
    ratio spikes to 1.0 meaninglessly, which would fake a vocal peak.

    AUD-M1: the reference is the median of *nonzero* frames, not all frames.
    A track that is >50% silent has an all-frames median of 0, which makes the
    floor 0 so the gate never fires and every silent gap reads as a full vocal
    peak — the exact fabrication the gate exists to prevent."""
    from dancelab.features.rms import frame_signal

    n = min(len(vocals), len(mix))
    v_frames = frame_signal(vocals[:n], frame_size, hop_size)
    m_frames = frame_signal(mix[:n], frame_size, hop_size)
    if v_frames.shape[0] == 0:
        return np.zeros(0)
    v_energy = np.mean(v_frames.astype(np.float64) ** 2, axis=1)
    m_energy = np.mean(m_frames.astype(np.float64) ** 2, axis=1)
    ratio = np.clip(v_energy / (m_energy + _EPS), 0.0, 1.0)
    nonzero = m_energy[m_energy > _EPS]
    reference = float(np.median(nonzero)) if nonzero.size else 0.0
    floor = 0.05 * reference
    ratio[m_energy < floor] = 0.0
    return ratio


# ------------------------------------------------------------------ hpss backend


def _vocal_activity_hpss(
    x: np.ndarray, sample_rate: int, frame_size: int, hop_size: int,
    band_hz: tuple[float, float],
) -> np.ndarray:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "librosa is required for vocal activity. Install: pip install 'dancelab-engine[audio]'"
        ) from exc

    x = np.asarray(x, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0)

    stft = librosa.stft(x, n_fft=frame_size, hop_length=hop_size)
    harmonic = librosa.decompose.hpss(stft)[0]
    power = np.abs(harmonic).astype(np.float64) ** 2

    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=frame_size)
    band = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    total = power.sum(axis=0) + _EPS
    return np.clip(power[band, :].sum(axis=0) / total, 0.0, 1.0)

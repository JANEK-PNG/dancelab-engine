"""Musical key detection → Camelot notation (harmonic mixing). STATUS: candidate.

Method: average chroma (CQT) over the track, correlate against the 24 rotated
Krumhansl-Schmuckler key profiles (12 roots × major/minor), pick the best.
Map to Camelot wheel (the 8A / 12B notation Rekordbox and DJs use).

Candidate, not stable: key estimation is unreliable on atonal / percussive
electronic tracks (techno, DnB) with weak tonal centres — confidence reflects
the correlation margin, and callers should treat low-confidence keys as unknown.
Deterministic. Requires the [audio] extra.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.errors import MissingDependencyError

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler tonal hierarchy profiles (C-rooted); rotated per root.
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Camelot wheel: root pitch-class → code. B ring = major, A ring = minor.
_MAJOR_CAMELOT = {0: "8B", 7: "9B", 2: "10B", 9: "11B", 4: "12B", 11: "1B",
                  6: "2B", 1: "3B", 8: "4B", 3: "5B", 10: "6B", 5: "7B"}
_MINOR_CAMELOT = {9: "8A", 4: "9A", 11: "10A", 6: "11A", 1: "12A", 8: "1A",
                  3: "2A", 10: "3A", 5: "4A", 0: "5A", 7: "6A", 2: "7A"}


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-12 else 0.0


def key_from_chroma(chroma_mean: np.ndarray) -> tuple[str, str, float]:
    """(key_name, camelot, confidence) from a 12-bin mean chroma vector (C-first).

    confidence = margin between best and 2nd-best correlation, scaled to [0,1].
    """
    scores: list[tuple[float, int, str]] = []
    for root in range(12):
        maj = np.roll(_KS_MAJOR, root)
        minr = np.roll(_KS_MINOR, root)
        scores.append((_corr(chroma_mean, maj), root, "major"))
        scores.append((_corr(chroma_mean, minr), root, "minor"))
    scores.sort(key=lambda s: -s[0])
    best_corr, root, mode = scores[0]
    margin = best_corr - scores[1][0]
    confidence = float(np.clip(margin * 5.0, 0.0, 1.0))  # ~0.2 margin → full conf
    camelot = _MAJOR_CAMELOT[root] if mode == "major" else _MINOR_CAMELOT[root]
    key_name = f"{PITCH_CLASSES[root]} {mode}"
    return key_name, camelot, round(confidence, 3)


def estimate_key(x: np.ndarray, sample_rate: int, hop_size: int = 512) -> tuple[str, str, float]:
    """Estimate track key. Returns (key_name, camelot, confidence)."""
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "librosa is required for key detection. Install: pip install 'dancelab-engine[audio]'"
        ) from exc

    x = np.asarray(x, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0)
    chroma = librosa.feature.chroma_cqt(y=x, sr=sample_rate, hop_length=hop_size)
    return key_from_chroma(chroma.mean(axis=1))

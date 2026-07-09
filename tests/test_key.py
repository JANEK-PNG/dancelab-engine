"""Key detection → Camelot. Profile correlation tested on synthetic chroma;
real-audio path gated on [audio]."""

import numpy as np
import pytest

from dancelab.features.key import (
    PITCH_CLASSES,
    _MAJOR_CAMELOT,
    _MINOR_CAMELOT,
    key_from_chroma,
)


def test_c_major_chroma_maps_to_8b():
    # strong C major triad energy (C, E, G) → C major = 8B
    chroma = np.zeros(12)
    for pc in (0, 4, 7):
        chroma[pc] = 1.0
    name, camelot, conf = key_from_chroma(chroma)
    assert name == "C major"
    assert camelot == "8B"
    assert 0.0 <= conf <= 1.0


def test_a_minor_chroma_maps_to_8a():
    chroma = np.zeros(12)
    for pc in (9, 0, 4):  # A, C, E
        chroma[pc] = 1.0
    name, camelot, _ = key_from_chroma(chroma)
    assert name == "A minor"
    assert camelot == "8A"


def test_camelot_wheel_is_complete_and_unique():
    codes = list(_MAJOR_CAMELOT.values()) + list(_MINOR_CAMELOT.values())
    assert len(codes) == 24 and len(set(codes)) == 24
    assert set(_MAJOR_CAMELOT) == set(range(12))
    assert set(_MINOR_CAMELOT) == set(range(12))


def test_flat_chroma_low_confidence():
    _, _, conf = key_from_chroma(np.ones(12))
    assert conf < 0.2  # no tonal centre → low confidence


def test_pitch_classes_length():
    assert len(PITCH_CLASSES) == 12


def test_estimate_key_on_synthetic_tone():
    pytest.importorskip("librosa")
    from dancelab.features.key import estimate_key

    sr = 22050
    # 4 s avoids the short-buffer warning emitted by librosa's internal CQT path.
    t = np.arange(sr * 4) / sr
    # A major triad tones (A2 110, C#4 277, E4 330) → root A
    y = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.18, 329.63)).astype(np.float32)
    name, camelot, _ = estimate_key(y, sr)
    assert name.startswith("A ")  # root A recovered
    assert camelot in ("11B", "8A")  # A major (11B) or relative A minor

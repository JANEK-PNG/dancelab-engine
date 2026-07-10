"""AUD-T2: end-to-end seam — real analyze pipeline → build_set → Rekordbox XML.

The layers are unit-tested in isolation with stored fixtures; this proves they
actually compose. Only load_audio is stubbed (to skip file decoding); key,
beatgrid, onset, segmentation, feature and descriptor extraction all run for
real on synthetic audio, then feed the real set builder and exporter.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("librosa")  # skip without the [audio] extra

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig, load_weights
from dancelab.core.pipeline import analyze_track
from dancelab.decision.set_builder import build_set
from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml


def _tone_signal(freqs: tuple[float, ...], source_path: str, sr: int = 22050) -> AudioSignal:
    # 4 s keeps librosa's CQT happy; a 2 Hz amplitude pulse gives onsets/beats.
    t = np.arange(sr * 4) / sr
    tone = sum(np.sin(2 * np.pi * f * t) for f in freqs)
    pulse = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 2.0 * t))  # ~120 BPM envelope
    samples = (tone * pulse).astype(np.float32)
    samples /= np.max(np.abs(samples)) + 1e-9
    return AudioSignal(samples=samples, sample_rate=sr, source_path=source_path)


def test_analyze_build_export_round_trip(monkeypatch, tmp_path):
    config = EngineConfig()

    signals = {
        "/tracks/Alpha.wav": _tone_signal((220.0, 277.18, 329.63), "/tracks/Alpha.wav"),  # A major
        "/tracks/Beta.wav": _tone_signal((261.63, 329.63, 392.0), "/tracks/Beta.wav"),    # C major
    }
    monkeypatch.setattr("dancelab.core.pipeline.load_audio", lambda path, cfg: signals[str(path)])

    analyses = [analyze_track(path, config) for path in signals]

    # the real pipeline produced two distinct, usable tracks
    assert len(analyses) == 2
    track_ids = [a.track.track_id for a in analyses]
    assert len(set(track_ids)) == 2
    for a in analyses:
        assert a.beatgrid is not None and a.beatgrid.bpm > 0
        assert a.features  # feature frames were extracted

    weights = load_weights("configs/descriptor_weights.yaml")
    plan = build_set(analyses, weights, arc="build")
    assert set(plan.track_order) == set(track_ids)

    xml = build_rekordbox_xml(analyses, set_plan=plan, playlist_name="Seam Test")
    for a in analyses:
        assert (a.track.title or a.track.track_id) in xml or a.track.track_id in xml
    assert "DJ_PLAYLISTS" in xml and "Seam Test" in xml
    assert xml.count("TrackID=") == 2  # both tracks in the COLLECTION
    assert xml.count("<TRACK Key=") == 2  # and both referenced in the playlist

    out = write_rekordbox_xml(xml, tmp_path / "seam.xml")
    assert out.read_text(encoding="utf-8").startswith("<?xml")

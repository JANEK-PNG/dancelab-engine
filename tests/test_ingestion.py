
import pytest

from dancelab.core.audio_types import AudioSignal
from dancelab.core.errors import IngestionError
from dancelab.ingestion.loader import SUPPORTED_EXTENSIONS, load_audio
from dancelab.ingestion.metadata import build_track, make_track_id


def test_supported_extensions_match_brief():
    # Implementation Brief input v0: .wav, .mp3, .aiff, .flac
    assert {".wav", ".mp3", ".aiff", ".flac"} <= SUPPORTED_EXTENSIONS


def test_missing_file_raises(config):
    with pytest.raises(IngestionError):
        load_audio("data/raw/does_not_exist.wav", config)


def test_unsupported_format_raises(config, tmp_path):
    bad = tmp_path / "track.ogg"
    bad.write_bytes(b"\x00")
    with pytest.raises(IngestionError):
        load_audio(bad, config)


def test_track_id_is_deterministic():
    assert make_track_id("a/b.wav") == make_track_id("a/b.wav")
    assert make_track_id("a/b.wav") != make_track_id("a/c.wav")


def test_build_track_from_signal():
    import numpy as np

    signal = AudioSignal(
        samples=np.zeros(44100), sample_rate=44100, source_path="data/raw/x.wav"
    )
    track = build_track(signal, style_label="techno")
    assert track.duration_sec == 1.0
    assert track.channels == 1
    assert track.style_label == "techno"
    assert track.title == "x"

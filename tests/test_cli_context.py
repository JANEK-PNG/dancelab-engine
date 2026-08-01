"""The context conditioning layer must be reachable from the terminal.

ContextProfile changes how mixability scores a pair — a festival afternoon is
not a 4am closing set. The layer is built, tested and wired into scoring, but
until now nothing on the CLI path ever supplied one, so it sat dark in the only
interface a DJ actually uses.
"""

import pytest

from dancelab.context.context_profile import get_context_profile
from dancelab.core.errors import ConfigError


def test_shipped_profiles_load_by_name():
    profile = get_context_profile("club_peak")
    assert profile.context_id == "club_peak"
    assert profile.venue_type == "club"


def test_unknown_profile_names_the_available_ones():
    with pytest.raises(ConfigError) as excinfo:
        get_context_profile("nonexistent_club")
    assert "club_peak" in str(excinfo.value)


def test_smart_playlist_forwards_the_context_to_the_set_builder(monkeypatch, tmp_path):
    """The whole point of the flag: the profile must reach build_set."""
    from dancelab.workflows import smart_playlist as wf

    seen = {}
    real_build_set = wf.build_set

    def _spy(analyses, weights, **kwargs):
        seen["context"] = kwargs.get("context")
        return real_build_set(analyses, weights, **kwargs)

    monkeypatch.setattr(wf, "build_set", _spy)

    profile = get_context_profile("festival_daytime")
    analyses = _two_analyzed_tracks()

    monkeypatch.setattr(wf, "discover_audio_files", lambda *a, **k: ["a.wav", "b.wav"])
    monkeypatch.setattr(wf, "analyze_files", lambda *a, **k: (analyses, []))

    from dancelab.core.config import load_config
    wf.build_smart_playlist_from_folder(
        tmp_path,
        load_config("configs/default.yaml"),
        target_track_count=2,
        context=profile,
        output_path=tmp_path / "out.xml",
    )
    assert seen["context"] is profile


def _two_analyzed_tracks():
    from dancelab.core.models import AnalysisResult, FeatureFrame, Track

    def one(tid, camelot, bpm, rms):
        return AnalysisResult(
            engine_version="t",
            track=Track(track_id=tid, key_estimate=camelot, bpm_estimate=bpm,
                        style_label="techno", source_path=f"/tmp/{tid}.wav"),
            features=[FeatureFrame(track_id=tid, timestamp_sec=float(t), rms=rms,
                                   low_freq_energy_ratio=0.5, bass_energy=50.0)
                      for t in range(30)],
        )

    return [one("t1", "8A", 128, 0.40), one("t2", "9A", 129, 0.42)]


def test_cli_rejects_an_unknown_profile_and_names_the_real_ones():
    from typer.testing import CliRunner
    from dancelab.cli.analyze import app

    result = CliRunner().invoke(app, ["export-rekordbox", "--context", "nope"])
    assert result.exit_code == 2
    assert "club_peak" in result.output


def test_context_flag_is_offered_by_both_set_building_commands():
    from typer.main import get_command

    from dancelab.cli.analyze import app

    root = get_command(app)
    for command_name in ("smart-playlist", "export-rekordbox"):
        command = root.commands[command_name]
        context_params = [param for param in command.params if param.name == "context"]

        assert len(context_params) == 1
        assert "--context" in context_params[0].opts

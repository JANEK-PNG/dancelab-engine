"""`dancelab preview` — the renderer needs a way in from the terminal.

The transition renderer existed but only two verification scripts called it, so
the fastest judgement a DJ can make — what does the seam sound like — was
unreachable from the CLI.
"""

from pathlib import Path

from typer.testing import CliRunner

from dancelab.cli.analyze import app

runner = CliRunner()


def test_missing_audio_file_is_an_input_error(tmp_path):
    result = runner.invoke(app, ["preview", str(tmp_path / "nope.wav"),
                                 str(tmp_path / "also_nope.wav")])
    assert result.exit_code == 2
    assert "no such audio file" in result.output


def test_unknown_blend_profile_lists_the_real_ones(tmp_path):
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    a.write_bytes(b"x"), b.write_bytes(b"x")
    result = runner.invoke(app, ["preview", str(a), str(b), "--profile", "wobble"])
    assert result.exit_code == 2
    assert "contour_blend" in result.output


def test_preview_is_reachable_from_the_main_cli():
    from dancelab.cli.analyze import app as main_app

    out = CliRunner().invoke(main_app, ["--help"]).output
    assert "preview" in out, "the renderer still has no way in"

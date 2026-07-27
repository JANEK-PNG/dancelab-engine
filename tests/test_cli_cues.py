"""CLI: `dancelab cues write --dry-run` plans + reports, writes nothing."""

import json
from pathlib import Path

from typer.testing import CliRunner

from dancelab.cli.cues import app
from dancelab.core.models import (
    SetPlan, SetTransition, AnalysisResult, BeatGrid, Track,
    TransitionWindow, WindowType,
)

runner = CliRunner()


def _bundle(tmp_path):
    set_plan = SetPlan(
        track_order=["A", "B"],
        transitions=[SetTransition(from_track_id="A", to_track_id="B",
                                   transition_score=0.8, harmonic_relation="adjacent")],
    )
    analyses = {
        tid: AnalysisResult(engine_version="t", track=Track(track_id=tid, title=tid),
                            beatgrid=BeatGrid(bpm=120.0, reliable=True))
        for tid in ("A", "B")
    }
    windows = {
        "A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
        "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9, window_type=WindowType.mix_in)],
    }
    bundle = {
        "set_plan": set_plan.model_dump(mode="json"),
        "analyses": {k: v.model_dump(mode="json") for k, v in analyses.items()},
        "windows": {k: [w.model_dump(mode="json") for w in v] for k, v in windows.items()},
    }
    p = tmp_path / "bundle.json"
    p.write_text(json.dumps(bundle))
    return p


def test_plan_only_is_the_default_and_writes_nothing(tmp_path):
    """No --write flag -> plan + report, nothing touched."""
    bundle = _bundle(tmp_path)
    no_db = tmp_path / "no_such_master.db"  # skip DB branch
    result = runner.invoke(app, [
        "write", "--set", str(bundle), "--mode", "in_out",
        "--on-conflict", "merge",
        "--db", str(no_db), "--timestamp", "20260724_1300",
    ])
    assert result.exit_code == 0, result.output
    assert "cues to write" in result.output
    assert "plan only" in result.output
    assert not no_db.exists()  # nothing created


def test_refuses_live_library_without_allow_live(tmp_path):
    """--write against the default (live) DB is refused unless --allow-live."""
    bundle = _bundle(tmp_path)
    result = runner.invoke(app, [
        "write", "--set", str(bundle), "--write",
        "--timestamp", "20260724_1300",
    ])
    assert result.exit_code == 2
    assert "Refusing to write the LIVE" in result.output


def test_restore_list_runs(tmp_path):
    result = runner.invoke(app, ["restore", "--list"])
    assert result.exit_code == 0

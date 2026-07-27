"""Shared fixtures. Tests run from the repo root (configs/ paths are relative)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolate_test_runtime(monkeypatch, tmp_path):
    """Run tests from the repo without touching the user's app storage."""
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("DANCELAB_CONFIG", "configs/default.yaml")

    import dancelab.storage.cache_manager as cache_manager_module

    test_cache = tmp_path / "cache"
    monkeypatch.setattr(cache_manager_module, "default_cache_root", lambda: test_cache)


@pytest.fixture
def config():
    from dancelab.core.config import load_config

    return load_config("configs/default.yaml")


# Tests that need a real Rekordbox library skip themselves elsewhere (CI, a
# fresh clone, or while Rekordbox is open). Those are the tests covering the
# code that writes to the DJ's library, so a silent skip turns a green run into
# a false reassurance. Say it out loud instead.
_LIBRARY_SKIP_HINTS = ("master.db", "pyrekordbox", "Rekordbox running")


def pytest_terminal_summary(terminalreporter):
    skipped = terminalreporter.stats.get("skipped", [])
    library_skips = [
        report for report in skipped
        if any(hint in str(report.longrepr) for hint in _LIBRARY_SKIP_HINTS)
    ]
    if not library_skips:
        return
    terminalreporter.write_sep("!", "REKORDBOX LIBRARY TESTS DID NOT RUN", red=True)
    terminalreporter.write_line(
        f"{len(library_skips)} test(s) covering writes to the Rekordbox library were "
        "skipped because no usable master.db was available (or Rekordbox is open)."
    )
    terminalreporter.write_line(
        "The database-free safety rules in tests/test_cue_write_ops.py still ran, "
        "but this run did NOT verify the Rekordbox I/O itself."
    )

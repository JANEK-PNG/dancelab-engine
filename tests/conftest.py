"""Shared fixtures. Tests run from the repo root (configs/ paths are relative)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolate_test_runtime(monkeypatch, tmp_path, request):
    """Run tests from the repo without touching the user's app storage."""
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("DANCELAB_CONFIG", "configs/default.yaml")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    import dancelab.storage.cache_manager as cache_manager_module

    test_cache = tmp_path / "cache"
    monkeypatch.setattr(cache_manager_module, "default_cache_root", lambda: test_cache)

    if Path(str(request.node.path)).name != "test_host_simple_mode.py":
        return

    from dancelab.host.desktop_app import desktop_available

    if not desktop_available():  # pragma: no cover - desktop dependency is optional
        return
    from dancelab.host.simple_mode import SimpleModeWindow

    test_autosave = tmp_path / "autosave" / "simple_mode_recovery.dlproj"
    monkeypatch.setattr(
        SimpleModeWindow,
        "_default_autosave_path",
        staticmethod(lambda: test_autosave),
    )


@pytest.fixture
def config():
    from dancelab.core.config import load_config

    return load_config("configs/default.yaml")

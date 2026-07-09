"""Shared fixtures. Tests run from the repo root (configs/ paths are relative)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("DANCELAB_CONFIG", "configs/default.yaml")


@pytest.fixture
def config():
    from dancelab.core.config import load_config

    return load_config("configs/default.yaml")

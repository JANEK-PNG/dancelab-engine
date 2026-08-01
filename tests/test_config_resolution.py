"""Configs must be findable from anywhere, not only from the source directory.

`dancelab room` from the home directory failed with "Config file not found:
configs/default.yaml" — the shipped defaults were relative paths that only
resolved when the working directory happened to be the repository. An installed
tool cannot ask its user to cd somewhere first.
"""

import pytest

from dancelab.core.config import load_config, load_weights
from dancelab.core.errors import ConfigError


def test_defaults_load_from_an_unrelated_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_config("configs/default.yaml") is not None
    assert load_weights("configs/descriptor_weights.yaml") is not None


def test_a_local_file_still_wins_over_the_shipped_one(tmp_path, monkeypatch):
    """A user's own config in the working directory must not be shadowed."""
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "descriptor_weights.yaml").write_text(
        (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "configs/descriptor_weights.yaml"
        ).read_text().replace("corpus_priors_weight: 1.0", "corpus_priors_weight: 0.0")
    )
    monkeypatch.chdir(tmp_path)
    assert load_weights("configs/descriptor_weights.yaml").corpus_priors_weight == 0.0


def test_a_genuinely_missing_config_still_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="not found"):
        load_config("configs/there_is_no_such_file.yaml")

"""cue_labels: defaults, comment rendering, user override merge."""

import yaml

from dancelab.decision.cue_labels import (
    load_cue_labels,
    render_comment,
    DEFAULT_CUE_LABELS,
)


def test_render_comment_omits_beats_when_none():
    assert render_comment("MIX OUT → next{beats}", None) == "MIX OUT → next"
    assert render_comment("MIX OUT → next{beats}", 32) == "MIX OUT → next (32 beats)"


def test_render_comment_without_token_is_passthrough():
    assert render_comment("MIX IN", 16) == "MIX IN"


def test_defaults_have_all_cue_types():
    for t in ("mix_in", "mix_out", "drop", "breakdown", "phrase", "unverified"):
        assert t in DEFAULT_CUE_LABELS
        assert "color" in DEFAULT_CUE_LABELS[t]
        assert "comment" in DEFAULT_CUE_LABELS[t]


def test_user_override_wins(tmp_path):
    p = tmp_path / "labels.yaml"
    p.write_text(yaml.safe_dump({"mix_in": {"comment": "IN!!!"}}))
    labels = load_cue_labels(p)
    assert labels["mix_in"]["comment"] == "IN!!!"
    # untouched types keep defaults
    assert labels["mix_out"]["comment"] == DEFAULT_CUE_LABELS["mix_out"]["comment"]
    # partial override keeps the non-overridden key (color) from default
    assert labels["mix_in"]["color"] == DEFAULT_CUE_LABELS["mix_in"]["color"]


def test_load_without_path_returns_defaults_copy():
    labels = load_cue_labels(None)
    labels["mix_in"]["comment"] = "mutated"
    assert DEFAULT_CUE_LABELS["mix_in"]["comment"] == "MIX IN"  # not mutated

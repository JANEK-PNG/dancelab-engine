"""Cue label config: per-cue-type color + comment template.

Ships sensible defaults; the DJ can override any color or comment in a YAML
file. Colors default to -1 (Rekordbox default) until the real palette is pinned
from the DJ's own DB (plan Task 11). Comment templates support the `{beats}`
token, rendered only when a reliable beat-count exists (ADR-005: never
fabricate).
"""

from __future__ import annotations

from pathlib import Path

import yaml

# `color` = Rekordbox hot-cue palette index (ColorTableIndex). Values below are
# proven valid — they already appear on the DJ's own cues. Semantic grouping:
# transition (mix_in/out) share one color, structural another, unverified a
# third. Exact hues are what Rekordbox renders for these indices; confirm/edit
# visually (colors are user-overridable). -1 = Rekordbox default.
_TRANSITION_COLOR = 0
_STRUCTURAL_COLOR = 22
_UNVERIFIED_COLOR = 56

DEFAULT_CUE_LABELS: dict[str, dict] = {
    "mix_in": {"color": _TRANSITION_COLOR, "comment": "MIX IN"},
    "mix_out": {"color": _TRANSITION_COLOR, "comment": "MIX OUT → next{beats}"},
    "drop": {"color": _STRUCTURAL_COLOR, "comment": "DROP"},
    "breakdown": {"color": _STRUCTURAL_COLOR, "comment": "BREAKDOWN"},
    "phrase": {"color": _STRUCTURAL_COLOR, "comment": "PHRASE"},
    "unverified": {"color": _UNVERIFIED_COLOR, "comment": "⚠ check by ear"},
}


def render_comment(template: str, beats: int | None) -> str:
    """Substitute the {beats} token; omit it entirely when beats is None."""
    if "{beats}" not in template:
        return template
    return template.replace("{beats}", f" ({beats} beats)" if beats is not None else "")


def load_cue_labels(path: Path | None = None) -> dict[str, dict]:
    """Return DEFAULT_CUE_LABELS deep-merged with an optional user YAML override.

    A fresh copy is always returned, so mutating the result never touches the
    module-level defaults.
    """
    merged = {k: dict(v) for k, v in DEFAULT_CUE_LABELS.items()}
    if path is not None and Path(path).exists():
        user = yaml.safe_load(Path(path).read_text()) or {}
        for cue_type, overrides in user.items():
            merged.setdefault(cue_type, {})
            merged[cue_type].update(overrides or {})
    return merged

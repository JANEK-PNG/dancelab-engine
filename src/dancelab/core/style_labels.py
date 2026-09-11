"""Umbrella genre labels: present in the data, refused as knowledge.

Streaming catalogs tag most electronic music with a top-level bucket —
"Electronic", "Dance" — and rekordbox copies that bucket into the track's
``style_label`` on import. Measured on the owner's collection 2026-09-10:
4 360 of 7 910 streams carry one of these two as their only genre.

An umbrella must score exactly like a missing genre: it says nothing about
whether the track fits a brief, and treating it as a real label made the
context fit *penalise* it (0.35 against 0.5 for unknown) while raising
confidence. Ingestion refuses to write these labels; scoring treats an
existing one as unknown. One list, two consumers, so they cannot drift.
"""

from __future__ import annotations

UMBRELLA_STYLE_LABELS = frozenset({"electronic", "dance", "music"})


def is_umbrella_style_label(label: str | None) -> bool:
    """True for a label that names a bucket, not a genre (case/space-insensitive)."""
    return bool(label) and label.strip().lower() in UMBRELLA_STYLE_LABELS


def effective_style_label(label: str | None) -> str | None:
    """The label as knowledge: ``None`` when it is missing or an umbrella."""
    return None if is_umbrella_style_label(label) else (label or None)

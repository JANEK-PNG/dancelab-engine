"""Lightweight source-file metadata extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioTagMetadata:
    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    bpm: float | None = None
    key: str | None = None


def _first_text(tags: dict, *keys: str) -> str | None:
    for key in keys:
        values = tags.get(key)
        if not values:
            continue
        if isinstance(values, (list, tuple)):
            value = values[0] if values else None
        else:
            value = values
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return None


def _parse_bpm(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    if not match:
        return None
    bpm = float(match.group(0))
    return bpm if bpm > 0 else None


def _normalize_genre(value: str | None) -> str | None:
    if not value:
        return None
    text = re.split(r"[;/|]", value, maxsplit=1)[0].strip()
    text = re.sub(r"\s+", "-", text.lower())
    return text or None


def read_audio_tags(path: str | Path) -> AudioTagMetadata:
    """Return source-backed tags when mutagen is installed; otherwise empty."""
    try:
        from mutagen import File
    except ImportError:
        return AudioTagMetadata()

    try:
        tagged = File(str(Path(path).expanduser()), easy=True)
    except Exception:
        return AudioTagMetadata()
    if tagged is None or not getattr(tagged, "tags", None):
        return AudioTagMetadata()

    tags = dict(tagged.tags or {})
    genre = _normalize_genre(_first_text(tags, "genre"))
    return AudioTagMetadata(
        title=_first_text(tags, "title"),
        artist=_first_text(tags, "artist", "albumartist", "composer"),
        genre=genre,
        bpm=_parse_bpm(_first_text(tags, "bpm")),
        key=_first_text(tags, "initialkey", "key"),
    )

"""Read-only parser for Rekordbox XML tempo references.

Rekordbox remains the owner of its library and beat grids. This module reads an
explicit XML export solely as an operational benchmark; it never opens or
modifies the Rekordbox database.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
import os
import unicodedata

from defusedxml import ElementTree as ET

MAX_REKORDBOX_XML_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class TempoMarker:
    time_sec: float
    bpm: float
    beat_in_bar: int


@dataclass(frozen=True)
class RekordboxTempoReference:
    track_id: str
    title: str
    artist: str
    source_path: str
    average_bpm: float
    tempo_markers: tuple[TempoMarker, ...]


def normalize_audio_path(value: str | Path) -> str:
    """Normalize a local path without resolving symlinks or touching disk."""
    raw = str(value)
    if raw.startswith("file:"):
        parsed = urlparse(raw)
        raw = unquote(parsed.path)
    normalized = unicodedata.normalize("NFC", raw)
    return os.path.normcase(os.path.normpath(normalized))


def load_rekordbox_tempo_references(path: Path) -> tuple[RekordboxTempoReference, ...]:
    if path.stat().st_size > MAX_REKORDBOX_XML_BYTES:
        raise ValueError(
            f"Rekordbox XML exceeds the {MAX_REKORDBOX_XML_BYTES}-byte safety limit"
        )
    root = ET.parse(path).getroot()
    references: list[RekordboxTempoReference] = []
    for element in root.findall("./COLLECTION/TRACK"):
        try:
            average_bpm = float(element.get("AverageBpm", "0"))
        except ValueError:
            average_bpm = 0.0
        location = element.get("Location", "")
        if average_bpm <= 0.0 or not location:
            continue

        markers: list[TempoMarker] = []
        for marker in element.findall("TEMPO"):
            try:
                time_sec = float(marker.get("Inizio", "nan"))
                bpm = float(marker.get("Bpm", "nan"))
                beat_in_bar = int(marker.get("Battito", "1"))
            except ValueError:
                continue
            if time_sec >= 0.0 and bpm > 0.0 and 1 <= beat_in_bar <= 4:
                markers.append(TempoMarker(time_sec, bpm, beat_in_bar))

        references.append(
            RekordboxTempoReference(
                track_id=element.get("TrackID", ""),
                title=element.get("Name", ""),
                artist=element.get("Artist", ""),
                source_path=normalize_audio_path(location),
                average_bpm=average_bpm,
                tempo_markers=tuple(sorted(markers, key=lambda item: item.time_sec)),
            )
        )
    return tuple(references)

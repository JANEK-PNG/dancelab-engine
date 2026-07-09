"""Rekordbox XML exporter (DJ_PLAYLISTS format).

Turns analyzed tracks + a set order + transition windows into a rekordbox.xml
that Rekordbox imports via its XML bridge (Preferences → Advanced → set the
Imported Library path). This carries our analysis so Rekordbox does not have to
re-analyze — SEE docs/rekordbox_import.md for the required import steps and the
honest caveats (RB re-analyzes unless the DJ unchecks Beatgrid; XML is a
separate view; right-click tracks+playlists to import).

Schema (researched — pyrekordbox / Rekordbox 7 manual):
  DJ_PLAYLISTS
    PRODUCT
    COLLECTION Entries
      TRACK TrackID Location AverageBpm Tonality TotalTime Name Artist Kind ...
        TEMPO Inizio Bpm Metro Battito         (beatgrid)
        POSITION_MARK Name Type Start Num ...  (cues: Num -1 memory, 0-7 hot A-H)
    PLAYLISTS
      NODE Type=0 (ROOT) → NODE Type=1 (playlist) → TRACK Key=TrackID

Stdlib only (xml.etree). Deterministic.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from dancelab import __version__
from dancelab.core.models import AnalysisResult, SetPlan, TransitionWindow, WindowType

# hot-cue colours (Rekordbox RGB) cycled across cue points
_CUE_COLOURS = [(40, 226, 20), (48, 90, 255), (255, 140, 0), (195, 47, 255),
                (255, 18, 123), (0, 224, 224), (230, 40, 40), (180, 180, 0)]


def _location_uri(source_path: str | None) -> str:
    """Absolute file path → Rekordbox file URI (file://localhost/… percent-encoded)."""
    if not source_path:
        return ""
    p = Path(source_path).resolve()
    return "file://localhost" + quote(str(p))


def _kind(source_path: str | None) -> str:
    ext = Path(source_path).suffix.lower().lstrip(".") if source_path else ""
    return {"mp3": "MP3 File", "aiff": "AIFF File", "aif": "AIFF File",
            "wav": "WAV File", "flac": "FLAC File", "m4a": "M4A File"}.get(ext, "Audio File")


def _track_windows_as_cues(
    windows: list[TransitionWindow], max_cues: int = 8
) -> list[tuple[str, float, int]]:
    """(label, start_sec, num) hot cues from transition windows, best first."""
    cues: list[tuple[str, float, int]] = []
    for i, w in enumerate(sorted(windows, key=lambda w: -w.score)[:max_cues]):
        label = {WindowType.mix_in: "Mix In", WindowType.mix_out: "Mix Out",
                 WindowType.bridge: "Bridge", WindowType.reset: "Reset"}.get(
                     w.window_type, "Cue")
        cues.append((label, w.start_sec, i))  # Num 0-7 → hot cues A-H
    return cues


def _track_element(
    analysis: AnalysisResult,
    track_id: int,
    windows: list[TransitionWindow] | None,
) -> ET.Element:
    t = analysis.track
    attrs = {
        "TrackID": str(track_id),
        "Name": t.title or "",
        "Artist": t.artist or "",
        "Location": _location_uri(t.source_path),
        "Kind": _kind(t.source_path),
        "TotalTime": str(int(t.duration_sec)) if t.duration_sec else "0",
    }
    if t.bpm_estimate:
        attrs["AverageBpm"] = f"{t.bpm_estimate:.2f}"
    if t.key_estimate:
        attrs["Tonality"] = t.key_estimate  # Camelot (e.g. "8A")
    if t.sample_rate:
        attrs["SampleRate"] = str(t.sample_rate)
    track_el = ET.Element("TRACK", attrs)

    # beatgrid → single TEMPO at the first beat (constant-tempo assumption)
    if analysis.beatgrid and analysis.beatgrid.beat_times_sec:
        first = (analysis.beatgrid.downbeats_sec or analysis.beatgrid.beat_times_sec)[0]
        ET.SubElement(track_el, "TEMPO", {
            "Inizio": f"{first:.3f}", "Bpm": f"{analysis.beatgrid.bpm:.2f}",
            "Metro": "4/4", "Battito": "1",
        })

    # transition windows → hot cues at mix points
    for label, start, num in _track_windows_as_cues(windows or []):
        r, g, b = _CUE_COLOURS[num % len(_CUE_COLOURS)]
        ET.SubElement(track_el, "POSITION_MARK", {
            "Name": label, "Type": "0", "Start": f"{start:.3f}",
            "Num": str(num), "Red": str(r), "Green": str(g), "Blue": str(b),
        })
    return track_el


def build_rekordbox_xml(
    analyses: list[AnalysisResult],
    set_plan: SetPlan | None = None,
    windows_by_track: dict[str, list[TransitionWindow]] | None = None,
    playlist_name: str = "DanceLab Set",
) -> str:
    """Build a DJ_PLAYLISTS XML string.

    set_plan (optional) orders the playlist; otherwise input order is used.
    windows_by_track (optional) supplies hot-cue points per track_id.
    """
    order = set_plan.track_order if set_plan else [a.track.track_id for a in analyses]
    by_id = {a.track.track_id: a for a in analyses}
    order = [tid for tid in order if tid in by_id]  # keep only known tracks

    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    ET.SubElement(root, "PRODUCT", {
        "Name": "DanceLab Engine", "Version": __version__, "Company": "DanceLab",
    })

    collection = ET.SubElement(root, "COLLECTION", {"Entries": str(len(order))})
    id_map: dict[str, int] = {}
    for i, tid in enumerate(order, start=1):
        id_map[tid] = i
        collection.append(_track_element(
            by_id[tid], i, (windows_by_track or {}).get(tid)
        ))

    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", {"Type": "0", "Name": "ROOT", "Count": "1"})
    pl = ET.SubElement(root_node, "NODE", {
        "Type": "1", "Name": playlist_name, "KeyType": "0", "Entries": str(len(order)),
    })
    for tid in order:
        ET.SubElement(pl, "TRACK", {"Key": str(id_map[tid])})

    ET.indent(root)  # pretty-print (py3.9+)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def write_rekordbox_xml(xml: str, path: str | Path) -> Path:
    p = Path(path)
    p.write_text(xml, encoding="utf-8")
    return p

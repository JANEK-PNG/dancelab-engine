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
        TEMPO Inizio Bpm Metro Battito         (optional diagnostic beatgrid)
        POSITION_MARK Name Type Start Num ...  (cues: Num -1 memory, 0-7 hot A-H)
    PLAYLISTS
      NODE Type=0 (ROOT) → NODE Type=1 (playlist) → TRACK Key=TrackID

Stdlib only (xml.etree). Deterministic.

AUD-L6 — constant-tempo assumption: diagnostic beatgrid export can emit a
single TEMPO node per track, but production Rekordbox export leaves BPM/grid to
Rekordbox and writes playlist order + hot cues only.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from dancelab import __version__
from dancelab.core.models import AnalysisResult, BeatGrid, SetPlan, TransitionWindow, WindowType
from dancelab.decision.transition_windows import rank_windows_for_role

# hot-cue colours (Rekordbox RGB) cycled across cue points
_CUE_COLOURS = [
    (40, 226, 20),
    (48, 90, 255),
    (255, 140, 0),
    (195, 47, 255),
    (255, 18, 123),
    (0, 224, 224),
    (230, 40, 40),
    (180, 180, 0),
]
_CUE_PHRASE_DIVISIONS_BEATS = (64, 32, 16, 8, 4, 2)
_CUE_PHRASE_SNAP_TOLERANCE_BEATS = {
    64: 4.0,
    32: 4.0,
    16: 4.0,
    8: 2.0,
    4: 1.0,
    2: 0.5,
}
_CUE_TRANSITION_BASELINE_BEATS = 64


def _location_uri(source_path: str | None) -> str:
    """Absolute file path → Rekordbox file URI (file://localhost/…).

    Encoding must mirror what Rekordbox itself writes, or its importer fails
    to match the file and silently drops our hot cues (verified against a
    real device library full of "(Original Mix)" / "O'Flynn" names — RB
    leaves ()'!&+,;=@$~[] literal and percent-encodes spaces as %20).
    XML-level escaping (& → &amp;) is handled by the XML writer, not here."""
    if not source_path:
        return ""
    p = Path(source_path).resolve()
    return "file://localhost" + quote(str(p), safe="/()'!&+,;=@$~[]")


def _kind(source_path: str | None) -> str:
    ext = Path(source_path).suffix.lower().lstrip(".") if source_path else ""
    return {
        "mp3": "MP3 File",
        "aiff": "AIFF File",
        "aif": "AIFF File",
        "wav": "WAV File",
        "flac": "FLAC File",
        "m4a": "M4A File",
    }.get(ext, "Audio File")


def _usable_export_grid(beatgrid: BeatGrid | None) -> BeatGrid | None:
    """Only grids with verified bar phase may become Rekordbox TEMPO data."""
    if (
        beatgrid is None
        or not beatgrid.reliable
        or not beatgrid.downbeat_phase_verified
        or not beatgrid.beat_times_sec
    ):
        return None
    return beatgrid


def _usable_beat_grid(beatgrid: BeatGrid | None) -> BeatGrid | None:
    """A reliable beat sequence may snap cues to beats without claiming phrases."""
    if beatgrid is None or not beatgrid.reliable or not beatgrid.beat_times_sec:
        return None
    return beatgrid


def _grid_anchor_sec(beatgrid: BeatGrid) -> float:
    return float((beatgrid.downbeats_sec or beatgrid.beat_times_sec)[0])


def _cue_phrase_division(beatgrid: BeatGrid, cue_sec: float) -> int | None:
    """Largest phrase division the cue sits on, measured from the grid anchor."""
    if beatgrid.bpm <= 0:
        return None
    beat_period = 60.0 / beatgrid.bpm
    beat_index = int(round((cue_sec - _grid_anchor_sec(beatgrid)) / beat_period))
    if beat_index < 0:
        return None
    for division in _CUE_PHRASE_DIVISIONS_BEATS:
        if beat_index % division == 0:
            return division
    return None


def _snap_to_phrase_grid(beatgrid: BeatGrid, target_sec: float) -> float:
    """Snap hot cues to phrase-aware beat boundaries, not arbitrary beats.

    The exporter writes actionable DJ hot cues, so starts should land on
    musically countable positions: 64/32/16/8/4/2-beat boundaries from the
    first exported downbeat. This prevents cues landing on e.g. beat 3 when the
    usable phrase point is beat 4.
    """
    if beatgrid.bpm <= 0:
        return target_sec

    beat_period = 60.0 / beatgrid.bpm
    anchor = _grid_anchor_sec(beatgrid)
    target_beat = (target_sec - anchor) / beat_period
    if target_beat < 0:
        return anchor

    for division in _CUE_PHRASE_DIVISIONS_BEATS:
        boundary = max(0, round(target_beat / division) * division)
        offset_beats = abs(target_beat - boundary)
        if boundary == 0 and target_beat > _CUE_PHRASE_SNAP_TOLERANCE_BEATS[2]:
            continue
        if offset_beats <= _CUE_PHRASE_SNAP_TOLERANCE_BEATS[division]:
            return anchor + boundary * beat_period

    # Last-resort safety: keep the cue on a 2-beat count rather than a random
    # off-count. This branch should be rare because division=2 is already lenient.
    boundary = max(0, round(target_beat / 2) * 2)
    return anchor + boundary * beat_period


def _snap_cue_start(analysis: AnalysisResult, start_sec: float) -> float:
    """Snap to a phrase only with verified phase; otherwise to the nearest beat."""
    beatgrid = _usable_beat_grid(analysis.beatgrid)
    if beatgrid is None:
        return start_sec
    if beatgrid.downbeat_phase_verified:
        return _snap_to_phrase_grid(beatgrid, start_sec)
    return float(min(beatgrid.beat_times_sec, key=lambda beat: abs(beat - start_sec)))


def _cue_min_separation_sec(analysis: AnalysisResult) -> float:
    duration = analysis.track.duration_sec or 0.0
    if duration <= 0:
        return 24.0
    return float(max(12.0, min(32.0, duration / 4.0)))


def _cue_priority(cue_profile: str) -> list[WindowType]:
    if cue_profile == "single":
        return []
    if cue_profile == "first":
        return [WindowType.mix_out, WindowType.bridge, WindowType.reset]
    if cue_profile == "last":
        return [WindowType.mix_in, WindowType.bridge, WindowType.reset]
    return [WindowType.mix_in, WindowType.mix_out, WindowType.bridge, WindowType.reset]


def _cue_label(window_type: WindowType, index_for_type: int) -> str:
    label = {
        WindowType.mix_in: "Mix In",
        WindowType.mix_out: "Mix Out",
        WindowType.bridge: "Bridge",
        WindowType.reset: "Reset",
        WindowType.peak_handoff: "Peak Handoff",
    }.get(window_type, "Cue")
    return label if index_for_type == 1 else f"{label} {index_for_type}"


def _track_windows_as_cues(
    analysis: AnalysisResult,
    windows: list[TransitionWindow],
    *,
    cue_profile: str,
    max_cues: int = 4,
) -> list[tuple[str, float, int]]:
    """(label, start_sec, num) hot cues from diverse, grid-snapped windows.

    A live playlist needs readable cue intent more than eight high-scoring
    markers. Select at most one strong cue per transition role first, enforce
    temporal separation, and only then fill remaining slots from fallback
    windows.
    """
    selected: list[TransitionWindow] = []
    min_sep = _cue_min_separation_sec(analysis)

    def try_add(window: TransitionWindow) -> bool:
        cue_start = _snap_cue_start(analysis, window.start_sec)
        if any(
            abs(cue_start - _snap_cue_start(analysis, item.start_sec)) < min_sep
            for item in selected
        ):
            return False
        selected.append(window)
        return True

    sorted_windows = sorted(windows, key=lambda window: window.score, reverse=True)
    beatgrid = _usable_export_grid(analysis.beatgrid)
    safe_mix_outs = rank_windows_for_role(
        sorted_windows,
        WindowType.mix_out,
        track_duration_sec=analysis.track.duration_sec,
        bpm=analysis.track.bpm_estimate or (beatgrid.bpm if beatgrid else None),
        transition_beats=_CUE_TRANSITION_BASELINE_BEATS,
        allow_infeasible_fallback=False,
    )
    eligible_windows = [
        window
        for window in sorted_windows
        if window.window_type != WindowType.mix_out or window in safe_mix_outs
    ]
    for window_type in _cue_priority(cue_profile):
        candidates = rank_windows_for_role(
            eligible_windows,
            window_type,
            track_duration_sec=analysis.track.duration_sec,
            bpm=analysis.track.bpm_estimate or (beatgrid.bpm if beatgrid else None),
            transition_beats=_CUE_TRANSITION_BASELINE_BEATS,
            allow_infeasible_fallback=False,
        )
        if candidates and try_add(candidates[0]) and len(selected) >= max_cues:
            break

    if len(selected) < max_cues:
        for window in eligible_windows:
            if window in selected:
                continue
            try_add(window)
            if len(selected) >= max_cues:
                break

    type_counts: dict[WindowType, int] = {}
    cues: list[tuple[str, float, int]] = []
    for num, window in enumerate(selected[:max_cues]):
        type_counts[window.window_type] = type_counts.get(window.window_type, 0) + 1
        cues.append(
            (
                _cue_label(window.window_type, type_counts[window.window_type]),
                _snap_cue_start(analysis, window.start_sec),
                num,
            )
        )
    return cues


def track_windows_as_cues(
    analysis: AnalysisResult,
    windows: list[TransitionWindow],
    *,
    cue_profile: str = "middle",
    max_cues: int = 4,
) -> list[tuple[str, float, int]]:
    """Public preview of the exact hot cues the Rekordbox exporter will use."""
    return _track_windows_as_cues(
        analysis,
        windows,
        cue_profile=cue_profile,
        max_cues=max_cues,
    )


def _track_element(
    analysis: AnalysisResult,
    track_id: int,
    windows: list[TransitionWindow] | None,
    *,
    cue_profile: str = "middle",
    export_beatgrid: bool = False,
) -> ET.Element:
    t = analysis.track
    attrs = {
        "TrackID": str(track_id),
        "Name": t.title or "",
        "Artist": t.artist or "",
        "Location": _location_uri(t.source_path),
        "Kind": _kind(t.source_path),
        # AUD-L4: round, don't truncate (300.9s → "301", not "300").
        "TotalTime": str(round(t.duration_sec)) if t.duration_sec else "0",
    }
    # Beat sync/grid belongs to DanceLab preview. The default Rekordbox export
    # intentionally avoids AverageBpm/TEMPO so RB can keep or compute its own
    # native grid. Set export_beatgrid=True only for explicit diagnostic exports.
    export_grid = _usable_export_grid(analysis.beatgrid) if export_beatgrid else None
    if export_grid:
        attrs["AverageBpm"] = f"{export_grid.bpm:.2f}"
    if t.key_estimate:
        attrs["Tonality"] = t.key_estimate  # Camelot (e.g. "8A")
    if t.sample_rate:
        attrs["SampleRate"] = str(t.sample_rate)
    track_el = ET.Element("TRACK", attrs)

    # Optional beatgrid → single TEMPO at the first beat (diagnostic/legacy only).
    if export_grid:
        first = (export_grid.downbeats_sec or export_grid.beat_times_sec)[0]
        ET.SubElement(
            track_el,
            "TEMPO",
            {
                "Inizio": f"{first:.3f}",
                "Bpm": f"{export_grid.bpm:.2f}",
                "Metro": "4/4",
                "Battito": "1",
            },
        )

    # transition windows → hot cues at mix points
    for label, start, num in _track_windows_as_cues(
        analysis,
        windows or [],
        cue_profile=cue_profile,
    ):
        r, g, b = _CUE_COLOURS[num % len(_CUE_COLOURS)]
        ET.SubElement(
            track_el,
            "POSITION_MARK",
            {
                "Name": label,
                "Type": "0",
                "Start": f"{start:.3f}",
                "Num": str(num),
                "Red": str(r),
                "Green": str(g),
                "Blue": str(b),
            },
        )
    return track_el


def build_rekordbox_xml(
    analyses: list[AnalysisResult],
    set_plan: SetPlan | None = None,
    windows_by_track: dict[str, list[TransitionWindow]] | None = None,
    playlist_name: str = "DanceLab Set",
    *,
    export_beatgrid: bool = False,
) -> str:
    """Build a DJ_PLAYLISTS XML string.

    set_plan (optional) orders the playlist; otherwise input order is used.
    windows_by_track (optional) supplies hot-cue points per track_id.
    export_beatgrid defaults to False: DanceLab exports playlist/hot cues, while
    Rekordbox keeps responsibility for native BPM/beatgrid analysis.
    """
    order = set_plan.track_order if set_plan else [a.track.track_id for a in analyses]
    by_id = {a.track.track_id: a for a in analyses}
    order = [tid for tid in order if tid in by_id]  # keep only known tracks

    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    ET.SubElement(
        root,
        "PRODUCT",
        {
            "Name": "DanceLab Engine",
            "Version": __version__,
            "Company": "DanceLab",
        },
    )

    collection = ET.SubElement(root, "COLLECTION", {"Entries": str(len(order))})
    id_map: dict[str, int] = {}
    for i, tid in enumerate(order, start=1):
        id_map[tid] = i
        if len(order) <= 1:
            cue_profile = "single"
        elif i == 1:
            cue_profile = "first"
        elif i == len(order):
            cue_profile = "last"
        else:
            cue_profile = "middle"
        collection.append(
            _track_element(
                by_id[tid],
                i,
                (windows_by_track or {}).get(tid),
                cue_profile=cue_profile,
                export_beatgrid=export_beatgrid,
            )
        )

    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", {"Type": "0", "Name": "ROOT", "Count": "1"})
    pl = ET.SubElement(
        root_node,
        "NODE",
        {
            "Type": "1",
            "Name": playlist_name,
            "KeyType": "0",
            "Entries": str(len(order)),
        },
    )
    for tid in order:
        ET.SubElement(pl, "TRACK", {"Key": str(id_map[tid])})

    ET.indent(root)  # pretty-print (py3.9+)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def write_rekordbox_xml(xml: str, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(xml, encoding="utf-8")
    return p

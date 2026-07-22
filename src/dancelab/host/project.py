"""DanceLab project files (.dlproj).

The active format stores the guided Simple Mode session while keeping the
legacy graph fields readable for backward compatibility. Heavy analyses stay
in the external cache. This module is headless so persistence remains testable
without Qt and reusable by other hosts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dancelab.core.errors import DanceLabError

PROJECT_FILE_SUFFIX = ".dlproj"
PROJECT_FORMAT_VERSION = 1
MAX_PROJECT_BYTES = 10 * 1024 * 1024
MAX_PROJECT_TEXT_LENGTH = 4096
MAX_PROJECT_SOURCE_FILES = 5000
MAX_PROJECT_NODES = 2000
MAX_PROJECT_CONNECTIONS = 10_000
MAX_PROJECT_DEVICE_TRACKS = 5000
MAX_PROJECT_CUES_PER_TRACK = 64


class ProjectFileError(DanceLabError):
    """Project file is missing, unreadable, or from an unsupported format."""


def _bounded_list(value: object, label: str, limit: int) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    if len(value) > limit:
        raise ValueError(f"{label} exceeds the limit of {limit}")
    return value


def _bounded_mapping(value: object, label: str, limit: int) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    if len(value) > limit:
        raise ValueError(f"{label} exceeds the limit of {limit}")
    return value


def _bounded_text(value: object, label: str) -> str:
    text = str(value)
    if len(text) > MAX_PROJECT_TEXT_LENGTH:
        raise ValueError(f"{label} exceeds {MAX_PROJECT_TEXT_LENGTH} characters")
    return text


@dataclass
class ProjectNode:
    instance_id: str
    node_id: str
    x: float
    y: float


@dataclass
class ProjectConnection:
    from_instance_id: str
    from_port_key: str
    to_instance_id: str
    to_port_key: str


@dataclass
class SimpleModeProjectState:
    """Lightweight Simple Mode session; heavy analyses remain external."""

    source_files: list[str] = field(default_factory=list)
    analysis_track_ids: dict[str, str] = field(default_factory=dict)
    current_step: int = 1
    target_mode: str = "count"
    target_track_count: int = 10
    target_duration_hours: float = 1.0
    brief_preset_id: str = "custom"
    style_focus: str = ""
    bpm_min: float | None = None
    bpm_max: float | None = None
    set_role: str = "builder"
    crowd_energy: str = "medium"
    energy_arc: str = "build"
    planner_mode: str = "smart"
    novelty_mode: str = "balanced"
    seed: int = 0
    must_have_ids: list[str] = field(default_factory=list)
    not_tonight_ids: list[str] = field(default_factory=list)
    locked_positions: dict[int, str] = field(default_factory=dict)
    plan: dict[str, Any] | None = None
    review_analysis_depth: str = "normal"
    playlist_name: str = "DanceLab Smart Set"
    export_path: str = ""
    annotator: str = ""
    blind_review: bool = False
    device_cues: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class DanceLabProject:
    name: str = "Untitled Project"
    workspace: str = "simple"
    # Legacy visual-host payload. Keep reading it so old files fail gracefully
    # in Simple Mode instead of becoming unreadable.
    nodes: list[ProjectNode] = field(default_factory=list)
    connections: list[ProjectConnection] = field(default_factory=list)
    node_configs: dict[str, dict] = field(default_factory=dict)
    simple_mode: SimpleModeProjectState | None = None
    format_version: int = PROJECT_FORMAT_VERSION


def save_project(project: DanceLabProject, path: str | Path) -> Path:
    p = Path(path)
    if p.suffix != PROJECT_FILE_SUFFIX:
        p = p.with_suffix(PROJECT_FILE_SUFFIX)
    p.parent.mkdir(parents=True, exist_ok=True)
    temporary = p.with_suffix(p.suffix + ".tmp")
    payload = json.dumps(asdict(project), indent=2, ensure_ascii=False)
    if len(payload.encode("utf-8")) > MAX_PROJECT_BYTES:
        raise ProjectFileError(
            f"Project exceeds the maximum size of {MAX_PROJECT_BYTES} bytes"
        )
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(p)
    return p


def load_project(path: str | Path) -> DanceLabProject:
    p = Path(path)
    if not p.exists():
        raise ProjectFileError(f"Project file not found: {p}")
    try:
        if p.stat().st_size > MAX_PROJECT_BYTES:
            raise ProjectFileError(
                f"Project file exceeds the maximum size of {MAX_PROJECT_BYTES} bytes"
            )
        data = json.loads(p.read_text(encoding="utf-8"))
    except ProjectFileError:
        raise
    except (OSError, json.JSONDecodeError, RecursionError) as exc:
        raise ProjectFileError(f"Cannot read project file {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectFileError(f"Malformed project file {p}: root must be an object")
    version = data.get("format_version")
    if version != PROJECT_FORMAT_VERSION:
        raise ProjectFileError(
            f"Unsupported project format {version!r} (this build reads {PROJECT_FORMAT_VERSION})."
        )
    try:
        simple_mode_data = data.get("simple_mode")
        simple_mode = None
        if simple_mode_data is not None:
            if not isinstance(simple_mode_data, dict):
                raise TypeError("simple_mode must be an object")
            source_files = _bounded_list(
                simple_mode_data.get("source_files", []),
                "simple_mode.source_files",
                MAX_PROJECT_SOURCE_FILES,
            )
            analysis_track_ids_data = _bounded_mapping(
                simple_mode_data.get("analysis_track_ids", {}),
                "simple_mode.analysis_track_ids",
                MAX_PROJECT_SOURCE_FILES,
            )
            must_have_ids = _bounded_list(
                simple_mode_data.get("must_have_ids", []),
                "simple_mode.must_have_ids",
                MAX_PROJECT_SOURCE_FILES,
            )
            not_tonight_ids = _bounded_list(
                simple_mode_data.get("not_tonight_ids", []),
                "simple_mode.not_tonight_ids",
                MAX_PROJECT_SOURCE_FILES,
            )
            locked_positions_data = _bounded_mapping(
                simple_mode_data.get("locked_positions", {}),
                "simple_mode.locked_positions",
                MAX_PROJECT_SOURCE_FILES,
            )
            device_cues_data = _bounded_mapping(
                simple_mode_data.get("device_cues", {}),
                "simple_mode.device_cues",
                MAX_PROJECT_DEVICE_TRACKS,
            )
            locked_positions = {
                int(position): _bounded_text(
                    track_id, f"simple_mode.locked_positions[{position!r}]"
                )
                for position, track_id in locked_positions_data.items()
            }
            device_cues: dict[str, list[dict[str, Any]]] = {}
            for name, cues in device_cues_data.items():
                safe_name = _bounded_text(name, "simple_mode.device_cues key")
                cue_rows = _bounded_list(
                    cues,
                    f"simple_mode.device_cues[{safe_name!r}]",
                    MAX_PROJECT_CUES_PER_TRACK,
                )
                if not all(isinstance(cue, dict) for cue in cue_rows):
                    raise TypeError(
                        f"simple_mode.device_cues[{safe_name!r}] entries must be objects"
                    )
                device_cues[safe_name] = [dict(cue) for cue in cue_rows]
            current_step = int(simple_mode_data.get("current_step", 1))
            if current_step < 0 or current_step > 5:
                raise ValueError("simple_mode.current_step must be between 0 and 5")
            simple_mode = SimpleModeProjectState(
                source_files=[
                    _bounded_text(path, "simple_mode.source_files entry")
                    for path in source_files
                ],
                analysis_track_ids={
                    _bounded_text(path, "simple_mode.analysis_track_ids key"):
                    _bounded_text(track_id, "simple_mode.analysis_track_ids value")
                    for path, track_id in analysis_track_ids_data.items()
                },
                current_step=current_step,
                target_mode=str(simple_mode_data.get("target_mode") or "count"),
                target_track_count=int(simple_mode_data.get("target_track_count", 10)),
                target_duration_hours=float(simple_mode_data.get("target_duration_hours", 1.0)),
                brief_preset_id=str(simple_mode_data.get("brief_preset_id") or "custom"),
                style_focus=str(simple_mode_data.get("style_focus") or ""),
                bpm_min=(
                    float(simple_mode_data["bpm_min"])
                    if simple_mode_data.get("bpm_min") is not None
                    else None
                ),
                bpm_max=(
                    float(simple_mode_data["bpm_max"])
                    if simple_mode_data.get("bpm_max") is not None
                    else None
                ),
                set_role=str(simple_mode_data.get("set_role") or "builder"),
                crowd_energy=str(simple_mode_data.get("crowd_energy") or "medium"),
                energy_arc=str(simple_mode_data.get("energy_arc") or "build"),
                planner_mode=str(simple_mode_data.get("planner_mode") or "smart"),
                novelty_mode=str(simple_mode_data.get("novelty_mode") or "balanced"),
                seed=int(simple_mode_data.get("seed", 0)),
                must_have_ids=[
                    _bounded_text(value, "simple_mode.must_have_ids entry")
                    for value in must_have_ids
                ],
                not_tonight_ids=[
                    _bounded_text(value, "simple_mode.not_tonight_ids entry")
                    for value in not_tonight_ids
                ],
                locked_positions=locked_positions,
                plan=(
                    dict(simple_mode_data["plan"])
                    if simple_mode_data.get("plan") is not None
                    else None
                ),
                review_analysis_depth=str(
                    simple_mode_data.get("review_analysis_depth") or "normal"
                ),
                playlist_name=str(
                    simple_mode_data.get("playlist_name") or "DanceLab Smart Set"
                ),
                export_path=str(simple_mode_data.get("export_path") or ""),
                annotator=str(simple_mode_data.get("annotator") or ""),
                blind_review=bool(simple_mode_data.get("blind_review", False)),
                device_cues=device_cues,
            )
        workspace = str(data.get("workspace") or ("simple" if simple_mode else "graph"))
        if workspace not in {"graph", "simple"}:
            raise ValueError(f"unsupported workspace {workspace!r}")
        nodes_data = _bounded_list(data.get("nodes", []), "nodes", MAX_PROJECT_NODES)
        connections_data = _bounded_list(
            data.get("connections", []),
            "connections",
            MAX_PROJECT_CONNECTIONS,
        )
        node_configs_data = _bounded_mapping(
            data.get("node_configs", {}),
            "node_configs",
            MAX_PROJECT_NODES,
        )
        return DanceLabProject(
            name=_bounded_text(data.get("name") or "Untitled Project", "name"),
            workspace=workspace,
            nodes=[ProjectNode(**node) for node in nodes_data],
            connections=[ProjectConnection(**conn) for conn in connections_data],
            node_configs={
                _bounded_text(key, "node_configs key"): dict(value)
                for key, value in node_configs_data.items()
            },
            simple_mode=simple_mode,
            format_version=version,
        )
    except (TypeError, ValueError) as exc:
        raise ProjectFileError(f"Malformed project file {p}: {exc}") from exc

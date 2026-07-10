"""DanceLab project files (.dlproj) — UI/UX audit Priority 1.

A project is the saved state of the desktop host graph: node instances with
canvas positions, connections, and per-node configs. Blender-style model: the
user always works "in a project"; New/Open/Save/Save As live in the File menu.

Plain JSON, headless (no Qt imports) so persistence is testable without a
display and other hosts can reuse it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dancelab.core.errors import DanceLabError

PROJECT_FILE_SUFFIX = ".dlproj"
PROJECT_FORMAT_VERSION = 1


class ProjectFileError(DanceLabError):
    """Project file is missing, unreadable, or from an unsupported format."""


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
class DanceLabProject:
    name: str = "Untitled Project"
    nodes: list[ProjectNode] = field(default_factory=list)
    connections: list[ProjectConnection] = field(default_factory=list)
    node_configs: dict[str, dict] = field(default_factory=dict)
    format_version: int = PROJECT_FORMAT_VERSION


def save_project(project: DanceLabProject, path: str | Path) -> Path:
    p = Path(path)
    if p.suffix != PROJECT_FILE_SUFFIX:
        p = p.with_suffix(PROJECT_FILE_SUFFIX)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(project), indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def load_project(path: str | Path) -> DanceLabProject:
    p = Path(path)
    if not p.exists():
        raise ProjectFileError(f"Project file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectFileError(f"Cannot read project file {p}: {exc}") from exc
    version = data.get("format_version")
    if version != PROJECT_FORMAT_VERSION:
        raise ProjectFileError(
            f"Unsupported project format {version!r} (this build reads {PROJECT_FORMAT_VERSION})."
        )
    try:
        return DanceLabProject(
            name=str(data.get("name") or "Untitled Project"),
            nodes=[ProjectNode(**node) for node in data.get("nodes", [])],
            connections=[ProjectConnection(**conn) for conn in data.get("connections", [])],
            node_configs={
                str(key): dict(value) for key, value in data.get("node_configs", {}).items()
            },
            format_version=version,
        )
    except TypeError as exc:
        raise ProjectFileError(f"Malformed project file {p}: {exc}") from exc

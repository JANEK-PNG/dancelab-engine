"""DanceLab project file (.dlproj) persistence — headless, no Qt required."""

import json

import pytest

from dancelab.host.project import (
    PROJECT_FILE_SUFFIX,
    DanceLabProject,
    ProjectConnection,
    ProjectFileError,
    ProjectNode,
    load_project,
    save_project,
)


def _sample_project() -> DanceLabProject:
    return DanceLabProject(
        name="Friday Set",
        nodes=[
            ProjectNode(instance_id="desktop_engine_1", node_id="engine", x=560.0, y=120.0),
            ProjectNode(instance_id="desktop_upload_tracks_2", node_id="upload_tracks", x=120.0, y=390.0),
            ProjectNode(instance_id="desktop_analyze_tracks_3", node_id="analyze_tracks", x=380.0, y=390.0),
        ],
        connections=[
            ProjectConnection(
                from_instance_id="desktop_upload_tracks_2",
                from_port_key="tracks",
                to_instance_id="desktop_analyze_tracks_3",
                to_port_key="tracks",
            )
        ],
        node_configs={"desktop_upload_tracks_2": {"paths_text": "/tmp/a.mp3\n/tmp/b.mp3"}},
    )


def test_project_roundtrip(tmp_path):
    saved = save_project(_sample_project(), tmp_path / "friday")
    assert saved.suffix == PROJECT_FILE_SUFFIX

    loaded = load_project(saved)
    assert loaded.name == "Friday Set"
    assert [n.instance_id for n in loaded.nodes] == [
        "desktop_engine_1",
        "desktop_upload_tracks_2",
        "desktop_analyze_tracks_3",
    ]
    assert loaded.nodes[1].x == 120.0 and loaded.nodes[1].y == 390.0
    assert loaded.connections[0].to_port_key == "tracks"
    assert loaded.node_configs["desktop_upload_tracks_2"]["paths_text"].endswith("b.mp3")


def test_missing_project_fails_loud(tmp_path):
    with pytest.raises(ProjectFileError, match="not found"):
        load_project(tmp_path / "nope.dlproj")


def test_unsupported_format_version_fails_loud(tmp_path):
    p = tmp_path / "future.dlproj"
    p.write_text(json.dumps({"format_version": 999, "nodes": []}), encoding="utf-8")
    with pytest.raises(ProjectFileError, match="Unsupported project format"):
        load_project(p)


def test_malformed_project_fails_loud(tmp_path):
    p = tmp_path / "broken.dlproj"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProjectFileError, match="Cannot read"):
        load_project(p)

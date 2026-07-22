"""DanceLab project file (.dlproj) persistence — headless, no Qt required."""

import json

import pytest

from dancelab.host.project import (
    MAX_PROJECT_BYTES,
    MAX_PROJECT_NODES,
    PROJECT_FILE_SUFFIX,
    DanceLabProject,
    ProjectConnection,
    ProjectFileError,
    ProjectNode,
    SimpleModeProjectState,
    load_project,
    save_project,
)


def _sample_project() -> DanceLabProject:
    return DanceLabProject(
        name="Friday Set",
        workspace="graph",
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


def test_legacy_visual_project_roundtrip_remains_readable(tmp_path):
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


def test_simple_mode_project_roundtrip_keeps_cache_references_external(tmp_path):
    project = DanceLabProject(
        name="Garden Continuation",
        workspace="simple",
        simple_mode=SimpleModeProjectState(
            source_files=["/music/a.mp3", "/music/b.mp3"],
            analysis_track_ids={"/music/a.mp3": "track-a", "/music/b.mp3": "track-b"},
            current_step=3,
            target_track_count=10,
            style_focus="uk bass, garage",
            bpm_max=135.0,
            set_role="bridge",
            must_have_ids=["track-a"],
            locked_positions={1: "track-a"},
            plan={"track_order": ["track-a", "track-b"]},
        ),
    )

    saved = save_project(project, tmp_path / "garden")
    raw = json.loads(saved.read_text(encoding="utf-8"))
    assert raw["workspace"] == "simple"
    assert "analyses" not in raw["simple_mode"]

    loaded = load_project(saved)
    assert loaded.workspace == "simple"
    assert loaded.simple_mode is not None
    assert loaded.simple_mode.style_focus == "uk bass, garage"
    assert loaded.simple_mode.bpm_max == 135.0
    assert loaded.simple_mode.locked_positions == {1: "track-a"}


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


def test_project_root_must_be_an_object(tmp_path):
    p = tmp_path / "array.dlproj"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ProjectFileError, match="root must be an object"):
        load_project(p)


def test_project_rejects_oversized_file_before_json_parse(tmp_path):
    p = tmp_path / "huge.dlproj"
    with p.open("wb") as handle:
        handle.truncate(MAX_PROJECT_BYTES + 1)
    with pytest.raises(ProjectFileError, match="maximum size"):
        load_project(p)


def test_project_rejects_unbounded_node_count(tmp_path):
    p = tmp_path / "too-many-nodes.dlproj"
    p.write_text(
        json.dumps(
            {
                "format_version": 1,
                "nodes": [{}] * (MAX_PROJECT_NODES + 1),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectFileError, match="nodes exceeds"):
        load_project(p)

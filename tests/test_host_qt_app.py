from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dancelab.contracts.node_host import get_node_host_registry
from dancelab.core.models import AnalysisResult, Track
from dancelab.host import desktop_app as desktop_app_module
from dancelab.host.desktop_app import NodeHostWindow, desktop_available

if desktop_available():
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
    )
else:  # pragma: no cover - exercised only when desktop dependency is unavailable
    QApplication = None
    QComboBox = None
    QLabel = None
    QLineEdit = None
    QPointF = None
    QPlainTextEdit = None
    QPushButton = None


@lru_cache(maxsize=1)
def _qt_bootstrap_available() -> bool:
    if not desktop_available():
        return False

    # NEW-M1: the probe must go through desktop_app, which is the only place
    # QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH get configured — probing
    # bare PySide6 fails to find the 'offscreen' plugin and silently skipped
    # the entire UI suite even with PySide6 installed.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen'); "
                "import dancelab.host.desktop_app as d; "
                "from PySide6.QtWidgets import QApplication; "
                "app = QApplication([]); "
                "print('qt-ok')"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")},
    )
    return probe.returncode == 0 and "qt-ok" in probe.stdout


class _DummyConfig:
    weights_file = "unused-weights.yaml"


def _analysis_from_path(path: str, _config: object) -> AnalysisResult:
    stem = Path(path).stem
    track_id = stem.lower().replace(" ", "_")
    return AnalysisResult(
        engine_version="test-qt-host",
        track=Track(
            track_id=track_id,
            title=stem,
            source_path=path,
        ),
    )


def _edge_decision_stub(**kwargs) -> dict[str, object]:
    analysis_a = kwargs["analysis_a"]
    analysis_b = kwargs["analysis_b"]
    return {
        "track_id_a": analysis_a.track.track_id,
        "track_id_b": analysis_b.track.track_id,
        "decision_class": "strong_candidate",
        "core_dj_compatibility_score": {
            "value": 0.88,
            "status": "candidate",
            "confidence": 0.93,
            "explanation": "Stubbed Qt-host decision payload.",
        },
        "standard_blend_allowed": True,
        "recommended_transition_strategy": "standard_blend",
        "blend_profile_auto": "plain_blend",
        "tempo_gate_status": "pass",
        "harmonic_gate_status": "pass",
        "tempo_window_feasibility": "high",
        "risks": [],
        "warnings": ["phrase review"],
        "reasoning": ["Qt host executed the first runnable flow."],
    }


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_builds_first_flow_and_runs_it():
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    window.runtime._config_cache = _DummyConfig()
    window.runtime._weights_cache = {"weights": "stub"}
    window.runtime._analyze_track = _analysis_from_path
    window.runtime._edge_decision = _edge_decision_stub

    window.build_first_flow()
    app.processEvents()

    assert len(window.node_items) == 6
    assert len(window.connection_models) == 4

    upload_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    )
    upload_config = window.runtime.ensure_node_config(upload_item.model.instance_id)
    upload_editor = next(
        widget
        for widget in window.inspector_container.findChildren(QPlainTextEdit)
        if not widget.isReadOnly()
    )
    upload_editor.setPlainText("/tmp/Track Alpha.mp3\n/tmp/Track Beta.mp3")
    app.processEvents()

    assert upload_config["paths_text"] == "/tmp/Track Alpha.mp3\n/tmp/Track Beta.mp3"
    choose_files_buttons = [
        widget
        for widget in window.inspector_container.findChildren(QPushButton)
        if widget.text() == "Open File Picker..."
    ]
    assert len(choose_files_buttons) == 1

    window.run_flow(wait=True)
    app.processEvents()

    telemetry_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "telemetry_screen"
    )
    telemetry_output = window.runtime.outputs[telemetry_item.model.instance_id]
    assert telemetry_output.ports["snapshot"]["score_text"] == "0.880"
    assert window.runtime.node_status[telemetry_item.model.instance_id] == "done"

    select_pair_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "select_pair"
    )
    window.scene.clearSelection()
    select_pair_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    combos = window.inspector_container.findChildren(QComboBox)
    assert len(combos) >= 2
    assert combos[0].count() == 2

    combos[0].setCurrentIndex(0)
    combos[1].setCurrentIndex(1)
    app.processEvents()

    select_pair_config = window.runtime.ensure_node_config(select_pair_item.model.instance_id)
    assert select_pair_config["track_id_a"] == "track_alpha"
    assert select_pair_config["track_id_b"] == "track_beta"

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_inspector_surfaces_audit_and_context_forms():
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    window.runtime._context_profiles_cache = {
        "club_peak": {
            "venue_type": "club",
            "set_role": "peak",
            "crowd_energy": "high",
            "time_of_night": "01:00-03:00",
        },
        "festival_daytime": {
            "venue_type": "festival",
            "set_role": "builder",
            "crowd_energy": "medium",
            "time_of_night": "14:00-18:00",
        },
    }

    decision_report_item = window.add_node("decision_report", 120.0, 320.0)
    window.scene.clearSelection()
    decision_report_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    inspector_texts = [
        widget.text()
        for widget in window.inspector_container.findChildren(QLabel)
        if widget.text()
    ]
    # decision_report is an output node whose host_execution_status is
    # "engine_only" (engine/CLI capability exists, no desktop executor adapter)
    # — the audit panel must surface that gap honestly rather than claim the
    # desktop can run it.
    assert any(
        "Engine/API capability exists, but the desktop host has no executor adapter yet." in text
        for text in inspector_texts
    )
    assert any("Implementation Notes" == text for text in inspector_texts)

    select_context_item = window.add_node("select_context", 420.0, 320.0)
    window.scene.clearSelection()
    select_context_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    combos = window.inspector_container.findChildren(QComboBox)
    assert len(combos) >= 1
    assert combos[0].count() == 2

    combos[0].setCurrentIndex(1)
    app.processEvents()

    select_context_config = window.runtime.ensure_node_config(select_context_item.model.instance_id)
    assert select_context_config["context_id"] == "festival_daytime"

    load_corpus_item = window.add_node("load_corpus", 720.0, 320.0)
    window.scene.clearSelection()
    load_corpus_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    line_edits = window.inspector_container.findChildren(QLineEdit)
    assert len(line_edits) >= 2
    load_mode_combos = window.inspector_container.findChildren(QComboBox)
    assert any(combo.count() >= 2 for combo in load_mode_combos)

    build_set_item = window.add_node("build_set", 980.0, 320.0)
    window.scene.clearSelection()
    build_set_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    build_set_combos = window.inspector_container.findChildren(QComboBox)
    assert any(combo.itemData(0) == "build" for combo in build_set_combos)

    export_item = window.add_node("export_rekordbox", 1240.0, 320.0)
    window.scene.clearSelection()
    export_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    export_line_edits = window.inspector_container.findChildren(QLineEdit)
    assert len(export_line_edits) >= 2
    assert any("dancelab_rekordbox.xml" in widget.text() for widget in export_line_edits)

    recommend_next_item = window.add_node("recommend_next", 1500.0, 320.0)
    window.scene.clearSelection()
    recommend_next_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()

    recommend_combos = window.inspector_container.findChildren(QComboBox)
    assert any(combo.findData("build") >= 0 and combo.findData("closing") >= 0 for combo in recommend_combos)
    recommend_editors = [
        widget
        for widget in window.inspector_container.findChildren(QPlainTextEdit)
        if widget.placeholderText() == "One track_id per line"
    ]
    assert len(recommend_editors) == 1

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_add_node_defaults_to_canvas_position_and_selects_it():
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())

    item = window.add_node("upload_tracks")
    app.processEvents()

    assert (item.model.x, item.model.y) != (0.0, 0.0)
    assert window.selected_node_item() is item

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_import_tracks_picker_creates_upload_node(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())

    monkeypatch.setattr(
        desktop_app_module.QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: (["/tmp/Track Alpha.mp3", "/tmp/Track Beta.wav"], ""),
    )

    merged = window.open_upload_file_picker()
    app.processEvents()

    upload_items = [
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    ]
    assert len(upload_items) == 1
    assert merged == ["/tmp/Track Alpha.mp3", "/tmp/Track Beta.wav"]
    assert window.selected_node_item() is upload_items[0]

    upload_config = window.runtime.ensure_node_config(upload_items[0].model.instance_id)
    assert upload_config["paths_text"] == "/tmp/Track Alpha.mp3\n/tmp/Track Beta.wav"

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_import_tracks_cancel_does_not_create_upload_node(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())

    monkeypatch.setattr(
        desktop_app_module.QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([], ""),
    )

    merged = window.open_upload_file_picker()
    app.processEvents()

    upload_items = [
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    ]
    assert merged == []
    assert upload_items == []

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_builds_smart_playlist_flow_from_folder(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    for index in range(1, 7):
        (music_dir / f"Track {index}.wav").write_bytes(b"fake wav")
    output_path = tmp_path / "exports" / "smart.xml"

    monkeypatch.setattr(window, "_choose_audio_folders", lambda **_kwargs: [music_dir])
    monkeypatch.setattr(window, "_confirm_audio_import", lambda files: [Path(path) for path in files])
    monkeypatch.setattr(
        desktop_app_module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(output_path), ""),
    )
    monkeypatch.setattr(
        desktop_app_module.QInputDialog,
        "getInt",
        lambda *args, **kwargs: (5, True),  # free count, no fixed presets
    )
    monkeypatch.setattr(
        desktop_app_module.QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Tomorrow Set", True),
    )

    window.build_smart_playlist_flow()
    app.processEvents()

    specs = [item.model.spec.node_id for item in window.node_items.values()]
    assert "upload_tracks" in specs
    assert "engine" in specs
    assert "build_set" in specs
    assert "export_rekordbox" in specs
    assert len(window.connection_models) == 4

    upload_item = next(item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks")
    engine_item = next(item for item in window.node_items.values() if item.model.spec.node_id == "engine")
    build_item = next(item for item in window.node_items.values() if item.model.spec.node_id == "build_set")
    export_item = next(item for item in window.node_items.values() if item.model.spec.node_id == "export_rekordbox")

    upload_config = window.runtime.ensure_node_config(upload_item.model.instance_id)
    build_config = window.runtime.ensure_node_config(build_item.model.instance_id)
    export_config = window.runtime.ensure_node_config(export_item.model.instance_id)

    assert len(upload_config["paths_text"].splitlines()) == 6
    assert build_config["target_track_count"] == 5
    assert export_config["playlist_name"] == "Tomorrow Set"
    assert export_config["output_path"] == str(output_path)
    assert window._default_run_target() == export_item.model.instance_id
    assert any(
        edge.from_instance_id == upload_item.model.instance_id
        and edge.to_instance_id == engine_item.model.instance_id
        and edge.to_port_key == "tracks_in"
        for edge in window.connection_models.values()
    )
    assert any(
        edge.from_instance_id == engine_item.model.instance_id
        and edge.from_port_key == "analysis_out"
        and edge.to_instance_id == build_item.model.instance_id
        for edge in window.connection_models.values()
    )

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_upload_folder_picker_accepts_multiple_folders(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    folder_a = tmp_path / "crate_a"
    folder_b = tmp_path / "crate_b"
    folder_a.mkdir()
    folder_b.mkdir()
    (folder_a / "Track Alpha.mp3").write_bytes(b"fake")
    (folder_b / "Track Beta.wav").write_bytes(b"fake")
    (folder_b / "notes.txt").write_text("ignore me", encoding="utf-8")

    monkeypatch.setattr(window, "_choose_audio_folders", lambda **_kwargs: [folder_a, folder_b])
    monkeypatch.setattr(window, "_confirm_audio_import", lambda files: [Path(path) for path in files])

    merged = window.open_upload_folder_picker()
    app.processEvents()

    assert merged == [
        str(folder_a / "Track Alpha.mp3"),
        str(folder_b / "Track Beta.wav"),
    ]
    upload_item = next(item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks")
    upload_config = window.runtime.ensure_node_config(upload_item.model.instance_id)
    assert upload_config["paths_text"] == "\n".join(merged)

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_dragging_socket_cable_creates_connection():
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    window.show()
    app.processEvents()

    upload_item = window.add_node("upload_tracks", 120.0, 390.0)
    engine_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "engine"
    )
    source = upload_item.output_handles["tracks"]
    target = engine_item.input_handles["tracks_in"]

    window.start_connection_drag(source, source.center_in_scene())
    window.update_connection_drag(target.center_in_scene())
    window.finish_connection_drag(target.center_in_scene())
    app.processEvents()

    assert len(window.connection_models) == 1
    edge = next(iter(window.connection_models.values()))
    assert edge.from_instance_id == upload_item.model.instance_id
    assert edge.from_port_key == "tracks"
    assert edge.to_instance_id == engine_item.model.instance_id
    assert edge.to_port_key == "tracks_in"

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_audio_drop_reuses_selected_upload_node():
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())

    upload_item = window.add_node("upload_tracks", 240.0, 240.0)
    merged = window.handle_audio_file_drop(
        ["/tmp/Track Alpha.mp3", "/tmp/Track Beta.mp3"],
        scene_pos=QPointF(1200.0, 900.0),
    )
    app.processEvents()

    upload_items = [
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    ]
    assert len(upload_items) == 1
    assert window.selected_node_item() is upload_item
    assert merged == ["/tmp/Track Alpha.mp3", "/tmp/Track Beta.mp3"]

    upload_config = window.runtime.ensure_node_config(upload_item.model.instance_id)
    assert upload_config["paths_text"] == "/tmp/Track Alpha.mp3\n/tmp/Track Beta.mp3"

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_canvas_zoom_helpers_clamp_and_reset():
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())

    for _ in range(24):
        window.view.zoom_by_steps(1.0)
    app.processEvents()
    assert window.view._zoom_value <= window.view.MAX_ZOOM

    for _ in range(48):
        window.view.zoom_by_steps(-1.0)
    app.processEvents()
    assert window.view._zoom_value >= window.view.MIN_ZOOM

    window.view.reset_zoom()
    app.processEvents()
    assert window.view._zoom_value == 1.0

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_project_save_load_roundtrip(tmp_path):
    # UI/UX audit P1: Blender-style project model — the saved .dlproj restores
    # nodes (with positions), connections and node configs.
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    window.build_first_flow()
    upload_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    )
    window.runtime.ensure_node_config(upload_item.model.instance_id)["paths_text"] = "/tmp/A.mp3"
    app.processEvents()

    saved = window._save_project_to_path(tmp_path / "roundtrip")
    assert saved.exists()
    assert window.windowTitle() == "DanceLab — roundtrip"

    node_ids_before = {
        item.model.instance_id: item.model.spec.node_id for item in window.node_items.values()
    }
    connections_before = set(window.connection_models)

    window.new_project()
    app.processEvents()
    assert len(window.node_items) == 1  # engine only

    window.load_project_from_path(saved)
    app.processEvents()

    node_ids_after = {
        item.model.instance_id: item.model.spec.node_id for item in window.node_items.values()
    }
    assert node_ids_after == node_ids_before
    assert set(window.connection_models) == connections_before
    restored = window.runtime.ensure_node_config(upload_item.model.instance_id)
    assert restored["paths_text"] == "/tmp/A.mp3"
    assert window.windowTitle() == "DanceLab — roundtrip"  # loaded → not dirty

    window.add_node("filter", 40.0, 40.0)
    app.processEvents()
    assert window.windowTitle().endswith("*")  # graph edit marks project dirty

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_menus_and_engine_status_guidance():
    # UI/UX audit P1: File/Engine/View menus exist and the status panel guides
    # the user (idle -> waiting for input -> ready).
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    app.processEvents()

    menu_titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
    assert menu_titles == ["File", "Engine", "View"]

    assert window.engine_state == "idle"
    assert "SMART PLAYLIST" in window.next_action_label.text() or "build a flow" in window.next_action_label.text()

    window.build_first_flow()
    app.processEvents()
    assert window.engine_state == "waiting_for_input"
    assert "Upload Tracks" in window.next_action_label.text()
    assert not window.run_button.isEnabled()

    upload_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    )
    window._set_upload_paths(upload_item, ["/tmp/A.mp3"], refresh_selection=False)
    app.processEvents()
    assert window.engine_state == "ready"
    assert "RUN ANALYSIS" in window.next_action_label.text()
    assert window.run_button.isEnabled()

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_engine_is_singleton_and_library_is_organized():
    # UI/UX audit §9: adding a second engine returns the existing one instead of
    # creating an undeletable duplicate. §8/§12: advanced categories collapsed,
    # counts shown subtly, nodes carry what/inputs/outputs tooltips.
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    app.processEvents()

    engines_before = [
        item for item in window.node_items.values() if item.model.spec.node_id == "engine"
    ]
    assert len(engines_before) == 1
    duplicate = window.add_node("engine")
    assert duplicate is engines_before[0]
    assert (
        len([i for i in window.node_items.values() if i.model.spec.node_id == "engine"]) == 1
    )

    tree = window.library_tree
    top_labels = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
    assert any("ANALYSIS & DECISION (" in label for label in top_labels)
    assert any("PROJECT / INPUT (" in label for label in top_labels)

    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if "DIAGNOSTICS" in item.text(0) or "UTILITIES" in item.text(0):
            assert "advanced" in item.text(0)
            assert not item.isExpanded()  # advanced groups start collapsed
        elif "ANALYSIS & DECISION" in item.text(0):
            assert item.isExpanded()
            child_tooltip = item.child(0).toolTip(0)
            assert "Inputs:" in child_tooltip or "Outputs:" in child_tooltip
            assert "Status:" in child_tooltip

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_qt_host_inspector_input_status_and_node_reset():
    # UI/UX audit §6/§7: inputs show connected/missing, Reset Node clears
    # config+output, pinch zoom helper clamps like button zoom.
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(get_node_host_registry())
    window.build_first_flow()
    app.processEvents()

    analyze_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "analyze_tracks"
    )
    window.scene.clearSelection()
    analyze_item.setSelected(True)
    window._sync_inspector()
    app.processEvents()
    inspector_texts = [
        widget.text()
        for widget in window.inspector_container.findChildren(QLabel)
        if widget.text()
    ]
    assert any("✓ connected" in text for text in inspector_texts)

    upload_item = next(
        item for item in window.node_items.values() if item.model.spec.node_id == "upload_tracks"
    )
    window.runtime.ensure_node_config(upload_item.model.instance_id)["paths_text"] = "/tmp/A.mp3"
    window.reset_node(upload_item)
    # inspector rebuild may recreate an empty config dict — reset means "no values"
    assert not window.runtime.node_configs.get(upload_item.model.instance_id)

    # pinch gesture path shares the clamped zoom helper
    window.view.zoom_by_factor(100.0)
    assert window.view._zoom_value <= window.view.MAX_ZOOM
    window.view.zoom_by_factor(0.0001)
    assert window.view._zoom_value >= window.view.MIN_ZOOM
    window.view.reset_zoom()

    window.close()

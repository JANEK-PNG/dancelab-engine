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
    assert any("Desktop runtime still does not execute this node." in text for text in inspector_texts)
    assert any("Desktop Audit" == text for text in inspector_texts)

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

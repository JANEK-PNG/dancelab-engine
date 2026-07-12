"""Qt desktop host shell for DanceLab.

This is the intended direction for the long-lived node-based host:
Python desktop software backed by the engine registry, not an HTML-first app.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dancelab.contracts.node_host import NodeHostRegistry, NodePortSpec, NodeSpec, get_node_host_registry
from dancelab.core.models import AnalysisResult
from dancelab.host.runtime import (
    DesktopHostRuntime,
    RuntimeConnection,
    RuntimeNodeState,
)
from dancelab.host.project import (
    PROJECT_FILE_SUFFIX,
    DanceLabProject,
    ProjectConnection,
    ProjectFileError,
    ProjectNode,
    load_project,
    save_project,
)
from dancelab.workflows.smart_playlist import MIN_PLAYLIST_TRACKS, discover_audio_files


def _prepare_qt_runtime() -> None:
    """ENV-1 hardening: macOS provenance keeps re-hiding PySide6 dylibs, which
    breaks Qt's plugin scan ("Could not find the Qt platform plugin 'cocoa'").
    Unhide them and point Qt at the plugin dir explicitly — idempotent, cheap,
    and a no-op on healthy installs."""
    import os
    import subprocess
    import sys

    try:
        import PySide6
    except ModuleNotFoundError:
        return
    qt_root = Path(PySide6.__file__).parent / "Qt"
    plugins = qt_root / "plugins"
    if plugins.is_dir():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugins / "platforms"))
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["chflags", "-R", "nohidden", str(Path(PySide6.__file__).parent)],
                capture_output=True, timeout=15, check=False,
            )
        except Exception:
            pass  # cosmetic hardening only — never block launch


_prepare_qt_runtime()

try:  # optional desktop dependency
    from PySide6.QtCore import (
        QEvent,
        QMimeData,
        QPoint,
        QPointF,
        QRectF,
        QSettings,
        Qt,
        QThread,
        Signal,
    )
    from PySide6.QtGui import (
        QAction,
        QBrush,
        QColor,
        QDrag,
        QFont,
        QLinearGradient,
        QPainter,
        QPainterPath,
        QPen,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDockWidget,
        QFileDialog,
        QGraphicsEllipseItem,
        QGraphicsItem,
        QGraphicsPathItem,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsView,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QPlainTextEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    from dancelab.host.import_dialogs import choose_audio_directories, confirm_suspicious_audio_files
except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
    _PYSIDE_IMPORT_ERROR = exc
else:
    _PYSIDE_IMPORT_ERROR = None


CATEGORY_COLORS: dict[str, str] = {
    "system": "#d99a4e",
    "input": "#45b0a0",
    "engine_ops": "#d99a4e",
    "sensors": "#a08bd0",
    "screens": "#5aa7d6",
    "utility": "#8b8f96",
    "output": "#6ea44d",
}

RUNTIME_COLORS: dict[str, str] = {
    "idle": "#72757b",
    "running": "#d8bf61",
    "done": "#7ecf8b",
    "error": "#d66b6b",
}

PORT_TYPE_COLORS: dict[str, str] = {
    "track_files": "#45b0a0",
    "track_id": "#5aa7d6",
    "track_id_list": "#e0c568",
    "track_pair_selection": "#7cb96b",
    "context_profile": "#a08bd0",
    "analysis_result": "#5aa7d6",
    "analysis_set": "#5aa7d6",
    "transition_window_set": "#d99a4e",
    "mixability_result": "#7cb96b",
    "edge_decision": "#7cb96b",
    "set_function_output": "#d99a4e",
    "context_evaluation": "#a08bd0",
    "next_track_recommendation": "#7cb96b",
    "sequence_decision": "#7cb96b",
    "set_plan": "#7cb96b",
    "telemetry_manifest": "#5aa7d6",
    "artifact_bundle": "#6f7278",
    "dataset_manifest": "#e0c568",
    "stem_bundle": "#45b0a0",
    "stem_window_feature_set": "#a08bd0",
    "scalar_signal": "#d99a4e",
    "warning_stream": "#c25b52",
    "rekordbox_xml": "#7cb96b",
    "host_snapshot": "#5aa7d6",
}

PORT_TYPE_EDGE_COLORS: dict[str, str] = {
    "track_files": "#3a8a7d",
    "track_id": "#48799c",
    "track_id_list": "#b8a355",
    "track_pair_selection": "#64914f",
    "context_profile": "#8a76b5",
    "analysis_result": "#48799c",
    "analysis_set": "#48799c",
    "transition_window_set": "#a3763f",
    "mixability_result": "#64914f",
    "edge_decision": "#64914f",
    "set_function_output": "#a3763f",
    "context_evaluation": "#8a76b5",
    "next_track_recommendation": "#64914f",
    "sequence_decision": "#64914f",
    "set_plan": "#64914f",
    "telemetry_manifest": "#48799c",
    "artifact_bundle": "#6f7278",
    "dataset_manifest": "#b8a355",
    "stem_bundle": "#3a8a7d",
    "stem_window_feature_set": "#8a76b5",
    "scalar_signal": "#a3763f",
    "warning_stream": "#94463f",
    "rekordbox_xml": "#64914f",
    "host_snapshot": "#48799c",
}

CATEGORY_MARKERS: dict[str, str] = {
    "system": "◆",
    "input": "■",
    "engine_ops": "◆",
    "sensors": "●",
    "screens": "□",
    "utility": "■",
    "output": "▣",
}

FORM_IMPLEMENTED_NODE_IDS = {
    "upload_tracks",
    "load_corpus",
    "select_track",
    "select_pair",
    "select_context",
    "extract_stems",
    "build_set",
    "export_rekordbox",
    "stem_export",
    "recommend_next",
}

HOST_FORM_REQUIRED_NODE_IDS = {
    "upload_tracks",
    "load_corpus",
    "select_track",
    "select_pair",
    "select_context",
    "extract_stems",
    "build_set",
    "decision_report",
    "validation_pack",
    "export_rekordbox",
    "stem_export",
    "save_snapshot",
}

AUDIO_FILE_FILTER = (
    "Audio Files (*.mp3 *.wav *.flac *.aif *.aiff *.m4a *.aac *.ogg *.opus);;All Files (*)"
)

AUDIO_FILE_SUFFIXES = {
    ".mp3",
    ".wav",
    ".flac",
    ".aif",
    ".aiff",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
}

NODE_AUDIT_NOTES: dict[str, list[str]] = {
    "analyze_tracks": [
        "Desktop host runtime accepts the optional `context` port contractually, but does not apply context-conditioned analysis yet.",
    ],
    "select_pair": [
        "Desktop host currently resolves pairs from analyzed tracks in session, not from `mixability_result` or `edge_decision` source variants declared in the contract.",
    ],
    "edge_decision": [
        "Desktop host runtime accepts the optional `context` port contractually, but does not apply context-conditioned pair scoring yet.",
    ],
    "telemetry_screen": [
        "Desktop screen adapter currently renders direct edge-decision snapshots, not full `telemetry_manifest`, `mixability_result`, or `sequence_decision` payload families.",
    ],
    "load_corpus": [
        "Desktop bridge now reads the local processed repository directly, but still lacks filtering, paging, and a public API route.",
    ],
    "transition_windows": [
        "Engine capability exists, but the desktop host does not yet execute or visualize this node directly.",
    ],
    "mixability": [
        "Engine capability exists, but the desktop host does not yet execute this node directly.",
    ],
    "context_evaluate": [
        "Engine capability exists, but the desktop host does not yet execute this node directly.",
    ],
    "set_function": [
        "Engine capability exists, but the desktop host does not yet execute this node directly.",
    ],
    "recommend_next": [
        "Desktop bridge now ranks a current track against a candidate pool, but still lacks advanced pool filters, persisted history presets, and a dedicated public API route in the host shell.",
    ],
    "recommend_sequence": [
        "Engine capability exists, but the desktop host does not yet execute this node directly.",
    ],
    "build_set": [
        "Desktop bridge now builds a SetPlan from loaded analyses or repository-backed track IDs, but still lacks a dedicated public API route and export follow-through.",
    ],
    "extract_stems": [
        "Desktop bridge runs stem-aware analysis and exports stems through explicit host-controlled artifact folders.",
    ],
    "stem_window_sensor": [
        "Underlying stem-window data exists, but the host adapter and visual consumer are not wired yet.",
    ],
    "waveform_screen": [
        "Waveform diagnostics exist elsewhere in the toolchain, but are not embedded as a desktop screen node yet.",
    ],
    "listen_screen": [
        "Listen-board diagnostics exist elsewhere in the toolchain, but are not embedded as a desktop screen node yet.",
    ],
    "pair_review_screen": [
        "Review-board diagnostics exist elsewhere in the toolchain, but are not embedded as a desktop screen node yet.",
    ],
    "control_center_screen": [
        "Control-center diagnostics exist elsewhere in the toolchain, but are not embedded as a desktop screen node yet.",
    ],
    "decision_report": [
        "Decision-report artifacts are implemented in the engine layer, but the desktop host lacks the bridge adapter and export controls.",
    ],
    "validation_pack": [
        "Validation-pack artifacts are implemented in the engine layer, but the desktop host lacks the bridge adapter and export controls.",
    ],
    "export_rekordbox": [
        "Desktop bridge now writes rekordbox XML to disk, but still lacks transition-window cue enrichment and a dedicated public API route.",
    ],
    "stem_export": [
        "Desktop bridge writes source audio, analysis JSON, stem manifest, and available WAV stems into a user-selected external folder.",
    ],
    "save_snapshot": [
        "Snapshot persistence is still a planned host feature; no disk target or serializer is wired yet.",
    ],
}


def desktop_available() -> bool:
    return _PYSIDE_IMPORT_ERROR is None


def _dedupe_paths(paths: list[str | Path]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = str(raw_path).strip()
        if not path or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _normalize_audio_paths(paths: list[str | Path]) -> list[str]:
    normalized: list[str] = []
    for raw_path in paths:
        candidate = str(raw_path).strip()
        if not candidate:
            continue
        expanded = str(Path(candidate).expanduser())
        if Path(expanded).suffix.lower() not in AUDIO_FILE_SUFFIXES:
            continue
        normalized.append(expanded)
    return _dedupe_paths(normalized)


def _audio_paths_from_mime_data(mime_data: Any) -> list[str]:
    if mime_data is None or not mime_data.hasUrls():
        return []
    local_paths: list[str] = []
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        local_paths.append(url.toLocalFile())
    return _normalize_audio_paths(local_paths)


def desktop_requirement_message() -> str:
    return (
        "PySide6 is required for the desktop node host. "
        "Install it with `pip install .[desktop]`."
    )


def _require_pyside6() -> None:
    if _PYSIDE_IMPORT_ERROR is not None:  # pragma: no cover - environment-dependent
        raise RuntimeError(desktop_requirement_message()) from _PYSIDE_IMPORT_ERROR


def _category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, "#8b8f96")


def _runtime_color(status: str) -> str:
    return RUNTIME_COLORS.get(status, "#72757b")


def _primary_port_type(port_spec: NodePortSpec) -> str:
    return port_spec.port_types[0] if port_spec.port_types else "scalar_signal"


def _port_color(port_spec: NodePortSpec, *, edge: bool = False) -> str:
    palette = PORT_TYPE_EDGE_COLORS if edge else PORT_TYPE_COLORS
    return palette.get(_primary_port_type(port_spec), "#8b8f96")


@dataclass
class NodeInstanceModel:
    instance_id: str
    spec: NodeSpec
    x: float
    y: float


if _PYSIDE_IMPORT_ERROR is None:
    class _FlowThread(QThread):
        """Runs the runtime graph without moving a Python QObject across threads.

        NEW-H2: analysis must never block the Qt event loop — emit the outcome
        back to the main thread instead. Keeping the worker as the QThread itself
        avoids a macOS/PySide QObject cleanup crash seen after long analyses."""

        completed = Signal(object)  # None on success, error string on failure

        def __init__(self, runtime, node_states, connections, target_instance_id):
            super().__init__()
            self._runtime = runtime
            self._node_states = node_states
            self._connections = connections
            self._target = target_instance_id

        def run(self) -> None:
            try:
                self._runtime.run(self._node_states, self._connections, self._target)
            except Exception as exc:  # surfaced on the UI thread, never swallowed
                self.completed.emit(str(exc))
            else:
                self.completed.emit(None)

    class NodeLibraryTree(QTreeWidget):
        MIME_TYPE = "application/x-dancelab-node-id"

        def __init__(self):
            super().__init__()
            self.setHeaderHidden(True)
            self.setDragEnabled(True)
            self.setDragDropMode(QTreeWidget.DragOnly)
            self.setSelectionMode(QTreeWidget.SingleSelection)

        def startDrag(self, supportedActions) -> None:
            item = self.currentItem()
            if item is None:
                return
            node_id = item.data(0, Qt.UserRole)
            if not isinstance(node_id, str):
                return

            mime = QMimeData()
            mime.setData(self.MIME_TYPE, node_id.encode("utf-8"))
            mime.setText(node_id)
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)


    class NodeCanvasView(QGraphicsView):
        MIN_ZOOM = 0.35
        MAX_ZOOM = 2.75
        ZOOM_STEP_IN = 1.12
        ZOOM_STEP_OUT = 1.0 / ZOOM_STEP_IN

        def __init__(self, host_window: "NodeHostWindow", scene: QGraphicsScene):
            super().__init__(scene)
            self.host_window = host_window
            self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
            self.setDragMode(QGraphicsView.NoDrag)
            self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
            self.setBackgroundBrush(QColor("#17181a"))
            self.setFrameShape(QGraphicsView.NoFrame)
            self.setAcceptDrops(True)
            self._last_pan_point: QPoint | None = None
            self._zoom_value = 1.0

        def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
            super().drawBackground(painter, rect)
            painter.fillRect(rect, QColor("#17181a"))

            minor_pen = QPen(QColor(35, 36, 40))
            major_pen = QPen(QColor(28, 29, 32))

            left = int(rect.left()) - (int(rect.left()) % 24)
            top = int(rect.top()) - (int(rect.top()) % 24)

            painter.setPen(minor_pen)
            x = left
            while x < rect.right():
                y = top
                while y < rect.bottom():
                    painter.drawPoint(QPointF(float(x), float(y)))
                    y += 24
                x += 24

            painter.setPen(major_pen)
            x = int(rect.left()) - (int(rect.left()) % 120)
            while x < rect.right():
                painter.drawLine(QPointF(float(x), rect.top()), QPointF(float(x), rect.bottom()))
                x += 120
            y = int(rect.top()) - (int(rect.top()) % 120)
            while y < rect.bottom():
                painter.drawLine(QPointF(rect.left(), float(y)), QPointF(rect.right(), float(y)))
                y += 120

        def _wheel_delta(self, event) -> QPoint:
            pixel_delta = event.pixelDelta()
            if not pixel_delta.isNull():
                return pixel_delta
            angle_delta = event.angleDelta()
            return QPoint(int(angle_delta.x() / 4), int(angle_delta.y() / 4))

        def _can_pan_from(self, event) -> bool:
            if event.button() in (Qt.MiddleButton, Qt.RightButton):
                return True
            if event.button() != Qt.LeftButton:
                return False
            return self.itemAt(event.pos()) is None

        def zoom_by_factor(self, factor: float) -> None:
            if factor <= 0:
                return
            next_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self._zoom_value * factor))
            applied_factor = next_zoom / self._zoom_value
            if abs(applied_factor - 1.0) < 1e-6:
                return
            self.scale(applied_factor, applied_factor)
            self._zoom_value = next_zoom

        def zoom_by_steps(self, steps: float) -> None:
            if steps == 0:
                return
            factor = self.ZOOM_STEP_IN ** steps if steps > 0 else self.ZOOM_STEP_OUT ** abs(steps)
            self.zoom_by_factor(factor)

        def event(self, event) -> bool:
            # UI/UX audit §7: macOS touchpad pinch arrives as a native gesture,
            # not a wheel event — without this, pinch-zoom simply did nothing.
            if (
                event.type() == QEvent.NativeGesture
                and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture
            ):
                self.zoom_by_factor(1.0 + float(event.value()))
                event.accept()
                return True
            return super().event(event)

        def reset_zoom(self) -> None:
            if self._zoom_value == 0:
                return
            self.scale(1.0 / self._zoom_value, 1.0 / self._zoom_value)
            self._zoom_value = 1.0

        def sync_zoom_from_transform(self) -> None:
            self._zoom_value = max(float(self.transform().m11()), 1e-6)

        def wheelEvent(self, event) -> None:
            modifiers = event.modifiers()
            if modifiers & (Qt.ControlModifier | Qt.MetaModifier):
                delta = event.angleDelta().y() or event.pixelDelta().y()
                steps = delta / 120.0 if delta else 0.0
                if steps == 0.0 and delta != 0:
                    steps = 1.0 if delta > 0 else -1.0
                self.zoom_by_steps(steps)
                event.accept()
                return

            delta = self._wheel_delta(event)
            if modifiers & Qt.ShiftModifier and not delta.x():
                # UI/UX audit §7: shift + scroll = horizontal pan
                delta = QPoint(delta.y(), 0)
            if delta.x():
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            if delta.y():
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()

        def mousePressEvent(self, event) -> None:
            if self._can_pan_from(event):
                self._last_pan_point = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event) -> None:
            if self._last_pan_point is not None:
                delta = event.pos() - self._last_pan_point
                self._last_pan_point = event.pos()
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event) -> None:
            if self._last_pan_point is not None and event.button() in (
                Qt.LeftButton,
                Qt.MiddleButton,
                Qt.RightButton,
            ):
                self._last_pan_point = None
                self.setCursor(Qt.ArrowCursor)
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def dragEnterEvent(self, event) -> None:
            if event.mimeData().hasFormat(NodeLibraryTree.MIME_TYPE):
                event.acceptProposedAction()
                return
            if _audio_paths_from_mime_data(event.mimeData()):
                event.acceptProposedAction()
                return
            super().dragEnterEvent(event)

        def dragMoveEvent(self, event) -> None:
            if event.mimeData().hasFormat(NodeLibraryTree.MIME_TYPE):
                event.acceptProposedAction()
                return
            if _audio_paths_from_mime_data(event.mimeData()):
                event.acceptProposedAction()
                return
            super().dragMoveEvent(event)

        def dropEvent(self, event) -> None:
            if event.mimeData().hasFormat(NodeLibraryTree.MIME_TYPE):
                node_id = bytes(event.mimeData().data(NodeLibraryTree.MIME_TYPE)).decode("utf-8").strip()
                if not node_id:
                    event.ignore()
                    return

                scene_pos = self.mapToScene(event.position().toPoint())
                self.host_window.add_node(node_id, x=scene_pos.x(), y=scene_pos.y())
                event.acceptProposedAction()
                return

            audio_paths = _audio_paths_from_mime_data(event.mimeData())
            if not audio_paths:
                super().dropEvent(event)
                return

            scene_pos = self.mapToScene(event.position().toPoint())
            self.host_window.handle_audio_file_drop(audio_paths, scene_pos=scene_pos)
            event.acceptProposedAction()


    class AudioPathTextEdit(QPlainTextEdit):
        def __init__(self, on_paths_dropped: Callable[[list[str]], None]):
            super().__init__()
            self._on_paths_dropped = on_paths_dropped
            self.setAcceptDrops(True)

        def dragEnterEvent(self, event) -> None:
            if _audio_paths_from_mime_data(event.mimeData()):
                event.acceptProposedAction()
                return
            super().dragEnterEvent(event)

        def dragMoveEvent(self, event) -> None:
            if _audio_paths_from_mime_data(event.mimeData()):
                event.acceptProposedAction()
                return
            super().dragMoveEvent(event)

        def dropEvent(self, event) -> None:
            audio_paths = _audio_paths_from_mime_data(event.mimeData())
            if audio_paths:
                self._on_paths_dropped(audio_paths)
                event.acceptProposedAction()
                return
            super().dropEvent(event)


    class PortHandleItem(QGraphicsEllipseItem):
        def __init__(
            self,
            node_item: "NodeBoxItem",
            port_spec: NodePortSpec,
            direction: str,
            y: float,
        ):
            super().__init__(-8.0, -8.0, 16.0, 16.0, node_item)
            self.node_item = node_item
            self.port_spec = port_spec
            self.direction = direction
            self.active = False
            self.compatible = False
            self.setAcceptedMouseButtons(Qt.LeftButton)
            x = node_item.rect().width() if direction == "output" else 0.0
            self.setPos(x, y)
            self.setZValue(2)
            self._refresh_style()

        def center_in_scene(self) -> QPointF:
            return self.mapToScene(self.rect().center())

        def set_state(self, *, active: bool = False, compatible: bool = False) -> None:
            self.active = active
            self.compatible = compatible
            self._refresh_style()

        def _refresh_style(self) -> None:
            fill = QColor(_port_color(self.port_spec))
            if self.active:
                fill = QColor("#d99a4e")
            border = QColor("#141517")
            width = 2.0
            if self.compatible:
                border = QColor("#7ecf8b")
                width = 3.0
            self.setBrush(fill)
            self.setPen(QPen(border, width))

        def mousePressEvent(self, event) -> None:
            self.node_item.setSelected(True)
            self.node_item.host_window.start_connection_drag(self, event.scenePos())
            event.accept()

        def mouseMoveEvent(self, event) -> None:
            self.node_item.host_window.update_connection_drag(event.scenePos())
            event.accept()

        def mouseReleaseEvent(self, event) -> None:
            self.node_item.host_window.finish_connection_drag(event.scenePos())
            event.accept()


    class ConnectionItem(QGraphicsPathItem):
        def __init__(
            self,
            connection_id: str,
            source_handle: PortHandleItem,
            target_handle: PortHandleItem,
        ):
            super().__init__()
            self.connection_id = connection_id
            self.source_handle = source_handle
            self.target_handle = target_handle
            self.setZValue(0)
            pen = QPen(QColor(_port_color(source_handle.port_spec, edge=True)), 2.8)
            pen.setCapStyle(Qt.RoundCap)
            self.setPen(pen)
            self.update_path()

        def update_path(self) -> None:
            start = self.source_handle.center_in_scene()
            end = self.target_handle.center_in_scene()
            dx = max(80.0, abs(end.x() - start.x()) * 0.55)
            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x() + dx, start.y()),
                QPointF(end.x() - dx, end.y()),
                end,
            )
            self.setPath(path)


    class PendingConnectionItem(QGraphicsPathItem):
        def __init__(self, source_handle: PortHandleItem):
            super().__init__()
            self.source_handle = source_handle
            self.current_scene_pos = source_handle.center_in_scene()
            self.setZValue(4)
            pen = QPen(QColor("#e6c896"), 2.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setStyle(Qt.DashLine)
            self.setPen(pen)
            self.update_path(self.current_scene_pos)

        def set_target_state(self, *, valid: bool = False, invalid: bool = False) -> None:
            if valid:
                color = QColor("#7ecf8b")
            elif invalid:
                color = QColor("#d66b6b")
            else:
                color = QColor("#e6c896")
            pen = QPen(color, 2.8 if valid else 2.4)
            pen.setCapStyle(Qt.RoundCap)
            pen.setStyle(Qt.SolidLine if valid else Qt.DashLine)
            self.setPen(pen)

        def update_path(self, scene_pos: QPointF) -> None:
            self.current_scene_pos = scene_pos
            start = self.source_handle.center_in_scene()
            end = scene_pos
            dx = max(80.0, abs(end.x() - start.x()) * 0.55)
            direction = 1.0 if self.source_handle.direction == "output" else -1.0
            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x() + direction * dx, start.y()),
                QPointF(end.x() - direction * dx, end.y()),
                end,
            )
            self.setPath(path)


    class NodeBoxItem(QGraphicsRectItem):
        def __init__(self, host_window: "NodeHostWindow", model: NodeInstanceModel):
            self.host_window = host_window
            width = 260.0 if model.spec.pinned else 196.0
            super().__init__(0.0, 0.0, width, self._estimated_height(model.spec))
            self.model = model
            self.setPos(model.x, model.y)
            self.setFlags(
                QGraphicsItem.ItemIsMovable
                | QGraphicsItem.ItemIsSelectable
                | QGraphicsItem.ItemSendsScenePositionChanges
            )
            self.setZValue(1)
            self.input_handles: dict[str, PortHandleItem] = {}
            self.output_handles: dict[str, PortHandleItem] = {}
            self.connections: list[ConnectionItem] = []
            self._create_handles()

        @staticmethod
        def _estimated_height(spec: NodeSpec) -> float:
            row_count = max(len(spec.inputs), len(spec.outputs))
            return (138.0 if spec.pinned else 120.0) + row_count * 22.0

        def header_height(self) -> float:
            return 30.0 if self.model.spec.pinned else 28.0

        def body_start(self) -> float:
            return self.header_height() + 78.0

        def _create_handles(self) -> None:
            for index, port in enumerate(self.model.spec.inputs):
                handle = PortHandleItem(self, port, "input", self.body_start() + index * 22.0)
                self.input_handles[port.key] = handle
            for index, port in enumerate(self.model.spec.outputs):
                handle = PortHandleItem(self, port, "output", self.body_start() + index * 22.0)
                self.output_handles[port.key] = handle

        def port_handle(self, direction: str, port_key: str) -> PortHandleItem | None:
            bucket = self.output_handles if direction == "output" else self.input_handles
            return bucket.get(port_key)

        def add_connection(self, connection: ConnectionItem) -> None:
            if connection not in self.connections:
                self.connections.append(connection)

        def remove_connection(self, connection: ConnectionItem) -> None:
            if connection in self.connections:
                self.connections.remove(connection)

        def itemChange(self, change, value):
            if change == QGraphicsItem.ItemPositionHasChanged:
                self.model.x = float(self.pos().x())
                self.model.y = float(self.pos().y())
                for connection in self.connections:
                    connection.update_path()
            return super().itemChange(change, value)

        def mouseDoubleClickEvent(self, event) -> None:
            if self.model.spec.node_id == "upload_tracks":
                self.host_window.open_upload_file_picker(self)
                event.accept()
                return
            super().mouseDoubleClickEvent(event)

        def paint(self, painter: QPainter, option, widget=None) -> None:
            spec = self.model.spec
            rect = self.rect()
            border_color = QColor("#35373c")
            fill_color = QColor("#232428")
            header_color = QColor("#2a2c30")
            corner_radius = 10.0 if spec.category == "sensors" else 7.0 if spec.pinned else 6.0

            if spec.pinned:
                fill_color = QColor("#211f1a")
                border_color = QColor("#8f6a38")

            border_pen = QPen(border_color, 1.2)
            if spec.category == "screens":
                border_pen.setStyle(Qt.DashLine)
            painter.setPen(border_pen)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(rect, corner_radius, corner_radius)

            painter.save()
            painter.setPen(Qt.NoPen)
            if spec.pinned:
                gradient = QLinearGradient(0.0, 0.0, 0.0, self.header_height())
                gradient.setColorAt(0.0, QColor("#2b2820"))
                gradient.setColorAt(1.0, QColor("#262319"))
                painter.setBrush(gradient)
            else:
                painter.setBrush(header_color)
            painter.drawRoundedRect(
                QRectF(0.0, 0.0, rect.width(), self.header_height()),
                corner_radius,
                corner_radius,
            )
            painter.drawRect(QRectF(0.0, self.header_height() - corner_radius, rect.width(), corner_radius))
            painter.restore()

            painter.setPen(QPen(QColor(_category_color(spec.category)), 2.0))
            painter.drawLine(QPointF(0.0, 1.0), QPointF(rect.width(), 1.0))

            marker_font = QFont("IBM Plex Mono", 10)
            marker_font.setBold(True)
            painter.setFont(marker_font)
            painter.setPen(QColor(_category_color(spec.category)))
            painter.drawText(QRectF(12.0, 6.0, 20.0, 18.0), CATEGORY_MARKERS.get(spec.category, "■"))

            label_font = QFont("IBM Plex Sans", 10)
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(QColor("#e6c896" if spec.pinned else "#d6d7d9"))
            title = spec.label.upper() if spec.pinned else spec.label
            painter.drawText(QRectF(30.0, 6.0, rect.width() - 100.0, 18.0), title)

            meta_font = QFont("IBM Plex Mono", 8)
            painter.setFont(meta_font)
            painter.setPen(QColor("#72757b"))
            painter.drawText(
                QRectF(14.0, self.header_height() + 12.0, rect.width() - 28.0, 14.0),
                f"{spec.runtime_side} · {spec.execution_mode}",
            )
            painter.setPen(QColor("#989ba1"))
            painter.drawText(
                QRectF(14.0, self.header_height() + 30.0, rect.width() - 28.0, 36.0),
                Qt.TextWordWrap,
                spec.summary,
            )

            runtime_status = self.host_window.runtime.node_status.get(self.model.instance_id, "idle")
            painter.setPen(QPen(QColor(_runtime_color(runtime_status)), 1.0))
            painter.drawText(
                QRectF(rect.width() - 72.0, 6.0, 60.0, 18.0),
                Qt.AlignRight,
                runtime_status,
            )
            painter.setBrush(QColor(_runtime_color(runtime_status)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(rect.width() - 88.0, 11.0, 7.0, 7.0))

            if runtime_status == "running":
                painter.setBrush(QColor("#d99a4e"))
                painter.drawRect(QRectF(12.0, self.header_height() - 3.0, rect.width() - 24.0, 2.0))

            painter.setFont(meta_font)
            painter.setPen(QColor("#989ba1"))
            for port_key, handle in self.input_handles.items():
                y = handle.pos().y()
                painter.drawText(QRectF(14.0, y - 8.0, rect.width() - 50.0, 14.0), port_key)
            for port_key, handle in self.output_handles.items():
                y = handle.pos().y()
                painter.drawText(
                    QRectF(14.0, y - 8.0, rect.width() - 28.0, 14.0),
                    Qt.AlignRight,
                    port_key,
                )

            if self.isSelected():
                painter.setPen(QPen(QColor(217, 154, 78, 38), 5.0))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-1.2, -1.2, 1.2, 1.2), corner_radius, corner_radius)
                painter.setPen(QPen(QColor("#d99a4e"), 1.4))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(
                    rect.adjusted(0.8, 0.8, -0.8, -0.8),
                    corner_radius,
                    corner_radius,
                )


    class NodeHostWindow(QMainWindow):
        def __init__(
            self,
            registry: NodeHostRegistry,
            *,
            config_path: str | Path = "configs/default.yaml",
        ):
            super().__init__()
            self.registry = registry
            self.node_specs: dict[str, NodeSpec] = {node.node_id: node for node in registry.nodes}
            self.runtime = DesktopHostRuntime(registry, config_path=config_path)
            self.instance_counter = 1
            self.node_items: dict[str, NodeBoxItem] = {}
            self.connection_models: dict[str, RuntimeConnection] = {}
            self.connection_items: dict[str, ConnectionItem] = {}
            self.pending_output_handle: PortHandleItem | None = None
            self.pending_connection_preview: PendingConnectionItem | None = None
            self.connection_drag_source: PortHandleItem | None = None
            self.connection_drag_started = False
            self.connection_drag_start_scene_pos: QPointF | None = None

            # UI/UX audit P1: Blender-style project model. The window always
            # works "inside a project"; dirty tracking drives the title marker.
            self.project_path: Path | None = None
            self.project_name = "Untitled Project"
            self._project_dirty = False
            self._suspend_dirty_tracking = False
            self.engine_state = "idle"

            self.setWindowTitle("DanceLab Signal Graph")
            self.resize(1600, 960)
            self.setStyleSheet(
                """
                QMainWindow, QWidget { background: #141517; color: #d6d7d9; }
                QScrollArea { background: #1b1c1f; border: none; }
                QDockWidget::title {
                    background: #1b1c1f;
                    color: #989ba1;
                    padding: 8px 10px;
                    border-bottom: 1px solid #26272b;
                }
                QTreeWidget, QPlainTextEdit, QComboBox, QLineEdit, QSpinBox {
                    background: #17181a;
                    border: 1px solid #2c2d31;
                    border-radius: 4px;
                    color: #d6d7d9;
                }
                QLineEdit, QSpinBox {
                    min-height: 28px;
                    padding: 2px 8px;
                }
                QComboBox {
                    min-height: 28px;
                    padding: 2px 8px;
                }
                QComboBox::drop-down {
                    width: 22px;
                    border-left: 1px solid #2c2d31;
                }
                QTreeWidget::item:selected {
                    background: #23251f;
                    color: #f0d0a0;
                }
                QTreeWidget::item {
                    min-height: 28px;
                }
                QToolBar {
                    background: #1b1c1f;
                    border-bottom: 1px solid #0d0d0f;
                    spacing: 6px;
                    padding: 6px 10px;
                }
                QPushButton {
                    background: #202124;
                    border: 1px solid #34363b;
                    border-radius: 4px;
                    padding: 6px 10px;
                }
                QPushButton:hover {
                    border-color: #d99a4e;
                }
                QPushButton[role="accent"] {
                    color: #e6c896;
                    border-color: rgba(217, 154, 78, 0.55);
                }
                QPushButton[role="primary"] {
                    background: #d99a4e;
                    color: #141517;
                    border-color: #efc58d;
                    font-weight: 600;
                    min-height: 36px;
                    padding: 8px 12px;
                }
                QPushButton[role="primary"]:hover {
                    background: #e6ad62;
                    border-color: #f3d2a8;
                }
                QLabel[role="title"] {
                    color: #eceded;
                    font-size: 15px;
                    font-weight: 600;
                }
                QLabel[role="section"] {
                    color: #d99a4e;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                }
                QLabel[role="hint"] {
                    color: #989ba1;
                    background: #17181a;
                    border: 1px dashed #2b2d31;
                    border-radius: 8px;
                    padding: 8px;
                }
                QLabel[role="callout"] {
                    color: #e6c896;
                    background: #1a1a18;
                    border: 1px solid #5b472f;
                    border-radius: 8px;
                    padding: 10px;
                }
                QLabel[role="pill"] {
                    background: #202124;
                    border: 1px solid #2c2d31;
                    border-radius: 999px;
                    padding: 3px 8px;
                    color: #989ba1;
                }
                QLabel[role="brand"] {
                    color: #eceded;
                    font-size: 13px;
                    font-weight: 600;
                }
                QLabel[role="patch"] {
                    color: #8b8d92;
                    font-family: "IBM Plex Mono";
                    font-size: 11px;
                }
                QLabel[role="toolbar_status"] {
                    color: #e6c896;
                    font-family: "IBM Plex Mono";
                    font-size: 11px;
                }
                QPushButton[role="hero"] {
                    background: #d99a4e;
                    color: #111214;
                    border: 1px solid #f0c98f;
                    border-radius: 8px;
                    font-weight: 700;
                    min-height: 38px;
                    padding: 8px 14px;
                }
                QPushButton[role="hero"]:hover {
                    background: #edb766;
                }
                QPushButton[role="preset"] {
                    background: #20231d;
                    color: #9bd27f;
                    border: 1px solid #4d7443;
                    border-radius: 8px;
                    font-weight: 600;
                    min-height: 34px;
                    padding: 7px 12px;
                }
                QWidget[role="inspector_card"] {
                    background: #17181a;
                    border: 1px solid #272a2f;
                    border-radius: 10px;
                }
                """
            )

            self._build_menus()
            self._build_toolbar()
            self._build_canvas()
            self._build_library()
            self._build_inspector()
            self._build_engine_status_bar()

            self.scene.selectionChanged.connect(self._sync_inspector)
            self.reset_canvas()
            self._mark_project_saved()

        def _build_menus(self) -> None:
            """UI/UX audit P1: classic creative-tool menus (Blender/Houdini model).

            Project, Engine and View actions live in separate menus so the
            toolbar can stay a small set of grouped, high-frequency controls."""
            menu_bar = self.menuBar()

            file_menu = menu_bar.addMenu("&File")
            new_action = QAction("New Project", self)
            new_action.setShortcut("Ctrl+N")
            new_action.triggered.connect(self.new_project)
            file_menu.addAction(new_action)
            open_action = QAction("Open Project...", self)
            open_action.setShortcut("Ctrl+O")
            open_action.triggered.connect(self.open_project_dialog)
            file_menu.addAction(open_action)
            self.recent_projects_menu = file_menu.addMenu("Open Recent")
            self._refresh_recent_projects_menu()
            file_menu.addSeparator()
            save_action = QAction("Save", self)
            save_action.setShortcut("Ctrl+S")
            save_action.triggered.connect(self.save_current_project)
            file_menu.addAction(save_action)
            save_as_action = QAction("Save As...", self)
            save_as_action.setShortcut("Ctrl+Shift+S")
            save_as_action.triggered.connect(self.save_project_as_dialog)
            file_menu.addAction(save_as_action)
            file_menu.addSeparator()
            import_tracks_action = QAction("Import Tracks...", self)
            import_tracks_action.triggered.connect(self.open_upload_file_picker)
            file_menu.addAction(import_tracks_action)
            import_folder_action = QAction("Import Folder...", self)
            import_folder_action.triggered.connect(self.open_upload_folder_picker)
            file_menu.addAction(import_folder_action)

            engine_menu = menu_bar.addMenu("&Engine")
            run_graph_action = QAction("Run Full Graph", self)
            run_graph_action.setShortcut("Ctrl+R")
            run_graph_action.setToolTip("Run every connected node down to the final output.")
            run_graph_action.triggered.connect(self.run_flow)
            engine_menu.addAction(run_graph_action)
            run_selected_action = QAction("Run Selected Node", self)
            run_selected_action.setToolTip("Run only the selected node and its upstream inputs.")
            run_selected_action.triggered.connect(self.run_selected_node)
            engine_menu.addAction(run_selected_action)
            engine_menu.addSeparator()
            reset_engine_action = QAction("Reset Engine", self)
            reset_engine_action.setToolTip("Clear all runtime outputs and errors; keep the graph.")
            reset_engine_action.triggered.connect(self.reset_engine)
            engine_menu.addAction(reset_engine_action)
            reset_canvas_action = QAction("Reset Canvas", self)
            reset_canvas_action.setToolTip("Clear the whole graph and start from the pinned engine node.")
            reset_canvas_action.triggered.connect(self.reset_canvas)
            engine_menu.addAction(reset_canvas_action)

            view_menu = menu_bar.addMenu("&View")
            zoom_in_action = QAction("Zoom In", self)
            zoom_in_action.setShortcut("Ctrl+=")
            zoom_in_action.triggered.connect(lambda: self.view.zoom_by_steps(1.0))
            view_menu.addAction(zoom_in_action)
            zoom_out_action = QAction("Zoom Out", self)
            zoom_out_action.setShortcut("Ctrl+-")
            zoom_out_action.triggered.connect(lambda: self.view.zoom_by_steps(-1.0))
            view_menu.addAction(zoom_out_action)
            reset_zoom_action = QAction("Reset Zoom", self)
            reset_zoom_action.setShortcut("Ctrl+0")
            reset_zoom_action.triggered.connect(lambda: self.view.reset_zoom())
            view_menu.addAction(reset_zoom_action)
            fit_action = QAction("Fit Engine", self)
            fit_action.triggered.connect(self.fit_engine)
            view_menu.addAction(fit_action)
            zoom_selected_action = QAction("Zoom to Selected", self)
            zoom_selected_action.setShortcut("F")
            zoom_selected_action.triggered.connect(self.zoom_to_selected)
            view_menu.addAction(zoom_selected_action)

        def _toolbar_section_label(self, toolbar, text: str) -> None:
            label = QLabel(text)
            label.setProperty("role", "patch")
            toolbar.addWidget(label)

        def _build_toolbar(self) -> None:
            # UI/UX audit P1: grouped toolbar — PROJECT | ENGINE | VIEW. Zoom
            # controls no longer sit between engine actions.
            toolbar = self.addToolBar("Signal Graph")
            toolbar.setMovable(False)

            brand = QLabel("SIGNAL GRAPH")
            brand.setProperty("role", "brand")
            toolbar.addWidget(brand)
            toolbar.addSeparator()

            self._toolbar_section_label(toolbar, "PROJECT")
            upload_button = QPushButton("UPLOAD FOLDER")
            upload_button.setProperty("role", "preset")
            upload_button.setToolTip("Add or reuse an Upload Tracks node and choose a music folder.")
            upload_button.clicked.connect(self.open_upload_folder_picker)
            toolbar.addWidget(upload_button)
            import_button = QPushButton("IMPORT TRACKS")
            import_button.setProperty("role", "preset")
            import_button.setToolTip("Add or reuse an Upload Tracks node and choose audio files.")
            import_button.clicked.connect(self.open_upload_file_picker)
            toolbar.addWidget(import_button)
            toolbar.addSeparator()

            self._toolbar_section_label(toolbar, "ENGINE")
            self.run_button = QPushButton("▶ RUN ANALYSIS")
            self.run_button.setProperty("role", "hero")
            self.run_button.setToolTip(
                "Run the whole graph: analyze uploaded tracks and execute every "
                "connected node down to the final output."
            )
            self.run_button.clicked.connect(self.run_flow)
            toolbar.addWidget(self.run_button)
            smart_playlist_button = QPushButton("SMART PLAYLIST")
            smart_playlist_button.setProperty("role", "preset")
            smart_playlist_button.setToolTip(
                "One-click flow: choose a folder -> analyze -> build a set -> export Rekordbox XML."
            )
            smart_playlist_button.clicked.connect(self.build_smart_playlist_flow)
            toolbar.addWidget(smart_playlist_button)
            first_flow_button = QPushButton("PAIR REVIEW FLOW")
            first_flow_button.setProperty("role", "preset")
            first_flow_button.setToolTip("Build the beginner review graph for testing pair decisions.")
            first_flow_button.clicked.connect(self.build_first_flow)
            toolbar.addWidget(first_flow_button)

            remove_action = QAction("Remove Selected", self)
            remove_action.triggered.connect(self.remove_selected_node)
            toolbar.addAction(remove_action)

            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            toolbar.addWidget(spacer)

            self._toolbar_section_label(toolbar, "VIEW")
            for label, handler in (
                ("Zoom In", lambda: self.view.zoom_by_steps(1.0)),
                ("Zoom Out", lambda: self.view.zoom_by_steps(-1.0)),
                ("Fit", self.fit_engine),
                ("Reset Zoom", lambda: self.view.reset_zoom()),
            ):
                view_action = QAction(label, self)
                view_action.triggered.connect(handler)
                toolbar.addAction(view_action)
            toolbar.addSeparator()

            self.toolbar_status_label = QLabel("ENGINE READY")
            self.toolbar_status_label.setProperty("role", "toolbar_status")
            toolbar.addWidget(self.toolbar_status_label)

        def _build_canvas(self) -> None:
            self.scene = QGraphicsScene(self)
            self.scene.setSceneRect(-1200.0, -800.0, 4200.0, 2800.0)
            self.view = NodeCanvasView(self, self.scene)
            self.setCentralWidget(self.view)

        def _build_library(self) -> None:
            dock = QDockWidget("Node Library", self)
            dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
            tree = NodeLibraryTree()
            tree.itemDoubleClicked.connect(self._handle_library_double_click)
            self.library_tree = tree
            dock.setWidget(tree)
            self.addDockWidget(Qt.LeftDockWidgetArea, dock)
            self._populate_library()

        def _build_inspector(self) -> None:
            dock = QDockWidget("Parameter Panel", self)
            dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
            dock.setMinimumWidth(360)
            dock.setMaximumWidth(460)
            self.inspector_scroll = QScrollArea()
            self.inspector_scroll.setWidgetResizable(True)
            self.inspector_container = QWidget()
            self.inspector_layout = QVBoxLayout(self.inspector_container)
            self.inspector_layout.setContentsMargins(12, 12, 12, 12)
            self.inspector_layout.setSpacing(10)
            self.inspector_scroll.setWidget(self.inspector_container)
            dock.setWidget(self.inspector_scroll)
            self.addDockWidget(Qt.RightDockWidgetArea, dock)

        def _node_library_tooltip(self, node: NodeSpec) -> str:
            """UI/UX audit §16: every node explains what/inputs/outputs/status."""
            audit = self._node_audit_snapshot(node)
            lines = [node.label, "", node.summary]
            if node.inputs:
                lines.append("")
                lines.append("Inputs:")
                lines.extend(f"  • {port.key} — {port.description}" for port in node.inputs)
            if node.outputs:
                lines.append("")
                lines.append("Outputs:")
                lines.extend(f"  • {port.key} — {port.description}" for port in node.outputs)
            lines.append("")
            lines.append(
                f"Status: {audit['readiness_label']} · runtime "
                f"{audit['runtime_status_label'].lower()} · form {audit['form_status_label'].lower()}"
            )
            return "\n".join(lines)

        def _populate_library(self) -> None:
            # UI/UX audit §8/§12/§14: friendly category names, subtle counts,
            # diagnostics/utilities collapsed as advanced by default.
            self.library_tree.clear()
            ordered = ["system", "input", "engine_ops", "screens", "output", "sensors", "utility"]
            display_names = {
                "system": "SYSTEM",
                "input": "PROJECT / INPUT",
                "engine_ops": "ANALYSIS & DECISION",
                "screens": "VIEWS",
                "output": "OUTPUTS",
                "sensors": "DIAGNOSTICS / SIGNALS",
                "utility": "UTILITIES",
            }
            advanced_categories = {"sensors", "utility"}
            for category in ordered:
                nodes = [node for node in self.registry.nodes if node.category == category]
                if not nodes:
                    continue
                summary = self._category_readiness_summary(nodes)
                display = display_names.get(category, category.replace("_", " ").upper())
                suffix = "  · advanced" if category in advanced_categories else ""
                parent = QTreeWidgetItem(
                    [f"{CATEGORY_MARKERS.get(category, '■')}  {display} ({len(nodes)}){suffix}"]
                )
                parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
                parent.setForeground(0, QBrush(QColor(_category_color(category))))
                parent.setToolTip(
                    0,
                    (
                        f"{summary['desktop_ready']} ready · "
                        f"{summary['partial']} partial · "
                        f"{summary['contract_only']} contract-only"
                    ),
                )
                self.library_tree.addTopLevelItem(parent)
                for node in nodes:
                    audit = self._node_audit_snapshot(node)
                    child = QTreeWidgetItem([f"{CATEGORY_MARKERS.get(category, '■')}  {node.label}"])
                    child.setData(0, Qt.UserRole, node.node_id)
                    child.setToolTip(0, self._node_library_tooltip(node))
                    child.setForeground(0, QBrush(QColor(audit["display_color"])))
                    parent.addChild(child)
                parent.setExpanded(category not in advanced_categories)

        def _handle_library_double_click(self, item: QTreeWidgetItem) -> None:
            node_id = item.data(0, Qt.UserRole)
            if isinstance(node_id, str):
                self.add_node(node_id)

        def _next_instance_id(self, node_id: str) -> str:
            instance_id = f"desktop_{node_id}_{self.instance_counter}"
            self.instance_counter += 1
            return instance_id

        def _current_view_scene_center(self) -> QPointF:
            return self.view.mapToScene(self.view.viewport().rect().center())

        def _suggest_node_position(self, spec: NodeSpec) -> tuple[float, float]:
            selected = self.selected_node_item()
            if selected is not None:
                return (
                    selected.model.x + selected.rect().width() + 48.0,
                    selected.model.y + 24.0,
                )

            scene_center = self._current_view_scene_center()
            width = 260.0 if spec.pinned else 196.0
            height = NodeBoxItem._estimated_height(spec)
            return (
                float(scene_center.x() - width / 2.0),
                float(scene_center.y() - height / 2.0),
            )

        def add_node(
            self,
            node_id: str,
            x: float | None = None,
            y: float | None = None,
            *,
            instance_id: str | None = None,
        ) -> NodeBoxItem:
            spec = self.node_specs[node_id]
            # UI/UX audit §9: the engine is a singleton — a second copy could be
            # added but never deleted (deletable=False). Return the existing one.
            if node_id == "engine":
                existing = next(
                    (
                        item
                        for item in self.node_items.values()
                        if item.model.spec.node_id == "engine"
                    ),
                    None,
                )
                if existing is not None:
                    self._select_node(existing)
                    self.statusBar().showMessage("Engine already exists in this graph.", 4000)
                    return existing
            if x is None or y is None:
                x, y = self._suggest_node_position(spec)
            model = NodeInstanceModel(
                instance_id=instance_id or self._next_instance_id(node_id),
                spec=spec,
                x=x,
                y=y,
            )
            item = NodeBoxItem(self, model)
            self.scene.addItem(item)
            self.node_items[model.instance_id] = item
            self._select_node(item)
            self.statusBar().showMessage(f"Added {spec.label}.", 2500)
            self._mark_project_dirty()
            self._refresh_engine_status()
            return item

        def selected_node_item(self) -> NodeBoxItem | None:
            selected_items = [
                item for item in self.scene.selectedItems() if isinstance(item, NodeBoxItem)
            ]
            return selected_items[0] if selected_items else None

        def _select_node(self, node_item: NodeBoxItem) -> None:
            self.scene.clearSelection()
            node_item.setSelected(True)
            self._refresh_port_states()
            self._sync_inspector()

        def _node_item_from_graphics_item(self, item: QGraphicsItem | None) -> NodeBoxItem | None:
            current = item
            while current is not None:
                if isinstance(current, NodeBoxItem):
                    return current
                current = current.parentItem()
            return None

        def _upload_nodes(self) -> list[NodeBoxItem]:
            return [
                node_item
                for node_item in self.node_items.values()
                if node_item.model.spec.node_id == "upload_tracks"
            ]

        def _default_audio_dialog_dir(self, paths: list[str] | None = None) -> str:
            if paths:
                return str(Path(paths[0]).expanduser().parent)
            return str(Path.home())

        def _configured_upload_paths(self, node_item: NodeBoxItem) -> list[str]:
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            return [
                line.strip()
                for line in str(config.get("paths_text", "")).splitlines()
                if line.strip()
            ]

        def _preferred_upload_node(self) -> NodeBoxItem | None:
            selected = self.selected_node_item()
            if selected is not None and selected.model.spec.node_id == "upload_tracks":
                return selected
            upload_nodes = self._upload_nodes()
            if len(upload_nodes) == 1:
                return upload_nodes[0]
            return None

        def _resolve_upload_target(self, scene_pos: QPointF | None = None) -> NodeBoxItem:
            if scene_pos is not None:
                dropped_item = self._node_item_from_graphics_item(
                    self.scene.itemAt(scene_pos, self.view.transform())
                )
                if dropped_item is not None and dropped_item.model.spec.node_id == "upload_tracks":
                    return dropped_item

            preferred = self._preferred_upload_node()
            if preferred is not None:
                return preferred

            if scene_pos is not None:
                return self.add_node("upload_tracks", x=scene_pos.x(), y=scene_pos.y())
            return self.add_node("upload_tracks")

        def _set_upload_paths(
            self,
            node_item: NodeBoxItem,
            paths: list[str | Path],
            *,
            replace: bool = False,
            refresh_selection: bool = True,
        ) -> list[str]:
            current_paths = [] if replace else self._configured_upload_paths(node_item)
            merged = _dedupe_paths([*current_paths, *_normalize_audio_paths(paths)])
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            config["paths_text"] = "\n".join(merged)
            self._mark_project_dirty()
            self._refresh_engine_status()
            if refresh_selection:
                self._select_node(node_item)
            return merged

        def _choose_audio_folders(self, *, title: str = "Choose Music Folder(s)") -> list[Path]:
            return choose_audio_directories(
                self,
                title=title,
                start_dir=self._default_audio_dialog_dir(),
            )

        def _discover_audio_files_from_folders(self, folders: list[Path]) -> list[Path]:
            files: list[Path] = []
            for folder in folders:
                files.extend(discover_audio_files(folder))
            return [Path(path) for path in _dedupe_paths(files)]

        def _confirm_audio_import(self, files: list[str | Path]) -> list[Path]:
            return confirm_suspicious_audio_files(self, files)

        def open_upload_file_picker(self, node_item: NodeBoxItem | None = None) -> list[str]:
            target = node_item or self._preferred_upload_node()
            selected, _ = QFileDialog.getOpenFileNames(
                self,
                "Choose Audio Tracks",
                self._default_audio_dialog_dir(
                    self._configured_upload_paths(target) if target is not None else None
                ),
                AUDIO_FILE_FILTER,
            )
            if not selected:
                return []
            selected_paths = self._confirm_audio_import(selected)
            if not selected_paths:
                self.statusBar().showMessage("Import cancelled or all suspicious files were skipped.", 6000)
                return []
            if target is None:
                target = self._resolve_upload_target()
            merged = self._set_upload_paths(target, selected_paths)
            self.statusBar().showMessage(
                f"Queued {len(merged)} audio file(s) in Upload Tracks.",
                4000,
            )
            return merged

        def open_upload_folder_picker(self, node_item: NodeBoxItem | None = None) -> list[str]:
            target = node_item or self._preferred_upload_node()
            folders = self._choose_audio_folders(title="Choose Music Folder(s)")
            if not folders:
                return []
            try:
                files = self._discover_audio_files_from_folders(folders)
            except ValueError as exc:
                self.statusBar().showMessage(str(exc), 6000)
                return []
            if not files:
                self.statusBar().showMessage("No supported audio files found in selected folder(s).", 6000)
                return []
            accepted_files = self._confirm_audio_import(files)
            if not accepted_files:
                self.statusBar().showMessage("Import cancelled or all suspicious files were skipped.", 6000)
                return []
            if target is None:
                target = self._resolve_upload_target()
            merged = self._set_upload_paths(target, accepted_files)
            self.statusBar().showMessage(
                f"Queued {len(accepted_files)} audio file(s) from {len(folders)} folder(s).",
                5000,
            )
            return merged

        def handle_audio_file_drop(
            self,
            paths: list[str | Path],
            *,
            scene_pos: QPointF | None = None,
        ) -> list[str]:
            target = self._resolve_upload_target(scene_pos)
            merged = self._set_upload_paths(target, paths)
            self.statusBar().showMessage(
                f"Queued {len(merged)} audio file(s) from Finder drop.",
                4000,
            )
            return merged

        def handle_port_click(self, handle: PortHandleItem) -> None:
            if handle.direction == "output":
                self.pending_output_handle = None if self.pending_output_handle is handle else handle
                self.statusBar().showMessage(
                    "Select a compatible input port to complete the connection.", 3000
                )
                self._refresh_port_states()
                self._sync_inspector()
                return

            if self.pending_output_handle is None:
                self.statusBar().showMessage(
                    "Start a connection from an output port first.", 3000
                )
                return

            if not self._ports_compatible(self.pending_output_handle.port_spec, handle.port_spec):
                self.statusBar().showMessage(
                    "Incompatible port types. Pick a highlighted compatible input.", 3500
                )
                return

            self.connect_ports(self.pending_output_handle, handle)
            self.pending_output_handle = None
            self._refresh_port_states()
            self._sync_inspector()
            self.statusBar().showMessage("Connection added.", 2500)

        def start_connection_drag(self, handle: PortHandleItem, scene_pos: QPointF) -> None:
            self.connection_drag_source = handle
            self.connection_drag_started = False
            self.connection_drag_start_scene_pos = scene_pos
            self.pending_connection_preview = PendingConnectionItem(handle)
            self.scene.addItem(self.pending_connection_preview)
            self._refresh_port_states()
            self.statusBar().showMessage(
                "Drag the cable to a highlighted compatible socket.",
                2500,
            )

        def update_connection_drag(self, scene_pos: QPointF) -> None:
            source = self.connection_drag_source
            if source is None or self.pending_connection_preview is None:
                return
            self.pending_connection_preview.update_path(scene_pos)
            if self.connection_drag_start_scene_pos is not None:
                dx = scene_pos.x() - self.connection_drag_start_scene_pos.x()
                dy = scene_pos.y() - self.connection_drag_start_scene_pos.y()
                if (dx * dx + dy * dy) > 16.0:
                    self.connection_drag_started = True

            target = self._port_handle_at_scene_pos(scene_pos, exclude=source)
            connectable = target is not None and self._handles_connectable(source, target)
            invalid_target = target is not None and not connectable
            self.pending_connection_preview.set_target_state(valid=connectable, invalid=invalid_target)
            self._refresh_port_states(hover_target=target if connectable else None)

        def finish_connection_drag(self, scene_pos: QPointF) -> None:
            source = self.connection_drag_source
            target = self._port_handle_at_scene_pos(scene_pos, exclude=source)
            if source is not None and target is not None and self._handles_connectable(source, target):
                output_handle, input_handle = self._connection_direction(source, target)
                self.connect_ports(output_handle, input_handle)
                self.pending_output_handle = None
                self.statusBar().showMessage("Connection added.", 2500)
            elif source is not None and not self.connection_drag_started:
                self.handle_port_click(source)
            elif source is not None:
                self.statusBar().showMessage(
                    "Connection cancelled. Drop on a highlighted compatible socket.",
                    3000,
                )
            self._clear_connection_drag()
            self._refresh_port_states()
            self._sync_inspector()

        def _clear_connection_drag(self) -> None:
            if self.pending_connection_preview is not None:
                self.scene.removeItem(self.pending_connection_preview)
            self.pending_connection_preview = None
            self.connection_drag_source = None
            self.connection_drag_started = False
            self.connection_drag_start_scene_pos = None

        def _all_port_handles(self) -> list[PortHandleItem]:
            handles: list[PortHandleItem] = []
            for node_item in self.node_items.values():
                handles.extend(node_item.input_handles.values())
                handles.extend(node_item.output_handles.values())
            return handles

        def _port_handle_at_scene_pos(
            self,
            scene_pos: QPointF,
            *,
            exclude: PortHandleItem | None = None,
        ) -> PortHandleItem | None:
            zoom = max(float(self.view.transform().m11()), 0.2)
            max_distance = 18.0 / zoom
            closest: tuple[float, PortHandleItem] | None = None
            for handle in self._all_port_handles():
                if handle is exclude:
                    continue
                center = handle.center_in_scene()
                dx = center.x() - scene_pos.x()
                dy = center.y() - scene_pos.y()
                distance = (dx * dx + dy * dy) ** 0.5
                if distance <= max_distance and (
                    closest is None or distance < closest[0]
                ):
                    closest = (distance, handle)
            return closest[1] if closest is not None else None

        def _connection_direction(
            self,
            first: PortHandleItem,
            second: PortHandleItem,
        ) -> tuple[PortHandleItem, PortHandleItem]:
            if first.direction == "output" and second.direction == "input":
                return first, second
            if first.direction == "input" and second.direction == "output":
                return second, first
            raise ValueError("Connection direction requires one output and one input handle.")

        def _handles_connectable(self, first: PortHandleItem, second: PortHandleItem) -> bool:
            if first.node_item is second.node_item:
                return False
            if first.direction == second.direction:
                return False
            output_handle, input_handle = self._connection_direction(first, second)
            return self._ports_compatible(output_handle.port_spec, input_handle.port_spec)

        def _ports_compatible(self, output_port: NodePortSpec, input_port: NodePortSpec) -> bool:
            output_types = set(output_port.port_types)
            return any(port_type in output_types for port_type in input_port.port_types)

        def _connection_key(
            self,
            source_handle: PortHandleItem,
            target_handle: PortHandleItem,
        ) -> str:
            return "::".join(
                [
                    source_handle.node_item.model.instance_id,
                    source_handle.port_spec.key,
                    target_handle.node_item.model.instance_id,
                    target_handle.port_spec.key,
                ]
            )

        def connect_ports(
            self,
            source_handle: PortHandleItem,
            target_handle: PortHandleItem,
        ) -> None:
            self._remove_connection_to_input(
                target_handle.node_item.model.instance_id,
                target_handle.port_spec.key,
            )
            connection_id = self._connection_key(source_handle, target_handle)
            if connection_id in self.connection_models:
                return

            model = RuntimeConnection(
                from_instance_id=source_handle.node_item.model.instance_id,
                from_port_key=source_handle.port_spec.key,
                to_instance_id=target_handle.node_item.model.instance_id,
                to_port_key=target_handle.port_spec.key,
            )
            item = ConnectionItem(connection_id, source_handle, target_handle)
            self.connection_models[connection_id] = model
            self.connection_items[connection_id] = item
            source_handle.node_item.add_connection(item)
            target_handle.node_item.add_connection(item)
            self.scene.addItem(item)
            item.update_path()
            self._mark_project_dirty()
            self._refresh_engine_status()

        def _remove_connection_to_input(self, instance_id: str, port_key: str) -> None:
            for connection_id, model in list(self.connection_models.items()):
                if model.to_instance_id == instance_id and model.to_port_key == port_key:
                    self.remove_connection(connection_id)

        def remove_connection(self, connection_id: str) -> None:
            item = self.connection_items.pop(connection_id, None)
            model = self.connection_models.pop(connection_id, None)
            if item is not None:
                item.source_handle.node_item.remove_connection(item)
                item.target_handle.node_item.remove_connection(item)
                self.scene.removeItem(item)
            if model is not None:
                self.statusBar().showMessage("Connection removed.", 2000)
                self._mark_project_dirty()
                self._refresh_engine_status()

        def _refresh_port_states(self, hover_target: PortHandleItem | None = None) -> None:
            active_source = self.connection_drag_source or self.pending_output_handle
            for node_item in self.node_items.values():
                for handle in node_item.input_handles.values():
                    compatible = (
                        active_source is not None
                        and active_source is not handle
                        and self._handles_connectable(active_source, handle)
                    )
                    handle.set_state(active=handle is active_source, compatible=compatible or handle is hover_target)
                for handle in node_item.output_handles.values():
                    compatible = (
                        active_source is not None
                        and active_source is not handle
                        and self._handles_connectable(active_source, handle)
                    )
                    handle.set_state(active=handle is active_source, compatible=compatible or handle is hover_target)

        def _serialize_node_states(self) -> list[RuntimeNodeState]:
            return [
                RuntimeNodeState(instance_id=item.model.instance_id, node_id=item.model.spec.node_id)
                for item in self.node_items.values()
            ]

        def _serialize_connections(self) -> list[RuntimeConnection]:
            return list(self.connection_models.values())

        def _clear_inspector(self) -> None:
            # setParent(None) detaches immediately — deleteLater alone leaves
            # widgets as findChildren-visible ghosts until the event loop spins,
            # so rebuilds appeared to accumulate stale controls.
            while self.inspector_layout.count():
                item = self.inspector_layout.takeAt(0)
                widget = item.widget()
                child_layout = item.layout()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
                elif child_layout is not None:
                    while child_layout.count():
                        inner = child_layout.takeAt(0)
                        if inner.widget() is not None:
                            inner.widget().setParent(None)
                            inner.widget().deleteLater()

        def _add_label(
            self,
            text: str,
            *,
            role: str | None = None,
            word_wrap: bool = True,
            mono: bool = False,
        ) -> QLabel:
            label = QLabel(text)
            label.setWordWrap(word_wrap)
            if role is not None:
                label.setProperty("role", role)
            if mono:
                font = QFont("IBM Plex Mono", 9)
                label.setFont(font)
            self.inspector_layout.addWidget(label)
            return label

        def _add_section_title(self, title: str) -> None:
            label = QLabel(title)
            label.setProperty("role", "section")
            self.inspector_layout.addWidget(label)

        def _add_pills(self, values: list[str]) -> None:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            for value in values:
                pill = QLabel(value)
                pill.setProperty("role", "pill")
                layout.addWidget(pill)
            layout.addStretch(1)
            self.inspector_layout.addWidget(row)

        def _set_toolbar_status(self, message: str) -> None:
            self.toolbar_status_label.setText(message.upper())

        def _pretty_json(self, value: Any) -> str:
            def normalize(obj: Any) -> Any:
                if hasattr(obj, "model_dump"):
                    return normalize(obj.model_dump(mode="json"))
                if isinstance(obj, dict):
                    return {key: normalize(val) for key, val in obj.items()}
                if isinstance(obj, list):
                    return [normalize(item) for item in obj]
                return obj

            return json.dumps(normalize(value), indent=2, ensure_ascii=True)

        def _node_form_status(self, spec: NodeSpec) -> str:
            if spec.node_id in FORM_IMPLEMENTED_NODE_IDS:
                return "implemented"
            if spec.node_id in HOST_FORM_REQUIRED_NODE_IDS:
                return "missing"
            return "not_required"

        def _node_audit_snapshot(self, spec: NodeSpec) -> dict[str, Any]:
            runtime_ready = self.runtime.supports_node(spec.node_id)
            host_status = spec.host_execution_status
            form_status = self._node_form_status(spec)

            if runtime_ready and form_status != "missing":
                readiness = "desktop_ready"
                display_color = "#7cb96b"
            elif runtime_ready or form_status == "implemented":
                readiness = "partial"
                display_color = "#d99a4e"
            else:
                readiness = "contract_only"
                display_color = "#8b8d92"

            gaps: list[str] = []
            if host_status == "engine_only":
                gaps.append("Engine/API capability exists, but the desktop host has no executor adapter yet.")
            elif host_status == "adapter_needed":
                gaps.append("A host adapter is still needed before this node can run in the desktop graph.")
            elif host_status == "planned":
                gaps.append("Host execution is planned, not implemented.")
            if not runtime_ready and host_status == "runnable":
                gaps.append("Desktop runtime still does not execute this node.")
            if form_status == "missing":
                gaps.append("Desktop host still lacks a host-side parameter form for this node.")
            if spec.status == "planned":
                gaps.append("Registry status is still planned, so the node should be treated as future-facing only.")
            gaps.extend(NODE_AUDIT_NOTES.get(spec.node_id, []))

            readiness_label = {
                "desktop_ready": "Desktop Ready",
                "partial": "Partial",
                "contract_only": "Contract Only",
            }[readiness]
            runtime_status_label = {
                "runnable": "Host Runnable",
                "engine_only": "Engine Only",
                "adapter_needed": "Adapter Needed",
                "planned": "Planned",
            }[host_status]
            form_status_label = {
                "implemented": "Form Ready",
                "missing": "Form Missing",
                "not_required": "No Form Needed",
            }[form_status]

            return {
                "readiness": readiness,
                "readiness_label": readiness_label,
                "runtime_ready": runtime_ready,
                "runtime_status_label": runtime_status_label,
                "host_execution_status": host_status,
                "form_status": form_status,
                "form_status_label": form_status_label,
                "display_color": display_color,
                "gaps": gaps,
            }

        def _category_readiness_summary(self, nodes: list[NodeSpec]) -> dict[str, int]:
            summary = {"desktop_ready": 0, "partial": 0, "contract_only": 0}
            for node in nodes:
                readiness = self._node_audit_snapshot(node)["readiness"]
                summary[readiness] += 1
            return summary

        def _add_audit_section(self, spec: NodeSpec) -> None:
            audit = self._node_audit_snapshot(spec)
            if not audit["gaps"]:
                return
            self._add_section_title("Implementation Notes")
            self._add_pills(
                [
                    audit["readiness_label"],
                    audit["runtime_status_label"],
                    audit["form_status_label"],
                ]
            )
            for gap in audit["gaps"]:
                self._add_label(gap, role="hint")

        def _upstream_analysis_choices(self) -> list[tuple[str, str]]:
            analyses = list(self.runtime.analysis_index.values())
            choices: list[tuple[str, str]] = []
            for analysis in analyses:
                label = analysis.track.title or analysis.track.track_id
                choices.append((analysis.track.track_id, f"{label} · {analysis.track.track_id}"))
            return choices

        def _track_label(self, track_id: str) -> str:
            analysis = self.runtime.analysis_index.get(track_id)
            if analysis is None:
                return track_id
            return f"{analysis.track.title or track_id} · {track_id}"

        def _incoming_connection(
            self,
            instance_id: str,
            input_port_key: str,
        ) -> RuntimeConnection | None:
            for connection in self.connection_models.values():
                if connection.to_instance_id == instance_id and connection.to_port_key == input_port_key:
                    return connection
            return None

        def _repository_track_choices(self) -> list[tuple[str, str]]:
            try:
                track_ids = self.runtime._repository(self.runtime._processed_dir()).list_track_ids()
            except Exception:
                return []
            return [(track_id, self._track_label(track_id)) for track_id in track_ids]

        def _track_choices_for_input(
            self,
            node_item: NodeBoxItem,
            input_port_key: str,
            *,
            fallback_to_session: bool = True,
            fallback_to_repository: bool = False,
        ) -> list[tuple[str, str]]:
            connection = self._incoming_connection(node_item.model.instance_id, input_port_key)
            if connection is not None:
                upstream = self.runtime.outputs.get(connection.from_instance_id)
                if upstream is not None:
                    payload = upstream.ports.get(connection.from_port_key)
                    if isinstance(payload, AnalysisResult):
                        track_id = payload.track.track_id
                        return [(track_id, self._track_label(track_id))]
                    if isinstance(payload, str):
                        return [(str(payload), self._track_label(str(payload)))]
                    if isinstance(payload, list) and payload:
                        if isinstance(payload[0], AnalysisResult):
                            return [
                                (
                                    analysis.track.track_id,
                                    f"{analysis.track.title or analysis.track.track_id} · {analysis.track.track_id}",
                                )
                                for analysis in payload
                            ]
                        if isinstance(payload[0], str):
                            return [(track_id, self._track_label(str(track_id))) for track_id in payload]
            if fallback_to_session:
                session_choices = self._upstream_analysis_choices()
                if session_choices:
                    return session_choices
            if fallback_to_repository:
                return self._repository_track_choices()
            return []

        def _upstream_track_choices(self, node_item: NodeBoxItem) -> list[tuple[str, str]]:
            return self._track_choices_for_input(node_item, "source")

        def _set_combo_to_value(
            self,
            combo: QComboBox,
            value: str | None,
            fallback_index: int = 0,
        ) -> None:
            if value:
                idx = combo.findData(value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    return
            if combo.count():
                combo.setCurrentIndex(fallback_index)

        def _populate_upload_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Upload Tracks")
            self._add_label(
                "Choose tracks from disk with the button below, or drop audio files from Finder onto this node, this panel, or the canvas.",
                role="callout",
            )
            controls = QWidget()
            controls_layout = QHBoxLayout(controls)
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(8)

            choose_button = QPushButton("Open File Picker...")
            choose_button.setProperty("role", "primary")
            folder_button = QPushButton("Open Folder...")
            clear_button = QPushButton("Clear List")
            controls_layout.addWidget(choose_button)
            controls_layout.addWidget(folder_button)
            controls_layout.addWidget(clear_button)
            self.inspector_layout.addWidget(controls)

            self.inspector_layout.addWidget(QLabel("Queued Audio Files"))

            def apply_paths(paths: list[str | Path], *, replace: bool = False) -> list[str]:
                merged = self._set_upload_paths(
                    node_item,
                    list(paths),
                    replace=replace,
                    refresh_selection=False,
                )
                field.blockSignals(True)
                field.setPlainText("\n".join(merged))
                field.blockSignals(False)
                sync_text()
                return merged

            field = AudioPathTextEdit(lambda dropped: apply_paths(dropped))
            field.setPlainText("\n".join(self._configured_upload_paths(node_item)))
            field.setPlaceholderText(
                "/Users/you/Music/Track A.mp3\n/Users/you/Music/Track B.wav"
            )
            field.setMinimumHeight(220)

            summary = QLabel()
            summary.setProperty("role", "hint")
            summary.setWordWrap(True)

            def current_paths() -> list[str]:
                return [line.strip() for line in field.toPlainText().splitlines() if line.strip()]

            def sync_text() -> None:
                paths = current_paths()
                config = self.runtime.ensure_node_config(node_item.model.instance_id)
                config["paths_text"] = "\n".join(paths)
                self._mark_project_dirty()
                self._refresh_engine_status()
                count = len(paths)
                if count == 0:
                    summary.setText("No audio files queued yet. Click Open File Picker... to choose tracks.")
                    return
                preview = ", ".join(Path(path).name or path for path in paths[:3])
                if count > 3:
                    preview = f"{preview} +{count - 3} more"
                summary.setText(f"{count} audio file(s) queued for analysis.\n{preview}")

            def clear_paths() -> None:
                apply_paths([], replace=True)

            field.textChanged.connect(sync_text)
            choose_button.clicked.connect(lambda: self.open_upload_file_picker(node_item))
            folder_button.clicked.connect(lambda: self.open_upload_folder_picker(node_item))
            clear_button.clicked.connect(clear_paths)
            self.inspector_layout.addWidget(field)
            self.inspector_layout.addWidget(summary)
            sync_text()

        def _populate_analysis_depth_form(
            self,
            node_item: NodeBoxItem,
            *,
            title: str = "Analysis Depth",
        ) -> None:
            self._add_section_title(title)
            self._add_label(
                "Normal is fast full-mix analysis. Deep enables Demucs stem-aware analysis "
                "for vocals/drums/bass/other, refreshes caches, and keeps more transition candidates.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            config.setdefault("analysis_depth", "normal")
            depth_combo = QComboBox()
            depth_combo.addItem("Normal - fast full-mix analysis", "normal")
            depth_combo.addItem("Deep - Demucs stem-aware analysis", "deep")
            self._set_combo_to_value(depth_combo, str(config.get("analysis_depth") or "normal"))
            config["analysis_depth"] = depth_combo.currentData()
            depth_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("analysis_depth", depth_combo.currentData())
            )
            self.inspector_layout.addWidget(depth_combo)

        def _populate_load_corpus_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Load Track Library")
            self._add_label(
                "Bridge the local processed repository into the graph. This node can expose track IDs only or hydrate full analyses.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            defaults = self.runtime.config()
            default_processed = str(Path(defaults.paths.processed_dir).expanduser())
            default_annotations = str((Path(defaults.paths.data_dir).expanduser() / "annotations"))
            config.setdefault("processed_dir", default_processed)
            config.setdefault("annotations_dir", default_annotations)
            config.setdefault("load_mode", "track_ids")

            def add_directory_field(
                label_text: str,
                config_key: str,
                dialog_title: str,
            ) -> QLineEdit:
                self.inspector_layout.addWidget(QLabel(label_text))
                row = QWidget()
                layout = QHBoxLayout(row)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(8)
                field = QLineEdit(str(config.get(config_key, "")))
                browse = QPushButton("Browse")

                def choose_directory() -> None:
                    start_dir = field.text().strip() or str(Path.home())
                    selected = QFileDialog.getExistingDirectory(self, dialog_title, start_dir)
                    if selected:
                        field.setText(selected)

                def sync_text(value: str) -> None:
                    config[config_key] = value.strip()

                field.textChanged.connect(sync_text)
                browse.clicked.connect(choose_directory)
                layout.addWidget(field, 1)
                layout.addWidget(browse)
                self.inspector_layout.addWidget(row)
                return field

            add_directory_field("Processed Directory", "processed_dir", "Choose Processed Directory")
            add_directory_field("Annotations Directory", "annotations_dir", "Choose Annotations Directory")

            self.inspector_layout.addWidget(QLabel("Load Mode"))
            mode_combo = QComboBox()
            mode_combo.addItem("Track IDs + Manifest", "track_ids")
            mode_combo.addItem("Track IDs + Analyses + Manifest", "analysis")
            self._set_combo_to_value(mode_combo, str(config.get("load_mode") or "track_ids"))
            config["load_mode"] = mode_combo.currentData()
            mode_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("load_mode", mode_combo.currentData())
            )
            self.inspector_layout.addWidget(mode_combo)

        def _populate_build_set_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Generate Set Sequence")
            self._add_label(
                "Build a SetPlan from analyzed tracks or repository-backed track IDs. The desktop host uses the engine weights and current corpus bridge.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            config.setdefault("arc", "build")
            config.setdefault("planner_mode", "smart")

            self.inspector_layout.addWidget(QLabel("Arc Mode"))
            arc_combo = QComboBox()
            for arc in ("build", "flat", "peak"):
                arc_combo.addItem(arc.title(), arc)
            self._set_combo_to_value(arc_combo, str(config.get("arc") or "build"))
            config["arc"] = arc_combo.currentData()
            arc_combo.currentIndexChanged.connect(lambda _: config.__setitem__("arc", arc_combo.currentData()))
            self.inspector_layout.addWidget(arc_combo)

            self.inspector_layout.addWidget(QLabel("Playlist Preference"))
            planner_combo = QComboBox()
            planner_combo.addItem("Smart Playlist - balanced", "smart")
            planner_combo.addItem("Harmonic Match - Camelot/key-first", "harmonic")
            planner_combo.addItem("BPM Match - tempo-first", "bpm")
            self._set_combo_to_value(planner_combo, str(config.get("planner_mode") or "smart"))
            config["planner_mode"] = planner_combo.currentData()
            planner_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("planner_mode", planner_combo.currentData())
            )
            self.inspector_layout.addWidget(planner_combo)

            self.inspector_layout.addWidget(QLabel("Leading Style(s)"))
            styles_field = QLineEdit(
                ", ".join(config.get("preferred_styles") or [])
                if isinstance(config.get("preferred_styles"), list)
                else str(config.get("preferred_styles") or "")
            )
            styles_field.setPlaceholderText("bass, uk bass, garage, breaks")

            def sync_styles(value: str) -> None:
                config["preferred_styles"] = [
                    part.strip()
                    for part in value.replace(";", ",").split(",")
                    if part.strip()
                ]

            styles_field.textChanged.connect(sync_styles)
            sync_styles(styles_field.text())
            self.inspector_layout.addWidget(styles_field)

            self.inspector_layout.addWidget(QLabel("BPM Min / Max"))
            bpm_row = QWidget()
            bpm_layout = QHBoxLayout(bpm_row)
            bpm_layout.setContentsMargins(0, 0, 0, 0)
            bpm_layout.setSpacing(8)
            bpm_min_field = QLineEdit("" if config.get("bpm_min") in (None, "") else str(config.get("bpm_min")))
            bpm_min_field.setPlaceholderText("no min")
            bpm_max_field = QLineEdit("" if config.get("bpm_max") in (None, "") else str(config.get("bpm_max")))
            bpm_max_field.setPlaceholderText("no max")

            def sync_bpm(key: str, value: str) -> None:
                text = value.strip()
                try:
                    parsed = float(text) if text else ""
                except ValueError:
                    parsed = ""
                config[key] = parsed

            bpm_min_field.textChanged.connect(lambda value: sync_bpm("bpm_min", value))
            bpm_max_field.textChanged.connect(lambda value: sync_bpm("bpm_max", value))
            sync_bpm("bpm_min", bpm_min_field.text())
            sync_bpm("bpm_max", bpm_max_field.text())
            bpm_layout.addWidget(bpm_min_field)
            bpm_layout.addWidget(bpm_max_field)
            self.inspector_layout.addWidget(bpm_row)

            context_profile = config.get("context_profile")
            if isinstance(context_profile, dict):
                context_bits = [
                    str(context_profile.get("context_id") or "custom context"),
                    str(context_profile.get("set_role") or ""),
                    str(context_profile.get("crowd_energy") or ""),
                ]
                self._add_label(
                    "Context brief: " + " · ".join(bit for bit in context_bits if bit),
                    role="hint",
                )

            self.inspector_layout.addWidget(QLabel("Target Track Count"))
            count_field = QLineEdit(
                "" if config.get("target_track_count") in (None, "") else str(config.get("target_track_count"))
            )
            count_field.setPlaceholderText("blank = all analyzed tracks")

            def sync_target_count(value: str) -> None:
                text = value.strip()
                config["target_track_count"] = int(text) if text.isdigit() else ""

            count_field.textChanged.connect(sync_target_count)
            sync_target_count(count_field.text())
            self.inspector_layout.addWidget(count_field)

            choices = self._upstream_track_choices(node_item)
            self.inspector_layout.addWidget(QLabel("Start Track"))
            start_combo = QComboBox()
            start_combo.addItem("Auto opener (lowest energy)", "")
            for value, label in choices:
                start_combo.addItem(label, value)
            self._set_combo_to_value(start_combo, str(config.get("start_track_id") or ""))
            config["start_track_id"] = start_combo.currentData()
            start_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("start_track_id", start_combo.currentData())
            )
            self.inspector_layout.addWidget(start_combo)

            if not choices:
                self._add_label(
                    "Connect Load Corpus or Analyze Tracks first. Build Set can also resolve repository-backed track IDs from the active corpus bridge.",
                    role="hint",
                )

        def _populate_export_rekordbox_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Export Rekordbox")
            self._add_label(
                "Write a rekordbox XML playlist from analyses and an optional SetPlan. Default export writes playlist order and hot cues only; Rekordbox remains responsible for native BPM/beatgrid.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            default_path = str(
                Path(self.runtime.config().paths.data_dir).expanduser() / "exports" / "dancelab_rekordbox.xml"
            )
            config.setdefault("output_path", default_path)
            config.setdefault("playlist_name", "DanceLab Set")
            config.setdefault("export_beatgrid", False)

            self.inspector_layout.addWidget(QLabel("Playlist Name"))
            playlist_field = QLineEdit(str(config.get("playlist_name", "")))
            playlist_field.textChanged.connect(
                lambda value: config.__setitem__("playlist_name", value.strip() or "DanceLab Set")
            )
            self.inspector_layout.addWidget(playlist_field)

            self.inspector_layout.addWidget(QLabel("Output XML Path"))
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            path_field = QLineEdit(str(config.get("output_path", "")))
            browse = QPushButton("Browse")

            def choose_output_path() -> None:
                start_dir = path_field.text().strip() or str(Path.home() / "Desktop")
                selected, _ = QFileDialog.getSaveFileName(
                    self,
                    "Export Rekordbox XML",
                    start_dir,
                    "XML Files (*.xml);;All Files (*)",
                )
                if selected:
                    path_field.setText(selected)

            path_field.textChanged.connect(lambda value: config.__setitem__("output_path", value.strip()))
            browse.clicked.connect(choose_output_path)
            layout.addWidget(path_field, 1)
            layout.addWidget(browse)
            self.inspector_layout.addWidget(row)

        def _populate_extract_stems_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Extract Stems")
            self._add_label(
                "Run stem-aware analysis from upstream track files. Auto uses Demucs when available and falls back honestly when it is not installed.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            config.setdefault("stem_method", "auto")
            config.setdefault("vocal_method", "")

            self.inspector_layout.addWidget(QLabel("Stem Method"))
            stem_combo = QComboBox()
            stem_combo.addItem("Auto (Demucs if available)", "auto")
            stem_combo.addItem("Demucs", "demucs")
            stem_combo.addItem("None / fallback only", "none")
            self._set_combo_to_value(stem_combo, str(config.get("stem_method") or "auto"))
            config["stem_method"] = stem_combo.currentData()
            stem_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("stem_method", stem_combo.currentData())
            )
            self.inspector_layout.addWidget(stem_combo)

            self.inspector_layout.addWidget(QLabel("Vocal Proxy Method"))
            vocal_combo = QComboBox()
            vocal_combo.addItem("Default engine config", "")
            vocal_combo.addItem("HPSS (fast proxy)", "hpss")
            vocal_combo.addItem("Auto", "auto")
            vocal_combo.addItem("Demucs", "demucs")
            self._set_combo_to_value(vocal_combo, str(config.get("vocal_method") or ""))
            config["vocal_method"] = vocal_combo.currentData()
            vocal_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("vocal_method", vocal_combo.currentData())
            )
            self.inspector_layout.addWidget(vocal_combo)

        def _populate_stem_export_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Stem Export")
            self._add_label(
                "Choose where per-track stem folders should be written. This keeps exports outside the engine repository unless you explicitly point it there.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            default_root = str(
                Path(self.runtime.config().paths.data_dir).expanduser() / "exports" / "stems"
            )
            config.setdefault("output_root", default_root)

            self.inspector_layout.addWidget(QLabel("Output Folder"))
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            path_field = QLineEdit(str(config.get("output_root", "")))
            browse = QPushButton("Browse")

            def choose_output_root() -> None:
                start_dir = path_field.text().strip() or str(Path.home() / "Desktop")
                selected = QFileDialog.getExistingDirectory(
                    self,
                    "Choose Stem Export Folder",
                    start_dir,
                )
                if selected:
                    path_field.setText(selected)

            path_field.textChanged.connect(lambda value: config.__setitem__("output_root", value.strip()))
            browse.clicked.connect(choose_output_root)
            layout.addWidget(path_field, 1)
            layout.addWidget(browse)
            self.inspector_layout.addWidget(row)

        def _populate_recommend_next_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Recommend Next")
            self._add_label(
                "Rank a candidate pool against one current track, with optional context and light set-history memory.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            config.setdefault("arc_mode", "build")
            config.setdefault("recent_history_text", "")

            current_connection = self._incoming_connection(node_item.model.instance_id, "current")
            current_choices = self._track_choices_for_input(
                node_item,
                "candidates",
                fallback_to_session=True,
                fallback_to_repository=True,
            )
            if current_connection is None:
                self.inspector_layout.addWidget(QLabel("Current Track"))
                if current_choices:
                    current_combo = QComboBox()
                    for value, label in current_choices:
                        current_combo.addItem(label, value)
                    self._set_combo_to_value(current_combo, str(config.get("current_track_id") or ""))
                    config["current_track_id"] = current_combo.currentData()
                    current_combo.currentIndexChanged.connect(
                        lambda _: config.__setitem__("current_track_id", current_combo.currentData())
                    )
                    self.inspector_layout.addWidget(current_combo)
                else:
                    current_field = QLineEdit(str(config.get("current_track_id", "")))
                    current_field.setPlaceholderText("track_id")
                    current_field.textChanged.connect(
                        lambda value: config.__setitem__("current_track_id", value.strip())
                    )
                    self.inspector_layout.addWidget(current_field)
            else:
                self._add_label(
                    "Current track is wired from an upstream node. Disconnect it if you want to choose the current track locally.",
                    role="hint",
                )

            self.inspector_layout.addWidget(QLabel("Arc Mode"))
            arc_combo = QComboBox()
            for arc in ("build", "flat", "peak", "closing"):
                arc_combo.addItem(arc.title(), arc)
            self._set_combo_to_value(arc_combo, str(config.get("arc_mode") or "build"))
            config["arc_mode"] = arc_combo.currentData()
            arc_combo.currentIndexChanged.connect(
                lambda _: config.__setitem__("arc_mode", arc_combo.currentData())
            )
            self.inspector_layout.addWidget(arc_combo)

            candidate_choices = self._track_choices_for_input(
                node_item,
                "candidates",
                fallback_to_session=True,
                fallback_to_repository=True,
            )
            if candidate_choices:
                self._add_label(
                    f"Candidate pool visible to the host: {len(candidate_choices)} track(s).",
                    role="hint",
                )
            else:
                self._add_label(
                    "Connect Load Corpus or Analyze Tracks to `candidates`, or make sure the repository path is available to the host.",
                    role="hint",
                )

            self.inspector_layout.addWidget(QLabel("Recent History"))
            history_field = QPlainTextEdit()
            history_field.setPlainText(str(config.get("recent_history_text", "")))
            history_field.setPlaceholderText("One track_id per line")
            history_field.setMinimumHeight(90)
            history_field.textChanged.connect(
                lambda: config.__setitem__("recent_history_text", history_field.toPlainText())
            )
            self.inspector_layout.addWidget(history_field)

        def _populate_select_track_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Select Track")
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            choices = self._upstream_track_choices(node_item)
            if not choices:
                self._add_label(
                    "Run upstream analysis first or connect a track source. Select Track needs visible candidates in session.",
                    role="hint",
                )
                return

            combo = QComboBox()
            for value, label in choices:
                combo.addItem(label, value)
            self._set_combo_to_value(combo, config.get("track_id"))
            config["track_id"] = combo.currentData()

            preview = QLabel()
            preview.setProperty("role", "hint")
            preview.setWordWrap(True)

            def sync_choice() -> None:
                track_id = combo.currentData()
                config["track_id"] = track_id
                analysis = self.runtime.analysis_index.get(str(track_id))
                if analysis is None:
                    preview.setText(f"Selected track id: {track_id}")
                    return
                preview.setText(
                    f"{analysis.track.title or track_id}\n{analysis.track.source_path or 'no source path recorded'}"
                )

            combo.currentIndexChanged.connect(sync_choice)
            self.inspector_layout.addWidget(combo)
            self.inspector_layout.addWidget(preview)
            sync_choice()

        def _populate_select_pair_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Select Pair")
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            choices = self._upstream_track_choices(node_item)
            if len(choices) < 2:
                self._add_label(
                    "Run upstream analysis first. The pair selector needs at least two analyzed tracks in session.",
                    role="hint",
                )
                return

            combo_a = QComboBox()
            combo_b = QComboBox()
            for value, label in choices:
                combo_a.addItem(label, value)
                combo_b.addItem(label, value)

            self._set_combo_to_value(combo_a, config.get("track_id_a"), 0)
            self._set_combo_to_value(combo_b, config.get("track_id_b"), 1)
            config["track_id_a"] = combo_a.currentData()
            config["track_id_b"] = combo_b.currentData()

            summary = QLabel("Track A = outgoing deck · Track B = incoming deck.")
            summary.setProperty("role", "hint")
            summary.setWordWrap(True)

            def sync_pair() -> None:
                track_id_a = combo_a.currentData()
                track_id_b = combo_b.currentData()
                if track_id_a == track_id_b and combo_b.count() > 1:
                    next_index = 1 if combo_b.currentIndex() == 0 else 0
                    combo_b.setCurrentIndex(next_index)
                    track_id_b = combo_b.currentData()
                config["track_id_a"] = track_id_a
                config["track_id_b"] = track_id_b

            combo_a.currentIndexChanged.connect(sync_pair)
            combo_b.currentIndexChanged.connect(sync_pair)

            self.inspector_layout.addWidget(QLabel("Track A"))
            self.inspector_layout.addWidget(combo_a)
            self.inspector_layout.addWidget(QLabel("Track B"))
            self.inspector_layout.addWidget(combo_b)
            self.inspector_layout.addWidget(summary)
            sync_pair()

        def _populate_select_context_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Select Context")
            try:
                profiles = self.runtime.context_profiles()
            except Exception as exc:
                self._add_label(f"Context profiles failed to load: {exc}", role="hint")
                return

            if not profiles:
                self._add_label("No context profiles are configured.", role="hint")
                return

            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            combo = QComboBox()
            for context_id in sorted(profiles):
                payload = profiles[context_id]
                label_bits = [
                    payload.get("venue_type"),
                    payload.get("set_role"),
                    payload.get("crowd_energy"),
                ]
                label = " · ".join([str(bit) for bit in label_bits if bit]) or context_id
                combo.addItem(f"{context_id} · {label}", context_id)

            self._set_combo_to_value(combo, config.get("context_id"))
            config["context_id"] = combo.currentData()

            preview = QLabel()
            preview.setProperty("role", "hint")
            preview.setWordWrap(True)

            def sync_context() -> None:
                context_id = str(combo.currentData())
                config["context_id"] = context_id
                payload = profiles.get(context_id, {})
                preview.setText(
                    "\n".join(
                        [
                            f"venue: {payload.get('venue_type', '--')}",
                            f"role: {payload.get('set_role', '--')}",
                            f"energy: {payload.get('crowd_energy', '--')}",
                            f"window: {payload.get('time_of_night', '--')}",
                        ]
                    )
                )

            combo.currentIndexChanged.connect(sync_context)
            self.inspector_layout.addWidget(combo)
            self.inspector_layout.addWidget(preview)
            sync_context()

        def _populate_output_preview(self, node_item: NodeBoxItem) -> None:
            output = self.runtime.outputs.get(node_item.model.instance_id)
            if output is None:
                self._add_label(
                    "No runtime output yet. Build the first flow, configure Upload Tracks, and run the graph.",
                    role="hint",
                )
                return

            self._add_section_title("Latest Output")
            if output.node_id == "telemetry_screen":
                snapshot = output.ports.get("snapshot", {})
                for key in ("pair_label", "score_text", "strategy", "profile", "decision_class"):
                    self._add_label(f"{key}: {snapshot.get(key, '--')}", mono=True)
                if snapshot.get("risks"):
                    self._add_section_title("Risks")
                    for value in snapshot["risks"]:
                        self._add_label(f"• {value}", mono=True)
                if snapshot.get("warnings"):
                    self._add_section_title("Warnings")
                    for value in snapshot["warnings"]:
                        self._add_label(f"• {value}", mono=True)
                return
            if output.node_id == "load_corpus":
                manifest = output.ports.get("manifest", {})
                validation = manifest.get("validation", {})
                self._add_label(f"tracks: {len(output.ports.get('track_ids', []))}", mono=True)
                self._add_label(
                    f"analyses loaded: {manifest.get('analysis_loaded', 0)} · annotation valid: {validation.get('valid', '--')}",
                    mono=True,
                )
                self._add_label(
                    f"processed: {manifest.get('processed_dir', '--')}",
                    mono=True,
                )
                return
            if output.node_id == "build_set":
                plan = output.ports.get("set_plan")
                if plan is not None:
                    self._add_label(
                        f"arc: {getattr(plan, 'arc', '--')} · tracks: {len(getattr(plan, 'track_order', []))}",
                        mono=True,
                    )
                    mean_score = getattr(plan, "mean_transition_score", None)
                    self._add_label(
                        "mean transition score: --" if mean_score is None else f"mean transition score: {mean_score:.3f}",
                        mono=True,
                    )
                    for track_id in list(getattr(plan, "track_order", []))[:8]:
                        self._add_label(track_id, mono=True)
                    return
            if output.node_id == "export_rekordbox":
                self._add_label(
                    f"playlist: {output.ports.get('playlist_name', '--')} · tracks: {output.ports.get('track_count', '--')}",
                    mono=True,
                )
                self._add_label(
                    f"written: {output.ports.get('artifact_path', '--')}",
                    mono=True,
                )
                preview = QPlainTextEdit()
                preview.setReadOnly(True)
                preview.setPlainText(str(output.ports.get("xml", ""))[:4000])
                self.inspector_layout.addWidget(preview)
                return
            if output.node_id == "extract_stems":
                track_ids = list(output.ports.get("track_ids", []))
                stem_bundles = output.ports.get("stems", {})
                stem_windows = list(output.ports.get("stem_windows", []))
                self._add_label(
                    f"tracks analyzed: {len(track_ids)} · stem bundles: {len(stem_bundles)} · stem windows: {len(stem_windows)}",
                    mono=True,
                )
                for track_id in track_ids[:8]:
                    self._add_label(str(track_id), mono=True)
                return
            if output.node_id == "stem_export":
                artifacts = output.ports.get("artifacts", {})
                items = list(artifacts.get("items", [])) if isinstance(artifacts, dict) else []
                self._add_label(
                    f"output: {artifacts.get('output_root', '--') if isinstance(artifacts, dict) else '--'}",
                    mono=True,
                )
                self._add_label(
                    f"tracks exported: {artifacts.get('track_count', len(items)) if isinstance(artifacts, dict) else len(items)}",
                    mono=True,
                )
                for item in items[:6]:
                    self._add_label(
                        f"{item.get('track_id', '--')} · stems: {', '.join(item.get('stems_written') or []) or 'manifest only'}",
                        mono=True,
                    )
                    self._add_label(str(item.get("artifact_path", "--")), mono=True)
                return
            if output.node_id == "recommend_next":
                recommendation = output.ports.get("recommendation")
                if recommendation is not None:
                    policy = getattr(getattr(recommendation, "recommendation_policy", None), "value", getattr(recommendation, "recommendation_policy", "--"))
                    self._add_label(
                        f"policy: {policy} · current: {getattr(recommendation, 'current_track_id', '--')}",
                        mono=True,
                    )
                    ranking = list(getattr(recommendation, "ranking", []))
                    for candidate in ranking[:5]:
                        candidate_policy = getattr(candidate.recommendation_policy, "value", candidate.recommendation_policy)
                        self._add_label(
                            f"#{candidate.rank} {candidate.track_id} · {candidate.score.value:.3f} · {candidate_policy}",
                            mono=True,
                        )
                    suppressed = list(getattr(recommendation, "suppressed_track_ids", []))
                    if suppressed:
                        self._add_label(f"suppressed: {', '.join(suppressed[:8])}", mono=True)
                    warnings = list(getattr(recommendation, "warnings", []))
                    if warnings:
                        self._add_section_title("Warnings")
                        for value in warnings[:6]:
                            self._add_label(f"• {value}", mono=True)
                    return

            preview = QPlainTextEdit()
            preview.setReadOnly(True)
            preview.setPlainText(self._pretty_json(output.ports))
            self.inspector_layout.addWidget(preview)

        def _populate_connections(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Connections")
            related = [
                (connection_id, model)
                for connection_id, model in self.connection_models.items()
                if model.from_instance_id == node_item.model.instance_id
                or model.to_instance_id == node_item.model.instance_id
            ]
            if not related:
                self._add_label(
                    "No live connections yet. Drag a cable from a socket to a highlighted compatible socket.",
                    role="hint",
                )
                return

            for connection_id, model in related:
                row = QWidget()
                layout = QHBoxLayout(row)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(8)
                source_item = self.node_items.get(model.from_instance_id)
                target_item = self.node_items.get(model.to_instance_id)
                label = QLabel(
                    f"{source_item.model.spec.label if source_item else model.from_instance_id}.{model.from_port_key} -> "
                    f"{target_item.model.spec.label if target_item else model.to_instance_id}.{model.to_port_key}"
                )
                label.setWordWrap(True)
                remove_button = QPushButton("Disconnect")
                remove_button.clicked.connect(lambda _checked=False, cid=connection_id: self._disconnect_and_refresh(cid))
                layout.addWidget(label, 1)
                layout.addWidget(remove_button)
                self.inspector_layout.addWidget(row)

        def _disconnect_and_refresh(self, connection_id: str) -> None:
            self.remove_connection(connection_id)
            self._sync_inspector()

        def _populate_port_section(
            self,
            title: str,
            ports: list[NodePortSpec],
            *,
            instance_id: str | None = None,
        ) -> None:
            if not ports:
                return
            self._add_section_title(title)
            for port in ports:
                text = f"{port.key} · {', '.join(port.port_types)}"
                # UI/UX audit §6: input ports state connected / missing so the
                # user can see at a glance why a node is not runnable yet.
                if instance_id is not None:
                    if self._incoming_connection(instance_id, port.key) is not None:
                        text = f"{text} · ✓ connected"
                    elif port.required:
                        text = f"{text} · ✗ required, not connected"
                    else:
                        text = f"{text} · optional"
                label = self._add_label(text, mono=True)
                label.setToolTip(port.description)

        def _populate_string_section(self, title: str, values: list[str]) -> None:
            if not values:
                return
            self._add_section_title(title)
            for value in values:
                self._add_label(value, mono=True)

        def _populate_quick_actions(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Quick Actions")
            preset_row = QWidget()
            preset_layout = QHBoxLayout(preset_row)
            preset_layout.setContentsMargins(0, 0, 0, 0)
            preset_layout.setSpacing(8)

            smart_button = QPushButton("Smart Playlist")
            smart_button.setProperty("role", "hero")
            smart_button.clicked.connect(self.build_smart_playlist_flow)
            preset_layout.addWidget(smart_button)

            pair_button = QPushButton("Pair Review")
            pair_button.setProperty("role", "preset")
            pair_button.clicked.connect(self.build_first_flow)
            preset_layout.addWidget(pair_button)
            self.inspector_layout.addWidget(preset_row)

            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            add_button = QPushButton("Add Near Center")
            add_button.clicked.connect(lambda: self.add_node(node_item.model.spec.node_id, 120.0, 120.0))
            layout.addWidget(add_button)

            run_button = QPushButton("Run Selected")
            run_button.setProperty("role", "accent")
            run_button.setEnabled(self.runtime.supports_node(node_item.model.spec.node_id))
            run_button.clicked.connect(lambda: self.run_flow(target_instance_id=node_item.model.instance_id))
            layout.addWidget(run_button)

            reset_button = QPushButton("Reset Node")
            reset_button.setToolTip("Clear this node's parameters and last output.")
            reset_button.clicked.connect(lambda: self.reset_node(node_item))
            layout.addWidget(reset_button)

            remove_button = QPushButton("Remove")
            remove_button.setEnabled(node_item.model.spec.deletable)
            remove_button.clicked.connect(self.remove_selected_node)
            layout.addWidget(remove_button)

            layout.addStretch(1)
            self.inspector_layout.addWidget(row)

        def _sync_inspector(self) -> None:
            self._clear_inspector()
            node_item = self.selected_node_item()
            if node_item is None:
                self._add_label("Inspector", role="title")
                self._add_label(
                    "Select a node on the canvas or double-click one from the library.",
                    role="hint",
                )
                self._set_toolbar_status(self.runtime.session_message or "engine ready")
                self.inspector_layout.addStretch(1)
                return

            spec = node_item.model.spec
            runtime_status = self.runtime.node_status.get(node_item.model.instance_id, "idle")

            title = QLabel(spec.label)
            title.setProperty("role", "title")
            self.inspector_layout.addWidget(title)
            self._add_label(spec.summary, role="hint")
            self._add_pills(
                [
                    spec.runtime_side,
                    spec.execution_mode,
                    runtime_status,
                ]
            )
            self._add_label(
                f"instance: {node_item.model.instance_id} · position: {node_item.model.x:.0f}, {node_item.model.y:.0f}",
                mono=True,
            )
            self._set_toolbar_status(f"{spec.label} · {runtime_status}")

            runtime_error = self.runtime.errors.get(node_item.model.instance_id)
            if runtime_error:
                self._add_label(f"Runtime error: {runtime_error}", role="hint")

            self._populate_quick_actions(node_item)

            if spec.node_id == "engine":
                self._populate_analysis_depth_form(node_item, title="Engine Analysis Settings")
            elif spec.node_id == "upload_tracks":
                self._populate_upload_form(node_item)
            elif spec.node_id == "analyze_tracks":
                self._populate_analysis_depth_form(node_item, title="Analyze Tracks Settings")
            elif spec.node_id == "load_corpus":
                self._populate_load_corpus_form(node_item)
            elif spec.node_id == "select_track":
                self._populate_select_track_form(node_item)
            elif spec.node_id == "select_pair":
                self._populate_select_pair_form(node_item)
            elif spec.node_id == "select_context":
                self._populate_select_context_form(node_item)
            elif spec.node_id == "extract_stems":
                self._populate_extract_stems_form(node_item)
            elif spec.node_id == "build_set":
                self._populate_build_set_form(node_item)
            elif spec.node_id == "export_rekordbox":
                self._populate_export_rekordbox_form(node_item)
            elif spec.node_id == "stem_export":
                self._populate_stem_export_form(node_item)
            elif spec.node_id == "recommend_next":
                self._populate_recommend_next_form(node_item)

            self._populate_output_preview(node_item)
            self._populate_connections(node_item)
            self._add_audit_section(spec)
            self._populate_port_section("Inputs", spec.inputs, instance_id=node_item.model.instance_id)
            self._populate_port_section("Outputs", spec.outputs)
            self._populate_string_section(
                "Recommended Next",
                [self.node_specs[node_id].label for node_id in spec.recommended_next if node_id in self.node_specs],
            )
            self._populate_string_section("Backed By", spec.backed_by)
            self._populate_string_section("API Routes", spec.api_routes)
            self._populate_string_section("Notes", spec.notes)
            self.inspector_scroll.verticalScrollBar().setValue(0)
            self.inspector_layout.addStretch(1)

        def reset_canvas(self) -> None:
            self.scene.clear()
            self.node_items.clear()
            self.connection_models.clear()
            self.connection_items.clear()
            self.pending_output_handle = None
            self.runtime.reset_runtime()
            self.instance_counter = 1
            self.view.reset_zoom()

            engine = self.add_node("engine", 560.0, 120.0)
            engine.setFlag(QGraphicsItem.ItemIsMovable, False)
            self.scene.clearSelection()
            engine.setSelected(True)
            self._refresh_port_states()
            self._sync_inspector()
            self._set_toolbar_status("engine ready")
            self._refresh_engine_status()
            self.statusBar().showMessage("Desktop host ready · engine pinned", 4000)

        def build_first_flow(self) -> None:
            self.reset_canvas()
            upload = self.add_node("upload_tracks", 120.0, 390.0)
            analyze = self.add_node("analyze_tracks", 380.0, 390.0)
            select_pair = self.add_node("select_pair", 640.0, 390.0)
            edge_decision = self.add_node("edge_decision", 900.0, 390.0)
            telemetry = self.add_node("telemetry_screen", 1160.0, 390.0)

            self.connect_ports(upload.output_handles["tracks"], analyze.input_handles["tracks"])
            self.connect_ports(analyze.output_handles["analysis"], select_pair.input_handles["source"])
            self.connect_ports(select_pair.output_handles["pair"], edge_decision.input_handles["pair"])
            self.connect_ports(edge_decision.output_handles["decision"], telemetry.input_handles["source"])

            self.scene.clearSelection()
            upload.setSelected(True)
            self._refresh_port_states()
            self._sync_inspector()
            self.statusBar().showMessage(
                "Flow built · upload -> analyze -> select pair -> edge decision -> telemetry",
                6000,
            )

        def build_smart_playlist_flow(self) -> None:
            folders = self._choose_audio_folders(title="Choose Music Folder(s)")
            if not folders:
                return
            try:
                files = self._discover_audio_files_from_folders(folders)
            except ValueError as exc:
                self.statusBar().showMessage(str(exc), 7000)
                return
            if not files:
                self.statusBar().showMessage("No supported audio files found in selected folder(s).", 7000)
                return
            files = self._confirm_audio_import(files)
            if not files:
                self.statusBar().showMessage("Smart Playlist cancelled or all suspicious files were skipped.", 7000)
                return

            if len(files) < MIN_PLAYLIST_TRACKS:
                self.statusBar().showMessage(
                    f"Smart Playlist needs at least {MIN_PLAYLIST_TRACKS} supported audio files.",
                    7000,
                )
                return
            target_count, ok = QInputDialog.getInt(
                self,
                "Smart Playlist Length",
                f"Number of tracks (2–{len(files)}):",
                min(10, len(files)),
                MIN_PLAYLIST_TRACKS,
                len(files),
            )
            if not ok:
                return

            folder_label = Path(folders[0]).name if len(folders) == 1 else "Selected Folders"
            default_name = f"DanceLab {folder_label} Set"
            playlist_name, ok = QInputDialog.getText(
                self,
                "Playlist Name",
                "Rekordbox playlist name",
                text=default_name,
            )
            if not ok:
                return
            playlist_name = playlist_name.strip() or default_name

            default_output = Path.home() / "Desktop" / f"{playlist_name.replace('/', '_')}.xml"
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Rekordbox XML",
                str(default_output),
                "XML Files (*.xml);;All Files (*)",
            )
            if not output_path:
                return

            self.build_pipeline_graph(
                files=files,
                target_count=target_count,
                arc="build",
                playlist_name=playlist_name,
                output_path=output_path,
            )
            self.statusBar().showMessage(
                f"Smart Playlist ready · {len(files)} files queued · {target_count} track export.",
                7000,
            )

        def build_pipeline_graph(
            self,
            *,
            files: list,
            target_count: int,
            arc: str = "build",
            planner_mode: str = "smart",
            analysis_depth: str = "normal",
            preferred_styles: list[str] | None = None,
            bpm_min: float | None = None,
            bpm_max: float | None = None,
            context_profile: Any | None = None,
            playlist_name: str = "DanceLab Set",
            output_path: str = "",
        ) -> None:
            """Materialize the standard pipeline as a wired graph:
            upload → engine → build_set → export, with configs filled in."""
            self.reset_canvas()
            engine = next(
                item for item in self.node_items.values() if item.model.spec.node_id == "engine"
            )
            upload = self.add_node("upload_tracks", 120.0, 390.0)
            build_set = self.add_node("build_set", 680.0, 390.0)
            export = self.add_node("export_rekordbox", 960.0, 390.0)

            self.connect_ports(upload.output_handles["tracks"], engine.input_handles["tracks_in"])
            self.connect_ports(engine.output_handles["analysis_out"], build_set.input_handles["analysis"])
            self.connect_ports(engine.output_handles["analysis_out"], export.input_handles["analysis"])
            self.connect_ports(build_set.output_handles["set_plan"], export.input_handles["set_plan"])

            self._set_upload_paths(upload, files, replace=True, refresh_selection=False)
            engine_config = self.runtime.ensure_node_config(engine.model.instance_id)
            engine_config["analysis_depth"] = analysis_depth
            build_config = self.runtime.ensure_node_config(build_set.model.instance_id)
            build_config["target_track_count"] = target_count
            build_config["arc"] = arc
            build_config["planner_mode"] = planner_mode
            build_config["preferred_styles"] = list(preferred_styles or [])
            build_config["bpm_min"] = bpm_min or ""
            build_config["bpm_max"] = bpm_max or ""
            if context_profile is not None:
                build_config["context_profile"] = (
                    context_profile.model_dump(mode="json")
                    if hasattr(context_profile, "model_dump")
                    else dict(context_profile)
                )
            export_config = self.runtime.ensure_node_config(export.model.instance_id)
            export_config["playlist_name"] = playlist_name
            if output_path:
                export_config["output_path"] = output_path

            self.scene.clearSelection()
            upload.setSelected(True)
            self._refresh_port_states()
            self._sync_inspector()
            self._refresh_engine_status()

        def import_simple_session(
            self,
            *,
            files: list,
            analyses: list[AnalysisResult],
            target_count: int,
            arc: str = "build",
            planner_mode: str = "smart",
            analysis_depth: str = "normal",
            preferred_styles: list[str] | None = None,
            bpm_min: float | None = None,
            bpm_max: float | None = None,
            context_profile: Any | None = None,
            playlist_name: str = "DanceLab Set",
            output_path: str = "",
        ) -> None:
            """Mirror the Simple Mode wizard pipeline as a wired graph.

            Analyses are seeded into the runtime cache (they were produced by
            the same engine on the same files), but node run-state stays idle —
            the graph honestly shows "not run HERE yet"; Run Analysis
            re-executes it in graph terms."""
            self.build_pipeline_graph(
                files=files,
                target_count=target_count,
                arc=arc,
                planner_mode=planner_mode,
                analysis_depth=analysis_depth,
                preferred_styles=preferred_styles,
                bpm_min=bpm_min,
                bpm_max=bpm_max,
                context_profile=context_profile,
                playlist_name=playlist_name,
                output_path=output_path,
            )
            for analysis in analyses:
                self.runtime.analysis_index[analysis.track.track_id] = analysis
            self.statusBar().showMessage(
                f"Imported from Simple Mode · {len(files)} tracks, "
                f"{len(analyses)} analyses cached · graph mirrors your wizard pipeline.",
                9000,
            )

        def fit_engine(self) -> None:
            engines = [item for item in self.node_items.values() if item.model.spec.node_id == "engine"]
            if engines:
                self.view.resetTransform()
                self.view.fitInView(engines[0], Qt.KeepAspectRatio)
                self.view.sync_zoom_from_transform()

        def zoom_to_selected(self) -> None:
            node_item = self.selected_node_item()
            if node_item is None:
                self.statusBar().showMessage("Select a node first.", 3000)
                return
            self.view.resetTransform()
            self.view.fitInView(
                node_item.sceneBoundingRect().adjusted(-120, -120, 120, 120), Qt.KeepAspectRatio
            )
            self.view.sync_zoom_from_transform()

        def remove_selected_node(self) -> None:
            node_item = self.selected_node_item()
            if node_item is None or not node_item.model.spec.deletable:
                return

            instance_id = node_item.model.instance_id
            for connection_id, model in list(self.connection_models.items()):
                if model.from_instance_id == instance_id or model.to_instance_id == instance_id:
                    self.remove_connection(connection_id)

            self.scene.removeItem(node_item)
            self.node_items.pop(instance_id, None)
            self.runtime.outputs.pop(instance_id, None)
            self.runtime.errors.pop(instance_id, None)
            self.runtime.node_status.pop(instance_id, None)
            self.runtime.node_configs.pop(instance_id, None)
            self._sync_inspector()
            self.statusBar().showMessage("Node removed.", 2500)
            self._mark_project_dirty()
            self._refresh_engine_status()

        # ------------------------------------------------------------ project model

        def _refresh_window_title(self) -> None:
            marker = " *" if self._project_dirty else ""
            self.setWindowTitle(f"DanceLab — {self.project_name}{marker}")

        def _mark_project_dirty(self) -> None:
            if self._suspend_dirty_tracking:
                return
            self._project_dirty = True
            self._refresh_window_title()

        def _mark_project_saved(self) -> None:
            self._project_dirty = False
            self._refresh_window_title()

        def _project_from_canvas(self) -> DanceLabProject:
            return DanceLabProject(
                name=self.project_name,
                nodes=[
                    ProjectNode(
                        instance_id=item.model.instance_id,
                        node_id=item.model.spec.node_id,
                        x=float(item.pos().x()),
                        y=float(item.pos().y()),
                    )
                    for item in self.node_items.values()
                ],
                connections=[
                    ProjectConnection(
                        from_instance_id=model.from_instance_id,
                        from_port_key=model.from_port_key,
                        to_instance_id=model.to_instance_id,
                        to_port_key=model.to_port_key,
                    )
                    for model in self.connection_models.values()
                ],
                node_configs={
                    instance_id: dict(config)
                    for instance_id, config in self.runtime.node_configs.items()
                    if instance_id in self.node_items and config
                },
            )

        def _apply_project(self, project: DanceLabProject) -> None:
            self._suspend_dirty_tracking = True
            try:
                self.scene.clear()
                self.node_items.clear()
                self.connection_models.clear()
                self.connection_items.clear()
                self.pending_output_handle = None
                self.runtime.reset_runtime()
                self.instance_counter = 1

                for node in project.nodes:
                    if node.node_id not in self.node_specs:
                        continue  # node vanished from the contract — skip, keep the rest
                    item = self.add_node(node.node_id, node.x, node.y, instance_id=node.instance_id)
                    if node.node_id == "engine":
                        item.setFlag(QGraphicsItem.ItemIsMovable, False)
                if not any(
                    item.model.spec.node_id == "engine" for item in self.node_items.values()
                ):
                    engine = self.add_node("engine", 560.0, 120.0)
                    engine.setFlag(QGraphicsItem.ItemIsMovable, False)

                for connection in project.connections:
                    source = self.node_items.get(connection.from_instance_id)
                    target = self.node_items.get(connection.to_instance_id)
                    if source is None or target is None:
                        continue
                    source_handle = source.output_handles.get(connection.from_port_key)
                    target_handle = target.input_handles.get(connection.to_port_key)
                    if source_handle is None or target_handle is None:
                        continue
                    self.connect_ports(source_handle, target_handle)

                for instance_id, config in project.node_configs.items():
                    if instance_id in self.node_items:
                        self.runtime.ensure_node_config(instance_id).update(config)

                # continue instance numbering past the loaded ids
                for instance_id in self.node_items:
                    tail = instance_id.rsplit("_", 1)[-1]
                    if tail.isdigit():
                        self.instance_counter = max(self.instance_counter, int(tail) + 1)

                self.scene.clearSelection()
                self._refresh_port_states()
                self._sync_inspector()
            finally:
                self._suspend_dirty_tracking = False
            self._refresh_engine_status()

        def new_project(self) -> None:
            self.project_path = None
            self.project_name = "Untitled Project"
            self.reset_canvas()
            self._mark_project_saved()
            self.statusBar().showMessage("New project.", 3000)

        def save_current_project(self) -> None:
            if self.project_path is None:
                self.save_project_as_dialog()
                return
            self._save_project_to_path(self.project_path)

        def save_project_as_dialog(self) -> None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Save DanceLab Project",
                str(Path.home() / f"{self.project_name}{PROJECT_FILE_SUFFIX}"),
                f"DanceLab Project (*{PROJECT_FILE_SUFFIX})",
            )
            if not selected:
                return
            self._save_project_to_path(Path(selected))

        def _save_project_to_path(self, path: Path) -> Path:
            self.project_name = Path(path).stem or self.project_name
            saved = save_project(self._project_from_canvas(), path)
            self.project_path = saved
            self._remember_recent_project(saved)
            self._mark_project_saved()
            self.statusBar().showMessage(f"Project saved · {saved}", 5000)
            return saved

        def open_project_dialog(self) -> None:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Open DanceLab Project",
                str(Path.home()),
                f"DanceLab Project (*{PROJECT_FILE_SUFFIX})",
            )
            if selected:
                self.load_project_from_path(Path(selected))

        def load_project_from_path(self, path: str | Path) -> None:
            try:
                project = load_project(path)
            except ProjectFileError as exc:
                self.statusBar().showMessage(str(exc), 8000)
                return
            self._apply_project(project)
            self.project_path = Path(path)
            self.project_name = project.name or Path(path).stem
            self._remember_recent_project(self.project_path)
            self._mark_project_saved()
            self.statusBar().showMessage(f"Project loaded · {self.project_name}", 5000)

        def _recent_projects(self) -> list[str]:
            settings = QSettings("DanceLab", "DesktopHost")
            stored = settings.value("recent_projects", [])
            if isinstance(stored, str):
                stored = [stored]
            return [str(path) for path in (stored or []) if str(path).strip()]

        def _remember_recent_project(self, path: Path) -> None:
            settings = QSettings("DanceLab", "DesktopHost")
            recents = [str(path)] + [p for p in self._recent_projects() if p != str(path)]
            settings.setValue("recent_projects", recents[:8])
            self._refresh_recent_projects_menu()

        def _refresh_recent_projects_menu(self) -> None:
            if not hasattr(self, "recent_projects_menu"):
                return
            self.recent_projects_menu.clear()
            recents = self._recent_projects()
            if not recents:
                empty = QAction("(no recent projects)", self)
                empty.setEnabled(False)
                self.recent_projects_menu.addAction(empty)
                return
            for recent in recents:
                action = QAction(recent, self)
                action.triggered.connect(
                    lambda checked=False, p=recent: self.load_project_from_path(p)
                )
                self.recent_projects_menu.addAction(action)

        # ------------------------------------------------------- engine status panel

        def _build_engine_status_bar(self) -> None:
            """UI/UX audit P1: persistent engine status — state + guided next step."""
            self.engine_state_label = QLabel("STATE · IDLE")
            self.engine_state_label.setProperty("role", "toolbar_status")
            self.next_action_label = QLabel("")
            self.statusBar().addPermanentWidget(self.next_action_label)
            self.statusBar().addPermanentWidget(self.engine_state_label)
            self._refresh_engine_status()

        def _engine_status(self) -> tuple[str, str]:
            """(state, next-action hint) for the guided status panel."""
            thread = getattr(self, "_flow_thread", None)
            if thread is not None and thread.isRunning():
                return "running", "Analysis in progress…"
            if self.runtime.errors:
                first_error = next(iter(self.runtime.errors.values()))
                return "error", f"Fix and re-run · {first_error}"
            if self.runtime.outputs:
                return "complete", "Review results in the Parameter Panel or export."
            uploads = self._upload_nodes()
            if len(self.node_items) <= 1:
                return "idle", "Click SMART PLAYLIST or build a flow to start."
            if uploads and not any(self._configured_upload_paths(item) for item in uploads):
                return "waiting_for_input", "Add audio files to Upload Tracks first."
            if self._default_run_target() is None:
                return "waiting_for_input", "Add a runnable node (e.g. Analyze Tracks)."
            return "ready", "Click ▶ RUN ANALYSIS."

        def _refresh_engine_status(self) -> None:
            if not hasattr(self, "engine_state_label"):
                return
            state, next_action = self._engine_status()
            self.engine_state = state
            self.engine_state_label.setText(f"STATE · {state.replace('_', ' ').upper()}")
            self.next_action_label.setText(f"Next: {next_action}")
            if hasattr(self, "run_button"):
                self.run_button.setEnabled(state in ("ready", "complete", "error"))

        # --------------------------------------------------------------- engine ops

        def run_selected_node(self) -> None:
            node_item = self.selected_node_item()
            if node_item is None:
                self.statusBar().showMessage("Select a node first.", 4000)
                return
            self.run_flow(target_instance_id=node_item.model.instance_id)

        def reset_node(self, node_item: NodeBoxItem) -> None:
            """UI/UX audit §6: per-node reset — clear config + runtime output."""
            instance_id = node_item.model.instance_id
            self.runtime.node_configs.pop(instance_id, None)
            self.runtime.outputs.pop(instance_id, None)
            self.runtime.errors.pop(instance_id, None)
            self.runtime.node_status.pop(instance_id, None)
            node_item.update()
            self._mark_project_dirty()
            self._sync_inspector()
            self._refresh_engine_status()
            self.statusBar().showMessage(f"{node_item.model.spec.label} reset to defaults.", 4000)

        def reset_engine(self) -> None:
            self.runtime.reset_runtime()
            for item in self.node_items.values():
                item.update()
            self._sync_inspector()
            self._refresh_engine_status()
            self.statusBar().showMessage("Engine reset · outputs cleared, graph kept.", 4000)

        def _default_run_target(self) -> str | None:
            # Toolbar "Run" executes the whole flow: target the terminal sink so
            # runtime.run pulls every upstream dependency. (Running a single node
            # is a separate action — the per-node Run button passes an explicit
            # target_instance_id, so the current selection must NOT hijack the
            # full-flow run here.)
            for sink_node_id in ("stem_export", "export_rekordbox", "telemetry_screen", "recommend_next", "build_set"):
                for candidate in self.node_items.values():
                    if candidate.model.spec.node_id == sink_node_id:
                        return candidate.model.instance_id
            for candidate in self.node_items.values():
                if candidate.model.spec.node_id == "telemetry_screen":
                    return candidate.model.instance_id
            for candidate in self.node_items.values():
                if self.runtime.supports_node(candidate.model.spec.node_id):
                    return candidate.model.instance_id
            return None

        def run_flow(
            self, *, target_instance_id: str | None = None, wait: bool = False
        ) -> None:
            """Execute the graph on a worker thread (NEW-H2: never block the UI).

            wait=True blocks until completion and drains the result signal —
            for tests and scripted use only."""
            if getattr(self, "_flow_thread", None) is not None and self._flow_thread.isRunning():
                self.statusBar().showMessage("A flow is already running…", 4000)
                return
            target = target_instance_id or self._default_run_target()
            if target is None:
                self.statusBar().showMessage("Nothing runnable is on the canvas yet.", 4000)
                return

            self.statusBar().showMessage("Running desktop flow…", 0)
            thread = _FlowThread(
                self.runtime,
                self._serialize_node_states(),
                self._serialize_connections(),
                target,
            )
            thread.completed.connect(self._on_flow_finished)
            self._flow_thread = thread
            thread.start()
            self._refresh_engine_status()
            if wait:
                thread.wait()
                QApplication.processEvents()

        def _on_flow_finished(self, error: object) -> None:
            finished_thread = self.sender()
            if finished_thread is self._flow_thread:
                self._flow_thread = None
            if isinstance(finished_thread, QThread):
                if finished_thread.isRunning() and QThread.currentThread() is not finished_thread:
                    finished_thread.wait(1000)
                finished_thread.deleteLater()
            if error:
                self._set_toolbar_status(f"run failed · {error}")
                self.statusBar().showMessage(f"Run failed · {error}", 7000)
            else:
                self._set_toolbar_status(self.runtime.session_message)
                self.statusBar().showMessage(self.runtime.session_message, 7000)
            for item in self.node_items.values():
                item.update()
            self._sync_inspector()
            self._refresh_engine_status()


def launch_desktop_host(
    registry: NodeHostRegistry | None = None,
    *,
    config_path: str | Path = "configs/default.yaml",
    mode: str = "simple",
) -> int:
    """Launch DanceLab. UI/UX audit §18: Simple Mode is the default start —
    the raw Signal Graph is the advanced mode ("graph")."""
    _require_pyside6()
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("DanceLab Host")
    app.setApplicationDisplayName("DanceLab Host")
    app.setOrganizationName("DanceLab")
    if mode == "graph":
        registry = registry or get_node_host_registry()
        window = NodeHostWindow(registry, config_path=config_path)
    else:
        from dancelab.host.simple_mode import SimpleModeWindow

        window = SimpleModeWindow(config_path=config_path)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


def main() -> int:
    mode = "graph" if "--graph" in sys.argv[1:] else "simple"
    return launch_desktop_host(mode=mode)

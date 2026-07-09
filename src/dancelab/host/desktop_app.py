"""Qt desktop host shell for DanceLab.

This is the intended direction for the long-lived node-based host:
Python desktop software backed by the engine registry, not an HTML-first app.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dancelab.contracts.node_host import NodeHostRegistry, NodePortSpec, NodeSpec, get_node_host_registry
from dancelab.host.runtime import (
    DesktopHostRuntime,
    RuntimeConnection,
    RuntimeNodeState,
)

try:  # optional desktop dependency
    from PySide6 import QtCore as _QtCore

    _pyside_root = Path(_QtCore.__file__).resolve().parent
    _qt_plugin_root = _pyside_root / "Qt" / "plugins"
    _qt_platform_plugin_root = _qt_plugin_root / "platforms"
    if _qt_plugin_root.exists():
        os.environ.setdefault("QT_PLUGIN_PATH", str(_qt_plugin_root))
    if _qt_platform_plugin_root.exists():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(_qt_platform_plugin_root))

    from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt
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
        QLabel,
        QLineEdit,
        QMainWindow,
        QPlainTextEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
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
    "build_set",
    "export_rekordbox",
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
        "Stem-aware engine capability exists, but the desktop host still lacks the public adapter and configuration surface.",
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
        "Stem export helper exists, but the desktop host lacks both the bridge executor and export-path controls.",
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

        def zoom_by_steps(self, steps: float) -> None:
            if steps == 0:
                return
            factor = self.ZOOM_STEP_IN ** steps if steps > 0 else self.ZOOM_STEP_OUT ** abs(steps)
            next_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self._zoom_value * factor))
            applied_factor = next_zoom / self._zoom_value
            if abs(applied_factor - 1.0) < 1e-6:
                return
            self.scale(applied_factor, applied_factor)
            self._zoom_value = next_zoom

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
            super().__init__(-6.0, -6.0, 12.0, 12.0, node_item)
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
                width = 2.4
            self.setBrush(fill)
            self.setPen(QPen(border, width))

        def mousePressEvent(self, event) -> None:
            self.node_item.setSelected(True)
            if self.direction == "output":
                self.node_item.host_window.start_connection_drag(self, event.scenePos())
                event.accept()
                return
            self.node_item.host_window.handle_port_click(self)
            event.accept()

        def mouseMoveEvent(self, event) -> None:
            if self.direction == "output":
                self.node_item.host_window.update_connection_drag(event.scenePos())
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event) -> None:
            if self.direction == "output":
                self.node_item.host_window.finish_connection_drag(event.scenePos())
                event.accept()
                return
            super().mouseReleaseEvent(event)


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

        def update_path(self, scene_pos: QPointF) -> None:
            self.current_scene_pos = scene_pos
            start = self.source_handle.center_in_scene()
            end = scene_pos
            dx = max(80.0, abs(end.x() - start.x()) * 0.55)
            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x() + dx, start.y()),
                QPointF(end.x() - dx, end.y()),
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
                    font-size: 18px;
                    font-weight: 600;
                }
                QLabel[role="section"] {
                    color: #989ba1;
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
                """
            )

            self._build_toolbar()
            self._build_canvas()
            self._build_library()
            self._build_inspector()

            self.scene.selectionChanged.connect(self._sync_inspector)
            self.reset_canvas()

        def _build_toolbar(self) -> None:
            toolbar = self.addToolBar("Signal Graph")
            toolbar.setMovable(False)

            brand = QLabel("SIGNAL GRAPH")
            brand.setProperty("role", "brand")
            toolbar.addWidget(brand)

            patch = QLabel("desktop host")
            patch.setProperty("role", "patch")
            toolbar.addWidget(patch)
            toolbar.addSeparator()

            build_action = QAction("Build First Flow", self)
            build_action.triggered.connect(self.build_first_flow)
            toolbar.addAction(build_action)

            smart_mix_action = QAction("Build Smart Mix", self)
            smart_mix_action.triggered.connect(self.build_smart_mix_flow)
            toolbar.addAction(smart_mix_action)

            import_action = QAction("Import Tracks...", self)
            import_action.triggered.connect(self.open_upload_file_picker)
            toolbar.addAction(import_action)

            reset_action = QAction("Reset Canvas", self)
            reset_action.triggered.connect(self.reset_canvas)
            toolbar.addAction(reset_action)

            fit_action = QAction("Fit Engine", self)
            fit_action.triggered.connect(self.fit_engine)
            toolbar.addAction(fit_action)

            zoom_in_action = QAction("Zoom In", self)
            zoom_in_action.triggered.connect(lambda: self.view.zoom_by_steps(1.0))
            toolbar.addAction(zoom_in_action)

            zoom_out_action = QAction("Zoom Out", self)
            zoom_out_action.triggered.connect(lambda: self.view.zoom_by_steps(-1.0))
            toolbar.addAction(zoom_out_action)

            reset_zoom_action = QAction("Reset Zoom", self)
            reset_zoom_action.triggered.connect(lambda: self.view.reset_zoom())
            toolbar.addAction(reset_zoom_action)

            run_action = QAction("Run Flow", self)
            run_action.triggered.connect(self.run_flow)
            toolbar.addAction(run_action)

            remove_action = QAction("Remove Selected", self)
            remove_action.triggered.connect(self.remove_selected_node)
            toolbar.addAction(remove_action)

            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            toolbar.addWidget(spacer)

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
            self.inspector_scroll = QScrollArea()
            self.inspector_scroll.setWidgetResizable(True)
            self.inspector_container = QWidget()
            self.inspector_layout = QVBoxLayout(self.inspector_container)
            self.inspector_layout.setContentsMargins(12, 12, 12, 12)
            self.inspector_layout.setSpacing(10)
            self.inspector_scroll.setWidget(self.inspector_container)
            dock.setWidget(self.inspector_scroll)
            self.addDockWidget(Qt.RightDockWidgetArea, dock)

        def _populate_library(self) -> None:
            self.library_tree.clear()
            ordered = ["system", "input", "engine_ops", "sensors", "screens", "utility", "output"]
            for category in ordered:
                nodes = [node for node in self.registry.nodes if node.category == category]
                if not nodes:
                    continue
                summary = self._category_readiness_summary(nodes)
                parent = QTreeWidgetItem(
                    [f"{CATEGORY_MARKERS.get(category, '■')}  {category.replace('_', ' ').upper()}  {len(nodes)}"]
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
                    child.setToolTip(
                        0,
                        (
                            f"{audit['readiness_label']} · runtime "
                            f"{audit['runtime_status_label'].lower()} · "
                            f"form {audit['form_status_label'].lower()}"
                        ),
                    )
                    child.setForeground(0, QBrush(QColor(audit["display_color"])))
                    parent.addChild(child)
                parent.setExpanded(True)

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
        ) -> NodeBoxItem:
            spec = self.node_specs[node_id]
            if x is None or y is None:
                x, y = self._suggest_node_position(spec)
            model = NodeInstanceModel(
                instance_id=self._next_instance_id(node_id),
                spec=spec,
                x=x,
                y=y,
            )
            item = NodeBoxItem(self, model)
            self.scene.addItem(item)
            self.node_items[model.instance_id] = item
            self._select_node(item)
            self.statusBar().showMessage(f"Added {spec.label}.", 2500)
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
            if refresh_selection:
                self._select_node(node_item)
            return merged

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
            if target is None:
                target = self._resolve_upload_target()
            merged = self._set_upload_paths(target, selected)
            self.statusBar().showMessage(
                f"Queued {len(merged)} audio file(s) in Upload Tracks.",
                4000,
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

        def _refresh_port_states(self) -> None:
            for node_item in self.node_items.values():
                for handle in node_item.input_handles.values():
                    compatible = False
                    if self.pending_output_handle is not None:
                        compatible = self._ports_compatible(
                            self.pending_output_handle.port_spec,
                            handle.port_spec,
                        )
                    handle.set_state(active=False, compatible=compatible)
                for handle in node_item.output_handles.values():
                    handle.set_state(active=handle is self.pending_output_handle, compatible=False)

        def _serialize_node_states(self) -> list[RuntimeNodeState]:
            return [
                RuntimeNodeState(instance_id=item.model.instance_id, node_id=item.model.spec.node_id)
                for item in self.node_items.values()
            ]

        def _serialize_connections(self) -> list[RuntimeConnection]:
            return list(self.connection_models.values())

        def _clear_inspector(self) -> None:
            while self.inspector_layout.count():
                item = self.inspector_layout.takeAt(0)
                widget = item.widget()
                child_layout = item.layout()
                if widget is not None:
                    widget.deleteLater()
                elif child_layout is not None:
                    while child_layout.count():
                        inner = child_layout.takeAt(0)
                        if inner.widget() is not None:
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
            if not runtime_ready:
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
            runtime_status_label = "Executable" if runtime_ready else "Not Executable"
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
            self._add_section_title("Desktop Audit")
            self._add_pills(
                [
                    audit["readiness_label"],
                    audit["runtime_status_label"],
                    audit["form_status_label"],
                ]
            )
            if not audit["gaps"]:
                self._add_label("No known desktop-host delivery gaps for this node right now.", role="hint")
                return
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
            clear_button = QPushButton("Clear List")
            controls_layout.addWidget(choose_button)
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
            clear_button.clicked.connect(clear_paths)
            self.inspector_layout.addWidget(field)
            self.inspector_layout.addWidget(summary)
            sync_text()

        def _populate_load_corpus_form(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Load Corpus")
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
            self._add_section_title("Build Set")
            self._add_label(
                "Build a SetPlan from analyzed tracks or repository-backed track IDs. The desktop host uses the engine weights and current corpus bridge.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            config.setdefault("arc", "build")

            self.inspector_layout.addWidget(QLabel("Arc Mode"))
            arc_combo = QComboBox()
            for arc in ("build", "flat", "peak"):
                arc_combo.addItem(arc.title(), arc)
            self._set_combo_to_value(arc_combo, str(config.get("arc") or "build"))
            config["arc"] = arc_combo.currentData()
            arc_combo.currentIndexChanged.connect(lambda _: config.__setitem__("arc", arc_combo.currentData()))
            self.inspector_layout.addWidget(arc_combo)

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
                "Write a rekordbox XML playlist from analyses and an optional SetPlan. This is a host-side export path, not an engine-side persistence feature.",
                role="hint",
            )
            config = self.runtime.ensure_node_config(node_item.model.instance_id)
            default_path = str(
                Path(self.runtime.config().paths.data_dir).expanduser() / "exports" / "dancelab_rekordbox.xml"
            )
            config.setdefault("output_path", default_path)
            config.setdefault("playlist_name", "DanceLab Set")

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
                    "No live connections yet. Click an output handle, then a compatible input handle.",
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

        def _populate_port_section(self, title: str, ports: list[NodePortSpec]) -> None:
            self._add_section_title(title)
            if not ports:
                self._add_label("No ports.", role="hint")
                return
            for port in ports:
                self._add_label(
                    f"{port.key} · {', '.join(port.port_types)}",
                    mono=True,
                )
                self._add_label(port.description)

        def _populate_string_section(self, title: str, values: list[str]) -> None:
            self._add_section_title(title)
            if not values:
                self._add_label("No entries.", role="hint")
                return
            for value in values:
                self._add_label(value, mono=True)

        def _populate_quick_actions(self, node_item: NodeBoxItem) -> None:
            self._add_section_title("Quick Actions")
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
            self._add_label(spec.summary)
            self._add_pills(
                [
                    spec.status,
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

            self._add_audit_section(spec)

            if spec.node_id == "upload_tracks":
                self._populate_upload_form(node_item)
            elif spec.node_id == "load_corpus":
                self._populate_load_corpus_form(node_item)
            elif spec.node_id == "select_track":
                self._populate_select_track_form(node_item)
            elif spec.node_id == "select_pair":
                self._populate_select_pair_form(node_item)
            elif spec.node_id == "select_context":
                self._populate_select_context_form(node_item)
            elif spec.node_id == "build_set":
                self._populate_build_set_form(node_item)
            elif spec.node_id == "export_rekordbox":
                self._populate_export_rekordbox_form(node_item)
            elif spec.node_id == "recommend_next":
                self._populate_recommend_next_form(node_item)

            self._populate_output_preview(node_item)
            self._populate_connections(node_item)
            self._populate_port_section("Inputs", spec.inputs)
            self._populate_port_section("Outputs", spec.outputs)
            self._populate_string_section(
                "Recommended Next",
                [self.node_specs[node_id].label for node_id in spec.recommended_next if node_id in self.node_specs],
            )
            self._populate_string_section("Backed By", spec.backed_by)
            self._populate_string_section("API Routes", spec.api_routes)
            self._populate_string_section("Notes", spec.notes)
            self._populate_quick_actions(node_item)
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

        def fit_engine(self) -> None:
            engines = [item for item in self.node_items.values() if item.model.spec.node_id == "engine"]
            if engines:
                self.view.resetTransform()
                self.view.fitInView(engines[0], Qt.KeepAspectRatio)
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

        def _default_run_target(self) -> str | None:
            node_item = self.selected_node_item()
            if node_item and self.runtime.supports_node(node_item.model.spec.node_id):
                return node_item.model.instance_id
            for candidate in self.node_items.values():
                if candidate.model.spec.node_id == "telemetry_screen":
                    return candidate.model.instance_id
            for candidate in self.node_items.values():
                if self.runtime.supports_node(candidate.model.spec.node_id):
                    return candidate.model.instance_id
            return None

        def run_flow(self, *, target_instance_id: str | None = None) -> None:
            target = target_instance_id or self._default_run_target()
            if target is None:
                self.statusBar().showMessage("Nothing runnable is on the canvas yet.", 4000)
                return

            self.statusBar().showMessage("Running desktop flow...", 1000)
            QApplication.processEvents()

            try:
                self.runtime.run(
                    self._serialize_node_states(),
                    self._serialize_connections(),
                    target,
                )
            except Exception as exc:
                self._set_toolbar_status(f"run failed · {exc}")
                self.statusBar().showMessage(f"Run failed · {exc}", 7000)
            else:
                self._set_toolbar_status(self.runtime.session_message)
                self.statusBar().showMessage(self.runtime.session_message, 7000)
            finally:
                for item in self.node_items.values():
                    item.update()
                self._sync_inspector()


def launch_desktop_host(
    registry: NodeHostRegistry | None = None,
    *,
    config_path: str | Path = "configs/default.yaml",
) -> int:
    _require_pyside6()
    registry = registry or get_node_host_registry()
    app = QApplication.instance() or QApplication([])
    window = NodeHostWindow(registry, config_path=config_path)
    window.show()
    return app.exec()


def main() -> int:
    return launch_desktop_host()

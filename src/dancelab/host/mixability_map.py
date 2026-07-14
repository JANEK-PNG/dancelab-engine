"""Optional BPM x energy exploration for Simple Mode.

The canvas is deliberately presentation-only. Candidate ordering comes from
``recommend_next`` and the detailed pair verdicts come from ``EdgeDecision``.
No compatibility formula is duplicated in the desktop host.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from dancelab.core.config import DescriptorWeights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    DecisionClass,
    EdgeDecision,
    NextTrackRecommendation,
)
from dancelab.decision.edge_decision import build_edge_decision
from dancelab.decision.next_track import recommend_next
from dancelab.decision.set_builder import track_energy


_CAMELOT_COLORS = (
    "#4CC9F0",
    "#4895EF",
    "#4361EE",
    "#5E60CE",
    "#7B2CBF",
    "#B14AED",
    "#E454B5",
    "#F15B64",
    "#F28E3B",
    "#E9C46A",
    "#73C66A",
    "#2EC4A6",
)

_DECISION_COLORS = {
    DecisionClass.strong_candidate: QColor("#3DDC97"),
    DecisionClass.review_required: QColor("#F2B84B"),
    DecisionClass.non_standard_strategy_required: QColor("#5CC8FF"),
    DecisionClass.reject_standard_blend: QColor("#FF5C68"),
}


@dataclass(frozen=True)
class MixMapPoint:
    """One plotted track backed by an engine ``AnalysisResult``."""

    track_id: str
    title: str
    artist: str
    bpm: float
    key: str
    energy: float
    energy_percent: int


def camelot_color(key: str | None) -> QColor:
    """Return a stable display color for a Camelot key, or neutral gray."""
    normalized = (key or "").strip().upper()
    if len(normalized) < 2 or normalized[-1] not in {"A", "B"}:
        return QColor("#7E8997")
    try:
        number = int(normalized[:-1])
    except ValueError:
        return QColor("#7E8997")
    if not 1 <= number <= 12:
        return QColor("#7E8997")
    color = QColor(_CAMELOT_COLORS[number - 1])
    if normalized.endswith("B"):
        color = color.lighter(118)
    return color


def build_mix_map_points(analyses: Iterable[AnalysisResult]) -> list[MixMapPoint]:
    """Normalize engine energy values for display and omit unknown BPM rows."""
    items = [analysis for analysis in analyses if analysis.track.bpm_estimate is not None]
    energies = [track_energy(analysis) for analysis in items]
    e_min = min(energies, default=0.0)
    e_max = max(energies, default=0.0)
    e_range = e_max - e_min

    points: list[MixMapPoint] = []
    for analysis, energy in zip(items, energies, strict=True):
        track = analysis.track
        fallback = Path(track.source_path).stem if track.source_path else track.track_id
        percent = 50 if e_range <= 1e-9 else round(100.0 * (energy - e_min) / e_range)
        points.append(
            MixMapPoint(
                track_id=track.track_id,
                title=(track.title or fallback or track.track_id).strip(),
                artist=(track.artist or "Unknown artist").strip(),
                bpm=float(track.bpm_estimate),
                key=(track.key_estimate or "Unknown").strip(),
                energy=float(energy),
                energy_percent=int(percent),
            )
        )
    return sorted(points, key=lambda point: (point.bpm, point.energy, point.track_id))


class MixMapCanvas(QWidget):
    """Native Qt scatter plot with engine-result edges."""

    track_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(350)
        self.setMouseTracking(True)
        self.setToolTip("Click a track to make it the current track.")
        self._points: list[MixMapPoint] = []
        self._selected_id: str | None = None
        self._hovered_id: str | None = None
        self._candidate_edges: dict[str, EdgeDecision] = {}
        self._candidate_scores: dict[str, float] = {}

    def set_points(self, points: Iterable[MixMapPoint]) -> None:
        self._points = list(points)
        valid_ids = {point.track_id for point in self._points}
        if self._selected_id not in valid_ids:
            self._selected_id = self._points[0].track_id if self._points else None
        self._candidate_edges.clear()
        self._candidate_scores.clear()
        self.update()

    def set_selected_track(self, track_id: str | None) -> None:
        self._selected_id = track_id
        self._candidate_edges.clear()
        self._candidate_scores.clear()
        self.update()

    def set_candidates(
        self,
        edges: dict[str, EdgeDecision],
        scores: dict[str, float],
    ) -> None:
        self._candidate_edges = dict(edges)
        self._candidate_scores = dict(scores)
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(58.0, 20.0, max(1.0, self.width() - 82.0), max(1.0, self.height() - 64.0))

    def _bpm_bounds(self) -> tuple[float, float]:
        values = [point.bpm for point in self._points]
        if not values:
            return 90.0, 180.0
        low, high = min(values), max(values)
        if abs(high - low) < 1.0:
            return low - 2.0, high + 2.0
        padding = max(1.0, (high - low) * 0.04)
        return low - padding, high + padding

    def _positions(self) -> dict[str, QPointF]:
        rect = self._plot_rect()
        low, high = self._bpm_bounds()
        span = max(high - low, 1e-9)
        return {
            point.track_id: QPointF(
                rect.left() + ((point.bpm - low) / span) * rect.width(),
                rect.bottom() - (point.energy_percent / 100.0) * rect.height(),
            )
            for point in self._points
        }

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#080C12"))
        rect = self._plot_rect()

        if not self._points:
            painter.setPen(QColor("#8B96A5"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Run Initial Check to populate the map.")
            return

        grid_pen = QPen(QColor("#1D2733"), 1.0)
        painter.setPen(grid_pen)
        low, high = self._bpm_bounds()
        for index in range(6):
            fraction = index / 5.0
            x = rect.left() + fraction * rect.width()
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.setPen(QColor("#778392"))
            painter.drawText(
                QRectF(x - 28.0, rect.bottom() + 8.0, 56.0, 18.0),
                Qt.AlignHCenter | Qt.AlignTop,
                f"{low + fraction * (high - low):.0f}",
            )
            painter.setPen(grid_pen)
        for index in range(5):
            fraction = index / 4.0
            y = rect.bottom() - fraction * rect.height()
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QColor("#778392"))
            painter.drawText(
                QRectF(4.0, y - 9.0, 46.0, 18.0),
                Qt.AlignRight | Qt.AlignVCenter,
                f"{round(fraction * 100):d}%",
            )
            painter.setPen(grid_pen)

        painter.setPen(QColor("#9AA6B5"))
        painter.drawText(
            QRectF(rect.left(), self.height() - 22.0, rect.width(), 18.0),
            Qt.AlignCenter,
            "BPM",
        )
        painter.save()
        painter.translate(12.0, rect.center().y())
        painter.rotate(-90.0)
        painter.drawText(QRectF(-80.0, -9.0, 160.0, 18.0), Qt.AlignCenter, "Relative energy")
        painter.restore()

        positions = self._positions()
        selected_position = positions.get(self._selected_id or "")
        if selected_position is not None:
            for candidate_id, edge in self._candidate_edges.items():
                target = positions.get(candidate_id)
                if target is None:
                    continue
                color = _DECISION_COLORS.get(edge.decision_class, QColor("#778392"))
                color.setAlpha(95)
                width = 1.0 + 2.5 * self._candidate_scores.get(candidate_id, 0.0)
                painter.setPen(QPen(color, width))
                painter.drawLine(selected_position, target)

        for point in self._points:
            position = positions[point.track_id]
            is_selected = point.track_id == self._selected_id
            is_candidate = point.track_id in self._candidate_edges
            radius = 8.0 if is_selected else (6.5 if is_candidate else 4.5)
            if is_selected:
                painter.setPen(QPen(QColor("#F5F7FA"), 2.5))
            elif is_candidate:
                edge = self._candidate_edges[point.track_id]
                painter.setPen(QPen(_DECISION_COLORS.get(edge.decision_class, QColor("#778392")), 2.0))
            else:
                painter.setPen(QPen(QColor("#111820"), 1.0))
            painter.setBrush(camelot_color(point.key))
            painter.drawEllipse(position, radius, radius)

        selected = next(
            (point for point in self._points if point.track_id == self._selected_id),
            None,
        )
        if selected is not None and selected_position is not None:
            painter.setPen(QColor("#F5F7FA"))
            label_rect = QRectF(
                min(selected_position.x() + 12.0, rect.right() - 190.0),
                max(rect.top(), selected_position.y() - 26.0),
                190.0,
                22.0,
            )
            painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, selected.title[:28])

    def _nearest_point(self, position: QPointF, radius: float = 12.0) -> MixMapPoint | None:
        positions = self._positions()
        nearest: tuple[float, MixMapPoint] | None = None
        for point in self._points:
            distance = (positions[point.track_id] - position).manhattanLength()
            if distance <= radius and (nearest is None or distance < nearest[0]):
                nearest = (distance, point)
        return nearest[1] if nearest else None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        point = self._nearest_point(event.position())
        hovered = point.track_id if point is not None else None
        if hovered != self._hovered_id:
            self._hovered_id = hovered
            if point is not None:
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{point.title}\n{point.artist} · {point.bpm:.2f} BPM · "
                    f"{point.key} · energy {point.energy_percent}%",
                    self,
                )
            else:
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            point = self._nearest_point(event.position())
            if point is not None:
                self._selected_id = point.track_id
                self._candidate_edges.clear()
                self._candidate_scores.clear()
                self.track_selected.emit(point.track_id)
                self.update()
                return
        super().mousePressEvent(event)


class _MixabilityRankingThread(QThread):
    completed = Signal(str, object, object)
    failed = Signal(str, str)

    def __init__(
        self,
        current: AnalysisResult,
        candidates: list[AnalysisResult],
        weights: DescriptorWeights,
        context: ContextProfile | None,
        arc_mode: str,
        *,
        limit: int = 6,
    ) -> None:
        super().__init__()
        self._current = current
        self._candidates = candidates
        self._weights = weights
        self._context = context
        self._arc_mode = arc_mode
        self._limit = limit

    def run(self) -> None:
        track_id = self._current.track.track_id
        try:
            recommendation = recommend_next(
                self._current,
                self._candidates,
                self._context,
                weights=self._weights,
                top_k=3,
                arc_mode=self._arc_mode,
            )
            if self.isInterruptionRequested():
                return
            by_id = {analysis.track.track_id: analysis for analysis in self._candidates}
            edges: dict[str, EdgeDecision] = {}
            for ranked in recommendation.ranking[: self._limit]:
                if self.isInterruptionRequested():
                    return
                candidate = by_id.get(ranked.track_id)
                if candidate is None:
                    continue
                edges[ranked.track_id] = build_edge_decision(
                    self._current,
                    candidate,
                    self._weights,
                    context=self._context,
                    top_k=3,
                )
        except Exception as exc:  # surfaced in the host, never swallowed
            self.failed.emit(track_id, str(exc))
        else:
            self.completed.emit(track_id, recommendation, edges)


class MixabilityMapWidget(QWidget):
    """Optional Simple Mode view over real recommendation and edge outputs."""

    find_requested = Signal(str)
    must_have_requested = Signal(str)
    ranking_completed = Signal(bool, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analyses: list[AnalysisResult] = []
        self._recommendation: NextTrackRecommendation | None = None
        self._edges: dict[str, EdgeDecision] = {}
        self._worker: _MixabilityRankingThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Current track"))
        self.track_combo = QComboBox()
        self.track_combo.setEditable(True)
        self.track_combo.setInsertPolicy(QComboBox.NoInsert)
        self.track_combo.setMinimumWidth(280)
        self.track_combo.currentIndexChanged.connect(self._on_combo_changed)
        controls.addWidget(self.track_combo, stretch=1)
        self.find_button = QPushButton("Find Mix Ideas")
        self.find_button.setProperty("role", "hero")
        self.find_button.clicked.connect(self._request_find)
        controls.addWidget(self.find_button)
        layout.addLayout(controls)

        self.status_label = QLabel(
            "Choose a current track, then run the engine. Dots show BPM and relative library energy; color shows Camelot key."
        )
        self.status_label.setProperty("role", "field_hint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.canvas = MixMapCanvas()
        self.canvas.track_selected.connect(self.select_track)
        layout.addWidget(self.canvas)

        legend = QLabel(
            "Lines: green strong candidate · cyan non-standard strategy · amber review · red reject standard blend"
        )
        legend.setProperty("role", "field_hint")
        legend.setWordWrap(True)
        layout.addWidget(legend)

        self.candidate_table = QTableWidget(0, 6)
        self.candidate_table.setObjectName("mixabilityCandidateTable")
        self.candidate_table.setHorizontalHeaderLabels(
            ["#", "Suggested next track", "Next", "Pair", "Decision", "Strategy"]
        )
        self.candidate_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.candidate_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.candidate_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.candidate_table.setShowGrid(False)
        self.candidate_table.setMinimumHeight(220)
        self.candidate_table.setMaximumHeight(260)
        self.candidate_table.verticalHeader().setVisible(False)
        self.candidate_table.verticalHeader().setDefaultSectionSize(34)
        header = self.candidate_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in range(2, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.candidate_table.itemSelectionChanged.connect(self._show_selected_candidate)
        self.candidate_table.cellDoubleClicked.connect(self._explore_candidate_row)
        layout.addWidget(self.candidate_table)

        detail_row = QHBoxLayout()
        self.detail_label = QLabel("No candidate selected.")
        self.detail_label.setProperty("role", "field_hint")
        self.detail_label.setWordWrap(True)
        detail_row.addWidget(self.detail_label, stretch=1)
        self.must_have_button = QPushButton("Make Must Have")
        self.must_have_button.setProperty("role", "secondary")
        self.must_have_button.setEnabled(False)
        self.must_have_button.clicked.connect(self._request_must_have)
        detail_row.addWidget(self.must_have_button)
        layout.addLayout(detail_row)

    def set_analyses(self, analyses: Iterable[AnalysisResult]) -> None:
        previous = self.current_track_id()
        self._analyses = list(analyses)
        points = build_mix_map_points(self._analyses)
        self.canvas.set_points(points)
        self.track_combo.blockSignals(True)
        self.track_combo.clear()
        for point in sorted(points, key=lambda item: (item.title.casefold(), item.artist.casefold())):
            self.track_combo.addItem(
                f"{point.title} — {point.artist} · {point.bpm:.2f} BPM · {point.key}",
                point.track_id,
            )
        index = self.track_combo.findData(previous)
        self.track_combo.setCurrentIndex(index if index >= 0 else (0 if points else -1))
        self.track_combo.blockSignals(False)
        self.canvas.set_selected_track(self.current_track_id())
        self._clear_results()
        self.find_button.setEnabled(len(points) >= 2)
        if points:
            omitted = len(self._analyses) - len(points)
            suffix = f" · {omitted} without BPM omitted" if omitted else ""
            self.status_label.setText(
                f"{len(points)} tracks mapped{suffix}. Choose a current track and click Find Mix Ideas."
            )
        else:
            self.status_label.setText("Run Initial Check to populate the map.")

    def current_track_id(self) -> str | None:
        value = self.track_combo.currentData()
        return str(value) if value else None

    def select_track(self, track_id: str) -> None:
        index = self.track_combo.findData(track_id)
        if index >= 0:
            self.track_combo.setCurrentIndex(index)

    def _on_combo_changed(self, _index: int) -> None:
        self.canvas.set_selected_track(self.current_track_id())
        self._clear_results()

    def _request_find(self) -> None:
        track_id = self.current_track_id()
        if track_id is not None:
            self.find_requested.emit(track_id)

    def begin_ranking(
        self,
        track_id: str,
        *,
        weights: DescriptorWeights,
        context: ContextProfile | None,
        arc_mode: str,
        excluded_track_ids: set[str] | None = None,
    ) -> bool:
        if self._worker is not None and self._worker.isRunning():
            return False
        by_id = {analysis.track.track_id: analysis for analysis in self._analyses}
        current = by_id.get(track_id)
        if current is None:
            self.status_label.setText("The selected track is no longer in the analyzed library.")
            return False
        excluded = set(excluded_track_ids or ())
        candidates = [
            analysis
            for analysis in self._analyses
            if analysis.track.track_id != track_id and analysis.track.track_id not in excluded
        ]
        if not candidates:
            self.status_label.setText("No eligible candidate tracks remain.")
            return False

        self._clear_results()
        self.find_button.setEnabled(False)
        self.track_combo.setEnabled(False)
        self.status_label.setText(
            f"Engine running for {len(candidates)} candidates… ranking first, then validating the top six pairs."
        )
        worker = _MixabilityRankingThread(
            current,
            candidates,
            weights,
            context,
            arc_mode,
        )
        worker.completed.connect(self._ranking_finished)
        worker.failed.connect(self._ranking_failed)
        worker.finished.connect(self._worker_finished)
        self._worker = worker
        worker.start()
        return True

    def _ranking_finished(
        self,
        track_id: str,
        recommendation: NextTrackRecommendation,
        edges: dict[str, EdgeDecision],
    ) -> None:
        if track_id != self.current_track_id():
            return
        self._recommendation = recommendation
        self._edges = dict(edges)
        ranking = recommendation.ranking[:6]
        scores = {candidate.track_id: candidate.score.value for candidate in ranking}
        self.canvas.set_candidates(self._edges, scores)

        by_id = {analysis.track.track_id: analysis for analysis in self._analyses}
        self.candidate_table.setRowCount(len(ranking))
        for row, candidate in enumerate(ranking):
            analysis = by_id.get(candidate.track_id)
            edge = self._edges.get(candidate.track_id)
            title = (
                analysis.track.title
                if analysis is not None and analysis.track.title
                else candidate.track_id
            )
            values = [
                str(candidate.rank),
                title,
                f"{candidate.score.value:.2f}",
                f"{edge.core_dj_compatibility_score.value:.2f}" if edge else "—",
                _humanize(edge.decision_class.value) if edge else "Not evaluated",
                _humanize(edge.recommended_transition_strategy.value) if edge else "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, candidate.track_id)
                if column in {0, 2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                self.candidate_table.setItem(row, column, item)
        if ranking:
            self.candidate_table.selectRow(0)
            self.status_label.setText(
                f"Engine ranked {len(recommendation.ranking)} eligible candidates; "
                f"the top {len(ranking)} have full EdgeDecision checks. Double-click a row to explore from it."
            )
        else:
            self.status_label.setText(
                "No candidate passed the engine confidence policy. Review the brief or analyze more tracks."
            )
        self.ranking_completed.emit(
            True,
            f"Mixability ready · {len(ranking)} detailed candidate(s)",
        )

    def _ranking_failed(self, track_id: str, message: str) -> None:
        if track_id == self.current_track_id():
            self.status_label.setText(f"Mixability analysis failed: {message}")
            self.ranking_completed.emit(False, f"Mixability failed · {message}")

    def _worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        self.track_combo.setEnabled(True)
        self.find_button.setEnabled(len(self._analyses) >= 2)
        if worker is not None:
            worker.deleteLater()

    def _clear_results(self) -> None:
        self._recommendation = None
        self._edges.clear()
        self.candidate_table.setRowCount(0)
        self.detail_label.setText("No candidate selected.")
        self.must_have_button.setEnabled(False)
        self.canvas.set_candidates({}, {})

    def _selected_candidate_id(self) -> str | None:
        row = self.candidate_table.currentRow()
        item = self.candidate_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.UserRole) if item is not None else None
        return str(value) if value else None

    def _show_selected_candidate(self) -> None:
        track_id = self._selected_candidate_id()
        if track_id is None or self._recommendation is None:
            self.detail_label.setText("No candidate selected.")
            self.must_have_button.setEnabled(False)
            return
        ranked = next(
            (candidate for candidate in self._recommendation.ranking if candidate.track_id == track_id),
            None,
        )
        edge = self._edges.get(track_id)
        if ranked is None:
            return
        detail = (
            f"Next-track score {ranked.score.value:.2f} · "
            f"confidence {ranked.score.confidence:.2f}."
        )
        if edge is not None:
            tempo = _humanize(edge.tempo_relation)
            harmony = _humanize(edge.harmonic_relation or "unknown")
            detail += (
                f"\nPair {edge.core_dj_compatibility_score.value:.2f} · "
                f"tempo {tempo} · harmony {harmony}. "
                f"Try {_humanize(edge.recommended_transition_strategy.value)} "
                f"with {_humanize(edge.blend_profile_auto.value)}."
            )
            if edge.risks:
                detail += " Review: " + "; ".join(edge.risks[:2])
            elif edge.warnings:
                detail += " Review: " + "; ".join(edge.warnings[:1])
            else:
                detail += " No major pair risk was raised by the current candidate model."
        self.detail_label.setText(detail)
        self.detail_label.setToolTip(detail)
        self.must_have_button.setEnabled(True)

    def _request_must_have(self) -> None:
        track_id = self._selected_candidate_id()
        if track_id is not None:
            self.must_have_requested.emit(track_id)

    def _explore_candidate_row(self, row: int, _column: int) -> None:
        item = self.candidate_table.item(row, 0)
        track_id = item.data(Qt.UserRole) if item is not None else None
        if track_id:
            self.select_track(str(track_id))

    def shutdown(self, wait_msec: int = 5000) -> None:
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        worker.requestInterruption()
        worker.wait(wait_msec)


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()

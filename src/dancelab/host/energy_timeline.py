"""Set-level energy timeline for the Simple Mode host.

Energy and transition quality stay sourced from engine outputs. The widget
normalizes energy only for display and never reorders or re-scores a set.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolTip, QVBoxLayout, QWidget

from dancelab.core.models import AnalysisResult, SetPlan
from dancelab.decision.set_builder import track_energy


@dataclass(frozen=True)
class SetEnergyPoint:
    position: int
    track_id: str
    title: str
    artist: str
    bpm: float | None
    key: str
    energy: float
    energy_percent: int
    transition_score_to_next: float | None
    transition_warning_count: int
    pinned: bool
    locked: bool


def build_set_energy_points(
    plan: SetPlan | None,
    analyses: Iterable[AnalysisResult],
) -> list[SetEnergyPoint]:
    """Build display points while preserving the exact ``SetPlan`` order."""
    if plan is None:
        return []
    items = list(analyses)
    by_id = {analysis.track.track_id: analysis for analysis in items}
    library_energies = [track_energy(analysis) for analysis in items]
    e_min = min(library_energies, default=0.0)
    e_max = max(library_energies, default=0.0)
    e_range = e_max - e_min
    transition_by_pair = {
        (transition.from_track_id, transition.to_track_id): transition
        for transition in plan.transitions
    }

    points: list[SetEnergyPoint] = []
    for order_index, track_id in enumerate(plan.track_order):
        analysis = by_id.get(track_id)
        if analysis is None:
            continue
        track = analysis.track
        energy = track_energy(analysis)
        percent = 50 if e_range <= 1e-9 else round(100.0 * (energy - e_min) / e_range)
        successor = plan.track_order[order_index + 1] if order_index + 1 < len(plan.track_order) else None
        transition = transition_by_pair.get((track_id, successor)) if successor else None
        fallback = Path(track.source_path).stem if track.source_path else track_id
        position = order_index + 1
        points.append(
            SetEnergyPoint(
                position=position,
                track_id=track_id,
                title=(track.title or fallback or track_id).strip(),
                artist=(track.artist or "Unknown artist").strip(),
                bpm=track.bpm_estimate,
                key=(track.key_estimate or "Unknown").strip(),
                energy=float(energy),
                energy_percent=int(percent),
                transition_score_to_next=(
                    float(transition.transition_score) if transition is not None else None
                ),
                transition_warning_count=(
                    len(transition.warnings) if transition is not None else 0
                ),
                pinned=track_id in plan.pinned_track_ids,
                locked=plan.locked_positions.get(position) == track_id,
            )
        )
    return points


def energy_color(percent: int) -> QColor:
    """Cool cyan to warm amber; energy is magnitude, never success/danger."""
    fraction = max(0.0, min(1.0, percent / 100.0))
    low = QColor("#5CC8FF")
    middle = QColor("#45D39B")
    high = QColor("#FFB454")
    if fraction <= 0.5:
        return _mix_color(low, middle, fraction * 2.0)
    return _mix_color(middle, high, (fraction - 0.5) * 2.0)


def _mix_color(start: QColor, end: QColor, fraction: float) -> QColor:
    return QColor(
        round(start.red() + (end.red() - start.red()) * fraction),
        round(start.green() + (end.green() - start.green()) * fraction),
        round(start.blue() + (end.blue() - start.blue()) * fraction),
    )


def _transition_color(score: float) -> QColor:
    if score >= 0.72:
        return QColor("#3DDC97")
    if score >= 0.52:
        return QColor("#F2B84B")
    return QColor("#FF5C68")


class EnergyTimelineCanvas(QWidget):
    track_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(230)
        self.setMouseTracking(True)
        self._points: list[SetEnergyPoint] = []
        self._selected_id: str | None = None

    def set_points(self, points: Iterable[SetEnergyPoint]) -> None:
        self._points = list(points)
        ids = {point.track_id for point in self._points}
        if self._selected_id not in ids:
            self._selected_id = self._points[0].track_id if self._points else None
        self.update()

    def select_track(self, track_id: str | None) -> None:
        if track_id is not None and any(point.track_id == track_id for point in self._points):
            self._selected_id = track_id
            self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(42.0, 34.0, max(1.0, self.width() - 60.0), max(1.0, self.height() - 90.0))

    def _positions(self) -> dict[str, QPointF]:
        rect = self._plot_rect()
        count = len(self._points)
        return {
            point.track_id: QPointF(
                rect.center().x()
                if count <= 1
                else rect.left() + index * rect.width() / (count - 1),
                rect.bottom() - point.energy_percent * rect.height() / 100.0,
            )
            for index, point in enumerate(self._points)
        }

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#080C12"))
        rect = self._plot_rect()
        if not self._points:
            painter.setPen(QColor("#7E8997"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Generate a set to see its energy timeline.")
            return

        for level in range(5):
            fraction = level / 4.0
            y = rect.bottom() - fraction * rect.height()
            painter.setPen(QPen(QColor("#1D2733"), 1.0))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QColor("#778392"))
            painter.drawText(
                QRectF(0.0, y - 9.0, 34.0, 18.0),
                Qt.AlignRight | Qt.AlignVCenter,
                f"{round(fraction * 100)}%",
            )

        positions = self._positions()
        path = self._curve_path(positions)
        fill_path = QPainterPath(path)
        fill_path.lineTo(rect.right(), rect.bottom())
        fill_path.lineTo(rect.left(), rect.bottom())
        fill_path.closeSubpath()
        fill = QLinearGradient(0.0, rect.top(), 0.0, rect.bottom())
        fill.setColorAt(0.0, QColor(92, 200, 255, 72))
        fill.setColorAt(1.0, QColor(92, 200, 255, 4))
        painter.fillPath(fill_path, fill)
        painter.setPen(QPen(QColor("#86D9FF"), 2.2))
        painter.drawPath(path)

        label_stride = max(1, (len(self._points) + 9) // 10)
        for index, point in enumerate(self._points):
            position = positions[point.track_id]
            selected = point.track_id == self._selected_id
            painter.setPen(
                QPen(QColor("#F5F7FA"), 2.5)
                if selected
                else QPen(QColor("#111820"), 1.0)
            )
            painter.setBrush(energy_color(point.energy_percent))
            radius = 7.5 if selected else (4.0 if len(self._points) > 24 else 5.5)
            painter.drawEllipse(position, radius, radius)
            if point.locked or point.pinned:
                painter.setPen(QColor("#F5F7FA"))
                painter.drawText(
                    QRectF(position.x() - 12.0, position.y() - 25.0, 24.0, 16.0),
                    Qt.AlignCenter,
                    "L" if point.locked else "P",
                )

            if index % label_stride == 0 or index == len(self._points) - 1:
                painter.setPen(QColor("#778392"))
                painter.drawText(
                    QRectF(position.x() - 18.0, rect.bottom() + 34.0, 36.0, 18.0),
                    Qt.AlignHCenter | Qt.AlignTop,
                    str(point.position),
                )

            if point.transition_score_to_next is not None and index + 1 < len(self._points):
                next_position = positions[self._points[index + 1].track_id]
                bar_rect = QRectF(
                    position.x() + 4.0,
                    rect.bottom() + 14.0,
                    max(2.0, next_position.x() - position.x() - 8.0),
                    5.0,
                )
                color = _transition_color(point.transition_score_to_next)
                if point.transition_warning_count:
                    color = color.darker(125)
                painter.fillRect(bar_rect, color)

        peak = max(self._points, key=lambda point: point.energy_percent)
        peak_pos = positions[peak.track_id]
        painter.setPen(QColor("#FFCF8B"))
        painter.drawText(
            QRectF(
                max(rect.left(), min(rect.right() - 80.0, peak_pos.x() - 40.0)),
                max(4.0, peak_pos.y() - 23.0),
                80.0,
                17.0,
            ),
            Qt.AlignCenter,
            f"PEAK #{peak.position}",
        )
        painter.setPen(QColor("#9AA6B5"))
        painter.drawText(
            QRectF(rect.left(), self.height() - 18.0, rect.width(), 16.0),
            Qt.AlignCenter,
            "Set position · bars show transition quality",
        )

    def _curve_path(self, positions: dict[str, QPointF]) -> QPainterPath:
        first = positions[self._points[0].track_id]
        path = QPainterPath(first)
        # A set is discrete: each point is one track. Cubic interpolation made
        # ordinary rises and drops look like a continuous sinusoidal signal.
        for point in self._points[1:]:
            path.lineTo(positions[point.track_id])
        return path

    def _nearest(self, position: QPointF, radius: float = 13.0) -> SetEnergyPoint | None:
        positions = self._positions()
        nearest: tuple[float, SetEnergyPoint] | None = None
        for point in self._points:
            distance = (positions[point.track_id] - position).manhattanLength()
            if distance <= radius and (nearest is None or distance < nearest[0]):
                nearest = (distance, point)
        return nearest[1] if nearest else None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        point = self._nearest(event.position())
        if point is None:
            QToolTip.hideText()
        else:
            bpm = f"{point.bpm:.2f} BPM" if point.bpm is not None else "BPM unknown"
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"#{point.position} {point.title}\n{point.artist} · {bpm} · {point.key} · "
                f"energy {point.energy_percent}%",
                self,
            )
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            point = self._nearest(event.position())
            if point is not None:
                self._selected_id = point.track_id
                self.track_selected.emit(point.track_id)
                self.update()
                return
        super().mousePressEvent(event)


class SetEnergyTimelineWidget(QWidget):
    track_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: list[SetEnergyPoint] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Energy timeline")
        title.setProperty("role", "section_title")
        header.addWidget(title)
        self.summary_label = QLabel("Generate a set to see its shape.")
        self.summary_label.setProperty("role", "field_hint")
        header.addWidget(self.summary_label)
        header.addStretch(1)
        layout.addLayout(header)

        self.canvas = EnergyTimelineCanvas()
        self.canvas.track_selected.connect(self._select_from_canvas)
        layout.addWidget(self.canvas)
        self.detail_label = QLabel("Click a point to select the same track in the sequence below.")
        self.detail_label.setProperty("role", "field_hint")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

    def set_plan(self, plan: SetPlan | None, analyses: Iterable[AnalysisResult]) -> None:
        self._points = build_set_energy_points(plan, analyses)
        self.canvas.set_points(self._points)
        self.setVisible(bool(self._points))
        if not self._points:
            self.summary_label.setText("Generate a set to see its shape.")
            return
        peak = max(self._points, key=lambda point: point.energy_percent)
        bpms = [point.bpm for point in self._points if point.bpm is not None]
        bpm_text = f" · {min(bpms):.0f}–{max(bpms):.0f} BPM" if bpms else ""
        mean = plan.mean_transition_score if plan is not None else None
        score_text = f" · mean transition {mean:.2f}" if mean is not None else ""
        arc = plan.arc if plan is not None else "unknown"
        self.summary_label.setText(
            f"{len(self._points)} tracks · {arc} arc · peak #{peak.position}{bpm_text}{score_text}"
        )
        self.select_track(self._points[0].track_id)

    def select_position(self, row: int) -> None:
        if 0 <= row < len(self._points):
            self.select_track(self._points[row].track_id)

    def select_track(self, track_id: str) -> None:
        point = next((item for item in self._points if item.track_id == track_id), None)
        if point is None:
            return
        self.canvas.select_track(track_id)
        transition = (
            f" · next transition {point.transition_score_to_next:.2f}"
            if point.transition_score_to_next is not None
            else " · final track"
        )
        flags = []
        if point.pinned:
            flags.append("Must Have")
        if point.locked:
            flags.append("locked here")
        flag_text = f" · {', '.join(flags)}" if flags else ""
        bpm = f"{point.bpm:.2f} BPM" if point.bpm is not None else "BPM unknown"
        self.detail_label.setText(
            f"#{point.position} {point.title} — {point.artist} · {bpm} · {point.key} · "
            f"relative library energy {point.energy_percent}%{transition}{flag_text}"
        )

    def _select_from_canvas(self, track_id: str) -> None:
        self.select_track(track_id)
        self.track_selected.emit(track_id)

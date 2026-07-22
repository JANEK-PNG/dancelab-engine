"""Analyzed-library presentation for Simple Mode.

The widget only reads ``AnalysisResult`` objects produced by the engine. It
never estimates BPM, key, energy, or compatibility itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dancelab.core.models import AnalysisResult
from dancelab.decision.set_builder import track_energy


@dataclass(frozen=True)
class LibraryTrackRow:
    """Display-ready values backed by one immutable engine result."""

    analysis: AnalysisResult
    title: str
    artist: str
    bpm: float | None
    key: str
    style: str
    energy: float
    energy_percent: int
    grid_reliable: bool
    grid_quality: float | None

    @property
    def track_id(self) -> str:
        return self.analysis.track.track_id


def build_library_rows(analyses: Iterable[AnalysisResult]) -> list[LibraryTrackRow]:
    """Convert engine outputs into rows and normalize energy within the library."""
    items = list(analyses)
    energies = [track_energy(analysis) for analysis in items]
    e_min = min(energies, default=0.0)
    e_max = max(energies, default=0.0)
    e_range = e_max - e_min

    rows: list[LibraryTrackRow] = []
    for analysis, energy in zip(items, energies, strict=True):
        track = analysis.track
        source = Path(track.source_path).stem if track.source_path else track.track_id
        title = (track.title or source or track.track_id).strip()
        artist = (track.artist or "Unknown artist").strip()
        grid = analysis.beatgrid
        if e_range <= 1e-9:
            energy_percent = 50
        else:
            energy_percent = round(100.0 * (energy - e_min) / e_range)
        rows.append(
            LibraryTrackRow(
                analysis=analysis,
                title=title,
                artist=artist,
                bpm=track.bpm_estimate,
                key=(track.key_estimate or "Unknown").strip(),
                style=(track.style_label or "Unclassified").strip(),
                energy=energy,
                energy_percent=int(energy_percent),
                grid_reliable=bool(grid is not None and grid.reliable),
                grid_quality=grid.quality_score if grid is not None else None,
            )
        )
    return rows


def filter_library_rows(
    rows: Iterable[LibraryTrackRow],
    *,
    query: str = "",
    style: str | None = None,
    key: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    reliable_only: bool = False,
    sort_by: str = "title",
) -> list[LibraryTrackRow]:
    """Filter and order rows without mutating engine outputs."""
    needle = query.strip().casefold()
    selected: list[LibraryTrackRow] = []
    for row in rows:
        track = row.analysis.track
        haystack = " ".join(
            (
                row.title,
                row.artist,
                row.style,
                row.key,
                track.source_path or "",
            )
        ).casefold()
        if needle and needle not in haystack:
            continue
        if style and row.style.casefold() != style.casefold():
            continue
        if key and row.key.casefold() != key.casefold():
            continue
        if bpm_min is not None and (row.bpm is None or row.bpm < bpm_min):
            continue
        if bpm_max is not None and (row.bpm is None or row.bpm > bpm_max):
            continue
        if reliable_only and not row.grid_reliable:
            continue
        selected.append(row)

    def title_key(row: LibraryTrackRow) -> tuple[str, str, str]:
        return row.title.casefold(), row.artist.casefold(), row.track_id

    if sort_by == "bpm_asc":
        return sorted(selected, key=lambda row: (row.bpm is None, row.bpm or 0.0, *title_key(row)))
    if sort_by == "bpm_desc":
        return sorted(
            selected,
            key=lambda row: (row.bpm is None, -(row.bpm or 0.0), *title_key(row)),
        )
    if sort_by == "energy_desc":
        return sorted(selected, key=lambda row: (-row.energy, *title_key(row)))
    if sort_by == "energy_asc":
        return sorted(selected, key=lambda row: (row.energy, *title_key(row)))
    if sort_by == "key":
        return sorted(selected, key=lambda row: (row.key.casefold(), *title_key(row)))
    return sorted(selected, key=title_key)


class AnalyzedLibraryWidget(QWidget):
    """Searchable library over the current session's analyzed tracks."""

    must_have_requested = Signal(str)
    not_tonight_requested = Signal(str)
    track_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[LibraryTrackRow] = []
        self._visible_rows: list[LibraryTrackRow] = []
        self._must_have_ids: set[str] = set()
        self._not_tonight_ids: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        title = QLabel("Analyzed Library")
        title.setProperty("role", "section_title")
        heading.addWidget(title)
        self.summary_label = QLabel("No analyzed tracks yet.")
        self.summary_label.setProperty("role", "field_hint")
        heading.addWidget(self.summary_label)
        heading.addStretch(1)
        layout.addLayout(heading)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search title, artist, style, key, or file path")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.refresh)
        layout.addWidget(self.search_edit)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.style_combo = QComboBox()
        self.style_combo.addItem("All styles", None)
        self.style_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.style_combo)

        self.key_combo = QComboBox()
        self.key_combo.addItem("All keys", None)
        self.key_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.key_combo)

        self.bpm_min_spin = self._bpm_spin("No min")
        self.bpm_min_spin.valueChanged.connect(self.refresh)
        filters.addWidget(self.bpm_min_spin)
        filters.addWidget(QLabel("to"))
        self.bpm_max_spin = self._bpm_spin("No max")
        self.bpm_max_spin.valueChanged.connect(self.refresh)
        filters.addWidget(self.bpm_max_spin)

        self.reliable_check = QCheckBox("Reliable grid only")
        self.reliable_check.toggled.connect(self.refresh)
        filters.addWidget(self.reliable_check)

        self.sort_combo = QComboBox()
        for label, value in (
            ("Title", "title"),
            ("BPM low-high", "bpm_asc"),
            ("BPM high-low", "bpm_desc"),
            ("Energy high-low", "energy_desc"),
            ("Energy low-high", "energy_asc"),
            ("Camelot key", "key"),
        ):
            self.sort_combo.addItem(label, value)
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.sort_combo)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("analyzedLibraryTable")
        self.table.setHorizontalHeaderLabels(
            ["Track", "Artist", "BPM", "Key", "Energy", "Style", "Beatgrid", "Use"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, stretch=1)

        action_row = QHBoxLayout()
        self.result_count_label = QLabel("0 tracks")
        self.result_count_label.setProperty("role", "field_hint")
        action_row.addWidget(self.result_count_label)
        action_row.addStretch(1)
        self.must_have_button = QPushButton("Add Must Have")
        self.must_have_button.setProperty("role", "secondary")
        self.must_have_button.setEnabled(False)
        self.must_have_button.clicked.connect(self._request_must_have)
        action_row.addWidget(self.must_have_button)
        self.not_tonight_button = QPushButton("Not Tonight")
        self.not_tonight_button.setProperty("role", "quiet")
        self.not_tonight_button.setEnabled(False)
        self.not_tonight_button.clicked.connect(self._request_not_tonight)
        action_row.addWidget(self.not_tonight_button)
        layout.addLayout(action_row)

    @staticmethod
    def _bpm_spin(empty_text: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 300.0)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSpecialValueText(empty_text)
        spin.setMaximumWidth(92)
        return spin

    def set_analyses(self, analyses: Iterable[AnalysisResult]) -> None:
        self._rows = build_library_rows(analyses)
        self._replace_filter_options()
        self.refresh()

    def set_track_states(
        self,
        *,
        must_have_ids: Iterable[str] = (),
        not_tonight_ids: Iterable[str] = (),
    ) -> None:
        self._must_have_ids = set(must_have_ids)
        self._not_tonight_ids = set(not_tonight_ids)
        self.refresh(preserve_track_id=self.selected_track_id())

    def selected_track_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            selected = self.table.selectionModel().selectedRows()
            row = selected[0].row() if selected else -1
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.UserRole)) if item is not None else None

    def refresh(self, *_args, preserve_track_id: str | None = None) -> None:
        if preserve_track_id is None:
            preserve_track_id = self.selected_track_id()
        bpm_min = self.bpm_min_spin.value() or None
        bpm_max = self.bpm_max_spin.value() or None
        self._visible_rows = filter_library_rows(
            self._rows,
            query=self.search_edit.text(),
            style=self.style_combo.currentData(),
            key=self.key_combo.currentData(),
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            reliable_only=self.reliable_check.isChecked(),
            sort_by=str(self.sort_combo.currentData() or "title"),
        )
        self.table.setRowCount(len(self._visible_rows))
        selected_row = -1
        for row_index, row in enumerate(self._visible_rows):
            self._populate_row(row_index, row)
            if row.track_id == preserve_track_id:
                selected_row = row_index
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        else:
            self.table.clearSelection()
        total = len(self._rows)
        visible = len(self._visible_rows)
        self.summary_label.setText(f"{total} analyzed")
        self.result_count_label.setText(
            f"{visible} of {total} tracks" if visible != total else f"{total} tracks"
        )
        self._sync_actions()

    def _replace_filter_options(self) -> None:
        current_style = self.style_combo.currentData()
        current_key = self.key_combo.currentData()
        styles = sorted({row.style for row in self._rows}, key=str.casefold)
        keys = sorted({row.key for row in self._rows}, key=str.casefold)
        self.style_combo.blockSignals(True)
        self.key_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItem("All styles", None)
        for style in styles:
            self.style_combo.addItem(style, style)
        self.key_combo.clear()
        self.key_combo.addItem("All keys", None)
        for key in keys:
            self.key_combo.addItem(key, key)
        style_index = self.style_combo.findData(current_style)
        key_index = self.key_combo.findData(current_key)
        self.style_combo.setCurrentIndex(max(0, style_index))
        self.key_combo.setCurrentIndex(max(0, key_index))
        self.style_combo.blockSignals(False)
        self.key_combo.blockSignals(False)

    def _populate_row(self, row_index: int, row: LibraryTrackRow) -> None:
        bpm_text = f"{row.bpm:.2f}" if row.bpm is not None else "-"
        quality = row.grid_quality
        if row.analysis.beatgrid is None:
            grid_text = "No grid"
        elif row.grid_reliable:
            grid_text = f"Reliable {quality:.0%}" if quality is not None else "Reliable"
        else:
            grid_text = "Review"
        if row.track_id in self._must_have_ids:
            use_text = "Must Have"
        elif row.track_id in self._not_tonight_ids:
            use_text = "Not Tonight"
        else:
            use_text = "Available"
        values = (
            row.title,
            row.artist,
            bpm_text,
            row.key,
            f"{row.energy_percent}%",
            row.style,
            grid_text,
            use_text,
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0:
                item.setData(Qt.UserRole, row.track_id)
                item.setToolTip(row.analysis.track.source_path or row.track_id)
            elif column == 3:
                confidence = row.analysis.track.key_confidence
                source = row.analysis.track.key_detection_source or "detector"
                confidence_text = f"{confidence:.0%}" if confidence is not None else "unknown"
                item.setToolTip(f"Key source: {source}; confidence: {confidence_text}")
            elif column == 4:
                item.setToolTip(f"Relative library energy; raw mean RMS: {row.energy:.4f}")
            elif column == 6:
                grid = row.analysis.beatgrid
                flags = grid.diagnostic_flags if grid is not None else []
                item.setToolTip("\n".join(flags) if flags else "No beatgrid warnings.")
                item.setForeground(QColor("#38D996" if row.grid_reliable else "#FFB454"))
            elif column == 7:
                if use_text == "Must Have":
                    item.setForeground(QColor("#5CC8FF"))
                elif use_text == "Not Tonight":
                    item.setForeground(QColor("#7E8A99"))
            self.table.setItem(row_index, column, item)

    def _sync_actions(self) -> None:
        track_id = self.selected_track_id()
        enabled = track_id is not None
        self.must_have_button.setEnabled(enabled)
        self.not_tonight_button.setEnabled(enabled)
        if not enabled:
            self.must_have_button.setText("Add Must Have")
            self.not_tonight_button.setText("Not Tonight")
            return
        self.must_have_button.setText(
            "Remove Must Have" if track_id in self._must_have_ids else "Add Must Have"
        )
        self.not_tonight_button.setText(
            "Restore Tonight" if track_id in self._not_tonight_ids else "Not Tonight"
        )

    def _on_selection_changed(self) -> None:
        self._sync_actions()
        track_id = self.selected_track_id()
        if track_id is not None:
            self.track_selected.emit(track_id)

    def _request_must_have(self) -> None:
        track_id = self.selected_track_id()
        if track_id is not None:
            self.must_have_requested.emit(track_id)

    def _request_not_tonight(self) -> None:
        track_id = self.selected_track_id()
        if track_id is not None:
            self.not_tonight_requested.emit(track_id)

"""Simple Mode — guided 5-step flow (UI/UX audit §18/§20).

The default user experience: Import Tracks → Analyze Library → Generate Set →
Review Transitions → Export. No node graph, no sensors, no telemetry — the
raw Signal Graph stays available behind "Open Graph Mode" for power users.

Reuses the engine primitives directly (workflows.smart_playlist for analysis,
decision.set_builder for ordering, export.rekordbox for XML) so Simple Mode
and Graph Mode cannot drift apart on behavior.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dancelab.core.config import EngineConfig, load_config, load_weights
from dancelab.core.models import AnalysisResult, SetPlan
from dancelab.core.pipeline import analyze_track
from dancelab.decision.set_builder import build_set
from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml
from dancelab.workflows.smart_playlist import (
    MIN_PLAYLIST_TRACKS,
    SmartPlaylistFailure,
    _transition_windows_for_playlist,
    analyze_files,
    discover_audio_files,
    estimate_track_count_for_duration,
)

_STEP_TITLES = [
    "1 · Import Tracks",
    "2 · Analyze Library",
    "3 · Generate Set",
    "4 · Review Transitions",
    "5 · Export",
]

_ARC_CHOICES = [
    ("build", "Build — rising energy"),
    ("peak", "Peak — keep energy high"),
    ("flat", "Flat — steady energy"),
]


class _AnalysisWorker(QObject):
    """Runs library analysis off the UI thread (same rule as the graph host)."""

    progress = Signal(int, int, str)
    finished = Signal(object)  # (analyses, failures) | error string

    def __init__(self, files: list[Path], config: EngineConfig, analyze_fn):
        super().__init__()
        self._files = files
        self._config = config
        self._analyze_fn = analyze_fn

    def run(self) -> None:
        try:
            analyses, failures = analyze_files(
                self._files,
                self._config,
                analyze_fn=self._analyze_fn,
                progress=lambda done, total, path: self.progress.emit(done, total, path),
            )
        except Exception as exc:  # surfaced on the UI thread, never swallowed
            self.finished.emit(str(exc))
        else:
            self.finished.emit((analyses, failures))


class SimpleModeWindow(QMainWindow):
    def __init__(self, *, config_path: str | Path = "configs/default.yaml"):
        super().__init__()
        self.config = load_config(config_path)
        self.analyze_fn = analyze_track  # injectable for tests
        self.files: list[Path] = []
        self.analyses: list[AnalysisResult] = []
        self.failures: list[SmartPlaylistFailure] = []
        self.plan: SetPlan | None = None
        self.selected_analyses: list[AnalysisResult] = []
        self.export_path: Path | None = None
        self.graph_window = None
        self._analysis_thread: QThread | None = None

        self.setWindowTitle("DanceLab Pro")
        self.resize(1080, 720)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #141517; color: #d6d7d9; }
            QListWidget, QPlainTextEdit, QComboBox, QLineEdit {
                background: #17181a; border: 1px solid #2c2d31; border-radius: 6px;
                color: #d6d7d9; min-height: 26px;
            }
            QLabel[role="title"] { font-size: 26px; font-weight: 700; color: #f0d0a0; }
            QLabel[role="subtitle"] { font-size: 14px; color: #989ba1; }
            QLabel[role="hint"] { color: #989ba1; }
            QPushButton {
                background: #20231d; color: #9bd27f; border: 1px solid #4d7443;
                border-radius: 8px; font-weight: 600; min-height: 32px; padding: 6px 14px;
            }
            QPushButton[role="hero"] {
                background: #e2a856; color: #141517; border: none; font-weight: 800;
                min-height: 40px; padding: 8px 18px;
            }
            QPushButton:disabled { color: #5a5c60; border-color: #2c2d31; }
            QProgressBar { background: #17181a; border: 1px solid #2c2d31; border-radius: 6px; }
            QProgressBar::chunk { background: #e2a856; }
            """
        )

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.step_list = QListWidget()
        self.step_list.setFixedWidth(230)
        self.step_list.setSelectionMode(QListWidget.NoSelection)
        self.step_list.setFocusPolicy(Qt.NoFocus)
        for title in _STEP_TITLES:
            QListWidgetItem(title, self.step_list)
        root_layout.addWidget(self.step_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(28, 24, 28, 18)
        right_layout.setSpacing(14)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_welcome_page())   # 0
        self.pages.addWidget(self._build_import_page())    # 1
        self.pages.addWidget(self._build_analyze_page())   # 2
        self.pages.addWidget(self._build_generate_page())  # 3
        self.pages.addWidget(self._build_review_page())    # 4
        self.pages.addWidget(self._build_export_page())    # 5
        right_layout.addWidget(self.pages, stretch=1)

        nav = QWidget()
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        self.back_button = QPushButton("← Back")
        self.back_button.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_button)
        self.nav_hint = QLabel("")
        self.nav_hint.setProperty("role", "hint")
        nav_layout.addWidget(self.nav_hint, stretch=1)
        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_button)
        right_layout.addWidget(nav)

        root_layout.addWidget(right, stretch=1)
        self.setCentralWidget(root)
        self._sync_navigation()

    # ------------------------------------------------------------------- pages

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        title = QLabel("DanceLab Pro")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("Create a DJ set from your tracks in 5 guided steps.")
        subtitle.setProperty("role", "subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        new_button = QPushButton("New Set")
        new_button.setProperty("role", "hero")
        new_button.clicked.connect(lambda: self.go_to_step(1))
        layout.addWidget(new_button, alignment=Qt.AlignCenter)

        open_project_button = QPushButton("Open Project… (Graph Mode)")
        open_project_button.setToolTip("Open a saved .dlproj graph in the advanced Signal Graph editor.")
        open_project_button.clicked.connect(self.open_project_in_graph_mode)
        layout.addWidget(open_project_button, alignment=Qt.AlignCenter)

        graph_button = QPushButton("Open Graph Mode (Advanced)")
        graph_button.setToolTip("Full node-graph editor: sensors, utilities, telemetry, custom flows.")
        graph_button.clicked.connect(self.open_graph_mode)
        layout.addWidget(graph_button, alignment=Qt.AlignCenter)
        layout.addStretch(2)
        return page

    def _build_import_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 1 — Import tracks")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel("Choose a music folder or individual audio files (mp3, wav, aiff, flac, m4a).")
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        folder_button = QPushButton("Choose Folder…")
        folder_button.clicked.connect(self.choose_import_folder)
        buttons.addWidget(folder_button)
        files_button = QPushButton("Choose Files…")
        files_button.clicked.connect(self.choose_import_files)
        buttons.addWidget(files_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.import_list = QListWidget()
        layout.addWidget(self.import_list, stretch=1)
        self.import_summary = QLabel("No tracks yet.")
        self.import_summary.setProperty("role", "hint")
        layout.addWidget(self.import_summary)
        return page

    def _build_analyze_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 2 — Analyze library")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel("BPM, key, energy, vocals and transition windows for every track. Cached — re-runs are instant.")
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        self.analyze_button = QPushButton("▶ Analyze Tracks")
        self.analyze_button.setProperty("role", "hero")
        self.analyze_button.clicked.connect(self.run_analysis)
        layout.addWidget(self.analyze_button, alignment=Qt.AlignLeft)

        self.analyze_progress = QProgressBar()
        self.analyze_progress.setValue(0)
        layout.addWidget(self.analyze_progress)
        self.analyze_status = QLabel("Not started.")
        self.analyze_status.setProperty("role", "hint")
        layout.addWidget(self.analyze_status)

        self.analyze_failures = QPlainTextEdit()
        self.analyze_failures.setReadOnly(True)
        self.analyze_failures.setPlaceholderText("Tracks that failed to analyze will be listed here.")
        layout.addWidget(self.analyze_failures, stretch=1)
        return page

    def _build_generate_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 3 — Generate set sequence")
        header.setProperty("role", "title")
        layout.addWidget(header)

        # Set length: free track count OR target duration — no fixed presets.
        length_row = QHBoxLayout()
        self.count_radio = QRadioButton("Number of tracks:")
        self.count_radio.setChecked(True)
        length_row.addWidget(self.count_radio)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(MIN_PLAYLIST_TRACKS, 500)
        self.count_spin.setValue(10)
        length_row.addWidget(self.count_spin)
        length_row.addSpacing(24)
        self.duration_radio = QRadioButton("Set length:")
        length_row.addWidget(self.duration_radio)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.25, 24.0)
        self.duration_spin.setSingleStep(0.25)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSuffix(" h")
        self.duration_spin.setToolTip(
            "Track count is estimated from the average length of your analyzed tracks."
        )
        length_row.addWidget(self.duration_spin)
        length_row.addStretch(1)
        layout.addLayout(length_row)

        def sync_length_inputs() -> None:
            self.count_spin.setEnabled(self.count_radio.isChecked())
            self.duration_spin.setEnabled(self.duration_radio.isChecked())

        self.count_radio.toggled.connect(sync_length_inputs)
        self.duration_radio.toggled.connect(sync_length_inputs)
        sync_length_inputs()

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Energy arc:"))
        self.arc_combo = QComboBox()
        for arc_value, arc_label in _ARC_CHOICES:
            self.arc_combo.addItem(arc_label, arc_value)
        controls.addWidget(self.arc_combo)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.generate_button = QPushButton("▶ Generate Set")
        self.generate_button.setProperty("role", "hero")
        self.generate_button.clicked.connect(self.generate_set)
        layout.addWidget(self.generate_button, alignment=Qt.AlignLeft)

        self.set_list = QListWidget()
        layout.addWidget(self.set_list, stretch=1)
        self.generate_status = QLabel("")
        self.generate_status.setProperty("role", "hint")
        layout.addWidget(self.generate_status)
        return page

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 4 — Review transitions")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel(
            "Every transition with its score, harmonic relation, BPM shift and warnings. "
            "Candidate estimates — not DJ-validated ground truth."
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.review_text = QPlainTextEdit()
        self.review_text.setReadOnly(True)
        layout.addWidget(self.review_text, stretch=1)
        return page

    def _build_export_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 5 — Export")
        header.setProperty("role", "title")
        layout.addWidget(header)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Playlist name:"))
        self.playlist_name_edit = QLineEdit("DanceLab Smart Set")
        name_row.addWidget(self.playlist_name_edit, stretch=1)
        layout.addLayout(name_row)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Output XML:"))
        self.export_path_edit = QLineEdit(str(Path.home() / "dancelab_set.xml"))
        path_row.addWidget(self.export_path_edit, stretch=1)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self.choose_export_path)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        self.export_button = QPushButton("▶ Export Rekordbox XML")
        self.export_button.setProperty("role", "hero")
        self.export_button.clicked.connect(self.export_set)
        layout.addWidget(self.export_button, alignment=Qt.AlignLeft)

        self.export_status = QLabel("")
        self.export_status.setProperty("role", "hint")
        self.export_status.setWordWrap(True)
        layout.addWidget(self.export_status)
        layout.addStretch(1)

        graph_button = QPushButton("Open Graph Mode (Advanced)")
        graph_button.clicked.connect(self.open_graph_mode)
        layout.addWidget(graph_button, alignment=Qt.AlignLeft)
        return page

    # -------------------------------------------------------------- navigation

    def current_step(self) -> int:
        return self.pages.currentIndex()

    def go_to_step(self, step: int) -> None:
        self.pages.setCurrentIndex(step)
        self._sync_navigation()

    def go_next(self) -> None:
        if self.current_step() < self.pages.count() - 1:
            self.go_to_step(self.current_step() + 1)

    def go_back(self) -> None:
        if self.current_step() > 0:
            self.go_to_step(self.current_step() - 1)

    def _step_ready(self, step: int) -> tuple[bool, str]:
        """Whether the user can advance PAST `step`, plus the guiding hint."""
        if step == 0:
            return True, "Start a new set or open the advanced graph."
        if step == 1:
            return bool(self.files), "Choose a folder or audio files to continue."
        if step == 2:
            return bool(self.analyses), "Run the analysis to continue."
        if step == 3:
            return self.plan is not None, "Generate the set to continue."
        if step == 4:
            return True, "Review the transitions, then export."
        return False, "Export your set, or go back to adjust it."

    def _sync_navigation(self) -> None:
        step = self.current_step()
        ready, hint = self._step_ready(step)
        self.next_button.setEnabled(ready and step < self.pages.count() - 1)
        self.back_button.setEnabled(step > 0)
        self.nav_hint.setText(hint)
        for index in range(self.step_list.count()):
            item = self.step_list.item(index)
            wizard_step = index + 1  # list has no welcome entry
            done, _ = self._step_ready(wizard_step)
            marker = "✓ " if done and wizard_step < 5 else ""
            item.setText(f"{marker}{_STEP_TITLES[index]}")
            font = item.font()
            font.setBold(wizard_step == step)
            item.setFont(font)

    # ------------------------------------------------------------------- steps

    def choose_import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Music Folder", str(Path.home()))
        if folder:
            self.set_import_files(discover_audio_files(folder))

    def choose_import_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Audio Tracks",
            str(Path.home()),
            "Audio Files (*.mp3 *.wav *.aiff *.aif *.flac *.m4a)",
        )
        if selected:
            self.set_import_files([Path(path) for path in selected])

    def set_import_files(self, files: list[Path]) -> None:
        self.files = list(files)
        self.analyses = []
        self.failures = []
        self.plan = None
        self.import_list.clear()
        for path in self.files:
            QListWidgetItem(path.name, self.import_list)
        self.import_summary.setText(
            f"{len(self.files)} track(s) ready to analyze." if self.files else "No tracks yet."
        )
        self.analyze_progress.setValue(0)
        self.analyze_status.setText("Not started.")
        self._sync_navigation()

    def run_analysis(self, *, wait: bool = False) -> None:
        if not self.files:
            self.analyze_status.setText("Import tracks first.")
            return
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            return
        self.analyze_button.setEnabled(False)
        self.analyze_progress.setMaximum(len(self.files))
        self.analyze_progress.setValue(0)
        self.analyze_status.setText("Analyzing…")

        thread = QThread(self)
        worker = _AnalysisWorker(self.files, self.config, self.analyze_fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_analysis_progress)
        worker.finished.connect(self._on_analysis_finished)
        # Same deadlock rule as the graph host: `thread` has main-thread
        # affinity, so a queued quit() never runs while wait=True parks the
        # main thread in thread.wait(). quit() is thread-safe.
        worker.finished.connect(thread.quit, Qt.DirectConnection)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._analysis_thread = thread
        self._analysis_worker = worker
        thread.start()
        if wait:
            thread.wait()
            QApplication.processEvents()

    def _on_analysis_progress(self, done: int, total: int, path: str) -> None:
        self.analyze_progress.setMaximum(total)
        self.analyze_progress.setValue(done)
        self.analyze_status.setText(f"Analyzing {done}/{total} · {Path(path).name}")

    def _on_analysis_finished(self, payload: object) -> None:
        self._analysis_thread = None
        self._analysis_worker = None
        self.analyze_button.setEnabled(True)
        if isinstance(payload, str):
            self.analyze_status.setText(f"Analysis failed · {payload}")
            self._sync_navigation()
            return
        self.analyses, self.failures = payload
        self.analyze_progress.setValue(self.analyze_progress.maximum())
        self.analyze_status.setText(
            f"Analyzed {len(self.analyses)} track(s) · {len(self.failures)} failed."
        )
        self.analyze_failures.setPlainText(
            "\n".join(f"{f.source_path} — {f.error}" for f in self.failures)
        )
        self._sync_navigation()

    def _target_track_count(self) -> int | None:
        """Resolve the requested set length to a track count, or None + status."""
        if self.duration_radio.isChecked():
            try:
                count = estimate_track_count_for_duration(
                    self.analyses, self.duration_spin.value() * 60.0
                )
            except ValueError as exc:
                self.generate_status.setText(str(exc))
                return None
            self.generate_status.setText(
                f"≈{count} track(s) fit {self.duration_spin.value():g} h "
                "(from your tracks' average length)."
            )
            return count
        count = int(self.count_spin.value())
        if len(self.analyses) < count:
            self.generate_status.setText(
                f"{count} tracks requested but only {len(self.analyses)} analyzed — "
                "using all of them."
            )
            return len(self.analyses)
        return count

    def generate_set(self) -> None:
        if not self.analyses:
            self.generate_status.setText("Analyze tracks first.")
            return
        target_count = self._target_track_count()
        if target_count is None:
            return
        arc = str(self.arc_combo.currentData())
        weights = load_weights(self.config.weights_file)
        self.plan = build_set(self.analyses, weights, arc=arc, target_track_count=target_count)
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}
        self.selected_analyses = [by_id[tid] for tid in self.plan.track_order if tid in by_id]

        self.set_list.clear()
        for position, track_id in enumerate(self.plan.track_order, start=1):
            track = by_id[track_id].track
            label = track.title or track_id
            details = []
            if track.bpm_estimate:
                details.append(f"{track.bpm_estimate:.0f} BPM")
            if track.key_estimate:
                details.append(track.key_estimate)
            suffix = f"  ·  {' · '.join(details)}" if details else ""
            QListWidgetItem(f"{position:>2}. {label}{suffix}", self.set_list)
        mean = self.plan.mean_transition_score
        known_durations = [
            analysis.track.duration_sec
            for analysis in self.selected_analyses
            if analysis.track.duration_sec
        ]
        duration_text = ""
        if known_durations and len(known_durations) == len(self.selected_analyses):
            total_min = sum(known_durations) / 60.0
            duration_text = f" · ≈{int(total_min // 60)}h {int(total_min % 60):02d}m"
        self.generate_status.setText(
            f"{len(self.plan.track_order)}-track set · arc {arc}{duration_text}"
            + (f" · mean transition score {mean:.2f}" if mean is not None else "")
        )
        self._populate_review()
        self._sync_navigation()

    def _populate_review(self) -> None:
        if self.plan is None:
            self.review_text.setPlainText("")
            return
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}

        def name(track_id: str) -> str:
            analysis = by_id.get(track_id)
            return (analysis.track.title if analysis else None) or track_id

        lines = []
        for transition in self.plan.transitions:
            bpm = ""
            if transition.bpm_from and transition.bpm_to:
                bpm = f" · {transition.bpm_from:.0f}→{transition.bpm_to:.0f} BPM"
            lines.append(
                f"{name(transition.from_track_id)}  →  {name(transition.to_track_id)}\n"
                f"    score {transition.transition_score:.2f} · "
                f"{transition.harmonic_relation}"
                f"{f' · {transition.key_from}→{transition.key_to}' if transition.key_from else ''}"
                f"{bpm}"
            )
            for warning in transition.warnings:
                lines.append(f"    ⚠ {warning}")
        if self.plan.warnings:
            lines.append("")
            lines.append("Set warnings:")
            lines.extend(f"  ⚠ {warning}" for warning in self.plan.warnings)
        self.review_text.setPlainText("\n".join(lines))

    def choose_export_path(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, "Export Rekordbox XML", self.export_path_edit.text(), "Rekordbox XML (*.xml)"
        )
        if selected:
            self.export_path_edit.setText(selected)

    def export_set(self) -> None:
        if self.plan is None or not self.selected_analyses:
            self.export_status.setText("Generate a set first.")
            return
        playlist_name = self.playlist_name_edit.text().strip() or "DanceLab Smart Set"
        windows = _transition_windows_for_playlist(self.selected_analyses, config=self.config)
        xml = build_rekordbox_xml(
            self.selected_analyses,
            set_plan=self.plan,
            windows_by_track=windows,
            playlist_name=playlist_name,
        )
        self.export_path = write_rekordbox_xml(xml, self.export_path_edit.text())
        self.export_status.setText(
            f"Exported · {self.export_path}\n"
            "In Rekordbox: Preferences → Advanced → Imported Library, then right-click "
            "the playlist to import. Uncheck re-analysis to keep the DanceLab beatgrid."
        )

    # -------------------------------------------------------------- graph mode

    def open_graph_mode(self):
        from dancelab.contracts.node_host import get_node_host_registry
        from dancelab.host.desktop_app import NodeHostWindow

        if self.graph_window is None:
            self.graph_window = NodeHostWindow(get_node_host_registry())
        self.graph_window.show()
        self.graph_window.raise_()
        return self.graph_window

    def open_project_in_graph_mode(self) -> None:
        from dancelab.host.project import PROJECT_FILE_SUFFIX

        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open DanceLab Project",
            str(Path.home()),
            f"DanceLab Project (*{PROJECT_FILE_SUFFIX})",
        )
        if not selected:
            return
        window = self.open_graph_mode()
        window.load_project_from_path(selected)

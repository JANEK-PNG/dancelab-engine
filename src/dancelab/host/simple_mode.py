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
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QThread, Signal
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
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dancelab.core.config import EngineConfig, load_config, load_weights
from dancelab.core.models import AnalysisResult, ContextProfile, SetPlan
from dancelab.core.pipeline import analyze_track
from dancelab.decision.library_profile import build_library_profile, normalize_style_list
from dancelab.decision.set_builder import build_set
from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml
from dancelab.host.import_dialogs import choose_audio_directories, confirm_suspicious_audio_files
from dancelab.host.pair_review import TransitionReviewWidget, compute_windows
from dancelab.workflows.smart_playlist import (
    MIN_PLAYLIST_TRACKS,
    auto_analysis_workers,
    SmartPlaylistFailure,
    _transition_windows_for_playlist,
    analysis_function_for_depth,
    analyze_files,
    config_for_analysis_depth,
    discover_audio_files,
    estimate_track_count_for_duration,
)

_STEP_TITLES = [
    "1 · Import Tracks",
    "2 · Initial Check",
    "3 · Generate Set",
    "4 · Review Transitions",
    "5 · Export",
]

_ARC_CHOICES = [
    ("build", "Build — rising energy"),
    ("peak", "Peak — keep energy high"),
    ("flat", "Flat — steady energy"),
]

_PLANNER_CHOICES = [
    ("smart", "Smart Playlist — balanced key, BPM, energy and mixability"),
    ("harmonic", "Harmonic Match — prefer nearby Camelot/key wheel moves"),
    ("bpm", "BPM Match — prefer similar tempo and smoother beatmatching"),
]

_NOVELTY_CHOICES = [
    ("balanced", "Balanced — vary sets, keep up to 3 carryover tracks"),
    ("conservative", "Conservative — small variation, up to 5 carryovers"),
    ("fresh", "Fresh — strong variation, 1 carryover"),
    ("exploratory", "Exploratory — max variation, no carryovers"),
    ("deterministic", "Deterministic — same input, identical set every time"),
]

_INITIAL_CHECK_DEPTH = "normal"
_INITIAL_CHECK_LABEL = (
    "Initial Check — fast cached BPM/key/energy/style scan. "
    "Deep Demucs stem analysis happens later only for the generated set tracks."
)

_SET_ROLE_CHOICES = [
    ("builder", "Build-up / regular set"),
    ("bridge", "Continuation after previous DJ"),
    ("opener", "Warm-up / low pressure"),
    ("peak", "Peak-time"),
    ("closer", "Closing / landing"),
]

_CROWD_ENERGY_CHOICES = [
    ("low", "Low / relaxed"),
    ("medium", "Medium / steady"),
    ("high", "High / driving"),
    ("descending", "Descending / cool-down"),
]

_SET_BRIEF_PRESETS = [
    {
        "id": "custom",
        "label": "Custom / no style constraint",
        "styles": "",
        "bpm_min": 0.0,
        "bpm_max": 0.0,
        "arc": "build",
        "planner_mode": "smart",
        "set_role": "builder",
        "crowd_energy": "medium",
    },
    {
        "id": "calm_uk_bass",
        "label": "Calm UK/Bass <=135 / continuation",
        "styles": "bass, uk bass, uk-bass, bass-house, garage, breaks, dubstep",
        "bpm_min": 0.0,
        "bpm_max": 135.0,
        "arc": "flat",
        "planner_mode": "smart",
        "set_role": "bridge",
        "crowd_energy": "medium",
    },
    {
        "id": "warmup_deep",
        "label": "Warm-up deep/soft <=124",
        "styles": "deep house, minimal, ambient-house, downtempo",
        "bpm_min": 0.0,
        "bpm_max": 124.0,
        "arc": "build",
        "planner_mode": "smart",
        "set_role": "opener",
        "crowd_energy": "low",
    },
]


class _AnalysisThread(QThread):
    """Runs library analysis without moving a Python QObject across threads."""

    progress = Signal(int, int, str)
    stage = Signal(str, str)  # (path, real pipeline stage — never simulated)
    track_done = Signal(str, str)  # (path, "cached" | "done" | "failed")
    completed = Signal(object)  # (analyses, failures) | error string

    def __init__(self, files: list[Path], config: EngineConfig, analyze_fn, *, tier: str = "quick", workers: int = 1):
        super().__init__()
        self._files = files
        self._config = config
        self._analyze_fn = analyze_fn
        self._tier = tier
        self._workers = workers
        self._stop_requested = False

    def request_stop(self) -> None:
        """PRODUCT_SPEC §9: cooperative stop — honored between tracks; every
        completed track is already committed to cache, nothing is lost."""
        self._stop_requested = True

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    def run(self) -> None:
        try:
            analyses, failures = analyze_files(
                self._files,
                self._config,
                analyze_fn=self._analyze_fn,
                tier=self._tier,
                workers=self._workers,
                progress=lambda done, total, path: self.progress.emit(done, total, path),
                stage_progress=lambda path, stage: self.stage.emit(path, stage),
                track_done=lambda path, status: self.track_done.emit(path, status),
                should_stop=lambda: self._stop_requested,
            )
        except Exception as exc:  # surfaced on the UI thread, never swallowed
            self.completed.emit(str(exc))
        else:
            self.completed.emit((analyses, failures))


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
        self.review_analysis_depth = _INITIAL_CHECK_DEPTH
        # DJ control (§15-17): pin ≡ Must Have (cap 10, engine-exempt from
        # overuse), lock = exact slot, Not Tonight = excluded this session.
        self.must_have_ids: set[str] = set()
        self.not_tonight_ids: set[str] = set()
        self.locked_positions: dict[int, str] = {}
        # DJ's real Rekordbox cues from a device import, keyed by filename
        self.device_cues: dict[str, list] = {}

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
        hint = QLabel(
            "Choose one or more music folders, or individual audio files (mp3, wav, aiff, flac, m4a)."
        )
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        folder_button = QPushButton("Choose Folder(s)…")
        folder_button.clicked.connect(self.choose_import_folder)
        buttons.addWidget(folder_button)
        files_button = QPushButton("Choose Files…")
        files_button.clicked.connect(self.choose_import_files)
        buttons.addWidget(files_button)
        usb_button = QPushButton("Import from USB…")
        usb_button.setToolTip(
            "Rekordbox performance USB: imports the audio AND your hot cues — "
            "verified cue points become transition data."
        )
        usb_button.clicked.connect(self.choose_import_usb)
        buttons.addWidget(usb_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.import_list = QListWidget()
        self.import_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.import_list, stretch=1)

        manage_row = QHBoxLayout()
        remove_selected_button = QPushButton("Remove Selected")
        remove_selected_button.setToolTip(
            "Remove the highlighted track(s) from this import. Files on disk are untouched."
        )
        remove_selected_button.clicked.connect(self.remove_selected_imports)
        manage_row.addWidget(remove_selected_button)
        clear_button = QPushButton("Clear Import")
        clear_button.setToolTip(
            "Empty the import list and start over. Files on disk are untouched."
        )
        clear_button.clicked.connect(self.clear_import)
        manage_row.addWidget(clear_button)
        manage_row.addStretch(1)
        layout.addLayout(manage_row)

        self.import_summary = QLabel("No tracks yet.")
        self.import_summary.setProperty("role", "hint")
        layout.addWidget(self.import_summary)
        return page

    def clear_import(self) -> None:
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            self.import_summary.setText("Stop processing first.")
            return
        self.set_import_files([])
        self.import_summary.setText("Import cleared. No tracks yet.")

    def remove_selected_imports(self) -> None:
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            return
        selected_rows = sorted(
            (self.import_list.row(item) for item in self.import_list.selectedItems()),
            reverse=True,
        )
        if not selected_rows:
            self.import_summary.setText("Select track(s) in the list first.")
            return
        remaining = [
            path for row, path in enumerate(self.files) if row not in set(selected_rows)
        ]
        removed = len(self.files) - len(remaining)
        self.set_import_files(remaining)
        self.import_summary.setText(
            f"Removed {removed} track(s) · {len(remaining)} remaining."
            if remaining
            else "All tracks removed. Import a folder or files to continue."
        )

    def _build_analyze_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 2 — Initial Check")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel(
            "Fast first pass over the full library: BPM, key, energy, source tags and transition windows. "
            "Deep stem analysis stays on-demand after the set is generated."
        )
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        self.analysis_depth_combo = QComboBox()
        self.analysis_depth_combo.addItem(_INITIAL_CHECK_LABEL, _INITIAL_CHECK_DEPTH)
        self.analysis_depth_combo.setVisible(False)

        initial_check_label = QLabel(_INITIAL_CHECK_LABEL)
        initial_check_label.setProperty("role", "hint")
        layout.addWidget(initial_check_label)

        analyze_row = QHBoxLayout()
        self.analyze_button = QPushButton("▶ Run Initial Check")
        self.analyze_button.setProperty("role", "hero")
        self.analyze_button.clicked.connect(self.run_analysis)
        analyze_row.addWidget(self.analyze_button)
        self.stop_button = QPushButton("Stop Processing")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.confirm_stop_processing)
        analyze_row.addWidget(self.stop_button)
        analyze_row.addStretch(1)
        layout.addLayout(analyze_row)

        self.analyze_progress = QProgressBar()
        self.analyze_progress.setValue(0)
        layout.addWidget(self.analyze_progress)
        self.analyze_status = QLabel("Not started.")
        self.analyze_status.setProperty("role", "hint")
        layout.addWidget(self.analyze_status)

        # Per-track checklist: each row is checked off as the engine finishes
        # it, and the current row shows the REAL pipeline stage (key detection,
        # beat tracking, ...) reported by the engine — not an animation.
        self.analyze_list = QListWidget()
        layout.addWidget(self.analyze_list, stretch=1)
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
        controls.addSpacing(18)
        controls.addWidget(QLabel("Preference:"))
        self.planner_mode_combo = QComboBox()
        for mode_value, mode_label in _PLANNER_CHOICES:
            self.planner_mode_combo.addItem(mode_label, mode_value)
        controls.addWidget(self.planner_mode_combo)
        controls.addStretch(1)
        layout.addLayout(controls)

        novelty_row = QHBoxLayout()
        novelty_row.addWidget(QLabel("Variation:"))
        self.novelty_combo = QComboBox()
        for mode_value, mode_label in _NOVELTY_CHOICES:
            self.novelty_combo.addItem(mode_label, mode_value)
        self.novelty_combo.setToolTip(
            "How much regenerating varies the set. Variation only breaks ties "
            "between similarly-strong options — BPM/key/risk rules always win."
        )
        novelty_row.addWidget(self.novelty_combo)
        novelty_row.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(0)
        self.seed_spin.setToolTip("0 = new variation each Generate; set a number to reproduce a set.")
        novelty_row.addWidget(self.seed_spin)
        novelty_row.addStretch(1)
        layout.addLayout(novelty_row)

        brief_title = QLabel("Set brief:")
        brief_title.setProperty("role", "subtitle")
        layout.addWidget(brief_title)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.set_brief_combo = QComboBox()
        for preset in _SET_BRIEF_PRESETS:
            self.set_brief_combo.addItem(str(preset["label"]), str(preset["id"]))
        self.set_brief_combo.setToolTip(
            "Fast event brief. Presets only fill the controls below; you can edit them before Generate."
        )
        preset_row.addWidget(self.set_brief_combo, stretch=1)
        layout.addLayout(preset_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Leading style(s):"))
        self.style_focus_edit = QLineEdit()
        self.style_focus_edit.setPlaceholderText("e.g. bass, uk bass, garage, breaks")
        self.style_focus_edit.setToolTip(
            "Comma-separated style/genre focus. Uses source-backed file genre tags when available."
        )
        style_row.addWidget(self.style_focus_edit, stretch=1)
        layout.addLayout(style_row)

        bpm_row = QHBoxLayout()
        bpm_row.addWidget(QLabel("BPM range:"))
        self.bpm_min_spin = QDoubleSpinBox()
        self.bpm_min_spin.setRange(0.0, 300.0)
        self.bpm_min_spin.setDecimals(1)
        self.bpm_min_spin.setSingleStep(1.0)
        self.bpm_min_spin.setSpecialValueText("No min")
        bpm_row.addWidget(self.bpm_min_spin)
        bpm_row.addWidget(QLabel("to"))
        self.bpm_max_spin = QDoubleSpinBox()
        self.bpm_max_spin.setRange(0.0, 300.0)
        self.bpm_max_spin.setDecimals(1)
        self.bpm_max_spin.setSingleStep(1.0)
        self.bpm_max_spin.setSpecialValueText("No max")
        bpm_row.addWidget(self.bpm_max_spin)
        bpm_row.addSpacing(18)
        bpm_row.addWidget(QLabel("Set role:"))
        self.set_role_combo = QComboBox()
        for role_value, role_label in _SET_ROLE_CHOICES:
            self.set_role_combo.addItem(role_label, role_value)
        bpm_row.addWidget(self.set_role_combo)
        bpm_row.addWidget(QLabel("Energy:"))
        self.crowd_energy_combo = QComboBox()
        for energy_value, energy_label in _CROWD_ENERGY_CHOICES:
            self.crowd_energy_combo.addItem(energy_label, energy_value)
        bpm_row.addWidget(self.crowd_energy_combo)
        bpm_row.addStretch(1)
        layout.addLayout(bpm_row)

        self.library_profile_label = QLabel(
            "Analyze tracks first. Then this panel will show detected styles and how many tracks match the brief."
        )
        self.library_profile_label.setProperty("role", "hint")
        layout.addWidget(self.library_profile_label)

        self.set_brief_combo.currentIndexChanged.connect(self._apply_set_brief_preset)
        self.style_focus_edit.textChanged.connect(lambda _: self._update_library_profile_summary())
        self.bpm_min_spin.valueChanged.connect(lambda _: self._update_library_profile_summary())
        self.bpm_max_spin.valueChanged.connect(lambda _: self._update_library_profile_summary())
        self.set_role_combo.currentIndexChanged.connect(lambda _: self._update_library_profile_summary())
        self.crowd_energy_combo.currentIndexChanged.connect(lambda _: self._update_library_profile_summary())

        self.generate_button = QPushButton("▶ Generate Set")
        self.generate_button.setProperty("role", "hero")
        self.generate_button.clicked.connect(self.generate_set)
        layout.addWidget(self.generate_button, alignment=Qt.AlignLeft)

        self.set_list = QListWidget()
        layout.addWidget(self.set_list, stretch=1)

        dj_row = QHBoxLayout()
        pin_button = QPushButton("📌 Pin")
        pin_button.setToolTip("Must Have — always in the set; engine picks the slot. Max 10.")
        pin_button.clicked.connect(self._on_pin_clicked)
        dj_row.addWidget(pin_button)
        lock_button = QPushButton("🔒 Lock")
        lock_button.setToolTip("Keep this track exactly here through regenerates.")
        lock_button.clicked.connect(self._on_lock_clicked)
        dj_row.addWidget(lock_button)
        rest_button = QPushButton("🌙 Rest")
        rest_button.setToolTip("Not Tonight — keep out of this set. Never deletes the file.")
        rest_button.clicked.connect(self._on_rest_clicked)
        dj_row.addWidget(rest_button)
        self.dj_control_status = QLabel("")
        self.dj_control_status.setProperty("role", "hint")
        dj_row.addWidget(self.dj_control_status, stretch=1)
        layout.addLayout(dj_row)

        self.generate_status = QLabel("")
        self.generate_status.setProperty("role", "hint")
        layout.addWidget(self.generate_status)

        # Deep-on-demand (spec deep-speed plan #1): separate stems only for the
        # tracks that made the set — minutes instead of an overnight library run.
        deep_row = QHBoxLayout()
        self.deep_upgrade_button = QPushButton("Deep-Analyze Set Tracks")
        self.deep_upgrade_button.setToolTip(
            "Run Demucs stem-aware analysis ONLY on the tracks in this set. "
            "Already-deep tracks are reused from cache."
        )
        self.deep_upgrade_button.setEnabled(False)
        self.deep_upgrade_button.clicked.connect(self.toggle_deep_upgrade)
        deep_row.addWidget(self.deep_upgrade_button)
        self.deep_status = QLabel("")
        self.deep_status.setProperty("role", "hint")
        deep_row.addWidget(self.deep_status, stretch=1)
        layout.addLayout(deep_row)
        return page

    # ---------------------------------------------------- DJ control (§15-17)

    MUST_HAVE_LIMIT = 10

    def _selected_set_track_id(self) -> str | None:
        item = self.set_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def toggle_must_have(self, track_id: str) -> str:
        """Returns: "added" | "limit" | "confirm_remove" | "conflict"."""
        if track_id in self.must_have_ids:
            return "confirm_remove"
        if len(self.must_have_ids) >= self.MUST_HAVE_LIMIT:
            return "limit"
        if track_id in self.not_tonight_ids:
            return "conflict"
        self.must_have_ids.add(track_id)
        return "added"

    def remove_must_have(self, track_id: str) -> None:
        self.must_have_ids.discard(track_id)

    def toggle_not_tonight(self, track_id: str) -> str:
        """Returns: "rested" | "restored" | "conflict"."""
        if track_id in self.not_tonight_ids:
            self.not_tonight_ids.discard(track_id)
            return "restored"
        if track_id in self.must_have_ids:
            return "conflict"
        self.not_tonight_ids.add(track_id)
        return "rested"

    def resolve_conflict(self, track_id: str, choice: str) -> None:
        """choice: "keep" (Must Have wins) | "skip" (rest tonight) | "clear"."""
        if choice == "keep":
            self.not_tonight_ids.discard(track_id)
            self.must_have_ids.add(track_id)
        elif choice == "skip":
            self.must_have_ids.discard(track_id)
            self.not_tonight_ids.add(track_id)
        else:
            self.must_have_ids.discard(track_id)
            self.not_tonight_ids.discard(track_id)

    def toggle_lock_here(self, track_id: str) -> None:
        """Lock the track to its current slot in the plan (or unlock)."""
        current = {pos for pos, tid in self.locked_positions.items() if tid == track_id}
        if current:
            for pos in current:
                del self.locked_positions[pos]
            return
        if self.plan and track_id in self.plan.track_order:
            slot = self.plan.track_order.index(track_id) + 1
            self.locked_positions = {
                pos: tid for pos, tid in self.locked_positions.items() if tid != track_id
            }
            self.locked_positions[slot] = track_id

    def _on_pin_clicked(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        track_id = self._selected_set_track_id()
        if track_id is None:
            return
        outcome = self.toggle_must_have(track_id)
        if outcome == "limit":
            QMessageBox.information(
                self, "Must Have limit",
                "You have to make a sacrifice.\nYou can only have "
                f"{self.MUST_HAVE_LIMIT} Must Have tracks. Choose wisely.",
            )
        elif outcome == "confirm_remove":
            box = QMessageBox(self)
            box.setWindowTitle("Don't you love me?")
            box.setText("Remove the Must Have flag? The file stays in your library.")
            keep = box.addButton("Keep", QMessageBox.RejectRole)
            remove = box.addButton("Remove", QMessageBox.AcceptRole)
            box.setDefaultButton(keep)
            box.exec()
            if box.clickedButton() is remove:
                self.remove_must_have(track_id)
        elif outcome == "conflict":
            self._conflict_dialog(track_id)
        self._refresh_dj_control_ui()

    def _on_rest_clicked(self) -> None:
        track_id = self._selected_set_track_id()
        if track_id is None:
            return
        if self.toggle_not_tonight(track_id) == "conflict":
            self._conflict_dialog(track_id)
        self._refresh_dj_control_ui()

    def _on_lock_clicked(self) -> None:
        track_id = self._selected_set_track_id()
        if track_id is not None:
            self.toggle_lock_here(track_id)
        self._refresh_dj_control_ui()

    def _conflict_dialog(self, track_id: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self)
        box.setWindowTitle("Two intentions")
        box.setText("This track is both Must Have and Not Tonight.\nWhich should DanceLab follow?")
        keep = box.addButton("Keep", QMessageBox.AcceptRole)
        skip = box.addButton("Skip tonight", QMessageBox.DestructiveRole)
        box.addButton("Clear both", QMessageBox.RejectRole)
        box.setDefaultButton(keep)
        box.exec()
        clicked = box.clickedButton()
        if clicked is keep:
            self.resolve_conflict(track_id, "keep")
        elif clicked is skip:
            self.resolve_conflict(track_id, "skip")
        else:
            self.resolve_conflict(track_id, "clear")

    def _refresh_dj_control_ui(self) -> None:
        self.dj_control_status.setText(
            f"Must Have {len(self.must_have_ids)}/{self.MUST_HAVE_LIMIT} · "
            f"locked {len(self.locked_positions)} · "
            f"Not Tonight {len(self.not_tonight_ids)} — Regenerate to apply."
        )

    # ------------------------------------------------- deep-on-demand upgrade

    def toggle_deep_upgrade(self) -> None:
        thread = self._analysis_thread
        if thread is not None and thread.isRunning():
            thread.request_stop()
            self.deep_status.setText("Stopping after current track…")
            return
        self.run_deep_upgrade()

    def run_deep_upgrade(self, *, wait: bool = False) -> None:
        if self.plan is None or not self.selected_analyses:
            self.deep_status.setText("Generate a set first.")
            return
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            self.deep_status.setText("Another job is running — stop it first.")
            return
        files = [
            Path(analysis.track.source_path)
            for analysis in self.selected_analyses
            if analysis.track.source_path
        ]
        if not files:
            self.deep_status.setText("Set tracks have no source paths.")
            return
        manager = self.cache_manager()
        if manager.low_disk():
            self.deep_status.setText(
                f"Low disk space — deep analysis blocked ({manager.root})."
            )
            return
        self.deep_upgrade_button.setText("Stop Deep Analysis")
        self.deep_status.setText(f"Deep-analyzing {len(files)} set track(s)…")
        thread = _AnalysisThread(
            files,
            self._config_for_analysis_depth("deep"),
            analysis_function_for_depth(self.analyze_fn, "deep"),
            tier="deep",       # §7 manifest: already-deep tracks reuse, zero compute
            workers=1,         # demucs memory pressure — single worker
        )
        thread.progress.connect(
            lambda done, total, path: self.deep_status.setText(
                f"Deep {done}/{total} · {Path(path).name}"
            )
        )
        thread.completed.connect(self._on_deep_upgrade_finished)
        self._analysis_thread = thread
        thread.start()
        if wait:
            thread.wait()
            QApplication.processEvents()

    def _on_deep_upgrade_finished(self, payload: object) -> None:
        finished_thread = self.sender()
        if finished_thread is self._analysis_thread:
            self._analysis_thread = None
        if isinstance(finished_thread, QThread):
            if finished_thread.isRunning() and QThread.currentThread() is not finished_thread:
                finished_thread.wait(1000)
            finished_thread.deleteLater()
        self.deep_upgrade_button.setText("Deep-Analyze Set Tracks")
        if isinstance(payload, str):
            self.deep_status.setText(f"Deep analysis failed · {payload}")
            return
        upgraded, failures = payload
        # merge: deep results replace quick ones by track_id; library keeps rest
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}
        for analysis in upgraded:
            by_id[analysis.track.track_id] = analysis
        self.analyses = list(by_id.values())
        selected_ids = set(self.plan.track_order) if self.plan else set()
        self.selected_analyses = [
            by_id[tid] for tid in (self.plan.track_order if self.plan else []) if tid in by_id
        ]
        _ = selected_ids
        self._review_windows_cache = {}  # windows recompute from stem-aware data
        self.review_analysis_depth = "deep"
        was_stopped = bool(getattr(finished_thread, "stop_requested", False))
        note = " (stopped early — rest stays quick)" if was_stopped else ""
        fail_note = f" · {len(failures)} failed" if failures else ""
        self.deep_status.setText(
            f"Deep data ready for {len(upgraded)} track(s){fail_note}{note}. "
            "Review now uses stem-aware transition data; Regenerate to re-score the order."
        )

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 4 — Review transitions")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel(
            "Pick a transition: song structure, transition windows, A/B decks with "
            "beat sync, quantized cueing and stem isolation. "
            "Candidate estimates — not DJ-validated ground truth."
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        split = QHBoxLayout()
        self.review_list = QListWidget()
        self.review_list.setMaximumWidth(340)
        self.review_list.currentRowChanged.connect(self._on_review_row_changed)
        split.addWidget(self.review_list)
        self.review_widget = TransitionReviewWidget()
        split.addWidget(self.review_widget, stretch=1)
        layout.addLayout(split, stretch=1)
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
        folders = choose_audio_directories(
            self,
            title="Choose Music Folder(s)",
            start_dir=str(Path.home()),
        )
        if not folders:
            return
        files: list[Path] = []
        for folder in folders:
            try:
                files.extend(discover_audio_files(folder))
            except ValueError as exc:
                self.import_summary.setText(str(exc))
                return
        files = self._dedupe_import_files(files)
        if not files:
            self.set_import_files([])
            self.import_summary.setText("No supported audio files found in selected folder(s).")
            return
        self._set_import_files_after_preflight(files)

    def choose_import_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Audio Tracks",
            str(Path.home()),
            "Audio Files (*.mp3 *.wav *.aiff *.aif *.flac *.m4a)",
        )
        if selected:
            self._set_import_files_after_preflight([Path(path) for path in selected])

    def _dedupe_import_files(self, files: list[Path]) -> list[Path]:
        seen: set[str] = set()
        result: list[Path] = []
        for path in files:
            normalized = str(Path(path).expanduser())
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(Path(normalized))
        return result

    def _set_import_files_after_preflight(self, files: list[Path]) -> None:
        accepted = confirm_suspicious_audio_files(self, files)
        self.set_import_files(self._dedupe_import_files(accepted))
        if files and not accepted:
            self.import_summary.setText("Import cancelled or all suspicious files were skipped.")

    def set_import_files(self, files: list[Path]) -> None:
        self.files = list(files)
        self.analyses = []
        self.failures = []
        self.plan = None
        self.review_analysis_depth = _INITIAL_CHECK_DEPTH
        self.import_list.clear()
        for path in self.files:
            QListWidgetItem(path.name, self.import_list)
        self.import_summary.setText(
            f"{len(self.files)} track(s) ready to analyze." if self.files else "No tracks yet."
        )
        self.analyze_progress.setValue(0)
        if self.files:
            self.analyze_status.setText(
                f"Initial Check not started. {self._analysis_estimate_text(_INITIAL_CHECK_DEPTH)}"
            )
        else:
            self.analyze_status.setText("Not started.")
        self.analyze_list.clear()
        self._update_library_profile_summary()
        self._sync_navigation()

    def cache_manager(self):
        from dancelab.storage.cache_manager import cache_manager_for

        return cache_manager_for(self.config)

    def _analysis_estimate_text(self, depth: str) -> str:
        from dancelab.storage.cache_manager import CacheManager, format_bytes

        manager = self.cache_manager()
        stems = depth == "deep"
        estimate = CacheManager.estimate(
            new_track_count=len(self.files),
            # duration unknown pre-analysis: honest 5-min assumption, labeled "~"
            stem_track_durations_sec=[300.0] * len(self.files) if stems else None,
        )
        from dancelab.core.backend import backend_report

        parts = [f"Estimated cache: ~{format_bytes(estimate.total_bytes)}"]
        parts.append(f"Free disk: {format_bytes(manager.free_disk_bytes())}")
        parts.append(f"Cache: {manager.root}")
        parts.append(backend_report()["label"])  # honest: actual device (§18)
        return " · ".join(parts)

    def run_analysis(self, *, wait: bool = False) -> None:
        if not self.files:
            self.analyze_status.setText("Import tracks first.")
            return
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            return
        self.analyze_button.setEnabled(False)
        self.analyze_progress.setMaximum(len(self.files))
        self.analyze_progress.setValue(0)
        depth = _INITIAL_CHECK_DEPTH
        self.review_analysis_depth = _INITIAL_CHECK_DEPTH
        self.analyze_status.setText("Running Initial Check…")

        self.analyze_list.clear()
        self._analyze_rows = {}
        for path in self.files:
            self._analyze_rows[str(path)] = self.analyze_list.count()
            QListWidgetItem(f"○  {path.name}", self.analyze_list)

        analysis_config = self._config_for_analysis_depth(depth)
        analyze_fn = analysis_function_for_depth(self.analyze_fn, depth)
        # §18: Initial Check fans out across performance cores. Demucs stays
        # isolated in Deep-Analyze Set Tracks after a set has been generated.
        workers = auto_analysis_workers()
        if workers > 1:
            self.analyze_status.setText(
                self.analyze_status.text() + f" · {workers} CPU workers"
            )
        thread = _AnalysisThread(
            self.files,
            analysis_config,
            analyze_fn,
            tier=("deep" if depth == "deep" else "quick"),  # §7: manifest decides reuse
            workers=workers,
        )
        thread.progress.connect(self._on_analysis_progress)
        thread.stage.connect(self._on_analysis_stage)
        thread.track_done.connect(self._on_track_done)
        thread.completed.connect(self._on_analysis_finished)
        self._analysis_thread = thread
        self.stop_button.setVisible(True)
        thread.start()
        if wait:
            thread.wait()
            QApplication.processEvents()

    def confirm_stop_processing(self) -> None:
        thread = self._analysis_thread
        if thread is None or not thread.isRunning():
            return
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self)
        box.setWindowTitle("Stop this job?")
        box.setText(
            "DanceLab will stop after the current track. Tracks already "
            "processed will be saved and will not need to be processed again."
        )
        keep_button = box.addButton("Keep Running", QMessageBox.RejectRole)
        stop_button = box.addButton("Stop After Current Track", QMessageBox.AcceptRole)
        box.setDefaultButton(keep_button)
        box.exec()
        if box.clickedButton() is stop_button:
            self.request_stop_processing()

    def request_stop_processing(self) -> None:
        """Programmatic stop (used by the modal and by tests)."""
        thread = self._analysis_thread
        if thread is None:
            return
        thread.request_stop()
        self.analyze_status.setText("Stopping after current track…")
        self.stop_button.setEnabled(False)

    def _set_analyze_row(self, path: str, text: str) -> None:
        row = getattr(self, "_analyze_rows", {}).get(path)
        if row is not None and row < self.analyze_list.count():
            self.analyze_list.item(row).setText(text)
            self.analyze_list.scrollToItem(self.analyze_list.item(row))

    def _on_analysis_progress(self, done: int, total: int, path: str) -> None:
        self.analyze_progress.setMaximum(total)
        self.analyze_progress.setValue(done)
        self.analyze_status.setText(f"Analyzing {done}/{total} · {Path(path).name}")
        self._set_analyze_row(path, f"▶  {Path(path).name} · starting…")

    def _on_track_done(self, path: str, status: str) -> None:
        # per-track ✓ the moment it happens — no waiting for the whole batch
        name = Path(path).name
        if status == "cached":
            self._set_analyze_row(path, f"✓  {name} · from cache")
        elif status == "done":
            self._set_analyze_row(path, f"✓  {name} · analyzed")
        else:
            self._set_analyze_row(path, f"✗  {name}")

    def _on_analysis_stage(self, path: str, stage: str) -> None:
        # stage names come straight from the engine pipeline hook
        self._set_analyze_row(path, f"▶  {Path(path).name} · {stage}…")

    def _on_analysis_finished(self, payload: object) -> None:
        finished_thread = self.sender()
        if finished_thread is self._analysis_thread:
            self._analysis_thread = None
        if isinstance(finished_thread, QThread):
            if finished_thread.isRunning() and QThread.currentThread() is not finished_thread:
                finished_thread.wait(1000)
            finished_thread.deleteLater()
        self.analyze_button.setEnabled(True)
        self.stop_button.setVisible(False)
        self.stop_button.setEnabled(True)
        was_stopped = bool(getattr(finished_thread, "stop_requested", False))
        if isinstance(payload, str):
            self.analyze_status.setText(f"Analysis failed · {payload}")
            self._sync_navigation()
            return
        self.analyses, self.failures = payload
        if was_stopped:
            # §9: completed tracks saved; the rest stays pending. Re-run
            # continues from cache — nothing is processed twice.
            pending = len(self.files) - len(self.analyses) - len(self.failures)
            self.analyze_status.setText(
                f"Stopped · {len(self.analyses)} analyzed, {pending} pending — "
                "run Initial Check again to continue."
            )
        else:
            self.analyze_progress.setValue(self.analyze_progress.maximum())
            self.analyze_status.setText(
                f"Initial Check complete · {len(self.analyses)} track(s) · {len(self.failures)} failed."
            )
        for analysis in self.analyses:
            track = analysis.track
            details = []
            if track.bpm_estimate:
                details.append(f"{track.bpm_estimate:.0f} BPM")
            if track.key_estimate:
                details.append(track.key_estimate)
            if track.duration_sec:
                details.append(f"{track.duration_sec / 60:.1f} min")
            suffix = f" · {' · '.join(details)}" if details else ""
            source = track.source_path or ""
            self._set_analyze_row(source, f"✓  {Path(source).name}{suffix}")
        for failure in self.failures:
            self._set_analyze_row(
                failure.source_path,
                f"✗  {Path(failure.source_path).name} — {failure.error}",
            )
        self._update_library_profile_summary()
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

    def _config_for_analysis_depth(self, depth: str) -> EngineConfig:
        return config_for_analysis_depth(self.config, depth)

    def _current_analysis_config(self) -> EngineConfig:
        return self._config_for_analysis_depth(self.review_analysis_depth)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _apply_set_brief_preset(self) -> None:
        preset_id = str(self.set_brief_combo.currentData() or "custom")
        preset = next(
            (item for item in _SET_BRIEF_PRESETS if item["id"] == preset_id),
            _SET_BRIEF_PRESETS[0],
        )
        self.style_focus_edit.setText(str(preset["styles"]))
        self.bpm_min_spin.setValue(float(preset["bpm_min"]))
        self.bpm_max_spin.setValue(float(preset["bpm_max"]))
        self._set_combo_value(self.arc_combo, str(preset["arc"]))
        self._set_combo_value(self.planner_mode_combo, str(preset["planner_mode"]))
        self._set_combo_value(self.set_role_combo, str(preset["set_role"]))
        self._set_combo_value(self.crowd_energy_combo, str(preset["crowd_energy"]))
        self._update_library_profile_summary()

    def _preferred_styles(self) -> list[str]:
        if not hasattr(self, "style_focus_edit"):
            return []
        raw = self.style_focus_edit.text().replace(";", ",")
        return normalize_style_list([part.strip() for part in raw.split(",") if part.strip()])

    def _selected_bpm_min(self) -> float | None:
        if not hasattr(self, "bpm_min_spin"):
            return None
        value = float(self.bpm_min_spin.value())
        return value if value > 0 else None

    def _selected_bpm_max(self) -> float | None:
        if not hasattr(self, "bpm_max_spin"):
            return None
        value = float(self.bpm_max_spin.value())
        return value if value > 0 else None

    def _selected_set_context(self) -> ContextProfile | None:
        styles = self._preferred_styles()
        bpm_min = self._selected_bpm_min()
        bpm_max = self._selected_bpm_max()
        role = str(self.set_role_combo.currentData() or "builder") if hasattr(self, "set_role_combo") else "builder"
        crowd = (
            str(self.crowd_energy_combo.currentData() or "medium")
            if hasattr(self, "crowd_energy_combo")
            else "medium"
        )
        preset_id = str(self.set_brief_combo.currentData() or "custom") if hasattr(self, "set_brief_combo") else "custom"
        if not styles and bpm_min is None and bpm_max is None and role == "builder" and crowd == "medium":
            return None
        return ContextProfile(
            context_id=f"simple_mode_{preset_id}",
            venue_type="event",
            set_role=role,
            crowd_energy=crowd,
            style_focus=styles,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
        )

    def _update_library_profile_summary(self) -> None:
        label = getattr(self, "library_profile_label", None)
        if label is None:
            return
        if not self.analyses:
            label.setText(
                "Analyze tracks first. Then this panel will show detected styles and how many tracks match the brief."
            )
            return
        styles = self._preferred_styles()
        bpm_min = self._selected_bpm_min()
        bpm_max = self._selected_bpm_max()
        context = self._selected_set_context()
        profile = build_library_profile(
            self.analyses,
            context=context,
            preferred_styles=styles,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
        )
        style_bits = [
            f"{style} ({count})"
            for style, count in list(profile.style_counts.items())[:6]
        ]
        detected = ", ".join(style_bits) if style_bits else "no source-backed genre/style tags"
        match_bits: list[str] = []
        if profile.preferred_styles:
            match_bits.append(
                f"{profile.preferred_style_track_count}/{profile.track_count} match style"
            )
        if profile.bpm_preference_min is not None or profile.bpm_preference_max is not None:
            bpm_min_text = profile.bpm_preference_min if profile.bpm_preference_min is not None else "-∞"
            bpm_max_text = profile.bpm_preference_max if profile.bpm_preference_max is not None else "+∞"
            match_bits.append(
                f"{profile.bpm_preference_track_count}/{profile.track_count} inside {bpm_min_text}-{bpm_max_text} BPM"
            )
        bpm_text = (
            f"BPM library {profile.bpm_min:g}-{profile.bpm_max:g}, mean {profile.bpm_mean:g}"
            if profile.bpm_min is not None and profile.bpm_max is not None and profile.bpm_mean is not None
            else "BPM library unknown"
        )
        warning = f" · {profile.warnings[0]}" if profile.warnings else ""
        matches = " · ".join(match_bits) if match_bits else "no active style/BPM limit"
        label.setText(f"{bpm_text} · styles: {detected} · {matches}{warning}")

    def generate_set(self) -> None:
        if not self.analyses:
            self.generate_status.setText("Analyze tracks first.")
            return
        target_count = self._target_track_count()
        if target_count is None:
            return
        arc = str(self.arc_combo.currentData())
        planner_mode = str(self.planner_mode_combo.currentData() or "smart")
        preferred_styles = self._preferred_styles()
        bpm_min = self._selected_bpm_min()
        bpm_max = self._selected_bpm_max()
        context = self._selected_set_context()
        weights = load_weights(self.config.weights_file)

        # §14: history-aware variation. Seed 0 = fresh variation per click
        # (session counter, recorded in the fingerprint — never untracked).
        from dancelab.decision.history import HistoryStore, context_hash, fingerprint_plan

        novelty_mode = str(self.novelty_combo.currentData() or "balanced")
        seed_value = int(self.seed_spin.value())
        if seed_value == 0 and novelty_mode != "deterministic":
            self._auto_seed = getattr(self, "_auto_seed", 0) + 1
            seed_value = self._auto_seed
        ctx_hash = context_hash(
            arc=arc,
            planner=planner_mode,
            count=target_count,
            mode=novelty_mode,
            styles=preferred_styles,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            context=context.context_id if context is not None else None,
            set_role=context.set_role if context is not None else None,
            crowd_energy=context.crowd_energy if context is not None else None,
        )
        store = HistoryStore(self.cache_manager().root / "history" / "playlists.jsonl")
        recent = store.recent(ctx_hash, limit=10)

        # §17: Not Tonight excluded from the candidate pool (Must Have wins a
        # conflict only through the explicit dialog — never silently)
        candidates = [
            analysis
            for analysis in self.analyses
            if analysis.track.track_id not in self.not_tonight_ids
        ]
        pinned = [tid for tid in self.must_have_ids if tid not in self.not_tonight_ids]
        target_count = min(target_count, len(candidates))
        if target_count < 2:
            self.generate_status.setText(
                "Not enough tracks left after Not Tonight exclusions."
            )
            return
        try:
            self.plan = build_set(
                candidates,
                weights,
                arc=arc,
                target_track_count=target_count,
                locked_positions=self.locked_positions or None,
                pinned_track_ids=pinned or None,
                planner_mode=planner_mode,
                context=context,
                preferred_styles=preferred_styles,
                bpm_min=bpm_min,
                bpm_max=bpm_max,
                novelty_mode=novelty_mode,
                history=recent,
                seed=seed_value if novelty_mode != "deterministic" else None,
            )
        except ValueError as exc:
            # §15 hard rule: impossible pins/locks fail loudly, never silently
            self.generate_status.setText(f"Constraint problem: {exc}")
            return
        store.append(
            fingerprint_plan(
                self.plan.track_order,
                ctx_hash=ctx_hash,
                seed=seed_value if novelty_mode != "deterministic" else None,
                novelty_mode=novelty_mode,
            )
        )
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
            if track.style_label:
                details.append(track.style_label)
            badges = []
            if self.locked_positions.get(position) == track_id:
                badges.append("🔒")
            elif track_id in self.must_have_ids:
                badges.append("📌")
            prefix = f"{''.join(badges)} " if badges else ""
            suffix = f"  ·  {' · '.join(details)}" if details else ""
            item = QListWidgetItem(f"{prefix}{position:>2}. {label}{suffix}", self.set_list)
            item.setData(Qt.UserRole, track_id)
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
        warning_text = f" · warning: {self.plan.warnings[0]}" if self.plan.warnings else ""
        brief_bits: list[str] = []
        if preferred_styles:
            brief_bits.append("style " + ", ".join(preferred_styles[:3]))
        if bpm_min is not None or bpm_max is not None:
            brief_bits.append(
                f"BPM {bpm_min if bpm_min is not None else '-∞'}-{bpm_max if bpm_max is not None else '+∞'}"
            )
        if context is not None and context.set_role:
            brief_bits.append(str(context.set_role))
        brief_text = f" · brief {' / '.join(brief_bits)}" if brief_bits else ""
        self.deep_upgrade_button.setEnabled(True)
        self.deep_status.setText(
            "Tip: Deep-Analyze Set Tracks separates stems for just these "
            f"{len(self.plan.track_order)} tracks — minutes, not an overnight run."
        )
        self.generate_status.setText(
            f"{len(self.plan.track_order)}-track set · mode {planner_mode} · arc {arc}{brief_text}{duration_text}"
            + (f" · mean transition score {mean:.2f}" if mean is not None else "")
            + warning_text
        )
        self._populate_review()
        self._sync_navigation()

    def _populate_review(self) -> None:
        self.review_list.clear()
        self._review_windows_cache = {}
        if self.plan is None:
            return
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}

        def name(track_id: str) -> str:
            analysis = by_id.get(track_id)
            return (analysis.track.title if analysis else None) or track_id

        for position, transition in enumerate(self.plan.transitions, start=1):
            warn = " ⚠" if transition.warnings else ""
            QListWidgetItem(
                f"{position}. {name(transition.from_track_id)}\n"
                f"    → {name(transition.to_track_id)} · {transition.transition_score:.2f}{warn}",
                self.review_list,
            )
        if self.plan.transitions:
            self.review_list.setCurrentRow(0)

    def _windows_for(self, analysis: AnalysisResult):
        cache = getattr(self, "_review_windows_cache", {})
        track_id = analysis.track.track_id
        if track_id not in cache:
            try:
                cache[track_id] = compute_windows(analysis, self._current_analysis_config())
            except Exception:
                cache[track_id] = []
        self._review_windows_cache = cache
        return cache[track_id]

    def choose_import_usb(self) -> None:
        root = QFileDialog.getExistingDirectory(self, "Choose Rekordbox USB", "/Volumes")
        if root:
            self.import_rekordbox_usb(root)

    def import_rekordbox_usb(self, root: str | Path) -> int:
        """Scan a Rekordbox USB: audio files + the DJ's verified hot cues."""
        from dancelab.ingestion.rekordbox_device import scan_device

        device_root = Path(root)
        tracks = scan_device(device_root)
        files: list[Path] = []
        for track in tracks:
            rel = track.source_path.lstrip("/")
            audio = device_root / rel
            if audio.exists():
                files.append(audio)
                self.device_cues[audio.name] = track.cues
        if not files:
            self.import_summary.setText(
                "No Rekordbox tracks with cues found on that drive "
                "(expected PIONEER/USBANLZ)."
            )
            return 0
        self._set_import_files_after_preflight(files)
        hot_total = sum(
            1 for t in tracks for c in t.cues if c.list_type == "hot"
        )
        self.import_summary.setText(
            f"{len(files)} track(s) from USB · {hot_total} of your hot cues imported "
            "— they become verified transition points."
        )
        return len(files)

    def _on_review_row_changed(self, row: int) -> None:
        if self.plan is None or row < 0 or row >= len(self.plan.transitions):
            return
        transition = self.plan.transitions[row]
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}
        analysis_a = by_id.get(transition.from_track_id)
        analysis_b = by_id.get(transition.to_track_id)
        if analysis_a is None or analysis_b is None:
            return
        windows_a = self._windows_for(analysis_a)
        windows_b = self._windows_for(analysis_b)
        self.review_widget.set_transition(
            analysis_a,
            analysis_b,
            transition,
            self.config,
            windows_a,
            windows_b,
        )
        # §13: the DJ's own hot cue near the mix-in becomes the verified B start
        from dancelab.decision.transition_cues import build_transition_cue

        user_cues_b = self.device_cues.get(
            Path(analysis_b.track.source_path or "").name
        )
        cue = build_transition_cue(
            transition,
            analysis_a=analysis_a,
            analysis_b=analysis_b,
            windows_a=windows_a,
            windows_b=windows_b,
            user_cues_b=user_cues_b,
        )
        if cue.b_cue_source == "rekordbox_hotcue" and cue.b_in_start_sec is not None:
            slot_name = chr(ord("A") + (cue.b_cue_slot or 1) - 1)
            self.review_widget.deck_b.set_user_cue(
                cue.b_in_start_sec, f"hot {slot_name}"
            )
        extra = " · ".join(cue.reasoning[:1])
        if cue.requires_manual_listen:
            extra = (extra + " · " if extra else "") + "⚠ listen before trusting this handoff"
        if extra:
            self.review_widget.header_label.setText(
                self.review_widget.header_label.text() + f"<br><i>{extra}</i>"
            )

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
        windows = _transition_windows_for_playlist(
            self.selected_analyses,
            config=self._current_analysis_config(),
        )
        xml = build_rekordbox_xml(
            self.selected_analyses,
            set_plan=self.plan,
            windows_by_track=windows,
            playlist_name=playlist_name,
            export_beatgrid=False,
        )
        self.export_path = write_rekordbox_xml(xml, self.export_path_edit.text())
        hot_cue_count = len(ET.fromstring(xml).findall("./COLLECTION/TRACK/POSITION_MARK"))
        self.export_status.setText(
            f"Exported · {self.export_path}\n"
            f"Rekordbox XML contains {hot_cue_count} hot cue marker(s).\n"
            "In Rekordbox: Preferences → Advanced → Imported Library, then right-click "
            "the playlist to import. Let Rekordbox analyze BPM/beatgrid; DanceLab exports "
            "playlist order and hot cues only."
        )

    # -------------------------------------------------------------- graph mode

    def open_graph_mode(self):
        from dancelab.contracts.node_host import get_node_host_registry
        from dancelab.host.desktop_app import NodeHostWindow

        created = self.graph_window is None
        if created:
            self.graph_window = NodeHostWindow(get_node_host_registry())
            if self.files:
                # mirror the wizard session as a wired graph so Advanced mode
                # shows what actually ran, not an empty canvas
                target_count = (
                    len(self.plan.track_order)
                    if self.plan is not None and self.plan.track_order
                    else int(self.count_spin.value())
                )
                self.graph_window.import_simple_session(
                    files=[str(path) for path in self.files],
                    analyses=self.analyses,
                    target_count=target_count,
                    arc=str(self.arc_combo.currentData()),
                    planner_mode=str(self.planner_mode_combo.currentData() or "smart"),
                    analysis_depth=_INITIAL_CHECK_DEPTH,
                    preferred_styles=self._preferred_styles(),
                    bpm_min=self._selected_bpm_min(),
                    bpm_max=self._selected_bpm_max(),
                    context_profile=self._selected_set_context(),
                    playlist_name=self.playlist_name_edit.text().strip() or "DanceLab Set",
                    output_path=self.export_path_edit.text().strip(),
                )
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

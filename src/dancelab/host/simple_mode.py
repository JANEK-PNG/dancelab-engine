"""Simple Mode — guided 5-step flow (UI/UX audit §18/§20).

The default user experience: Import Tracks → Analyze Library → Generate Set →
Review Transitions → Export. No node graph, no sensors, no telemetry in the
primary product surface.

Reuses the engine primitives directly (workflows.smart_playlist for analysis,
decision.set_builder for ordering, export.rekordbox for XML) so Simple Mode
and lower-level host tooling cannot drift apart on behavior.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QCloseEvent, QColor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
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
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dancelab.core.config import EngineConfig, load_config, load_weights
from dancelab.core.models import AnalysisResult, ContextProfile, SetPlan, SetTransition
from dancelab.core.pipeline import analyze_track
from dancelab.decision.library_profile import build_library_profile, normalize_style_list
from dancelab.decision.set_builder import build_set
from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml
from dancelab.host.analyzed_library import AnalyzedLibraryWidget
from dancelab.host.energy_timeline import SetEnergyTimelineWidget
from dancelab.host.import_dialogs import choose_audio_directories, confirm_suspicious_audio_files
from dancelab.host.mixability_map import MixabilityMapWidget
from dancelab.host.pair_review import TransitionReviewWidget, compute_windows
from dancelab.host.project import (
    PROJECT_FILE_SUFFIX,
    DanceLabProject,
    ProjectFileError,
    SimpleModeProjectState,
    load_project,
    save_project,
)
from dancelab.ingestion.rekordbox_device import DeviceCue
from dancelab.storage.repositories import FileAnalysisRepository, TrackNotFoundError
from dancelab.validation.transition_edits import (
    TransitionEditEvent,
    append_transition_edit,
    latest_transition_edits,
    transition_edits_path,
)
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


def _simple_mode_stylesheet() -> str:
    """DanceLab Simple Mode skin using the design-system token values.

    This intentionally stays conservative: clear hierarchy, large targets,
    subdued chrome, and one primary action per step.
    """
    return """
    QMainWindow, QWidget {
        background: #05070B;
        color: #F5F7FA;
        font-family: "SF Pro Text", "Inter", "IBM Plex Sans", "Helvetica Neue", "Arial";
        font-size: 14px;
    }
    QWidget#simpleRoot { background: #05070B; }
    QMenuBar {
        background: #0B0F14;
        color: #B6C0CC;
        border-bottom: 1px solid #232B36;
    }
    QMenuBar::item:selected { background: #151C25; color: #F5F7FA; }
    QMenu {
        background: #111821;
        color: #F5F7FA;
        border: 1px solid #354151;
        padding: 6px;
    }
    QMenu::item { padding: 6px 28px 6px 12px; }
    QMenu::item:selected { background: #163044; }
    QScrollArea#simpleScrollArea {
        background: transparent;
        border: none;
    }
    QScrollArea#simpleScrollArea > QWidget > QWidget {
        background: transparent;
    }
    QWidget#generateScrollContent {
        background: transparent;
    }
    QScrollBar:vertical {
        background: #05070B;
        width: 10px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #354151;
        border-radius: 5px;
        min-height: 36px;
    }
    QScrollBar::handle:vertical:hover {
        background: #5D6875;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QWidget#sidebar {
        background: #0B0F14;
        border-right: 1px solid #232B36;
    }
    QWidget#contentPane { background: #05070B; }
    QLabel { background: transparent; }
    QWidget[role="project_bar"] {
        background: #0B0F14;
        border: 1px solid #232B36;
        border-radius: 12px;
    }
    QWidget[role="nav_bar"] {
        background: #0B0F14;
        border: 1px solid #232B36;
        border-radius: 12px;
    }
    QWidget[role="card"], QWidget[role="context_panel"] {
        background: #0B0F14;
        border: 1px solid #232B36;
        border-radius: 12px;
    }
    QWidget[role="control_tile"], QWidget[role="field_group"] {
        background: #080C11;
        border: 1px solid #232B36;
        border-radius: 2px;
    }
    QWidget[role="metric_card"] {
        background: #0B0F14;
        border: 1px solid #263241;
        border-radius: 16px;
    }
    QWidget[role="metric_card"][accent="true"] {
        background: #0D141C;
        border: 1px solid #2A5E78;
    }
    QWidget[role="control_tile"][selected="true"] {
        background: #0D141C;
        border: 2px solid #5CC8FF;
    }
    QWidget[role="context_panel"] {
        background: #080C11;
    }
    QLabel[role="sidebar_brand"] {
        color: #F5F7FA;
        font-size: 18px;
        font-weight: 750;
        letter-spacing: 0.2px;
    }
    QLabel[role="sidebar_caption"] {
        color: #7E8A99;
        font-size: 12px;
    }
    QLabel[role="project_title"] {
        color: #F5F7FA;
        font-size: 15px;
        font-weight: 650;
    }
    QLabel[role="project_meta"] {
        color: #7E8A99;
        font-size: 12px;
    }
    QLabel[role="status_chip"] {
        background: #111821;
        color: #B6C0CC;
        border: 1px solid #354151;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 650;
    }
    QLabel[role="status_chip"][state="ready"] {
        color: #5CC8FF;
        border-color: #2A5E78;
    }
    QLabel[role="status_chip"][state="running"] {
        color: #B9A7FF;
        border-color: #5B4D86;
    }
    QLabel[role="status_chip"][state="complete"] {
        color: #38D996;
        border-color: #246B51;
    }
    QLabel[role="status_chip"][state="review"] {
        color: #FFB454;
        border-color: #7A5425;
    }
    QLabel[role="status_chip"][state="danger"] {
        color: #FF5A66;
        border-color: #78313A;
    }
    QLabel[role="title"] {
        font-size: 32px;
        font-weight: 650;
        color: #F5F7FA;
        letter-spacing: -0.4px;
    }
    QLabel[role="subtitle"] {
        font-size: 18px;
        font-weight: 600;
        color: #F5F7FA;
    }
    QLabel[role="section_title"] {
        font-size: 15px;
        font-weight: 700;
        color: #F5F7FA;
    }
    QLabel[role="field_label"] {
        color: #F5F7FA;
        font-size: 13px;
        font-weight: 700;
    }
    QLabel[role="field_hint"] {
        color: #7E8A99;
        font-size: 12px;
    }
    QLabel[role="metric_title"] {
        color: #7E8A99;
        font-size: 11px;
        font-weight: 750;
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }
    QLabel[role="metric_value"] {
        color: #F5F7FA;
        font-size: 24px;
        font-weight: 650;
        letter-spacing: -0.3px;
    }
    QLabel[role="metric_caption"] {
        color: #B6C0CC;
        font-size: 12px;
    }
    QLabel[role="inline_label"] {
        color: #B6C0CC;
        font-size: 13px;
        font-weight: 650;
    }
    QLabel[role="metric"] {
        color: #B6C0CC;
        font-size: 13px;
        line-height: 145%;
    }
    QLabel[role="ai_label"] {
        background: #111821;
        color: #7CF7D4;
        border: 1px solid #2B6B5D;
        border-radius: 999px;
        padding: 4px 9px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.4px;
        text-transform: uppercase;
    }
    QLabel[role="empty_state"] {
        color: #7E8A99;
        font-size: 14px;
    }
    QLabel[role="hint"] {
        color: #B6C0CC;
        line-height: 145%;
    }
    QListWidget, QTableWidget {
        background: #0B0F14;
        border: 1px solid #232B36;
        border-radius: 10px;
        color: #F5F7FA;
        padding: 6px;
        outline: none;
    }
    QListWidget#generatedSequenceList {
        background: #080C11;
        border-color: #232B36;
    }
    QListWidget#stepList {
        background: transparent;
        border: none;
        padding: 8px 0;
    }
    QListWidget#stepList::item {
        min-height: 38px;
        border-radius: 10px;
        padding: 8px 12px;
        margin: 3px 0;
    }
    QListWidget::item:selected {
        background: #111821;
        color: #F5F7FA;
    }
    QListWidget::item:hover {
        background: #151C25;
    }
    QTableWidget {
        alternate-background-color: #080C11;
        gridline-color: #232B36;
    }
    QTableWidget::item {
        padding: 6px 8px;
        border-bottom: 1px solid #151C25;
    }
    QTableWidget::item:selected {
        background: #163044;
        color: #F5F7FA;
    }
    QHeaderView::section {
        background: #111821;
        color: #B6C0CC;
        border: none;
        border-right: 1px solid #232B36;
        border-bottom: 1px solid #354151;
        padding: 8px;
        font-size: 12px;
        font-weight: 700;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: #0B0F14;
        border: 1px solid #354151;
        border-radius: 2px;
        color: #F5F7FA;
        min-height: 30px;
        padding: 4px 10px;
        selection-background-color: #2A5E78;
    }
    QSpinBox, QDoubleSpinBox {
        min-width: 64px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
        border: 1px solid #5CC8FF;
    }
    QRadioButton, QCheckBox {
        color: #B6C0CC;
        spacing: 8px;
    }
    QRadioButton::indicator, QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border-radius: 7px;
        border: 1px solid #354151;
        background: #0B0F14;
    }
    QCheckBox::indicator {
        border-radius: 4px;
    }
    QRadioButton::indicator:checked {
        background: #5CC8FF;
        border: 4px solid #0B0F14;
    }
    QCheckBox::indicator:checked {
        background: #5CC8FF;
        border-color: #5CC8FF;
    }
    QPushButton {
        background: #111821;
        color: #F5F7FA;
        border: 1px solid #354151;
        border-radius: 10px;
        font-weight: 650;
        min-height: 34px;
        padding: 7px 16px;
    }
    QPushButton:hover { background: #151C25; border-color: #5D6875; }
    QPushButton:pressed { background: #0B0F14; }
    QPushButton[role="hero"] {
        background: #5CC8FF;
        color: #05070B;
        border: 1px solid #7DD7FF;
        font-weight: 750;
        min-height: 42px;
        padding: 9px 20px;
    }
    QPushButton[role="hero"]:hover { background: #7DD7FF; }
    QPushButton[role="secondary"] {
        background: #111821;
        color: #F5F7FA;
    }
    QPushButton[role="view_switch"] {
        background: transparent;
        color: #8B96A5;
        border: 1px solid #354151;
        border-radius: 999px;
        min-height: 30px;
        padding: 4px 13px;
    }
    QPushButton[role="view_switch"][selected="true"] {
        background: #163044;
        color: #7DD7FF;
        border-color: #3B89AE;
    }
    QPushButton[role="quiet"] {
        background: transparent;
        border-color: #354151;
        color: #B6C0CC;
    }
    QPushButton[role="disclosure"] {
        background: transparent;
        border: none;
        color: #B6C0CC;
        text-align: left;
        padding: 4px 0;
        min-height: 24px;
        font-weight: 650;
    }
    QPushButton[role="disclosure"]:hover {
        color: #F5F7FA;
        background: transparent;
    }
    QPushButton[role="danger"] {
        background: #2B1117;
        border-color: #78313A;
        color: #FF8A92;
    }
    QPushButton[role="rating"] {
        min-width: 32px;
        max-width: 38px;
        padding: 5px 0;
        border-radius: 8px;
    }
    QPushButton[role="preset_card"] {
        background: #0B0F14;
        color: #B6C0CC;
        border: 1px solid #354151;
        border-radius: 2px;
        min-height: 90px;
        text-align: left;
        padding: 14px 16px;
        font-weight: 650;
    }
    QPushButton[role="preset_card"]:hover {
        background: #111821;
        border-color: #5CC8FF;
    }
    QPushButton[role="preset_card"][selected="true"] {
        background: #111821;
        color: #F5F7FA;
        border: 2px solid #5CC8FF;
    }
    QPushButton:disabled {
        background: #0B0F14;
        color: #566170;
        border-color: #232B36;
    }
    QProgressBar {
        background: #111821;
        border: none;
        border-radius: 4px;
        min-height: 8px;
        max-height: 8px;
        text-align: center;
    }
    QProgressBar::chunk {
        background: #5CC8FF;
        border-radius: 4px;
    }
    """


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
        self._analysis_thread: QThread | None = None
        self.review_analysis_depth = _INITIAL_CHECK_DEPTH
        # DJ control (§15-17): pin ≡ Must Have (cap 10, engine-exempt from
        # overuse), lock = exact slot, Not Tonight = excluded this session.
        self.must_have_ids: set[str] = set()
        self.not_tonight_ids: set[str] = set()
        self.locked_positions: dict[int, str] = {}
        # DJ's real Rekordbox cues from a device import, keyed by filename
        self.device_cues: dict[str, list] = {}
        self.project_path: Path | None = None
        self.project_name = "Untitled Set"
        self._project_dirty = False
        self._suspend_project_dirty = True
        self.autosave_path = self._default_autosave_path()

        self.setWindowTitle("DanceLab Pro")
        self.resize(1180, 760)
        self.setStyleSheet(_simple_mode_stylesheet())
        self._build_project_menu()

        root = QWidget()
        root.setObjectName("simpleRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 20, 14, 18)
        sidebar_layout.setSpacing(10)
        brand = QLabel("DanceLab Pro")
        brand.setProperty("role", "sidebar_brand")
        sidebar_layout.addWidget(brand)
        caption = QLabel("Smart set builder")
        caption.setProperty("role", "sidebar_caption")
        sidebar_layout.addWidget(caption)
        self.step_list = QListWidget()
        self.step_list.setObjectName("stepList")
        self.step_list.setSelectionMode(QListWidget.NoSelection)
        self.step_list.setFocusPolicy(Qt.NoFocus)
        for title in _STEP_TITLES:
            item = QListWidgetItem(title, self.step_list)
            item.setSizeHint(QSize(0, 44))
        sidebar_layout.addWidget(self.step_list, stretch=1)
        root_layout.addWidget(sidebar)

        right = QWidget()
        right.setObjectName("contentPane")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(34, 28, 34, 22)
        right_layout.setSpacing(18)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_welcome_page())   # 0
        self.pages.addWidget(self._build_import_page())    # 1
        self.pages.addWidget(self._build_analyze_page())   # 2
        self.pages.addWidget(self._build_generate_page())  # 3
        self.pages.addWidget(self._build_review_page())    # 4
        self.pages.addWidget(self._build_export_page())    # 5
        right_layout.addWidget(self._build_project_bar())
        right_layout.addWidget(self.pages, stretch=1)

        nav = QWidget()
        nav.setProperty("role", "nav_bar")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(12, 10, 12, 10)
        nav_layout.setSpacing(12)
        self.back_button = QPushButton("← Back")
        self.back_button.setProperty("role", "secondary")
        self.back_button.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_button)
        self.nav_hint = QLabel("")
        self.nav_hint.setProperty("role", "hint")
        nav_layout.addWidget(self.nav_hint, stretch=1)
        self.next_button = QPushButton("Next →")
        self.next_button.setProperty("role", "hero")
        self.next_button.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_button)
        right_layout.addWidget(nav)

        root_layout.addWidget(right, stretch=1)
        self.setCentralWidget(root)
        self._connect_project_dirty_signals()
        self._suspend_project_dirty = False
        self._mark_project_saved()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30_000)
        self._autosave_timer.timeout.connect(self._write_autosave)
        self._autosave_timer.start()
        self._sync_responsive_layout()
        self._sync_navigation()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().resizeEvent(event)
        self._sync_responsive_layout()

    def _build_project_bar(self) -> QWidget:
        bar = QWidget()
        bar.setProperty("role", "project_bar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(2)
        self.project_title_label = QLabel("Untitled Set")
        self.project_title_label.setProperty("role", "project_title")
        title_stack.addWidget(self.project_title_label)
        self.project_status_label = QLabel("No tracks imported yet.")
        self.project_status_label.setProperty("role", "project_meta")
        title_stack.addWidget(self.project_status_label)
        layout.addLayout(title_stack, stretch=1)

        self.mode_status_chip = QLabel("Simple Mode")
        self.mode_status_chip.setProperty("role", "status_chip")
        self.mode_status_chip.setProperty("state", "ready")
        layout.addWidget(self.mode_status_chip)

        self.save_status_chip = QLabel("Not saved")
        self.save_status_chip.setProperty("role", "status_chip")
        self.save_status_chip.setProperty("state", "review")
        layout.addWidget(self.save_status_chip)

        self.cache_status_chip = QLabel("Cache ready")
        self.cache_status_chip.setProperty("role", "status_chip")
        self.cache_status_chip.setProperty("state", "ready")
        self._refresh_cache_status()
        layout.addWidget(self.cache_status_chip)

        self.engine_status_chip = QLabel("Engine ready")
        self.engine_status_chip.setProperty("role", "status_chip")
        self.engine_status_chip.setProperty("state", "ready")
        layout.addWidget(self.engine_status_chip)

        save_button = QPushButton("Save")
        save_button.setProperty("role", "quiet")
        save_button.setToolTip("Save this Simple Mode project (Ctrl+S).")
        save_button.clicked.connect(self.save_current_project)
        layout.addWidget(save_button)
        return bar

    def _refresh_dynamic_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _set_engine_status(self, text: str, state: str = "ready") -> None:
        label = getattr(self, "engine_status_chip", None)
        if label is None:
            return
        label.setText(text)
        label.setProperty("state", state)
        self._refresh_dynamic_style(label)

    def _set_project_status(self, text: str, *, title: str | None = None) -> None:
        status = getattr(self, "project_status_label", None)
        if status is not None:
            status.setText(text)
        if title is not None and hasattr(self, "project_title_label"):
            self.project_title_label.setText(title)

    def _refresh_cache_status(self) -> None:
        label = getattr(self, "cache_status_chip", None)
        if label is None:
            return
        try:
            root = self.cache_manager().root
        except Exception:
            label.setText("Cache unknown")
            label.setToolTip("Cache location could not be resolved yet.")
            label.setProperty("state", "review")
        else:
            label.setText("Cache ready")
            label.setToolTip(f"Cache stored at: {root}")
            label.setProperty("state", "ready")
        self._refresh_dynamic_style(label)

    # ---------------------------------------------------------- project document

    @staticmethod
    def _default_autosave_path() -> Path:
        if sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support" / "DanceLab"
        else:
            root = Path.home() / ".local" / "share" / "DanceLab"
        return root / "autosave" / "simple_mode_recovery.dlproj"

    def _build_project_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
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

        self.recover_project_action = QAction("Recover Autosaved Project", self)
        self.recover_project_action.triggered.connect(self.recover_autosaved_project)
        file_menu.addAction(self.recover_project_action)
        self._refresh_recovery_action()

        file_menu.addSeparator()
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_project)
        file_menu.addAction(save_action)
        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_project_as_dialog)
        file_menu.addAction(save_as_action)

    def _connect_project_dirty_signals(self) -> None:
        for signal in (
            self.count_radio.toggled,
            self.duration_radio.toggled,
            self.count_spin.valueChanged,
            self.duration_spin.valueChanged,
            self.set_brief_combo.currentIndexChanged,
            self.style_focus_edit.textChanged,
            self.bpm_min_spin.valueChanged,
            self.bpm_max_spin.valueChanged,
            self.set_role_combo.currentIndexChanged,
            self.crowd_energy_combo.currentIndexChanged,
            self.arc_combo.currentIndexChanged,
            self.planner_mode_combo.currentIndexChanged,
            self.novelty_combo.currentIndexChanged,
            self.seed_spin.valueChanged,
            self.playlist_name_edit.textChanged,
            self.export_path_edit.textChanged,
            self.annotator_edit.textChanged,
            self.blind_check.toggled,
        ):
            signal.connect(self._mark_project_dirty)

    def _refresh_project_ui(self) -> None:
        marker = " *" if self._project_dirty else ""
        self.setWindowTitle(f"DanceLab Pro - {self.project_name}{marker}")
        title = getattr(self, "project_title_label", None)
        if title is not None:
            title.setText(f"{self.project_name}{marker}")
        chip = getattr(self, "save_status_chip", None)
        if chip is None:
            return
        if self._project_dirty:
            chip.setText("Unsaved changes")
            chip.setProperty("state", "review")
        elif self.project_path is not None:
            chip.setText("Saved")
            chip.setToolTip(str(self.project_path))
            chip.setProperty("state", "complete")
        elif self.autosave_path.exists():
            chip.setText("Recovery available")
            chip.setToolTip(str(self.autosave_path))
            chip.setProperty("state", "review")
        else:
            chip.setText("Not saved")
            chip.setProperty("state", "review")
        self._refresh_dynamic_style(chip)

    def _mark_project_dirty(self, *_args) -> None:
        if self._suspend_project_dirty:
            return
        self._project_dirty = True
        self._refresh_project_ui()

    def _mark_project_saved(self) -> None:
        self._project_dirty = False
        self._refresh_project_ui()

    def _project_from_simple_mode(self) -> DanceLabProject:
        analysis_track_ids = {
            str(analysis.track.source_path): analysis.track.track_id
            for analysis in self.analyses
            if analysis.track.source_path
        }
        cues: dict[str, list[dict]] = {}
        for name, entries in self.device_cues.items():
            cues[name] = [
                asdict(cue) if hasattr(cue, "__dataclass_fields__") else dict(cue)
                for cue in entries
            ]
        state = SimpleModeProjectState(
            source_files=[str(path) for path in self.files],
            analysis_track_ids=analysis_track_ids,
            current_step=self.current_step(),
            target_mode="duration" if self.duration_radio.isChecked() else "count",
            target_track_count=int(self.count_spin.value()),
            target_duration_hours=float(self.duration_spin.value()),
            brief_preset_id=str(self.set_brief_combo.currentData() or "custom"),
            style_focus=self.style_focus_edit.text().strip(),
            bpm_min=self._selected_bpm_min(),
            bpm_max=self._selected_bpm_max(),
            set_role=str(self.set_role_combo.currentData() or "builder"),
            crowd_energy=str(self.crowd_energy_combo.currentData() or "medium"),
            energy_arc=str(self.arc_combo.currentData() or "build"),
            planner_mode=str(self.planner_mode_combo.currentData() or "smart"),
            novelty_mode=str(self.novelty_combo.currentData() or "balanced"),
            seed=int(self.seed_spin.value()),
            must_have_ids=sorted(self.must_have_ids),
            not_tonight_ids=sorted(self.not_tonight_ids),
            locked_positions=dict(self.locked_positions),
            plan=self.plan.model_dump(mode="json") if self.plan is not None else None,
            review_analysis_depth=self.review_analysis_depth,
            playlist_name=self.playlist_name_edit.text().strip() or "DanceLab Smart Set",
            export_path=self.export_path_edit.text().strip(),
            annotator=self.annotator_edit.text().strip(),
            blind_review=self.blind_check.isChecked(),
            device_cues=cues,
        )
        return DanceLabProject(
            name=self.project_name,
            workspace="simple",
            simple_mode=state,
        )

    def new_project(self) -> None:
        if not self._confirm_project_transition():
            return
        self._suspend_project_dirty = True
        try:
            self.project_path = None
            self.project_name = "Untitled Set"
            self.must_have_ids.clear()
            self.not_tonight_ids.clear()
            self.locked_positions.clear()
            self.device_cues.clear()
            self.set_import_files([])
            self.count_radio.setChecked(True)
            self.count_spin.setValue(10)
            self.duration_spin.setValue(1.0)
            self.set_brief_combo.setCurrentIndex(
                max(0, self.set_brief_combo.findData("custom"))
            )
            self.style_focus_edit.clear()
            self.bpm_min_spin.setValue(0.0)
            self.bpm_max_spin.setValue(0.0)
            self._set_combo_value(self.set_role_combo, "builder")
            self._set_combo_value(self.crowd_energy_combo, "medium")
            self._set_combo_value(self.arc_combo, "build")
            self._set_combo_value(self.planner_mode_combo, "smart")
            self._set_combo_value(self.novelty_combo, "balanced")
            self.seed_spin.setValue(0)
            self.playlist_name_edit.setText("DanceLab Smart Set")
            self.export_path_edit.setText(str(Path.home() / "dancelab_set.xml"))
            self.annotator_edit.clear()
            self.blind_check.setChecked(False)
            self.go_to_step(1)
        finally:
            self._suspend_project_dirty = False
        self._clear_autosave()
        self._set_project_status("No tracks imported yet.")
        self._mark_project_saved()

    def save_current_project(self) -> Path | None:
        if self.project_path is None:
            return self.save_project_as_dialog()
        return self._save_project_to_path(self.project_path)

    def save_project_as_dialog(self) -> Path | None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save DanceLab Project",
            str(Path.home() / f"{self.project_name}{PROJECT_FILE_SUFFIX}"),
            f"DanceLab Project (*{PROJECT_FILE_SUFFIX})",
        )
        if not selected:
            return None
        return self._save_project_to_path(Path(selected))

    def _save_project_to_path(self, path: str | Path) -> Path:
        destination = Path(path)
        self.project_name = destination.stem or self.project_name
        saved = save_project(self._project_from_simple_mode(), destination)
        self.project_path = saved
        self._remember_recent_project(saved)
        self._clear_autosave()
        self._mark_project_saved()
        self._set_project_status(f"Project saved at {saved}")
        return saved

    def open_project_dialog(self) -> None:
        if not self._confirm_project_transition():
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open DanceLab Project",
            str(Path.home()),
            f"DanceLab Project (*{PROJECT_FILE_SUFFIX})",
        )
        if selected:
            self.load_project_from_path(selected)

    def load_project_from_path(self, path: str | Path) -> bool:
        try:
            project = load_project(path)
            if project.workspace != "simple" or project.simple_mode is None:
                raise ProjectFileError(
                    "This legacy project does not contain a guided DanceLab session."
                )
            self._apply_simple_project(project)
        except ProjectFileError as exc:
            self._show_project_error(str(exc))
            return False
        self.project_path = Path(path)
        self.project_name = project.name or self.project_path.stem
        self._remember_recent_project(self.project_path)
        self._clear_autosave()
        self._mark_project_saved()
        self._set_project_status(
            f"Project loaded · {len(self.analyses)} cached analysis result(s) restored"
        )
        return True

    def _apply_simple_project(self, project: DanceLabProject) -> None:
        state = project.simple_mode
        if state is None:
            raise ProjectFileError("Simple Mode state is missing from the project.")
        self._suspend_project_dirty = True
        try:
            self.project_name = project.name
            self.must_have_ids = set(state.must_have_ids)
            self.not_tonight_ids = set(state.not_tonight_ids)
            self.locked_positions = dict(state.locked_positions)
            try:
                self.device_cues = {
                    name: [DeviceCue(**cue) for cue in cues]
                    for name, cues in state.device_cues.items()
                }
            except TypeError as exc:
                raise ProjectFileError(f"Saved Rekordbox cue data is malformed: {exc}") from exc
            self.set_import_files([Path(path) for path in state.source_files])

            preset_index = self.set_brief_combo.findData(state.brief_preset_id)
            self.set_brief_combo.setCurrentIndex(max(0, preset_index))
            self.style_focus_edit.setText(state.style_focus)
            self.bpm_min_spin.setValue(state.bpm_min or 0.0)
            self.bpm_max_spin.setValue(state.bpm_max or 0.0)
            self._set_combo_value(self.set_role_combo, state.set_role)
            self._set_combo_value(self.crowd_energy_combo, state.crowd_energy)
            self._set_combo_value(self.arc_combo, state.energy_arc)
            self._set_combo_value(self.planner_mode_combo, state.planner_mode)
            self._set_combo_value(self.novelty_combo, state.novelty_mode)
            self.seed_spin.setValue(state.seed)
            self.count_spin.setValue(state.target_track_count)
            self.duration_spin.setValue(state.target_duration_hours)
            self.duration_radio.setChecked(state.target_mode == "duration")
            self.count_radio.setChecked(state.target_mode != "duration")
            self.playlist_name_edit.setText(state.playlist_name)
            if state.export_path:
                self.export_path_edit.setText(state.export_path)
            self.annotator_edit.setText(state.annotator)
            self.blind_check.setChecked(state.blind_review)
            self.review_analysis_depth = state.review_analysis_depth

            missing_cache = self._restore_project_analyses(state)
            self.plan = None
            if state.plan is not None:
                try:
                    candidate_plan = SetPlan.model_validate(state.plan)
                except Exception as exc:
                    raise ProjectFileError(f"Saved set plan is malformed: {exc}") from exc
                available = {analysis.track.track_id for analysis in self.analyses}
                if all(track_id in available for track_id in candidate_plan.track_order):
                    self.plan = candidate_plan
                    by_id = {
                        analysis.track.track_id: analysis for analysis in self.analyses
                    }
                    self.selected_analyses = [
                        by_id[track_id] for track_id in self.plan.track_order
                    ]
                    self._populate_set_list_from_plan()
                    self.deep_upgrade_button.setEnabled(True)
                    self._sync_generate_controls_visibility()
                    self._populate_review()

            target_step = state.current_step
            if not self.files:
                target_step = min(target_step, 1)
            elif not self.analyses:
                target_step = min(target_step, 2)
            elif self.plan is None:
                target_step = min(target_step, 3)
            self.go_to_step(target_step)
            if missing_cache:
                self.analyze_status.setText(
                    f"Project loaded · {len(self.analyses)} cached · "
                    f"{missing_cache} need Initial Check"
                )
        finally:
            self._suspend_project_dirty = False
        self._update_library_profile_summary()
        self._refresh_dj_control_ui()
        self._sync_navigation()

    def _restore_project_analyses(self, state: SimpleModeProjectState) -> int:
        repository = FileAnalysisRepository(self.config.paths.processed_dir)
        loaded: list[AnalysisResult] = []
        missing = 0
        for source in state.source_files:
            track_id = state.analysis_track_ids.get(source)
            if not track_id:
                missing += 1
                continue
            try:
                loaded.append(repository.get(track_id))
            except TrackNotFoundError:
                missing += 1
        self.analyses = loaded
        self.failures = []
        self.analysis_library.set_analyses(loaded)
        self.mixability_map.set_analyses(loaded)
        self.analysis_library.set_track_states(
            must_have_ids=self.must_have_ids,
            not_tonight_ids=self.not_tonight_ids,
        )
        self.analyze_list.clear()
        by_source = {
            str(analysis.track.source_path): analysis for analysis in loaded
        }
        for source in state.source_files:
            analysis = by_source.get(source)
            if analysis is None:
                QListWidgetItem(f"○  {Path(source).name} · Initial Check needed", self.analyze_list)
                continue
            details = [
                f"{analysis.track.bpm_estimate:.2f} BPM"
                if analysis.track.bpm_estimate is not None
                else "BPM unknown",
                analysis.track.key_estimate or "key unknown",
            ]
            QListWidgetItem(
                f"✓  {Path(source).name} · {' · '.join(details)} · from cache",
                self.analyze_list,
            )
        if loaded:
            self.analysis_results_stack.setCurrentWidget(self.analysis_library)
            self.analyze_progress.setMaximum(max(1, len(state.source_files)))
            self.analyze_progress.setValue(len(loaded))
            self.analyze_status.setText(
                f"Project loaded · {len(loaded)} analysis result(s) restored from cache."
            )
        else:
            self.analysis_results_stack.setCurrentWidget(self.analyze_list)
        return missing

    def _populate_set_list_from_plan(self) -> None:
        self.set_list.clear()
        if self.plan is None:
            self.energy_timeline.set_plan(None, self.analyses)
            self._show_generate_empty_state()
            return
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}
        for position, track_id in enumerate(self.plan.track_order, start=1):
            analysis = by_id.get(track_id)
            if analysis is None:
                continue
            track = analysis.track
            details = [
                value
                for value in (
                    f"{track.bpm_estimate:.2f} BPM" if track.bpm_estimate else None,
                    track.key_estimate,
                    track.style_label,
                )
                if value
            ]
            badges: list[str] = []
            if self.locked_positions.get(position) == track_id:
                badges.append("🔒")
            elif track_id in self.must_have_ids:
                badges.append("📌")
            prefix = f"{''.join(badges)} " if badges else ""
            suffix = f"  ·  {' · '.join(details)}" if details else ""
            item = QListWidgetItem(
                f"{prefix}{position:>2}. {track.title or track_id}{suffix}",
                self.set_list,
            )
            item.setData(Qt.UserRole, track_id)
        self.energy_timeline.set_plan(self.plan, self.analyses)
        if self.set_list.count():
            self.set_list.setCurrentRow(0)

    def _select_set_track_from_timeline(self, track_id: str) -> None:
        for row in range(self.set_list.count()):
            item = self.set_list.item(row)
            if item.data(Qt.UserRole) == track_id:
                self.set_list.setCurrentRow(row)
                self.set_list.scrollToItem(item)
                return

    def _confirm_project_transition(self) -> bool:
        if not self._project_dirty or not self.isVisible():
            return True
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self)
        box.setWindowTitle("Save changes?")
        box.setText(f"Save changes to {self.project_name} before continuing?")
        save_button = box.addButton("Save", QMessageBox.AcceptRole)
        discard_button = box.addButton("Discard", QMessageBox.DestructiveRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()
        if box.clickedButton() is save_button:
            return self.save_current_project() is not None
        return box.clickedButton() is discard_button

    def _show_project_error(self, message: str) -> None:
        self._set_project_status(message)
        self._set_engine_status("Project error", "danger")
        if self.isVisible():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Cannot open project", message)

    def _write_autosave(self) -> Path | None:
        if not self._project_dirty:
            return None
        try:
            saved = save_project(self._project_from_simple_mode(), self.autosave_path)
        except OSError as exc:
            self._set_project_status(f"Autosave failed: {exc}")
            return None
        self._refresh_recovery_action()
        return saved

    def recover_autosaved_project(self) -> bool:
        if not self.autosave_path.exists():
            self._show_project_error("No Simple Mode autosave is available.")
            return False
        if not self._confirm_project_transition():
            return False
        try:
            project = load_project(self.autosave_path)
            if project.workspace != "simple" or project.simple_mode is None:
                raise ProjectFileError("Autosave does not contain a Simple Mode session.")
            self._apply_simple_project(project)
        except ProjectFileError as exc:
            self._show_project_error(str(exc))
            return False
        self.project_path = None
        self.project_name = f"{project.name} (Recovered)"
        self._mark_project_dirty()
        self._set_project_status("Recovered autosave · use Save As to keep it")
        return True

    def _clear_autosave(self) -> None:
        self.autosave_path.unlink(missing_ok=True)
        self._refresh_recovery_action()

    def _refresh_recovery_action(self) -> None:
        action = getattr(self, "recover_project_action", None)
        if action is not None:
            action.setEnabled(self.autosave_path.exists())

    def _recent_projects(self) -> list[str]:
        stored = QSettings("DanceLab", "SimpleMode").value("recent_projects", [])
        if isinstance(stored, str):
            stored = [stored]
        return [str(path) for path in (stored or []) if str(path).strip()]

    def _remember_recent_project(self, path: Path) -> None:
        recents = [str(path)] + [
            recent for recent in self._recent_projects() if recent != str(path)
        ]
        QSettings("DanceLab", "SimpleMode").setValue("recent_projects", recents[:8])
        self._refresh_recent_projects_menu()

    def _open_recent_project(self, path: str) -> None:
        if self._confirm_project_transition():
            self.load_project_from_path(path)

    def _refresh_recent_projects_menu(self) -> None:
        menu = getattr(self, "recent_projects_menu", None)
        if menu is None:
            return
        menu.clear()
        recents = self._recent_projects()
        if not recents:
            empty = QAction("(no recent projects)", self)
            empty.setEnabled(False)
            menu.addAction(empty)
            return
        for recent in recents:
            action = QAction(recent, self)
            action.triggered.connect(
                lambda checked=False, project_path=recent: self._open_recent_project(project_path)
            )
            menu.addAction(action)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        if not self._confirm_project_transition():
            event.ignore()
            return
        mixability_map = getattr(self, "mixability_map", None)
        if mixability_map is not None:
            mixability_map.shutdown()
        if not self._project_dirty:
            self._clear_autosave()
        super().closeEvent(event)

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
        folder_button.setProperty("role", "hero")
        folder_button.clicked.connect(self.choose_import_folder)
        buttons.addWidget(folder_button)
        files_button = QPushButton("Choose Files…")
        files_button.setProperty("role", "secondary")
        files_button.clicked.connect(self.choose_import_files)
        buttons.addWidget(files_button)
        usb_button = QPushButton("Import from USB…")
        usb_button.setProperty("role", "secondary")
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
        remove_selected_button.setProperty("role", "quiet")
        remove_selected_button.setToolTip(
            "Remove the highlighted track(s) from this import. Files on disk are untouched."
        )
        remove_selected_button.clicked.connect(self.remove_selected_imports)
        manage_row.addWidget(remove_selected_button)
        clear_button = QPushButton("Clear Import")
        clear_button.setProperty("role", "danger")
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
        self.stop_button.setProperty("role", "danger")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.confirm_stop_processing)
        analyze_row.addWidget(self.stop_button)
        analyze_row.addStretch(1)
        layout.addLayout(analyze_row)

        self.analyze_progress = QProgressBar()
        self.analyze_progress.setValue(0)
        self.analyze_progress.setTextVisible(False)
        layout.addWidget(self.analyze_progress)
        self.analyze_status = QLabel("Not started.")
        self.analyze_status.setProperty("role", "hint")
        layout.addWidget(self.analyze_status)

        # Per-track checklist: each row is checked off as the engine finishes
        # it, and the current row shows the REAL pipeline stage (key detection,
        # beat tracking, ...) reported by the engine — not an animation.
        self.analysis_results_stack = QStackedWidget()
        self.analyze_list = QListWidget()
        self.analysis_results_stack.addWidget(self.analyze_list)

        self.analysis_library = AnalyzedLibraryWidget()
        self.analysis_library.must_have_requested.connect(
            self._on_library_must_have_requested
        )
        self.analysis_library.not_tonight_requested.connect(
            self._on_library_not_tonight_requested
        )
        self.analysis_results_stack.addWidget(self.analysis_library)
        self.analysis_results_stack.setCurrentWidget(self.analyze_list)
        layout.addWidget(self.analysis_results_stack, stretch=1)
        return page

    def _build_generate_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        header = QLabel("Step 3 — Generate set sequence")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel(
            "Build a practical set brief first. DanceLab will use it to rank tracks, "
            "order transitions, and produce a reviewable sequence."
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setObjectName("simpleScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_content = QWidget()
        scroll_content.setObjectName("generateScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(0)

        workspace = QHBoxLayout()
        workspace.setSpacing(18)
        scroll_layout.addLayout(workspace)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        main_column = QVBoxLayout()
        main_column.setSpacing(14)
        workspace.addLayout(main_column, stretch=1)

        overview_row = QHBoxLayout()
        overview_row.setSpacing(12)
        self.library_metric_value, self.library_metric_caption = self._add_metric_card(
            overview_row,
            "Library",
            "No tracks",
            "Import and run Initial Check",
        )
        self.target_metric_value, self.target_metric_caption = self._add_metric_card(
            overview_row,
            "Target",
            "10 tracks",
            "Exact set size",
            accent=True,
        )
        self.brief_metric_value, self.brief_metric_caption = self._add_metric_card(
            overview_row,
            "Brief",
            "Custom",
            "No style or tempo constraint",
        )
        main_column.addLayout(overview_row)

        preset_card = self._make_card()
        preset_card.setMinimumHeight(150)
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(18, 16, 18, 16)
        preset_layout.setSpacing(12)
        preset_layout.addWidget(self._section_label("Choose a starting brief"))
        preset_hint = QLabel("Pick a preset, then adjust style, tempo and energy below.")
        preset_hint.setProperty("role", "hint")
        preset_layout.addWidget(preset_hint)

        self.set_brief_combo = QComboBox()
        for preset in _SET_BRIEF_PRESETS:
            self.set_brief_combo.addItem(str(preset["label"]), str(preset["id"]))
        self.set_brief_combo.setToolTip(
            "Fast event brief. Presets only fill the controls below; you can edit them before Generate."
        )
        self.set_brief_combo.setVisible(False)

        preset_buttons = QHBoxLayout()
        preset_buttons.setSpacing(10)
        self.preset_card_buttons: dict[str, QPushButton] = {}
        for preset in _SET_BRIEF_PRESETS:
            button = QPushButton(self._preset_tile_text(preset))
            button.setProperty("role", "preset_card")
            button.setProperty("selected", "false")
            button.clicked.connect(
                lambda checked=False, preset_id=str(preset["id"]): self._select_set_brief_preset(preset_id)
            )
            preset_buttons.addWidget(button)
            self.preset_card_buttons[str(preset["id"])] = button
        preset_layout.addLayout(preset_buttons)
        preset_layout.addWidget(self.set_brief_combo)
        main_column.addWidget(preset_card)

        self.generate_inline_action_card = self._make_card()
        inline_action_layout = QHBoxLayout(self.generate_inline_action_card)
        inline_action_layout.setContentsMargins(18, 14, 18, 14)
        inline_action_layout.setSpacing(12)
        inline_action_text = QVBoxLayout()
        inline_action_text.setContentsMargins(0, 0, 0, 0)
        inline_action_text.setSpacing(4)
        inline_action_text.addWidget(self._section_label("Next action"))
        self.generate_inline_status = QLabel("Ready when the brief matches your set.")
        self.generate_inline_status.setProperty("role", "metric")
        self.generate_inline_status.setWordWrap(True)
        inline_action_text.addWidget(self.generate_inline_status)
        inline_action_layout.addLayout(inline_action_text, stretch=1)
        self.generate_inline_button = QPushButton("▶ Generate Set")
        self.generate_inline_button.setProperty("role", "hero")
        self.generate_inline_button.clicked.connect(self.generate_set)
        inline_action_layout.addWidget(self.generate_inline_button)
        self.generate_inline_action_card.setVisible(False)
        main_column.addWidget(self.generate_inline_action_card)

        brief_card = self._make_card()
        brief_card.setMinimumHeight(390)
        brief_layout = QVBoxLayout(brief_card)
        brief_layout.setContentsMargins(18, 16, 18, 16)
        brief_layout.setSpacing(14)

        length_title = self._section_label("Set length")
        brief_layout.addWidget(length_title)
        length_tiles = QHBoxLayout()
        length_tiles.setSpacing(10)

        self.count_length_tile = self._make_control_tile(selected=True)
        count_tile_layout = QVBoxLayout(self.count_length_tile)
        count_tile_layout.setContentsMargins(14, 12, 14, 12)
        count_tile_layout.setSpacing(8)
        self.count_radio = QRadioButton("Track count")
        self.count_radio.setChecked(True)
        count_tile_layout.addWidget(self.count_radio)
        count_tile_layout.addWidget(self._field_hint("Best when you need exactly 5, 10, 15 or 20 tracks."))
        count_value_row = QHBoxLayout()
        count_value_row.setSpacing(8)
        count_value_row.addWidget(self._inline_label("Tracks"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(MIN_PLAYLIST_TRACKS, 500)
        self.count_spin.setValue(10)
        self._configure_plain_spinbox(self.count_spin)
        count_value_row.addWidget(self.count_spin)
        count_value_row.addStretch(1)
        count_tile_layout.addLayout(count_value_row)
        length_tiles.addWidget(self.count_length_tile)

        self.duration_length_tile = self._make_control_tile(selected=False)
        duration_tile_layout = QVBoxLayout(self.duration_length_tile)
        duration_tile_layout.setContentsMargins(14, 12, 14, 12)
        duration_tile_layout.setSpacing(8)
        self.duration_radio = QRadioButton("Target duration")
        duration_tile_layout.addWidget(self.duration_radio)
        duration_tile_layout.addWidget(self._field_hint("DanceLab estimates track count from your analyzed library."))
        duration_value_row = QHBoxLayout()
        duration_value_row.setSpacing(8)
        duration_value_row.addWidget(self._inline_label("Length"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.25, 24.0)
        self.duration_spin.setSingleStep(0.25)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSuffix(" h")
        self._configure_plain_spinbox(self.duration_spin)
        self.duration_spin.setToolTip(
            "Track count is estimated from the average length of your analyzed tracks."
        )
        duration_value_row.addWidget(self.duration_spin)
        duration_value_row.addStretch(1)
        duration_tile_layout.addLayout(duration_value_row)
        length_tiles.addWidget(self.duration_length_tile)
        brief_layout.addLayout(length_tiles)

        def sync_length_inputs() -> None:
            self.count_spin.setEnabled(self.count_radio.isChecked())
            self.duration_spin.setEnabled(self.duration_radio.isChecked())
            self._set_control_tile_selected(self.count_length_tile, self.count_radio.isChecked())
            self._set_control_tile_selected(self.duration_length_tile, self.duration_radio.isChecked())

        self.count_radio.toggled.connect(sync_length_inputs)
        self.duration_radio.toggled.connect(sync_length_inputs)
        self.count_radio.toggled.connect(lambda _: self._update_generate_context_panel())
        self.duration_radio.toggled.connect(lambda _: self._update_generate_context_panel())
        self.count_spin.valueChanged.connect(lambda _: self._update_generate_context_panel())
        self.duration_spin.valueChanged.connect(lambda _: self._update_generate_context_panel())
        sync_length_inputs()

        brief_layout.addWidget(self._section_label("Musical intent"))
        style_group = self._make_field_group()
        style_group_layout = QVBoxLayout(style_group)
        style_group_layout.setContentsMargins(14, 12, 14, 12)
        style_group_layout.setSpacing(8)
        style_group_layout.addWidget(self._field_label("Style focus"))
        style_group_layout.addWidget(self._field_hint("Optional. Use source-backed genre tags when available."))
        self.style_focus_edit = QLineEdit()
        self.style_focus_edit.setPlaceholderText("e.g. bass, uk bass, garage, breaks")
        self.style_focus_edit.setToolTip(
            "Comma-separated style/genre focus. Uses source-backed file genre tags when available."
        )
        style_group_layout.addWidget(self.style_focus_edit)
        brief_layout.addWidget(style_group)

        intent_row = QHBoxLayout()
        intent_row.setSpacing(10)
        bpm_group = self._make_field_group()
        bpm_group_layout = QVBoxLayout(bpm_group)
        bpm_group_layout.setContentsMargins(14, 12, 14, 12)
        bpm_group_layout.setSpacing(8)
        bpm_group_layout.addWidget(self._field_label("Tempo window"))
        bpm_group_layout.addWidget(self._field_hint("Leave open for full library range."))
        bpm_inputs = QHBoxLayout()
        bpm_inputs.setSpacing(8)
        self.bpm_min_spin = QDoubleSpinBox()
        self.bpm_min_spin.setRange(0.0, 300.0)
        self.bpm_min_spin.setDecimals(1)
        self.bpm_min_spin.setSingleStep(1.0)
        self.bpm_min_spin.setSpecialValueText("No min")
        self._configure_plain_spinbox(self.bpm_min_spin)
        bpm_inputs.addWidget(self.bpm_min_spin)
        bpm_inputs.addWidget(self._inline_label("to"))
        self.bpm_max_spin = QDoubleSpinBox()
        self.bpm_max_spin.setRange(0.0, 300.0)
        self.bpm_max_spin.setDecimals(1)
        self.bpm_max_spin.setSingleStep(1.0)
        self.bpm_max_spin.setSpecialValueText("No max")
        self._configure_plain_spinbox(self.bpm_max_spin)
        bpm_inputs.addWidget(self.bpm_max_spin)
        bpm_inputs.addStretch(1)
        bpm_group_layout.addLayout(bpm_inputs)
        intent_row.addWidget(bpm_group)

        context_group = self._make_field_group()
        context_group_layout = QVBoxLayout(context_group)
        context_group_layout.setContentsMargins(14, 12, 14, 12)
        context_group_layout.setSpacing(8)
        context_group_layout.addWidget(self._field_label("Set context"))
        context_group_layout.addWidget(self._field_hint("Role and crowd energy guide sequencing pressure."))
        context_inputs = QHBoxLayout()
        context_inputs.setSpacing(8)
        self.set_role_combo = QComboBox()
        for role_value, role_label in _SET_ROLE_CHOICES:
            self.set_role_combo.addItem(role_label, role_value)
        context_inputs.addWidget(self.set_role_combo, stretch=1)
        self.crowd_energy_combo = QComboBox()
        for energy_value, energy_label in _CROWD_ENERGY_CHOICES:
            self.crowd_energy_combo.addItem(energy_label, energy_value)
        context_inputs.addWidget(self.crowd_energy_combo, stretch=1)
        context_group_layout.addLayout(context_inputs)
        intent_row.addWidget(context_group, stretch=1)
        brief_layout.addLayout(intent_row)

        self.advanced_options_toggle = QPushButton("Advanced options ▸")
        self.advanced_options_toggle.setCheckable(True)
        self.advanced_options_toggle.setProperty("role", "disclosure")
        brief_layout.addWidget(self.advanced_options_toggle)

        self.advanced_options_widget = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_options_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Energy arc:"))
        self.arc_combo = QComboBox()
        for arc_value, arc_label in _ARC_CHOICES:
            self.arc_combo.addItem(arc_label, arc_value)
        controls.addWidget(self.arc_combo)
        controls.addSpacing(14)
        controls.addWidget(QLabel("Preference:"))
        self.planner_mode_combo = QComboBox()
        for mode_value, mode_label in _PLANNER_CHOICES:
            self.planner_mode_combo.addItem(mode_label, mode_value)
        controls.addWidget(self.planner_mode_combo)
        controls.addStretch(1)
        advanced_layout.addLayout(controls)

        novelty_row = QHBoxLayout()
        novelty_row.setSpacing(10)
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
        advanced_layout.addLayout(novelty_row)
        self.advanced_options_widget.setVisible(False)
        self.advanced_options_toggle.toggled.connect(self._set_advanced_options_visible)
        brief_layout.addWidget(self.advanced_options_widget)
        main_column.addWidget(brief_card)

        self.result_card = self._make_card()
        self.result_card.setMinimumHeight(250)
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setContentsMargins(18, 16, 18, 16)
        result_layout.setSpacing(12)
        result_header = QHBoxLayout()
        result_header.addWidget(self._section_label("Explore and shape the set"))
        result_header.addStretch(1)

        self.sequence_view_button = QPushButton("Set Sequence")
        self.sequence_view_button.setProperty("role", "view_switch")
        self.sequence_view_button.clicked.connect(
            lambda: self._set_generate_result_view("sequence")
        )
        result_header.addWidget(self.sequence_view_button)
        self.mix_map_view_button = QPushButton("Mixability Map")
        self.mix_map_view_button.setProperty("role", "view_switch")
        self.mix_map_view_button.setToolTip(
            "Optional visual exploration. Recommend Next ranks candidates; "
            "EdgeDecision validates the top six pairs."
        )
        self.mix_map_view_button.clicked.connect(
            lambda: self._set_generate_result_view("mixability")
        )
        result_header.addWidget(self.mix_map_view_button)
        result_layout.addLayout(result_header)

        self.generate_result_stack = QStackedWidget()
        sequence_widget = QWidget()
        sequence_layout = QVBoxLayout(sequence_widget)
        sequence_layout.setContentsMargins(0, 0, 0, 0)
        sequence_layout.setSpacing(10)
        sequence_header = QHBoxLayout()
        sequence_header.addWidget(self._section_label("Generated sequence"))
        sequence_header.addStretch(1)
        self.deep_upgrade_button = QPushButton("Deep-Analyze Set Tracks")
        self.deep_upgrade_button.setProperty("role", "secondary")
        self.deep_upgrade_button.setToolTip(
            "Run Demucs stem-aware analysis ONLY on the tracks in this set. "
            "Already-deep tracks are reused from cache."
        )
        self.deep_upgrade_button.setEnabled(False)
        self.deep_upgrade_button.clicked.connect(self.toggle_deep_upgrade)
        sequence_header.addWidget(self.deep_upgrade_button)
        sequence_layout.addLayout(sequence_header)

        self.energy_timeline = SetEnergyTimelineWidget()
        self.energy_timeline.track_selected.connect(
            self._select_set_track_from_timeline
        )
        sequence_layout.addWidget(self.energy_timeline)

        self.set_list = QListWidget()
        self.set_list.setObjectName("generatedSequenceList")
        self.set_list.setMinimumHeight(210)
        self.set_list.currentRowChanged.connect(self.energy_timeline.select_position)
        sequence_layout.addWidget(self.set_list, stretch=1)

        self.dj_controls_widget = QWidget()
        dj_row = QHBoxLayout(self.dj_controls_widget)
        dj_row.setContentsMargins(0, 0, 0, 0)
        dj_row.setSpacing(10)
        pin_button = QPushButton("📌 Pin")
        pin_button.setProperty("role", "secondary")
        pin_button.setToolTip("Must Have — always in the set; engine picks the slot. Max 10.")
        pin_button.clicked.connect(self._on_pin_clicked)
        dj_row.addWidget(pin_button)
        lock_button = QPushButton("🔒 Lock")
        lock_button.setProperty("role", "secondary")
        lock_button.setToolTip("Keep this track exactly here through regenerates.")
        lock_button.clicked.connect(self._on_lock_clicked)
        dj_row.addWidget(lock_button)
        rest_button = QPushButton("🌙 Rest")
        rest_button.setProperty("role", "quiet")
        rest_button.setToolTip("Not Tonight — keep out of this set. Never deletes the file.")
        rest_button.clicked.connect(self._on_rest_clicked)
        dj_row.addWidget(rest_button)
        self.dj_control_status = QLabel("")
        self.dj_control_status.setProperty("role", "hint")
        dj_row.addWidget(self.dj_control_status, stretch=1)
        self.dj_controls_widget.setVisible(False)
        sequence_layout.addWidget(self.dj_controls_widget)

        self.deep_status = QLabel("")
        self.deep_status.setProperty("role", "hint")
        sequence_layout.addWidget(self.deep_status)
        self.generate_result_stack.addWidget(sequence_widget)

        self.mixability_map = MixabilityMapWidget()
        self.mixability_map.find_requested.connect(self._run_mixability_map)
        self.mixability_map.must_have_requested.connect(
            self._on_library_must_have_requested
        )
        self.mixability_map.ranking_completed.connect(
            self._on_mixability_ranking_completed
        )
        self.generate_result_stack.addWidget(self.mixability_map)
        result_layout.addWidget(self.generate_result_stack, stretch=1)
        self._set_generate_result_view("sequence")
        main_column.addWidget(self.result_card, stretch=1)

        context_panel = QWidget()
        self.generate_context_panel = context_panel
        context_panel.setProperty("role", "context_panel")
        context_panel.setMinimumWidth(280)
        context_panel.setMaximumWidth(350)
        context_panel.setMinimumHeight(520)
        context_layout = QVBoxLayout(context_panel)
        context_layout.setContentsMargins(18, 16, 18, 16)
        context_layout.setSpacing(12)
        context_layout.addWidget(self._section_label("Session brief"))

        self.library_profile_label = QLabel(
            "Analyze tracks first. Then this panel will show detected styles and how many tracks match the brief."
        )
        self.library_profile_label.setProperty("role", "metric")
        self.library_profile_label.setWordWrap(True)
        context_layout.addWidget(self.library_profile_label)

        self.generate_context_label = QLabel(
            "Choose a brief, then generate a set. The sequence will appear on the left."
        )
        self.generate_context_label.setProperty("role", "metric")
        self.generate_context_label.setWordWrap(True)
        context_layout.addWidget(self.generate_context_label)

        context_layout.addSpacing(6)
        context_layout.addWidget(self._section_label("Next action"))
        self.engine_recommendation_label = QLabel("Engine recommendation")
        self.engine_recommendation_label.setProperty("role", "ai_label")
        context_layout.addWidget(self.engine_recommendation_label, alignment=Qt.AlignLeft)
        self.generate_status = QLabel("Ready when the brief matches your set.")
        self.generate_status.setProperty("role", "metric")
        self.generate_status.setWordWrap(True)
        context_layout.addWidget(self.generate_status)

        self.generate_button = QPushButton("▶ Generate Set")
        self.generate_button.setProperty("role", "hero")
        self.generate_button.clicked.connect(self.generate_set)
        context_layout.addWidget(self.generate_button)
        context_layout.addStretch(1)
        workspace.addWidget(context_panel, alignment=Qt.AlignTop)

        self.set_brief_combo.currentIndexChanged.connect(self._apply_set_brief_preset)
        self.style_focus_edit.textChanged.connect(lambda _: self._update_library_profile_summary())
        self.bpm_min_spin.valueChanged.connect(lambda _: self._update_library_profile_summary())
        self.bpm_max_spin.valueChanged.connect(lambda _: self._update_library_profile_summary())
        self.set_role_combo.currentIndexChanged.connect(lambda _: self._update_library_profile_summary())
        self.crowd_energy_combo.currentIndexChanged.connect(lambda _: self._update_library_profile_summary())
        self._apply_set_brief_preset()
        self._show_generate_empty_state()
        self._sync_generate_controls_visibility()
        return page

    def _preset_tile_text(self, preset: dict[str, object]) -> str:
        preset_id = str(preset["id"])
        if preset_id == "calm_uk_bass":
            return "Calm UK/Bass\n≤135 BPM · continuation"
        if preset_id == "warmup_deep":
            return "Warm-up deep/soft\n≤124 BPM · low pressure"
        return "Custom\nNo style or tempo constraint"

    def _make_card(self) -> QWidget:
        card = QWidget()
        card.setProperty("role", "card")
        return card

    def _add_metric_card(
        self,
        row: QHBoxLayout,
        title: str,
        value: str,
        caption: str,
        *,
        accent: bool = False,
    ) -> tuple[QLabel, QLabel]:
        card = QWidget()
        card.setProperty("role", "metric_card")
        card.setProperty("accent", "true" if accent else "false")
        card.setMinimumHeight(104)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setProperty("role", "metric_title")
        layout.addWidget(title_label)
        value_label = QLabel(value)
        value_label.setProperty("role", "metric_value")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)
        caption_label = QLabel(caption)
        caption_label.setProperty("role", "metric_caption")
        caption_label.setWordWrap(True)
        layout.addWidget(caption_label)
        layout.addStretch(1)
        row.addWidget(card, stretch=1)
        return value_label, caption_label

    def _make_control_tile(self, *, selected: bool = False) -> QWidget:
        tile = QWidget()
        tile.setProperty("role", "control_tile")
        tile.setProperty("selected", "true" if selected else "false")
        tile.setMinimumHeight(96)
        return tile

    def _make_field_group(self) -> QWidget:
        group = QWidget()
        group.setProperty("role", "field_group")
        group.setMinimumHeight(96)
        return group

    def _set_control_tile_selected(self, tile: QWidget, selected: bool) -> None:
        tile.setProperty("selected", "true" if selected else "false")
        self._refresh_dynamic_style(tile)

    def _configure_plain_spinbox(self, spinbox: QAbstractSpinBox) -> None:
        spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "section_title")
        return label

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "field_label")
        return label

    def _field_hint(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "field_hint")
        label.setWordWrap(True)
        return label

    def _inline_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "inline_label")
        return label

    def _show_generate_empty_state(self) -> None:
        if not hasattr(self, "set_list") or self.plan is not None:
            return
        timeline = getattr(self, "energy_timeline", None)
        if timeline is not None:
            timeline.set_plan(None, self.analyses)
        self.set_list.clear()
        item = QListWidgetItem("Generate a set to see the proposed sequence.")
        item.setForeground(QBrush(QColor("#7E8A99")))
        item.setFlags(Qt.NoItemFlags)
        self.set_list.addItem(item)

    def _set_generate_result_view(self, view: str) -> None:
        """Switch the optional exploration surface without changing workflow state."""
        is_map = view == "mixability"
        stack = getattr(self, "generate_result_stack", None)
        if stack is not None:
            stack.setCurrentIndex(1 if is_map else 0)
        self._generate_result_view = "mixability" if is_map else "sequence"
        for name, selected in (
            ("sequence_view_button", not is_map),
            ("mix_map_view_button", is_map),
        ):
            button = getattr(self, name, None)
            if button is not None:
                button.setProperty("selected", "true" if selected else "false")
                self._refresh_dynamic_style(button)
        self._sync_responsive_layout()

    def _run_mixability_map(self, track_id: str) -> None:
        started = self.mixability_map.begin_ranking(
            track_id,
            weights=load_weights(self.config.weights_file),
            context=self._selected_set_context(),
            arc_mode=str(self.arc_combo.currentData() or "build"),
            excluded_track_ids=self.not_tonight_ids,
        )
        if started:
            self._set_engine_status("Ranking mix ideas", "running")
            self._set_project_status(
                "Mixability Map is ranking candidates with Recommend Next and EdgeDecision"
            )

    def _on_mixability_ranking_completed(self, success: bool, message: str) -> None:
        self._set_engine_status(
            "Mix ideas ready" if success else "Mixability needs review",
            "complete" if success else "danger",
        )
        self._set_project_status(message)

    def _select_set_brief_preset(self, preset_id: str) -> None:
        index = self.set_brief_combo.findData(preset_id)
        if index >= 0:
            self.set_brief_combo.setCurrentIndex(index)
        self._refresh_preset_cards()

    def _refresh_preset_cards(self) -> None:
        buttons = getattr(self, "preset_card_buttons", {})
        if not buttons:
            return
        selected = str(self.set_brief_combo.currentData() or "custom")
        for preset_id, button in buttons.items():
            button.setProperty("selected", "true" if preset_id == selected else "false")
            self._refresh_dynamic_style(button)

    def _set_advanced_options_visible(self, visible: bool) -> None:
        self.advanced_options_widget.setVisible(visible)
        self.advanced_options_toggle.setText(
            "Advanced options ▾" if visible else "Advanced options ▸"
        )

    def _sync_generate_controls_visibility(self) -> None:
        controls = getattr(self, "dj_controls_widget", None)
        if controls is not None:
            controls.setVisible(self.plan is not None)
        result_card = getattr(self, "result_card", None)
        if result_card is not None:
            result_card.setVisible(bool(self.analyses) or self.plan is not None)
        map_button = getattr(self, "mix_map_view_button", None)
        if map_button is not None:
            map_button.setEnabled(len(self.analyses) >= 2)
        self._sync_responsive_layout()

    def _sync_responsive_layout(self) -> None:
        """Apply desktop breakpoints without letting Qt squeeze controls below usable size."""
        context_panel = getattr(self, "generate_context_panel", None)
        inline_action = getattr(self, "generate_inline_action_card", None)
        if context_panel is None or inline_action is None:
            return
        compact_generate_page = self.width() < 1320
        map_visible = getattr(self, "_generate_result_view", "sequence") == "mixability"
        context_panel.setVisible(not compact_generate_page and not map_visible)
        inline_action.setVisible(compact_generate_page and not map_visible)

    def _set_generate_status(self, text: str) -> None:
        for attr in ("generate_status", "generate_inline_status"):
            label = getattr(self, attr, None)
            if label is not None:
                label.setText(text)

    def _refresh_generate_metric_cards(self) -> None:
        library_value = getattr(self, "library_metric_value", None)
        target_value = getattr(self, "target_metric_value", None)
        brief_value = getattr(self, "brief_metric_value", None)
        if library_value is None or target_value is None or brief_value is None:
            return

        if self.analyses:
            library_value.setText(f"{len(self.analyses)} analyzed")
            bpms = [
                analysis.track.bpm_estimate
                for analysis in self.analyses
                if analysis.track.bpm_estimate is not None
            ]
            if bpms:
                self.library_metric_caption.setText(f"BPM {min(bpms):.0f}-{max(bpms):.0f}")
            else:
                self.library_metric_caption.setText("BPM pending")
        elif self.files:
            library_value.setText(f"{len(self.files)} imported")
            self.library_metric_caption.setText("Initial Check pending")
        else:
            library_value.setText("No tracks")
            self.library_metric_caption.setText("Import and run Initial Check")

        count = self._target_track_count_preview()
        target_value.setText(f"{count} tracks")
        if hasattr(self, "duration_radio") and self.duration_radio.isChecked():
            self.target_metric_caption.setText(f"Estimated from {self.duration_spin.value():g} h")
        else:
            self.target_metric_caption.setText("Exact set size")

        styles = self._preferred_styles()
        bpm_min = self._selected_bpm_min()
        bpm_max = self._selected_bpm_max()
        if styles:
            brief_value.setText(", ".join(styles[:2]))
        else:
            preset_label = str(self.set_brief_combo.currentText()).split("<=")[0].strip()
            brief_value.setText(preset_label or "Custom")
        bpm_text = (
            f"{bpm_min if bpm_min is not None else 'open'}-{bpm_max if bpm_max is not None else 'open'} BPM"
            if bpm_min is not None or bpm_max is not None
            else "No tempo limit"
        )
        role_text = str(self.set_role_combo.currentText()) if hasattr(self, "set_role_combo") else "Set"
        self.brief_metric_caption.setText(f"{bpm_text} · {role_text}")

    def _update_generate_context_panel(self) -> None:
        label = getattr(self, "generate_context_label", None)
        if label is None:
            return
        count = self._target_track_count_preview()
        styles = self._preferred_styles()
        bpm_min = self._selected_bpm_min()
        bpm_max = self._selected_bpm_max()
        role = str(self.set_role_combo.currentText()) if hasattr(self, "set_role_combo") else ""
        energy = str(self.crowd_energy_combo.currentText()) if hasattr(self, "crowd_energy_combo") else ""
        bpm_text = (
            f"{bpm_min if bpm_min is not None else 'no min'}–{bpm_max if bpm_max is not None else 'no max'} BPM"
        )
        style_text = ", ".join(styles[:4]) if styles else "no style filter"
        label.setText(
            f"Target: {count} track(s)\n"
            f"Style: {style_text}\n"
            f"Tempo: {bpm_text}\n"
            f"Role: {role}\n"
            f"Energy: {energy}"
        )
        self._refresh_generate_metric_cards()

    def _target_track_count_preview(self) -> int:
        if not hasattr(self, "duration_radio") or not self.duration_radio.isChecked():
            return int(self.count_spin.value()) if hasattr(self, "count_spin") else MIN_PLAYLIST_TRACKS
        try:
            return estimate_track_count_for_duration(
                self.analyses, self.duration_spin.value() * 60.0
            )
        except ValueError:
            return int(self.count_spin.value()) if hasattr(self, "count_spin") else MIN_PLAYLIST_TRACKS

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
        self._mark_project_dirty()

    def _on_rest_clicked(self) -> None:
        track_id = self._selected_set_track_id()
        if track_id is None:
            return
        if self.toggle_not_tonight(track_id) == "conflict":
            self._conflict_dialog(track_id)
        self._refresh_dj_control_ui()
        self._mark_project_dirty()

    def _on_lock_clicked(self) -> None:
        track_id = self._selected_set_track_id()
        if track_id is not None:
            self.toggle_lock_here(track_id)
        self._refresh_dj_control_ui()
        self._mark_project_dirty()

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
        library = getattr(self, "analysis_library", None)
        if library is not None:
            library.set_track_states(
                must_have_ids=self.must_have_ids,
                not_tonight_ids=self.not_tonight_ids,
            )

    def _on_library_must_have_requested(self, track_id: str) -> None:
        """Apply the existing planner constraint from the analyzed library."""
        from PySide6.QtWidgets import QMessageBox

        if track_id in self.must_have_ids:
            self.remove_must_have(track_id)
        else:
            outcome = self.toggle_must_have(track_id)
            if outcome == "limit":
                QMessageBox.information(
                    self,
                    "Must Have limit",
                    f"You can only have {self.MUST_HAVE_LIMIT} Must Have tracks.",
                )
            elif outcome == "conflict":
                self._conflict_dialog(track_id)
        self._refresh_dj_control_ui()
        self._mark_project_dirty()

    def _on_library_not_tonight_requested(self, track_id: str) -> None:
        """Apply the existing session exclusion from the analyzed library."""
        if self.toggle_not_tonight(track_id) == "conflict":
            self._conflict_dialog(track_id)
        self._refresh_dj_control_ui()
        self._mark_project_dirty()

    # ------------------------------------------------- deep-on-demand upgrade

    def toggle_deep_upgrade(self) -> None:
        thread = self._analysis_thread
        if thread is not None and thread.isRunning():
            thread.request_stop()
            self.deep_status.setText("Stopping after current track…")
            self._set_engine_status("Stopping job", "review")
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
            self._set_engine_status("Low disk space", "danger")
            return
        self.deep_upgrade_button.setText("Stop Deep Analysis")
        self.deep_status.setText(f"Deep-analyzing {len(files)} set track(s)…")
        self._set_engine_status("Deep analysis running", "running")
        self._set_project_status(
            f"Deep-analyzing {len(files)} selected set track(s) · stems on demand"
        )
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
            self._set_engine_status("Deep analysis failed", "danger")
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
        self._set_engine_status(
            "Deep data ready" if not was_stopped else "Deep analysis stopped",
            "complete" if not was_stopped and not failures else "review",
        )
        self._set_project_status(
            f"{len(upgraded)} deep track(s) ready{fail_note}{note}"
        )
        self.analysis_library.set_analyses(self.analyses)
        self.mixability_map.set_analyses(self.analyses)
        self.energy_timeline.set_plan(self.plan, self.analyses)
        self.analysis_library.set_track_states(
            must_have_ids=self.must_have_ids,
            not_tonight_ids=self.not_tonight_ids,
        )
        self._mark_project_dirty()

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Step 4 — Review transitions")
        header.setProperty("role", "title")
        layout.addWidget(header)
        hint = QLabel(
            "Pick a transition, audition one sample-accurate A→B render, and compare "
            "phrase-locked fader/EQ models. Source decks keep the editable waveform, "
            "8-beat quantized cueing and stem isolation. Preview templates are not "
            "DJ-validated ground truth."
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
        self.review_widget.annotationCommitted.connect(self._record_transition_annotation)
        split.addWidget(self.review_widget, stretch=1)
        layout.addLayout(split, stretch=1)

        # Validation Mode (weight-calibration study): blind rating so engine
        # scores can't anchor the rater; A/B decks stay fully usable.
        validation_row = QHBoxLayout()
        self.blind_check = QCheckBox("Blind rating (hide engine scores)")
        self.blind_check.toggled.connect(self._on_blind_toggled)
        validation_row.addWidget(self.blind_check)
        validation_row.addWidget(QLabel("Rater:"))
        self.annotator_edit = QLineEdit("")
        self.annotator_edit.setPlaceholderText("your name")
        self.annotator_edit.setMaximumWidth(140)
        validation_row.addWidget(self.annotator_edit)
        validation_row.addWidget(QLabel("Rate:"))
        self.rating_buttons: list[QPushButton] = []
        for value in (1, 2, 3, 4, 5):
            button = QPushButton(str(value))
            button.setProperty("role", "rating")
            button.setMaximumWidth(36)
            button.clicked.connect(lambda checked=False, v=value: self.rate_current_transition(v))
            validation_row.addWidget(button)
            self.rating_buttons.append(button)
        self.rating_comment = QLineEdit("")
        self.rating_comment.setPlaceholderText("optional comment")
        validation_row.addWidget(self.rating_comment, stretch=1)
        layout.addLayout(validation_row)
        self.validation_status = QLabel("")
        self.validation_status.setProperty("role", "hint")
        layout.addWidget(self.validation_status)
        return page

    # -------------------------------------------- validation mode (§ weights)

    def _on_blind_toggled(self, enabled: bool) -> None:
        self.review_widget.blind = enabled
        row = max(self.review_list.currentRow(), 0)
        given = getattr(self, "_ratings_given", set())
        self._populate_review()  # list rows re-render without scores in blind
        self._ratings_given = given  # toggling blind must not wipe progress
        if self.review_list.count():
            self.review_list.setCurrentRow(min(row, self.review_list.count() - 1))

    def _validation_csv_path(self) -> Path:
        annotator = (self.annotator_edit.text().strip() or "anonymous").replace(" ", "_")
        root = Path(self.cache_manager().root) / "validation"
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{annotator}_transition_ratings.csv"

    def _transition_edits_csv_path(self) -> Path:
        return transition_edits_path(
            self.cache_manager().root,
            self.annotator_edit.text(),
        )

    @staticmethod
    def _optional_float(value) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _optional_int(value) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    def _record_transition_annotation(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        row = self.review_list.currentRow()
        if self.plan is None or row < 0 or row >= len(self.plan.transitions):
            self.validation_status.setText("Select a transition before editing its waveform.")
            return
        transition = self.plan.transitions[row]
        try:
            event = TransitionEditEvent(
                pair_id=f"{transition.from_track_id}__{transition.to_track_id}",
                track_id_a=transition.from_track_id,
                track_id_b=transition.to_track_id,
                deck=str(payload.get("deck", "")),
                track_id=str(payload.get("track_id", "")),
                action=str(payload.get("action", "")),
                marker_type=str(payload.get("marker_type", "")),
                marker_label=str(payload.get("marker_label", "")),
                marker_name=str(payload.get("marker_name", "")),
                reference_source=str(payload.get("reference_source", "")),
                reference_start_sec=self._optional_float(payload.get("reference_start_sec")),
                reference_end_sec=self._optional_float(payload.get("reference_end_sec")),
                reference_start_beat=self._optional_int(payload.get("reference_start_beat")),
                reference_end_beat=self._optional_int(payload.get("reference_end_beat")),
                user_start_sec=float(payload.get("user_start_sec", 0.0)),
                user_end_sec=self._optional_float(payload.get("user_end_sec")),
                user_start_beat=self._optional_int(payload.get("user_start_beat")),
                user_end_beat=self._optional_int(payload.get("user_end_beat")),
                track_duration_sec=self._optional_float(payload.get("track_duration_sec")),
                quantize_grid_beats=int(payload.get("quantize_grid_beats", 0)),
                beatgrid_reliable=bool(payload.get("beatgrid_reliable", False)),
                engine_pair_score=float(transition.transition_score),
                annotator=self.annotator_edit.text().strip() or "anonymous",
            )
            saved = append_transition_edit(self._transition_edits_csv_path(), event)
        except (OSError, TypeError, ValueError) as exc:
            self.validation_status.setText(f"Could not save waveform correction: {exc}")
            return
        if saved.action == "transition_region_set":
            detail = f"{saved.user_start_sec:.1f}–{saved.user_end_sec:.1f}s"
        else:
            detail = f"Hot Cue {saved.marker_label} → {saved.user_start_sec:.1f}s"
        self.validation_status.setText(
            f"Saved Deck {saved.deck} correction {detail} · "
            f"{self._transition_edits_csv_path().name}"
        )

    def _restore_transition_annotations(self, transition: SetTransition) -> None:
        pair_id = f"{transition.from_track_id}__{transition.to_track_id}"
        latest = latest_transition_edits(self._transition_edits_csv_path(), pair_id)
        for (deck_code, action, label), row in latest.items():
            deck = self.review_widget.deck_a if deck_code == "A" else self.review_widget.deck_b
            if action == "transition_region_set":
                start = self._optional_float(row.get("user_start_sec"))
                end = self._optional_float(row.get("user_end_sec"))
                if start is not None and end is not None:
                    deck.restore_transition_selection(start, end)
            elif action in {"hot_cue_moved", "hot_cue_set"} and label:
                sec = self._optional_float(row.get("user_start_sec"))
                if sec is not None:
                    deck.restore_hot_cue(label, sec)

    def rate_current_transition(self, rating: int) -> None:
        import csv

        row = self.review_list.currentRow()
        if self.plan is None or row < 0 or row >= len(self.plan.transitions):
            self.validation_status.setText("Select a transition first.")
            return
        transition = self.plan.transitions[row]
        path = self._validation_csv_path()
        is_new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if is_new:
                writer.writerow([
                    "pair_id", "track_id_a", "track_id_b", "engine_score",
                    "dj_mixability_rating", "comment", "blind",
                ])
            writer.writerow([
                f"{transition.from_track_id}__{transition.to_track_id}",
                transition.from_track_id,
                transition.to_track_id,
                f"{transition.transition_score:.4f}",
                rating,
                self.rating_comment.text().strip(),
                int(self.blind_check.isChecked()),
            ])
        self.rating_comment.clear()
        self._ratings_given = getattr(self, "_ratings_given", set())
        self._ratings_given.add(row)
        total = len(self.plan.transitions)
        done = len(self._ratings_given)
        if done < total:
            self.validation_status.setText(
                f"Rated {done}/{total} · saved to {path.name}"
            )
            if row + 1 < total:
                self.review_list.setCurrentRow(row + 1)  # flow: next transition
        else:
            self.validation_status.setText(
                f"Rated {done}/{total} · {self._validation_report(path)}"
            )

    def _validation_report(self, csv_path: Path) -> str:
        """Honest engine-vs-human agreement from this rater's file."""
        import csv

        from dancelab.validation.dj_decision_metrics import (
            kendall_tau,
            rating_correlation,
        )

        engine_scores: list[float] = []
        ratings: list[float] = []
        with open(csv_path, encoding="utf-8") as handle:
            for record in csv.DictReader(handle):
                engine_scores.append(float(record["engine_score"]))
                ratings.append(float(record["dj_mixability_rating"]))
        rho = rating_correlation(engine_scores, ratings)
        tau = kendall_tau(engine_scores, ratings)
        rho_text = f"ρ={rho:.2f}" if rho is not None else "ρ=n/a (low n or no variance)"
        tau_text = f"τ={tau:.2f}" if tau is not None else "τ=n/a"
        return f"engine vs you: {rho_text} · {tau_text} (n={len(ratings)}) — {csv_path}"

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
        browse_button.setProperty("role", "secondary")
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
            return True, "Start a new guided set."
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
            if wizard_step == step:
                marker = "● "
                item.setForeground(QBrush(QColor("#F5F7FA")))
                item.setBackground(QBrush(QColor("#111821")))
            elif done and wizard_step < step:
                marker = "✓ "
                item.setForeground(QBrush(QColor("#38D996")))
                item.setBackground(QBrush(QColor(0, 0, 0, 0)))
            else:
                marker = "○ "
                item.setForeground(QBrush(QColor("#7E8A99")))
                item.setBackground(QBrush(QColor(0, 0, 0, 0)))
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
        self.selected_analyses = []
        self.import_list.clear()
        for path in self.files:
            QListWidgetItem(path.name, self.import_list)
        self.import_summary.setText(
            f"{len(self.files)} track(s) ready to analyze." if self.files else "No tracks yet."
        )
        if self.files:
            self._set_project_status(
                f"{len(self.files)} track(s) imported · Initial Check pending",
                title="New Set",
            )
            self._set_engine_status("Engine ready", "ready")
        else:
            self._set_project_status("No tracks imported yet.", title="Untitled Set")
            self._set_engine_status("Engine ready", "ready")
        self.analyze_progress.setValue(0)
        if self.files:
            self.analyze_status.setText(
                f"Initial Check not started. {self._analysis_estimate_text(_INITIAL_CHECK_DEPTH)}"
            )
        else:
            self.analyze_status.setText("Not started.")
        self.analyze_list.clear()
        self.analysis_library.set_analyses([])
        self.mixability_map.set_analyses([])
        self.analysis_results_stack.setCurrentWidget(self.analyze_list)
        self.deep_upgrade_button.setEnabled(False)
        self.deep_status.setText("")
        self._show_generate_empty_state()
        self._set_generate_result_view("sequence")
        self._sync_generate_controls_visibility()
        self._update_library_profile_summary()
        self._sync_navigation()
        self._mark_project_dirty()

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
        self._set_project_status(
            f"{len(self.files)} track(s) queued for Initial Check",
            title=self.project_title_label.text() if hasattr(self, "project_title_label") else None,
        )
        self._set_engine_status("Initial Check running", "running")
        self._refresh_cache_status()

        self.analysis_results_stack.setCurrentWidget(self.analyze_list)
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
        self._set_engine_status("Stopping job", "review")
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
            self._set_engine_status("Analysis failed", "danger")
            self._set_project_status("Initial Check failed. Review the error and run again.")
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
            self._set_engine_status("Stopped", "review")
            self._set_project_status(
                f"{len(self.analyses)} analyzed · {pending} pending · cache preserved"
            )
        else:
            self.analyze_progress.setValue(self.analyze_progress.maximum())
            self.analyze_status.setText(
                f"Initial Check complete · {len(self.analyses)} track(s) · {len(self.failures)} failed."
            )
            state = "complete" if not self.failures else "review"
            self._set_engine_status("Initial Check complete", state)
            self._set_project_status(
                f"{len(self.analyses)} analyzed · {len(self.failures)} failed · ready to generate"
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
        self.analysis_library.set_analyses(self.analyses)
        self.mixability_map.set_analyses(self.analyses)
        self.analysis_library.set_track_states(
            must_have_ids=self.must_have_ids,
            not_tonight_ids=self.not_tonight_ids,
        )
        if self.analyses:
            self.analysis_results_stack.setCurrentWidget(self.analysis_library)
        self._sync_generate_controls_visibility()
        self._update_library_profile_summary()
        self._sync_navigation()
        self._mark_project_dirty()

    def _target_track_count(self) -> int | None:
        """Resolve the requested set length to a track count, or None + status."""
        if self.duration_radio.isChecked():
            try:
                count = estimate_track_count_for_duration(
                    self.analyses, self.duration_spin.value() * 60.0
                )
            except ValueError as exc:
                self._set_generate_status(str(exc))
                return None
            self._set_generate_status(
                f"≈{count} track(s) fit {self.duration_spin.value():g} h "
                "(from your tracks' average length)."
            )
            return count
        count = int(self.count_spin.value())
        if len(self.analyses) < count:
            self._set_generate_status(
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

    def _apply_set_brief_preset(self, *_args) -> None:
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
        self._refresh_preset_cards()
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
            self._update_generate_context_panel()
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
        self._update_generate_context_panel()

    def generate_set(self) -> None:
        if not self.analyses:
            self._set_generate_status("Analyze tracks first.")
            self._set_engine_status("Waiting for analysis", "review")
            return
        target_count = self._target_track_count()
        if target_count is None:
            self._set_engine_status("Set length needs review", "review")
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
            self._set_generate_status(
                "Not enough tracks left after Not Tonight exclusions."
            )
            self._set_engine_status("Not enough tracks", "review")
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
            self._set_generate_status(f"Constraint problem: {exc}")
            self._set_engine_status("Set constraints blocked", "review")
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
        self._set_generate_result_view("sequence")
        self._populate_set_list_from_plan()
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
        self._sync_generate_controls_visibility()
        self.deep_status.setText(
            "Tip: Deep-Analyze Set Tracks separates stems for just these "
            f"{len(self.plan.track_order)} tracks — minutes, not an overnight run."
        )
        self._set_generate_status(
            f"{len(self.plan.track_order)}-track set · mode {planner_mode} · arc {arc}{brief_text}{duration_text}"
            + (f" · mean transition score {mean:.2f}" if mean is not None else "")
            + warning_text
        )
        playlist_title = (
            self.playlist_name_edit.text().strip()
            if hasattr(self, "playlist_name_edit") and self.playlist_name_edit.text().strip()
            else "DanceLab Smart Set"
        )
        self._set_project_status(
            f"{len(self.plan.track_order)}-track sequence generated · review transitions next",
            title=playlist_title,
        )
        self._set_engine_status("Set generated", "complete")
        self._mark_project_dirty()
        self._populate_review()
        self._sync_navigation()

    def _populate_review(self) -> None:
        self._ratings_given = set()
        self.review_list.clear()
        self._review_windows_cache = {}
        if self.plan is None:
            return
        by_id = {analysis.track.track_id: analysis for analysis in self.analyses}

        def name(track_id: str) -> str:
            analysis = by_id.get(track_id)
            return (analysis.track.title if analysis else None) or track_id

        for position, transition in enumerate(self.plan.transitions, start=1):
            blind = getattr(self, "blind_check", None) is not None and self.blind_check.isChecked()
            warn = " ⚠" if (transition.warnings and not blind) else ""
            score_text = "" if blind else f" · {transition.transition_score:.2f}"
            QListWidgetItem(
                f"{position}. {name(transition.from_track_id)}\n"
                f"    → {name(transition.to_track_id)}{score_text}{warn}",
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
        user_cues_a = self.device_cues.get(
            Path(analysis_a.track.source_path or "").name,
            [],
        )
        user_cues_b = self.device_cues.get(
            Path(analysis_b.track.source_path or "").name,
            [],
        )
        self.review_widget.deck_a.set_hot_cues(user_cues_a)
        self.review_widget.deck_b.set_hot_cues(user_cues_b)
        # §13: the DJ's own hot cue near the mix-in becomes the verified B start
        from dancelab.decision.transition_cues import build_transition_cue

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
                cue.b_in_start_sec, slot_name
            )
        self._restore_transition_annotations(transition)
        if self.blind_check.isChecked():
            return  # blind: no engine commentary; the DJ's own cue stays usable
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
            self._set_engine_status("Waiting for set", "review")
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
        self._set_project_status(
            f"Exported Rekordbox XML · {hot_cue_count} hot cue marker(s)",
            title=playlist_name,
        )
        self._set_engine_status("Export complete", "complete")

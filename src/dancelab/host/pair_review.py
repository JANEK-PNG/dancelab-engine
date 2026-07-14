"""Transition review tool: A/B decks, song structure, stems, beat sync.

Everything shown here is engine data, not decoration:
- structure strips paint the ACTUAL segments (intro/build/drop/breakdown/
  groove/outro) and transition windows the analysis produced;
- beat sync computes the playback rate from the two tracks' estimated BPMs
  (half/double-time aware, same octave-folding as the decision layer);
- quantize snaps seeks to the track's 8-beat phrase grid;
- stem isolation runs real source separation (demucs when installed) or an
  honest DSP fallback (HPSS harmonic/percussive split + low-pass bass) and is
  labeled accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    QRunnable,
    QRectF,
    Qt,
    QThread,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dancelab.core.config import EngineConfig, load_weights
from dancelab.core.models import (
    AnalysisResult,
    SetTransition,
    TransitionWindow,
    TransitionWindowInput,
    WindowType,
)
from dancelab.decision._common import nearest_bpm_variant
from dancelab.decision.tempo_adjustment import (
    TempoPlan,
    build_balanced_tempo_plan,
    nearest_octave_candidate,
)
from dancelab.decision.transition_windows import (
    detect_transition_windows,
    rank_windows_for_role,
)
from dancelab.export.rekordbox import track_windows_as_cues
from dancelab.host.preview_timing import snap_to_grid
from dancelab.host.transition_simulation import (
    DEFAULT_DURATION_BEATS,
    DEFAULT_GRID_BEATS,
    PROFILE_OPTIONS,
    TRANSITION_DURATION_OPTIONS,
    TransitionDurationPlan,
    TransitionEnvelope,
    TransitionRenderResult,
    TransitionWaveform,
    build_transition_envelope,
    plan_transition_duration,
    render_transition_preview,
    sample_transition_envelope,
    transition_preview_cache_path,
)
from dancelab.host.waveform_cache import WaveformData, load_or_build_waveform
from dancelab.ingestion.rekordbox_device import DeviceCue
from dancelab.ingestion.loader import load_audio

SEGMENT_COLORS = {
    "intro": "#4a6fa5",
    "build": "#b08a3e",
    "drop": "#c05050",
    "breakdown": "#7a5aa0",
    "groove": "#4d7443",
    "outro": "#3f7f8a",
    "unknown": "#3a3b3f",
}

WINDOW_COLORS = {
    WindowType.mix_in: "#7cb96b",
    WindowType.mix_out: "#e2a856",
    WindowType.bridge: "#8ab4d8",
    WindowType.reset: "#c987c9",
}

CUE_COLORS = (
    "#38D996",
    "#5CC8FF",
    "#FFB454",
    "#B9A7FF",
    "#FF7BA8",
    "#57D9D0",
    "#FF6B72",
    "#C4D76B",
)


@dataclass
class WaveformCueMarker:
    label: str
    name: str
    time_sec: float
    source: str
    reference_time_sec: float
    color: str


# ------------------------------------------------------------- pure helpers


def beat_sync_rate(bpm_master: float | None, bpm_other: float | None) -> float | None:
    """Playback rate that brings `other` to the master tempo.

    Half/double-time aware (a 65 BPM read of a 130 BPM track syncs at ~1.0,
    not 2.0). None when either tempo is unknown — never guess a rate.
    Clamped to [0.5, 2.0]: outside that a "sync" is not a usable preview.
    """
    if not bpm_master or not bpm_other:
        return None
    effective_other = nearest_bpm_variant(bpm_master, bpm_other)
    if effective_other is None or effective_other <= 0:
        return None
    rate = float(bpm_master) / float(effective_other)
    return float(min(2.0, max(0.5, rate)))


def best_window(
    windows: list[TransitionWindow],
    window_type: WindowType,
    *,
    analysis: AnalysisResult | None = None,
    transition_beats: int | None = None,
) -> TransitionWindow | None:
    track = analysis.track if analysis is not None else None
    beatgrid = analysis.beatgrid if analysis is not None else None
    bpm = (track.bpm_estimate if track is not None else None) or (
        beatgrid.bpm if beatgrid is not None else None
    )
    ranked = rank_windows_for_role(
        windows,
        window_type,
        track_duration_sec=track.duration_sec if track is not None else None,
        bpm=bpm,
        transition_beats=transition_beats,
        outgoing_guard_beats=DEFAULT_GRID_BEATS,
    )
    return ranked[0] if ranked else None


def waveform_envelope_from_features(analysis: AnalysisResult) -> list[float]:
    """Normalized RMS envelope for Rekordbox-style visual timing.

    The engine does not persist raw waveform peaks yet, but analysis features
    already carry frame-level RMS. That is enough for a truthful visual
    amplitude envelope without re-reading large audio files during review.
    """
    values = [
        float(frame.rms)
        for frame in analysis.features
        if frame.rms is not None and np.isfinite(frame.rms)
    ]
    if not values:
        return []
    arr = np.asarray(values, dtype=np.float64)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi <= lo:
        return [0.35 for _ in values]
    arr = (arr - lo) / (hi - lo)
    return [float(max(0.04, min(1.0, value))) for value in arr]


def compute_windows(analysis: AnalysisResult, config: EngineConfig, top_k: int = 6):
    weights = load_weights(config.weights_file)
    return detect_transition_windows(
        TransitionWindowInput(
            track_id=analysis.track.track_id,
            segments=analysis.segments,
            feature_frames=analysis.features,
            beatgrid=analysis.beatgrid,
        ),
        weights.transition_window,
        top_k=top_k,
    ).windows


# ---------------------------------------------------------- stem rendering


def _demucs_available() -> bool:
    try:
        import demucs.pretrained  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def render_preview_stems(
    source_path: str,
    track_id: str,
    config: EngineConfig,
    out_root: str | Path,
) -> dict[str, Path]:
    """Write isolated-stem wavs for preview; returns {label: wav_path}.

    demucs installed → true 4-stem separation (Vocals/Drums/Bass/Other).
    Otherwise an honest DSP fallback: HPSS Harmonic/Percussive split plus a
    low-pass Bass band — labeled as such, never sold as full separation.
    Results are cached on disk per track.
    """
    import soundfile as sf

    out_dir = Path(out_root).expanduser() / track_id
    manifest = out_dir / ".complete"
    if manifest.exists():
        return {
            wav.stem.replace("_", " ").title(): wav
            for wav in sorted(out_dir.glob("*.wav"))
        }
    out_dir.mkdir(parents=True, exist_ok=True)

    signal = load_audio(source_path, config)
    samples = np.asarray(signal.samples, dtype=np.float32)
    if samples.ndim > 1:
        samples = samples.mean(axis=0)
    sr = signal.sample_rate
    rendered: dict[str, Path] = {}

    if _demucs_available():
        from dancelab.stems.extractor import extract_stems
        from dancelab.stems.workflow import stem_enabled_config

        bundle = extract_stems(signal, track_id, stem_enabled_config(config))
        if bundle is not None and bundle.channels:
            for stem_type, stem_signal in bundle.channels.items():
                stem = np.asarray(stem_signal.samples, dtype=np.float32)
                if stem.ndim > 1:
                    stem = stem.mean(axis=0)
                path = out_dir / f"{stem_type.value}.wav"
                sf.write(path, stem, sr)
                rendered[stem_type.value.title()] = path

    if not rendered:
        import librosa
        from scipy.signal import butter, sosfiltfilt

        harmonic, percussive = librosa.effects.hpss(samples)
        for label, audio in (("harmonic", harmonic), ("percussive", percussive)):
            path = out_dir / f"{label}.wav"
            sf.write(path, audio.astype(np.float32), sr)
            rendered[label.title()] = path

        low, high = config.bands.get("bass", [20.0, 150.0])
        sos = butter(4, high, btype="lowpass", fs=sr, output="sos")
        bass = sosfiltfilt(sos, samples).astype(np.float32)
        path = out_dir / "bass_band.wav"
        sf.write(path, bass, sr)
        rendered["Bass Band"] = path

    manifest.write_text("ok", encoding="utf-8")
    return rendered


class _StemWorker(QObject):
    finished = Signal(object)  # dict[label, str path] | error string

    def __init__(self, source_path: str, track_id: str, config: EngineConfig, out_root: str):
        super().__init__()
        self._args = (source_path, track_id, config, out_root)

    def run(self) -> None:
        try:
            rendered = render_preview_stems(*self._args)
        except Exception as exc:
            self.finished.emit(str(exc))
        else:
            self.finished.emit({label: str(path) for label, path in rendered.items()})


class _WaveformWorkerSignals(QObject):
    finished = Signal(object)


class _WaveformWorker(QRunnable):
    """Decode/cache one waveform without blocking the Qt event loop."""

    def __init__(
        self,
        token: int,
        source_path: str,
        track_id: str,
        cache_dir: str,
    ) -> None:
        super().__init__()
        self.token = token
        self.source_path = source_path
        self.track_id = track_id
        self.cache_dir = cache_dir
        self.signals = _WaveformWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            data, cache_path, built_now = load_or_build_waveform(
                self.source_path,
                self.track_id,
                self.cache_dir,
            )
        except Exception as exc:
            self.signals.finished.emit(
                {
                    "token": self.token,
                    "track_id": self.track_id,
                    "error": str(exc),
                }
            )
        else:
            self.signals.finished.emit(
                {
                    "token": self.token,
                    "track_id": self.track_id,
                    "data": data,
                    "cache_path": str(cache_path),
                    "built_now": built_now,
                }
            )


class _TransitionRenderWorkerSignals(QObject):
    finished = Signal(object)


class _TransitionRenderWorker(QRunnable):
    """Render one A→B audition without blocking the Qt event loop."""

    def __init__(self, token: int, pair_key: tuple[str, str], render_args: dict[str, Any]):
        super().__init__()
        self.token = token
        self.pair_key = pair_key
        self.render_args = render_args
        self.signals = _TransitionRenderWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = render_transition_preview(**self.render_args)
        except Exception as exc:
            self.signals.finished.emit(
                {"token": self.token, "pair_key": self.pair_key, "error": str(exc)}
            )
        else:
            self.signals.finished.emit(
                {"token": self.token, "pair_key": self.pair_key, "result": result}
            )


# ----------------------------------------------------------------- widgets


class StructureStrip(QWidget):
    """Interactive waveform viewport used for DJ validation.

    Click seeks, drag on empty waveform creates a transition region, cue
    markers can be dragged, wheel/pinch zooms, and Shift-drag pans.  Engine
    windows remain a read-only reference layer underneath the DJ correction.
    """

    seekRequested = Signal(float)
    selectionCommitted = Signal(float, float)
    cueMoved = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(154)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.grabGesture(Qt.PinchGesture)
        self.duration_sec = 0.0
        self.view_start_sec = 0.0
        self.view_end_sec = 0.0
        self.segments = []
        self.windows: list[TransitionWindow] = []
        self.waveform: list[float] = []
        self.waveform_data: WaveformData | None = None
        self.beat_times: list[float] = []
        self.downbeats: list[float] = []
        self.beatgrid_reliable = False
        self.quantize_enabled = True
        self.quantize_grid_beats = 8
        self.playhead_sec: float | None = None
        self.suggested_region: tuple[float, float] | None = None
        self.user_selection: tuple[float, float] | None = None
        self.cue_markers: dict[str, WaveformCueMarker] = {}
        self._drag_mode: str | None = None
        self._drag_start_x = 0.0
        self._drag_last_x = 0.0
        self._drag_start_time = 0.0
        self._drag_cue_label = ""
        self._drag_cue_original = 0.0

    def set_data(
        self,
        *,
        duration_sec: float,
        segments,
        windows,
        waveform=None,
        beat_times=None,
        downbeats=None,
        beatgrid_reliable: bool = False,
        suggested_region: tuple[float, float] | None = None,
    ) -> None:
        self.duration_sec = max(float(duration_sec or 0.0), 0.0)
        self.view_start_sec = 0.0
        self.view_end_sec = self.duration_sec
        self.segments = list(segments or [])
        self.windows = list(windows or [])
        self.waveform = list(waveform or [])
        self.waveform_data = None
        self.beat_times = [float(value) for value in (beat_times or [])]
        self.downbeats = [float(value) for value in (downbeats or [])]
        self.beatgrid_reliable = bool(beatgrid_reliable)
        self.playhead_sec = None
        self.suggested_region = suggested_region
        self.user_selection = None
        self.cue_markers = {}
        self.update()

    def set_waveform_data(self, data: WaveformData) -> None:
        self.waveform_data = data
        if self.duration_sec <= 0 and data.duration_sec > 0:
            self.duration_sec = data.duration_sec
            self.fit_to_track()
        self.update()

    def set_playhead(self, sec: float | None) -> None:
        self.playhead_sec = sec
        self.update()

    def set_cue_markers(self, markers: list[WaveformCueMarker]) -> None:
        self.cue_markers = {marker.label: marker for marker in markers}
        self.update()

    def upsert_cue_marker(self, marker: WaveformCueMarker) -> None:
        self.cue_markers[marker.label] = marker
        self.update()

    def set_cue_position(self, label: str, sec: float) -> None:
        marker = self.cue_markers.get(label)
        if marker is None:
            return
        marker.time_sec = self._clamp_time(sec)
        self.update()

    def set_user_selection(self, start_sec: float | None, end_sec: float | None) -> None:
        if start_sec is None or end_sec is None:
            self.user_selection = None
        else:
            start = self._clamp_time(start_sec)
            end = self._clamp_time(end_sec)
            self.user_selection = (min(start, end), max(start, end))
        self.update()

    def _visible_duration(self) -> float:
        return max(self.view_end_sec - self.view_start_sec, 1e-9)

    def _clamp_time(self, sec: float) -> float:
        return max(0.0, min(float(sec), self.duration_sec))

    def _quantize_time(self, sec: float) -> float:
        sec = self._clamp_time(sec)
        if self.quantize_enabled and self.beatgrid_reliable and self.beat_times:
            return snap_to_grid(
                sec,
                self.beat_times,
                self.downbeats,
                grid_beats=self.quantize_grid_beats,
            )
        return sec

    def _x(self, sec: float) -> float:
        return (float(sec) - self.view_start_sec) / self._visible_duration() * max(self.width(), 1)

    def _time_at_x(self, x: float) -> float:
        fraction = max(0.0, min(float(x) / max(self.width(), 1), 1.0))
        return self.view_start_sec + fraction * self._visible_duration()

    def fit_to_track(self) -> None:
        self.view_start_sec = 0.0
        self.view_end_sec = self.duration_sec
        self.update()

    def zoom_at(self, x: float, factor: float) -> None:
        if self.duration_sec <= 0 or factor <= 0:
            return
        old_span = self._visible_duration()
        new_span = max(2.0, min(self.duration_sec, old_span * factor))
        anchor = self._time_at_x(x)
        fraction = max(0.0, min(x / max(self.width(), 1), 1.0))
        start = anchor - fraction * new_span
        start = max(0.0, min(start, max(self.duration_sec - new_span, 0.0)))
        self.view_start_sec = start
        self.view_end_sec = start + new_span
        self.update()

    def pan_by(self, delta_sec: float) -> None:
        if self.duration_sec <= 0:
            return
        span = min(self._visible_duration(), self.duration_sec)
        start = self.view_start_sec + float(delta_sec)
        start = max(0.0, min(start, max(self.duration_sec - span, 0.0)))
        self.view_start_sec = start
        self.view_end_sec = start + span
        self.update()

    def _cue_at_x(self, x: float) -> WaveformCueMarker | None:
        visible = [
            marker
            for marker in self.cue_markers.values()
            if self.view_start_sec <= marker.time_sec <= self.view_end_sec
        ]
        if not visible:
            return None
        marker = min(visible, key=lambda item: abs(self._x(item.time_sec) - x))
        return marker if abs(self._x(marker.time_sec) - x) <= 9.0 else None

    def _selection_handle_at_x(self, x: float) -> str | None:
        if self.user_selection is None:
            return None
        start, end = self.user_selection
        if abs(self._x(start) - x) <= 8.0:
            return "selection_start"
        if abs(self._x(end) - x) <= 8.0:
            return "selection_end"
        return None

    def mousePressEvent(self, event) -> None:
        if self.duration_sec <= 0:
            return
        self.setFocus(Qt.MouseFocusReason)
        x = float(event.position().x())
        self._drag_start_x = x
        self._drag_last_x = x
        self._drag_start_time = self._time_at_x(x)
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier
        ):
            self._drag_mode = "pan"
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() != Qt.LeftButton:
            return
        marker = self._cue_at_x(x)
        if marker is not None:
            self._drag_mode = "cue"
            self._drag_cue_label = marker.label
            self._drag_cue_original = marker.time_sec
            self.setCursor(Qt.SizeHorCursor)
            return
        handle = self._selection_handle_at_x(x)
        if handle is not None:
            self._drag_mode = handle
            self.setCursor(Qt.SizeHorCursor)
            return
        self._drag_mode = "pending_selection"

    def mouseMoveEvent(self, event) -> None:
        x = float(event.position().x())
        if self._drag_mode == "pan":
            delta_px = self._drag_last_x - x
            self.pan_by(delta_px / max(self.width(), 1) * self._visible_duration())
            self._drag_last_x = x
            return
        if self._drag_mode == "cue":
            marker = self.cue_markers.get(self._drag_cue_label)
            if marker is not None:
                marker.time_sec = self._quantize_time(self._time_at_x(x))
                self.update()
            return
        if self._drag_mode == "pending_selection" and abs(x - self._drag_start_x) >= 4.0:
            self._drag_mode = "selection"
        if self._drag_mode == "selection":
            start = self._quantize_time(self._drag_start_time)
            end = self._quantize_time(self._time_at_x(x))
            self.user_selection = (min(start, end), max(start, end))
            self.update()
            return
        if self._drag_mode in {"selection_start", "selection_end"} and self.user_selection:
            start, end = self.user_selection
            value = self._quantize_time(self._time_at_x(x))
            if self._drag_mode == "selection_start":
                start = min(value, end)
            else:
                end = max(value, start)
            self.user_selection = (start, end)
            self.update()
            return

        marker = self._cue_at_x(x)
        handle = self._selection_handle_at_x(x)
        self.setCursor(Qt.SizeHorCursor if marker or handle else Qt.CrossCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() not in {Qt.LeftButton, Qt.MiddleButton}:
            return
        mode = self._drag_mode
        self._drag_mode = None
        self.setCursor(Qt.CrossCursor)
        if mode == "pending_selection":
            self.seekRequested.emit(self._quantize_time(self._time_at_x(event.position().x())))
            return
        if mode in {"selection", "selection_start", "selection_end"}:
            if self.user_selection is not None:
                start, end = self.user_selection
                if end - start > 1e-6:
                    self.selectionCommitted.emit(start, end)
                else:
                    self.user_selection = None
                    self.seekRequested.emit(start)
                    self.update()
            return
        if mode == "cue":
            marker = self.cue_markers.get(self._drag_cue_label)
            if marker is not None and abs(marker.time_sec - self._drag_cue_original) > 1e-6:
                self.cueMoved.emit(
                    {
                        "label": marker.label,
                        "name": marker.name,
                        "source": marker.source,
                        "reference_time_sec": marker.reference_time_sec,
                        "previous_time_sec": self._drag_cue_original,
                        "user_time_sec": marker.time_sec,
                    }
                )

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.fit_to_track()

    def wheelEvent(self, event) -> None:
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        if pixel.x():
            self.pan_by(-pixel.x() / max(self.width(), 1) * self._visible_duration())
        else:
            delta = pixel.y() or angle.y()
            if delta:
                self.zoom_at(event.position().x(), 0.82 if delta > 0 else 1.22)
        event.accept()

    def event(self, event) -> bool:
        if event.type() == QEvent.NativeGesture and event.gestureType() == Qt.ZoomNativeGesture:
            position = event.position() if hasattr(event, "position") else self.rect().center()
            value = float(event.value())
            factor = max(0.55, min(1.8, 1.0 - value))
            self.zoom_at(float(position.x()), factor)
            return True
        if event.type() == QEvent.Gesture:
            pinch = event.gesture(Qt.PinchGesture)
            if pinch is not None and pinch.scaleFactor() > 0:
                self.zoom_at(float(pinch.centerPoint().x()), 1.0 / float(pinch.scaleFactor()))
                return True
        return super().event(event)

    @staticmethod
    def _format_time(sec: float) -> str:
        sec = max(0.0, sec)
        return f"{int(sec // 60)}:{int(sec % 60):02d}"

    def _paint_grid(self, painter: QPainter, lane_top: int, lane_bottom: int) -> None:
        if not self.beatgrid_reliable or not self.beat_times:
            return
        visible = [
            (index, beat)
            for index, beat in enumerate(self.beat_times)
            if self.view_start_sec <= beat <= self.view_end_sec
        ]
        if not visible:
            return
        spacing = self.width() * (
            (self.beat_times[1] - self.beat_times[0]) / self._visible_duration()
        ) if len(self.beat_times) > 1 else self.width()
        anchor_time = (self.downbeats or self.beat_times)[0]
        anchor_index = min(
            range(len(self.beat_times)),
            key=lambda index: abs(self.beat_times[index] - anchor_time),
        )
        downbeat_keys = {round(value, 3) for value in self.downbeats}
        for index, beat in visible:
            phrase = (index - anchor_index) % self.quantize_grid_beats == 0
            downbeat = round(beat, 3) in downbeat_keys
            if not phrase and not downbeat and spacing < 9.0:
                continue
            color = QColor("#5CC8FF" if phrase else "#6D7887")
            color.setAlpha(82 if phrase else (54 if downbeat else 26))
            painter.setPen(QPen(color, 1))
            x = int(self._x(beat))
            painter.drawLine(x, lane_top, x, lane_bottom)

    @staticmethod
    def _wave_color(low: float, mid: float, high: float) -> QColor:
        low_rgb = (255, 180, 84)
        mid_rgb = (56, 217, 150)
        high_rgb = (92, 200, 255)
        emphasized = (low**1.8, mid**1.8, high**1.8)
        total = max(sum(emphasized), 1e-9)
        weights = tuple(value / total for value in emphasized)
        rgb = [
            int(sum(weight * color[channel] for weight, color in zip(weights, (low_rgb, mid_rgb, high_rgb))))
            for channel in range(3)
        ]
        return QColor(*rgb)

    def _paint_waveform(
        self,
        painter: QPainter,
        lane_top: int,
        lane_bottom: int,
    ) -> None:
        width = max(self.width(), 1)
        lane_mid = (lane_top + lane_bottom) / 2.0
        lane_half = max((lane_bottom - lane_top) / 2.0 - 3.0, 1.0)
        data = self.waveform_data
        if data is not None and data.bin_count:
            count = data.bin_count
            duration = max(data.duration_sec, self.duration_sec, 1e-9)
            for x in range(width):
                t0 = self._time_at_x(x)
                t1 = self._time_at_x(x + 1)
                i0 = max(0, min(int(t0 / duration * count), count - 1))
                i1 = max(i0 + 1, min(int(np.ceil(t1 / duration * count)), count))
                minimum = float(np.min(data.minimum[i0:i1]))
                maximum = float(np.max(data.maximum[i0:i1]))
                low = float(np.mean(data.low[i0:i1]))
                mid = float(np.mean(data.mid[i0:i1]))
                high = float(np.mean(data.high[i0:i1]))
                painter.setPen(QPen(self._wave_color(low, mid, high), 1))
                y0 = int(lane_mid - maximum * lane_half)
                y1 = int(lane_mid - minimum * lane_half)
                painter.drawLine(x, y0, x, max(y1, y0 + 1))
        elif self.waveform:
            painter.setPen(QPen(QColor("#8AA3B8"), 1))
            count = len(self.waveform)
            duration = max(self.duration_sec, 1e-9)
            for x in range(width):
                sec = self._time_at_x(x)
                index = max(0, min(int(sec / duration * count), count - 1))
                amplitude = max(1.0, float(self.waveform[index]) * lane_half)
                painter.drawLine(
                    x,
                    int(lane_mid - amplitude),
                    x,
                    int(lane_mid + amplitude),
                )
        painter.setPen(QPen(QColor(92, 200, 255, 70), 1))
        painter.drawLine(0, int(lane_mid), width, int(lane_mid))

    def _paint_region(
        self,
        painter: QPainter,
        region: tuple[float, float] | None,
        color: QColor,
        *,
        dashed: bool,
        lane_top: int,
        lane_bottom: int,
    ) -> None:
        if region is None:
            return
        start, end = region
        if end < self.view_start_sec or start > self.view_end_sec:
            return
        x0 = self._x(max(start, self.view_start_sec))
        x1 = self._x(min(end, self.view_end_sec))
        fill = QColor(color)
        fill.setAlpha(28 if dashed else 52)
        painter.fillRect(QRectF(x0, lane_top, max(x1 - x0, 2.0), lane_bottom - lane_top), fill)
        pen = QPen(color, 1.5, Qt.DashLine if dashed else Qt.SolidLine)
        painter.setPen(pen)
        painter.drawRect(QRectF(x0, lane_top, max(x1 - x0, 2.0), lane_bottom - lane_top))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#080C11"))
        height = self.height()
        width = max(self.width(), 1)
        lane_top = 26
        lane_bottom = height - 26

        self._paint_grid(painter, lane_top, lane_bottom)
        self._paint_region(
            painter,
            self.suggested_region,
            QColor("#FFB454"),
            dashed=True,
            lane_top=lane_top,
            lane_bottom=lane_bottom,
        )
        self._paint_region(
            painter,
            self.user_selection,
            QColor("#5CC8FF"),
            dashed=False,
            lane_top=lane_top,
            lane_bottom=lane_bottom,
        )
        self._paint_waveform(painter, lane_top, lane_bottom)

        for segment in self.segments:
            if segment.end_sec < self.view_start_sec or segment.start_sec > self.view_end_sec:
                continue
            seg_type = getattr(segment.segment_type, "value", str(segment.segment_type))
            color = QColor(SEGMENT_COLORS.get(seg_type, SEGMENT_COLORS["unknown"]))
            color.setAlpha(210)
            x0 = self._x(max(segment.start_sec, self.view_start_sec))
            x1 = self._x(min(segment.end_sec, self.view_end_sec))
            painter.fillRect(QRectF(x0, height - 8, max(x1 - x0 - 1, 1), 6), color)

        for window in self.windows:
            if window.end_sec < self.view_start_sec or window.start_sec > self.view_end_sec:
                continue
            color = QColor(WINDOW_COLORS.get(window.window_type, QColor("#ffffff")))
            color.setAlpha(210)
            x0 = self._x(max(window.start_sec, self.view_start_sec))
            x1 = self._x(min(window.end_sec, self.view_end_sec))
            painter.fillRect(QRectF(x0, 20, max(x1 - x0, 2), 4), color)

        for marker in self.cue_markers.values():
            if not self.view_start_sec <= marker.time_sec <= self.view_end_sec:
                continue
            color = QColor(marker.color)
            x = int(self._x(marker.time_sec))
            painter.setPen(QPen(color, 2))
            painter.drawLine(x, 18, x, lane_bottom)
            badge = QRectF(max(1, x - 10), 1, 20, 17)
            painter.fillRect(badge, color)
            painter.setPen(QPen(QColor("#05070B"), 1))
            painter.drawText(badge, Qt.AlignCenter, marker.label)

        if self.playhead_sec is not None and self.view_start_sec <= self.playhead_sec <= self.view_end_sec:
            painter.setPen(QPen(QColor("#F5F7FA"), 2))
            x = int(self._x(self.playhead_sec))
            painter.drawLine(x, 0, x, height - 8)

        painter.setPen(QPen(QColor("#7E8A99"), 1))
        painter.drawText(4, height - 11, self._format_time(self.view_start_sec))
        end_text = self._format_time(self.view_end_sec)
        end_width = painter.fontMetrics().horizontalAdvance(end_text)
        painter.drawText(width - end_width - 4, height - 11, end_text)
        if self.user_selection:
            start, end = self.user_selection
            label = f"DJ transition {self._format_time(start)}–{self._format_time(end)}"
            painter.setPen(QPen(QColor("#7DD7FF"), 1))
            label_width = painter.fontMetrics().horizontalAdvance(label)
            label_x = max(8, min(int(self._x(start)) + 8, width - label_width - 8))
            painter.drawText(label_x, lane_top + 15, label)
        painter.end()


class TransitionSimulationView(QWidget):
    """Three-lane waveform and mixer-curve view for one rendered preview."""

    seekRequested = Signal(float)

    _A_COLORS = {
        "low_a": QColor("#FF6B5F"),
        "mid_a": QColor("#FFD166"),
        "high_a": QColor("#66D17A"),
        "fader_a": QColor("#F5F7FA"),
    }
    _B_COLORS = {
        "low_b": QColor("#52D6D3"),
        "mid_b": QColor("#5EA7FF"),
        "high_b": QColor("#D47CFF"),
        "fader_b": QColor("#F5F7FA"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(260)
        self.setMouseTracking(True)
        self.envelope = build_transition_envelope("plain_blend")
        self.result: TransitionRenderResult | None = None
        self.playhead_fraction: float | None = None

    def set_envelope(self, envelope: TransitionEnvelope) -> None:
        self.envelope = envelope
        self.result = None
        self.playhead_fraction = None
        self.update()

    def set_render_result(self, result: TransitionRenderResult) -> None:
        self.envelope = result.envelope
        self.result = result
        self.playhead_fraction = 0.0
        self.update()

    def clear_audio(self) -> None:
        self.result = None
        self.playhead_fraction = None
        self.update()

    def set_playhead_fraction(self, fraction: float | None) -> None:
        self.playhead_fraction = (
            None if fraction is None else float(min(1.0, max(0.0, fraction)))
        )
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(
            104.0,
            26.0,
            max(self.width() - 296.0, 2.0),
            max(self.height() - 52.0, 3.0),
        )

    def _lane_rects(self) -> list[QRectF]:
        plot = self._plot_rect()
        gap = 7.0
        lane_height = (plot.height() - gap * 2.0) / 3.0
        return [
            QRectF(plot.left(), plot.top() + index * (lane_height + gap), plot.width(), lane_height)
            for index in range(3)
        ]

    @staticmethod
    def _draw_waveform(
        painter: QPainter,
        rect: QRectF,
        waveform: TransitionWaveform | None,
        color: QColor,
    ) -> None:
        center = rect.center().y()
        painter.setPen(QPen(QColor(106, 123, 142, 48), 1))
        painter.drawLine(QPointF(rect.left(), center), QPointF(rect.right(), center))
        if waveform is None or not waveform.minimum:
            return
        minimum = waveform.minimum
        maximum = waveform.maximum
        count = max(len(minimum), 1)
        half_height = max(rect.height() * 0.42, 1.0)
        wave_color = QColor(color)
        wave_color.setAlpha(112)
        painter.setPen(QPen(wave_color, 1))
        for index, (low, high) in enumerate(zip(minimum, maximum)):
            x = rect.left() + (index + 0.5) / count * rect.width()
            painter.drawLine(
                QPointF(x, center - float(high) * half_height),
                QPointF(x, center - float(low) * half_height),
            )

    @staticmethod
    def _draw_curve(
        painter: QPainter,
        rect: QRectF,
        values: np.ndarray,
        color: QColor,
        *,
        dashed: bool = False,
    ) -> None:
        if values.size < 2:
            return
        points = QPolygonF(
            [
                QPointF(
                    rect.left() + index / (values.size - 1) * rect.width(),
                    rect.bottom() - 5.0 - float(value) * max(rect.height() - 10.0, 1.0),
                )
                for index, value in enumerate(values)
            ]
        )
        curve_color = QColor(color)
        curve_color.setAlpha(225 if not dashed else 178)
        painter.setPen(QPen(curve_color, 1.6, Qt.DashLine if dashed else Qt.SolidLine))
        painter.drawPolyline(points)

    def current_mixer_values(self, fraction: float | None = None) -> dict[str, float]:
        """Current six EQ values and two channel faders at the playhead."""
        progress = self.playhead_fraction if fraction is None else fraction
        progress = float(min(1.0, max(0.0, progress or 0.0)))
        curves = sample_transition_envelope(self.envelope, 1001)
        index = min(int(round(progress * 1000)), 1000)
        return {name: float(values[index]) for name, values in curves.items()}

    @staticmethod
    def _draw_knob(
        painter: QPainter,
        center: QPointF,
        radius: float,
        value: float,
        color: QColor,
        label: str,
    ) -> None:
        value = float(min(1.0, max(0.0, value)))
        arc_rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )
        painter.setPen(QPen(QColor("#344251"), 3.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(arc_rect, 225 * 16, -270 * 16)
        painter.setPen(QPen(color, 3.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(arc_rect, 225 * 16, int(-270 * 16 * value))

        angle = np.deg2rad(225.0 - 270.0 * value)
        needle_length = radius * 0.72
        endpoint = QPointF(
            center.x() + float(np.cos(angle)) * needle_length,
            center.y() - float(np.sin(angle)) * needle_length,
        )
        painter.setPen(QPen(QColor("#DDE7F0"), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(center, endpoint)
        painter.setBrush(QColor("#111923"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, 2.7, 2.7)

        painter.setPen(QPen(QColor("#AAB6C5"), 1))
        painter.drawText(
            QRectF(center.x() - radius - 5.0, center.y() - radius - 16.0, radius * 2.0 + 10.0, 14.0),
            Qt.AlignCenter,
            label,
        )
        painter.setPen(QPen(color, 1))
        painter.drawText(
            QRectF(center.x() - radius - 5.0, center.y() + radius + 2.0, radius * 2.0 + 10.0, 13.0),
            Qt.AlignCenter,
            f"{value:.2f}",
        )

    def _draw_eq_panel(
        self,
        painter: QPainter,
        rect: QRectF,
        values: dict[str, float],
        *,
        deck: str,
    ) -> None:
        painter.fillRect(rect, QColor("#0D141D"))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(92, 200, 255, 40), 1))
        painter.drawRect(rect)
        suffix = deck.lower()
        names = ("high", "mid", "low")
        labels = ("HI", "MID", "LOW")
        colors = (
            (QColor("#66D17A"), QColor("#FFD166"), QColor("#FF6B5F"))
            if deck == "A"
            else (QColor("#D47CFF"), QColor("#5EA7FF"), QColor("#52D6D3"))
        )
        column_width = rect.width() / 3.0
        radius = min(16.0, max(10.0, rect.height() * 0.22), column_width * 0.28)
        center_y = rect.center().y()
        for index, (name, label, color) in enumerate(zip(names, labels, colors)):
            center = QPointF(rect.left() + (index + 0.5) * column_width, center_y)
            self._draw_knob(
                painter,
                center,
                radius,
                values[f"{name}_{suffix}"],
                color,
                label,
            )

    @staticmethod
    def _draw_fader_panel(
        painter: QPainter,
        rect: QRectF,
        values: dict[str, float],
    ) -> None:
        painter.fillRect(rect, QColor("#101923"))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(92, 200, 255, 40), 1))
        painter.drawRect(rect)
        painter.setPen(QPen(QColor("#7E8A99"), 1))
        painter.drawText(
            QRectF(rect.left() + 8.0, rect.top() + 3.0, rect.width() - 16.0, 14.0),
            Qt.AlignCenter,
            "LIVE CHANNEL FADERS",
        )
        for row, (name, label, color) in enumerate(
            (("fader_a", "A", QColor("#FFB454")), ("fader_b", "B", QColor("#5CC8FF")))
        ):
            y = rect.top() + 25.0 + row * max((rect.height() - 31.0) / 2.0, 14.0)
            left = rect.left() + 27.0
            right = rect.right() - 10.0
            painter.setPen(QPen(QColor("#344251"), 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            value = float(values[name])
            active_x = left + value * max(right - left, 1.0)
            painter.setPen(QPen(color, 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(left, y), QPointF(active_x, y))
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(active_x, y), 4.5, 4.5)
            painter.setPen(QPen(QColor("#DDE7F0"), 1))
            painter.drawText(
                QRectF(rect.left() + 6.0, y - 8.0, 16.0, 16.0),
                Qt.AlignCenter,
                label,
            )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#080D13"))
        plot = self._plot_rect()
        lanes = self._lane_rects()

        painter.setPen(QPen(QColor("#7E8A99"), 1))
        labels = ("OUTGOING A", "MIXED PREVIEW", "INCOMING B")
        for index, (label, lane) in enumerate(zip(labels, lanes)):
            painter.fillRect(lane, QColor("#0D141D" if index != 1 else "#101923"))
            painter.drawText(
                QRectF(8.0, lane.top(), 88.0, lane.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                label,
            )

        for beat in self.envelope.beat_positions:
            fraction = beat / max(float(self.envelope.duration_beats), 1.0)
            x = plot.left() + fraction * plot.width()
            major = beat in (0.0, float(self.envelope.duration_beats) / 2.0, float(self.envelope.duration_beats))
            color = QColor(92, 200, 255, 82 if major else 38)
            painter.setPen(QPen(color, 1.3 if major else 1.0))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(QPen(QColor("#657384"), 1))
            painter.drawText(
                QRectF(x - 18.0, plot.bottom() + 3.0, 36.0, 18.0),
                Qt.AlignHCenter | Qt.AlignTop,
                str(int(beat)),
            )

        waveforms = (
            self.result.outgoing if self.result else None,
            self.result.mixed if self.result else None,
            self.result.incoming if self.result else None,
        )
        for lane, waveform, color in zip(
            lanes,
            waveforms,
            (QColor("#FFB454"), QColor("#DDE7F0"), QColor("#5CC8FF")),
        ):
            self._draw_waveform(painter, lane, waveform, color)

        curve_count = max(int(plot.width() / 3.0), 64)
        curves = sample_transition_envelope(self.envelope, curve_count)
        for name in ("low_a", "mid_a", "high_a"):
            self._draw_curve(painter, lanes[0], curves[name], self._A_COLORS[name])
        self._draw_curve(
            painter, lanes[0], curves["fader_a"], self._A_COLORS["fader_a"], dashed=True
        )
        self._draw_curve(
            painter, lanes[1], curves["fader_a"], QColor("#FFB454"), dashed=True
        )
        self._draw_curve(
            painter, lanes[1], curves["fader_b"], QColor("#5CC8FF"), dashed=True
        )
        for name in ("low_b", "mid_b", "high_b"):
            self._draw_curve(painter, lanes[2], curves[name], self._B_COLORS[name])
        self._draw_curve(
            painter, lanes[2], curves["fader_b"], self._B_COLORS["fader_b"], dashed=True
        )

        mixer_values = self.current_mixer_values()
        panel_left = plot.right() + 8.0
        panel_width = max(self.width() - panel_left - 8.0, 2.0)
        panels = [
            QRectF(panel_left, lane.top(), panel_width, lane.height())
            for lane in lanes
        ]
        self._draw_eq_panel(painter, panels[0], mixer_values, deck="A")
        self._draw_fader_panel(painter, panels[1], mixer_values)
        self._draw_eq_panel(painter, panels[2], mixer_values, deck="B")

        painter.setPen(QPen(QColor("#7E8A99"), 1))
        painter.drawText(8, 17, "EQ LOW / MID / HIGH · dashed = channel fader")
        grid_text = f"{self.envelope.grid_beats}-BEAT CONTROL GRID"
        grid_width = painter.fontMetrics().horizontalAdvance(grid_text)
        painter.drawText(self.width() - grid_width - 14, 17, grid_text)

        if self.playhead_fraction is not None:
            x = plot.left() + self.playhead_fraction * plot.width()
            painter.setPen(QPen(QColor("#F5F7FA"), 2))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        plot = self._plot_rect()
        if not plot.contains(event.position()):
            return super().mousePressEvent(event)
        fraction = (event.position().x() - plot.left()) / max(plot.width(), 1.0)
        self.seekRequested.emit(float(min(1.0, max(0.0, fraction))))


class Deck(QWidget):
    """One playable deck: structure strip, transport, stem isolation."""

    annotationCommitted = Signal(object)

    def __init__(self, role_label: str, deck_code: str = "A"):
        super().__init__()
        self.deck_code = deck_code
        self.analysis: AnalysisResult | None = None
        self.config: EngineConfig | None = None
        self.windows: list[TransitionWindow] = []
        self.cue_window_type = WindowType.mix_out
        self.preview_duration_beats = DEFAULT_DURATION_BEATS
        self.user_cue_sec: float | None = None   # DJ's verified Rekordbox hot cue
        self.user_cue_label: str = ""
        self._quantize = True
        self.playback_rate = 1.0
        self._player = None
        self._audio_output = None
        self._stem_paths: dict[str, str] = {}
        self._stem_thread: QThread | None = None
        self._current_source_label = "Mix"
        self._waveform_token = 0
        self._waveform_workers: dict[int, _WaveformWorker] = {}
        self._waveform_cache_manager = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.title_label = QLabel(role_label)
        self.title_label.setProperty("role", "subtitle")
        layout.addWidget(self.title_label)

        self.strip = StructureStrip()
        self.strip.seekRequested.connect(self.seek)
        self.strip.selectionCommitted.connect(self._on_selection_committed)
        self.strip.cueMoved.connect(self._on_cue_moved)
        self.strip.quantize_enabled = self._quantize
        layout.addWidget(self.strip)

        self.waveform_help = QLabel(
            "Click: seek · drag: mark transition · drag A–H: move hot cue · "
            "wheel/pinch: zoom · Shift-drag: pan · double-click: fit"
        )
        self.waveform_help.setProperty("role", "hint")
        self.waveform_help.setWordWrap(True)
        layout.addWidget(self.waveform_help)

        transport = QHBoxLayout()
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_button)
        self.cue_button = QPushButton("Cue Window")
        self.cue_button.setToolTip("Jump to the best transition window (snapped to the 8-beat grid).")
        self.cue_button.clicked.connect(self.cue_to_window)
        transport.addWidget(self.cue_button)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setProperty("role", "hint")
        transport.addWidget(self.time_label)
        transport.addStretch(1)
        layout.addLayout(transport)

        self.stem_row = QHBoxLayout()
        self.stem_status = QLabel("")
        self.stem_status.setProperty("role", "hint")
        stems_line = QHBoxLayout()
        stems_line.addLayout(self.stem_row)
        stems_line.addWidget(self.stem_status)
        stems_line.addStretch(1)
        layout.addLayout(stems_line)

    @property
    def quantize(self) -> bool:
        return self._quantize

    @quantize.setter
    def quantize(self, enabled: bool) -> None:
        self._quantize = bool(enabled)
        if hasattr(self, "strip"):
            self.strip.quantize_enabled = self._quantize

    # --- data -----------------------------------------------------------

    def set_track(
        self,
        analysis: AnalysisResult,
        config: EngineConfig,
        windows: list[TransitionWindow],
        cue_window_type: WindowType,
    ) -> None:
        self.stop()
        if self._player is not None:
            # QMediaPlayer keeps its previous source after stop(). When the
            # review row changes, leaving that source in place makes Play
            # start the old audio while the UI already shows the new track.
            self._player.setSource(QUrl())
            self._player.setPosition(0)
        self.analysis = analysis
        self.config = config
        self.windows = windows
        self.cue_window_type = cue_window_type
        self._stem_paths = {}
        self._current_source_label = "Mix"
        track = analysis.track
        details = []
        if track.bpm_estimate:
            details.append(f"{track.bpm_estimate:.0f} BPM")
        if track.key_estimate:
            details.append(track.key_estimate)
        role = "outgoing" if cue_window_type == WindowType.mix_out else "incoming"
        self.title_label.setText(
            f"{track.title or track.track_id} · {' · '.join(details)} ({role})"
        )
        cue = best_window(
            windows,
            cue_window_type,
            analysis=analysis,
            transition_beats=self.preview_duration_beats,
        )
        beatgrid = analysis.beatgrid
        self.strip.set_data(
            duration_sec=track.duration_sec or 0.0,
            segments=analysis.segments,
            windows=windows,
            waveform=waveform_envelope_from_features(analysis),
            beat_times=beatgrid.beat_times_sec if beatgrid else [],
            downbeats=beatgrid.downbeats_sec if beatgrid else [],
            beatgrid_reliable=bool(beatgrid and beatgrid.reliable),
            suggested_region=(cue.start_sec, cue.end_sec) if cue else None,
        )
        engine_markers = []
        for name, start_sec, slot_index in track_windows_as_cues(
            analysis,
            windows,
            cue_profile="middle",
        ):
            label = chr(ord("A") + slot_index)
            engine_markers.append(
                WaveformCueMarker(
                    label=label,
                    name=name,
                    time_sec=float(start_sec),
                    source="engine_transition_window",
                    reference_time_sec=float(start_sec),
                    color=CUE_COLORS[slot_index % len(CUE_COLORS)],
                )
            )
        self.strip.set_cue_markers(engine_markers)
        self.strip.set_playhead(None)
        self.time_label.setText(
            f"0:00 / {int((track.duration_sec or 0.0) // 60)}:{int((track.duration_sec or 0.0) % 60):02d}"
        )
        self._rebuild_stem_buttons()
        self.user_cue_sec = None
        self.user_cue_label = ""
        self.cue_button.setText(
            f"Cue {cue_window_type.value.replace('_', '-')}"
            + (f" ({cue.start_sec:.0f}s)" if cue else " (none found)")
        )
        self.cue_button.setEnabled(cue is not None)
        self._request_detailed_waveform()

    def set_hot_cues(self, cues: list[DeviceCue] | None) -> None:
        """Overlay imported Rekordbox hot cues on the exact waveform."""
        for cue in cues or []:
            if cue.list_type != "hot" or not 1 <= cue.hot_slot <= 8:
                continue
            index = cue.hot_slot - 1
            label = chr(ord("A") + index)
            sec = max(0.0, cue.time_ms / 1000.0)
            self.strip.upsert_cue_marker(
                WaveformCueMarker(
                    label=label,
                    name=f"Rekordbox Hot Cue {label}",
                    time_sec=sec,
                    source="rekordbox_hotcue",
                    reference_time_sec=sec,
                    color=CUE_COLORS[index],
                )
            )

    def set_user_cue(self, sec: float, label: str) -> None:
        """DJ's own verified Rekordbox hot cue — takes priority over windows."""
        normalized = label.strip().upper().removeprefix("HOT ").strip()
        normalized = normalized if len(normalized) == 1 and normalized in "ABCDEFGH" else label.strip()
        self.user_cue_sec = float(sec)
        self.user_cue_label = normalized
        if (
            len(normalized) == 1
            and normalized in "ABCDEFGH"
            and normalized not in self.strip.cue_markers
        ):
            index = ord(normalized) - ord("A")
            self.strip.upsert_cue_marker(
                WaveformCueMarker(
                    label=normalized,
                    name=f"Rekordbox Hot Cue {normalized}",
                    time_sec=float(sec),
                    source="rekordbox_hotcue",
                    reference_time_sec=float(sec),
                    color=CUE_COLORS[index],
                )
            )
        self._update_user_cue_button()

    def _update_user_cue_button(self) -> None:
        if self.user_cue_sec is None:
            return
        sec = self.user_cue_sec
        minutes, seconds = divmod(sec, 60)
        self.cue_button.setText(
            f"Cue YOUR hot {self.user_cue_label} @ {int(minutes)}:{seconds:04.1f}"
        )
        self.cue_button.setEnabled(True)

    def restore_transition_selection(self, start_sec: float, end_sec: float) -> None:
        self.strip.set_user_selection(start_sec, end_sec)

    def set_preview_duration_beats(self, duration_beats: int) -> None:
        self.preview_duration_beats = int(duration_beats)
        if self.analysis is None:
            return
        cue = best_window(
            self.windows,
            self.cue_window_type,
            analysis=self.analysis,
            transition_beats=self.preview_duration_beats,
        )
        self.strip.suggested_region = (
            (cue.start_sec, cue.end_sec) if cue is not None else None
        )
        self.strip.update()
        if self.user_cue_sec is not None:
            self._update_user_cue_button()
            return
        self.cue_button.setText(
            f"Cue {self.cue_window_type.value.replace('_', '-')}"
            + (f" ({cue.start_sec:.0f}s)" if cue else " (none found)")
        )
        self.cue_button.setEnabled(cue is not None)

    def restore_hot_cue(self, label: str, sec: float) -> None:
        self.strip.set_cue_position(label, sec)
        if label == self.user_cue_label:
            self.user_cue_sec = sec
            self._update_user_cue_button()

    def _request_detailed_waveform(self) -> None:
        if self.analysis is None or self.config is None:
            return
        source = self.analysis.track.source_path
        if not source or not Path(source).exists():
            self.waveform_help.setText(
                "Overview waveform only · source file unavailable for detailed peaks"
            )
            return
        from dancelab.storage.cache_manager import cache_manager_for

        manager = cache_manager_for(self.config)
        self._waveform_cache_manager = manager
        self._waveform_token += 1
        token = self._waveform_token
        worker = _WaveformWorker(
            token,
            source,
            self.analysis.track.track_id,
            str(manager.class_dir("waveforms")),
        )
        worker.signals.finished.connect(self._on_waveform_ready)
        self._waveform_workers[token] = worker
        self.waveform_help.setText(
            "Preparing detailed waveform… · click: seek · drag: mark transition · "
            "drag A–H: move hot cue"
        )
        QThreadPool.globalInstance().start(worker)

    def _on_waveform_ready(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        token = int(payload.get("token", -1))
        self._waveform_workers.pop(token, None)
        if token != self._waveform_token or self.analysis is None:
            return
        if payload.get("track_id") != self.analysis.track.track_id:
            return
        data = payload.get("data")
        if isinstance(data, WaveformData):
            self.strip.set_waveform_data(data)
            cache_path = payload.get("cache_path")
            if cache_path and self._waveform_cache_manager is not None:
                try:
                    self._waveform_cache_manager.register(
                        "waveforms",
                        self.analysis.track.track_id,
                        cache_path,
                    )
                except (OSError, ValueError):
                    pass
            self.waveform_help.setText(
                "Detailed waveform ready · click: seek · drag: mark transition · "
                "drag A–H: move hot cue · wheel/pinch: zoom · Shift-drag: pan"
            )
        else:
            self.waveform_help.setText(
                "Overview waveform active · detailed waveform unavailable · "
                "click: seek · drag: mark transition"
            )

    def _beat_index(self, sec: float | None) -> int | None:
        if sec is None or self.analysis is None or self.analysis.beatgrid is None:
            return None
        beats = self.analysis.beatgrid.beat_times_sec
        if not beats:
            return None
        return int(np.argmin(np.abs(np.asarray(beats, dtype=np.float64) - sec)))

    def _annotation_base(self) -> dict[str, object]:
        analysis = self.analysis
        beatgrid = analysis.beatgrid if analysis else None
        return {
            "deck": self.deck_code,
            "track_id": analysis.track.track_id if analysis else "",
            "track_duration_sec": analysis.track.duration_sec if analysis else None,
            "quantize_grid_beats": 8 if self.quantize else 0,
            "beatgrid_reliable": bool(beatgrid and beatgrid.reliable),
        }

    def _on_selection_committed(self, start_sec: float, end_sec: float) -> None:
        reference = best_window(
            self.windows,
            self.cue_window_type,
            analysis=self.analysis,
            transition_beats=self.preview_duration_beats,
        )
        payload = self._annotation_base()
        payload.update(
            {
                "action": "transition_region_set",
                "marker_type": self.cue_window_type.value,
                "marker_label": "",
                "marker_name": self.cue_window_type.value.replace("_", " ").title(),
                "reference_source": "engine_transition_window" if reference else "none",
                "reference_start_sec": reference.start_sec if reference else None,
                "reference_end_sec": reference.end_sec if reference else None,
                "reference_start_beat": self._beat_index(reference.start_sec) if reference else None,
                "reference_end_beat": self._beat_index(reference.end_sec) if reference else None,
                "user_start_sec": start_sec,
                "user_end_sec": end_sec,
                "user_start_beat": self._beat_index(start_sec),
                "user_end_beat": self._beat_index(end_sec),
            }
        )
        self.annotationCommitted.emit(payload)

    def _on_cue_moved(self, change: object) -> None:
        if not isinstance(change, dict):
            return
        label = str(change.get("label", ""))
        user_sec = float(change.get("user_time_sec", 0.0))
        if label == self.user_cue_label:
            self.user_cue_sec = user_sec
            self._update_user_cue_button()
        reference_sec = change.get("reference_time_sec")
        payload = self._annotation_base()
        payload.update(
            {
                "action": "hot_cue_moved",
                "marker_type": "hot_cue",
                "marker_label": label,
                "marker_name": str(change.get("name", "")),
                "reference_source": str(change.get("source", "")),
                "reference_start_sec": reference_sec,
                "reference_end_sec": None,
                "reference_start_beat": self._beat_index(reference_sec),
                "reference_end_beat": None,
                "user_start_sec": user_sec,
                "user_end_sec": None,
                "user_start_beat": self._beat_index(user_sec),
                "user_end_beat": None,
            }
        )
        self.annotationCommitted.emit(payload)

    def _rebuild_stem_buttons(self) -> None:
        while self.stem_row.count():
            item = self.stem_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        mix_button = QPushButton("Mix")
        mix_button.setToolTip("Play the full mix.")
        mix_button.clicked.connect(lambda: self.select_source("Mix"))
        self.stem_row.addWidget(mix_button)
        isolate_button = QPushButton("Isolate Stems…")
        if _demucs_available():
            isolate_button.setToolTip("Separate Vocals / Drums / Bass / Other (demucs).")
        else:
            isolate_button.setToolTip(
                "demucs not installed — DSP fallback: Harmonic / Percussive (HPSS) "
                "+ low-passed Bass Band."
            )
        isolate_button.clicked.connect(self.render_stems)
        self.stem_row.addWidget(isolate_button)

    def _add_stem_buttons(self, stems: dict[str, Any]) -> None:
        self._stem_paths = stems
        for label in stems:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, name=label: self.select_source(name))
            self.stem_row.addWidget(button)

    # --- stems ----------------------------------------------------------

    def render_stems(self) -> None:
        if self.analysis is None or self.config is None:
            return
        if self._stem_paths:
            return
        if self._stem_thread is not None and self._stem_thread.isRunning():
            return
        source = self.analysis.track.source_path
        if not source or not Path(source).exists():
            self.stem_status.setText("source file missing — cannot isolate stems")
            return
        self.stem_status.setText("separating stems… (first run is slow)")
        from dancelab.storage.cache_manager import cache_manager_for

        # PRODUCT_SPEC §8: stems live in the visible cache root, not the repo
        out_root = str(
            cache_manager_for(self.config).class_dir("stems")
        )
        thread = QThread(self)
        worker = _StemWorker(source, self.analysis.track.track_id, self.config, out_root)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_stems_ready)
        worker.finished.connect(thread.quit, Qt.DirectConnection)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._stem_thread = thread
        self._stem_worker = worker
        thread.start()

    def _on_stems_ready(self, payload: object) -> None:
        self._stem_thread = None
        self._stem_worker = None
        if isinstance(payload, str):
            self.stem_status.setText(f"stem separation failed · {payload}")
            return
        self.stem_status.setText(
            "true separation (demucs)" if _demucs_available() else "DSP fallback (HPSS + bass band)"
        )
        self._add_stem_buttons(payload)

    # --- playback -------------------------------------------------------

    def _ensure_player(self):
        if self._player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)
            self._player.positionChanged.connect(self._on_position)
            self._player.playbackStateChanged.connect(self._on_state)
            # silent audio failures are a lie of omission — surface them
            self._player.errorOccurred.connect(self._on_player_error)
            if not self._player.isAvailable():
                # ENV-1 can hide Qt's multimedia backend ("No QtMultimedia
                # backends found") — player constructs but never plays
                self.stem_status.setText(
                    "⚠ audio backend unavailable — quit and relaunch via ./run_app.sh"
                )
        return self._player

    def _on_player_error(self, error, message: str) -> None:
        source = self._player.source().toLocalFile() if self._player else ""
        missing = source and not Path(source).exists()
        detail = "file missing — re-import or re-mount the drive" if missing else (message or str(error))
        self.stem_status.setText(f"⚠ playback failed: {detail}")

    def playback_problem(self) -> str | None:
        """Pre-flight check: why Play would silently fail, or None."""
        if self.analysis is None:
            return "no track loaded"
        source = self.analysis.track.source_path
        if not source:
            return "analysis has no source path"
        if not Path(source).exists():
            return f"file missing: {source}"
        return None

    def _source_for(self, label: str) -> str | None:
        if label == "Mix":
            return self.analysis.track.source_path if self.analysis else None
        return self._stem_paths.get(label)

    def select_source(self, label: str) -> None:
        source = self._source_for(label)
        if not source:
            return
        player = self._ensure_player()
        position = player.position()
        was_playing = player.playbackState() == player.PlaybackState.PlayingState
        player.setSource(QUrl.fromLocalFile(source))
        player.setPlaybackRate(self.playback_rate)
        player.setPosition(position)
        self._current_source_label = label
        if was_playing:
            player.play()

    def toggle_play(self) -> None:
        if self.analysis is None or not self.analysis.track.source_path:
            return
        player = self._ensure_player()
        if player.source().isEmpty():
            self.select_source(self._current_source_label)
        if player.playbackState() == player.PlaybackState.PlayingState:
            player.pause()
        else:
            player.setPlaybackRate(self.playback_rate)
            player.play()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()

    def seek(self, sec: float) -> None:
        if self.analysis is None:
            return
        if (
            self.quantize
            and self.analysis.beatgrid is not None
            and self.analysis.beatgrid.reliable
        ):
            sec = snap_to_grid(
                sec,
                self.analysis.beatgrid.beat_times_sec,
                self.analysis.beatgrid.downbeats_sec,
            )
        player = self._ensure_player()
        if player.source().isEmpty():
            self.select_source(self._current_source_label)
        player.setPosition(int(sec * 1000))
        self.strip.set_playhead(sec)

    def cue_to_window(self) -> None:
        cue_sec = self.preview_cue_sec()
        if cue_sec is not None:
            self.seek(cue_sec)

    def preview_cue_sec(self, *, duration_beats: int | None = None) -> float | None:
        """Best current review cue, with DJ corrections ahead of engine estimates."""
        if self.strip.user_selection is not None:
            cue_sec = float(self.strip.user_selection[0])
        elif self.user_cue_sec is not None:
            cue_sec = float(self.user_cue_sec)
        else:
            cue = best_window(
                self.windows,
                self.cue_window_type,
                analysis=self.analysis,
                transition_beats=duration_beats or self.preview_duration_beats,
            )
            if cue is None:
                return None
            cue_sec = float(cue.start_sec)
        if (
            self.quantize
            and self.analysis is not None
            and self.analysis.beatgrid is not None
            and self.analysis.beatgrid.reliable
        ):
            cue_sec = snap_to_grid(
                cue_sec,
                self.analysis.beatgrid.beat_times_sec,
                self.analysis.beatgrid.downbeats_sec,
            )
        return cue_sec

    def set_playback_rate(self, rate: float) -> None:
        self.playback_rate = rate
        if self._player is not None:
            self._player.setPlaybackRate(rate)

    def _on_position(self, position_ms: int) -> None:
        sec = position_ms / 1000.0
        self.strip.set_playhead(sec)
        duration = (self.analysis.track.duration_sec or 0.0) if self.analysis else 0.0
        self.time_label.setText(
            f"{int(sec // 60)}:{int(sec % 60):02d} / {int(duration // 60)}:{int(duration % 60):02d}"
        )

    def _on_state(self, state) -> None:
        playing = state == self._player.PlaybackState.PlayingState
        self.play_button.setText("⏸ Pause" if playing else "▶ Play")


class TransitionReviewWidget(QWidget):
    """Full review tool: sample-accurate Transition Lab plus source decks."""

    annotationCommitted = Signal(object)

    def __init__(self):
        super().__init__()
        self._preview_player = None
        self._preview_audio_output = None
        self._preview_result: TransitionRenderResult | None = None
        self._preview_signature: tuple[object, ...] | None = None
        self._preview_token = 0
        self._preview_workers: dict[int, _TransitionRenderWorker] = {}
        self._pending_signatures: dict[int, tuple[object, ...]] = {}
        self._current_pair_key: tuple[str, str] = ("", "")
        self._tempo_plan: TempoPlan | None = None
        self._live_curves: dict[str, np.ndarray] = {}
        self._preview_animation_timer = QTimer(self)
        self._preview_animation_timer.setInterval(33)
        self._preview_animation_timer.timeout.connect(self._refresh_preview_animation)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.blind = False  # validation mode: hide engine opinions, keep audio
        self.header_label = QLabel("Select a transition to review it.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        lab_heading = QHBoxLayout()
        lab_title = QLabel("Transition Lab")
        lab_title.setProperty("role", "subtitle")
        lab_heading.addWidget(lab_title)
        provenance = QLabel("Host-side audition · research-inspired template · not DJ ground truth")
        provenance.setProperty("role", "hint")
        lab_heading.addWidget(provenance)
        lab_heading.addStretch(1)
        layout.addLayout(lab_heading)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Mix model:"))
        self.profile_combo = QComboBox()
        for profile_id, label in PROFILE_OPTIONS:
            self.profile_combo.addItem(label, profile_id)
        default_index = self.profile_combo.findData("plain_blend")
        self.profile_combo.setCurrentIndex(max(default_index, 0))
        self.profile_combo.setToolTip(
            "Audition template only. It does not change engine scores or exported cue points."
        )
        controls.addWidget(self.profile_combo)
        controls.addWidget(QLabel("Length:"))
        self.duration_combo = QComboBox()
        self.duration_combo.addItem(
            f"Auto · {DEFAULT_DURATION_BEATS} beats",
            "auto",
        )
        for beats in TRANSITION_DURATION_OPTIONS:
            self.duration_combo.addItem(f"{beats} beats", beats)
        self.duration_combo.setToolTip(
            "DJ transition lengths cluster on 32-beat phrase multiples. Auto keeps the "
            "64-beat corpus baseline; choose 128+ for a deliberately longer blend. "
            "The renderer shortens only when source audio would run out."
        )
        controls.addWidget(self.duration_combo)
        controls.addWidget(QLabel("Tempo:"))
        self.tempo_strategy_combo = QComboBox()
        self.tempo_strategy_combo.addItem("Follow outgoing", "follow_outgoing")
        self.tempo_strategy_combo.addItem(
            "M8-M10 recommendation (shadow)", "balanced_m10"
        )
        self.tempo_strategy_combo.setToolTip(
            "Research recommendation only. Playback keeps the validated follow-outgoing "
            "clock until beat-synchronous M11 validation proves the two-deck target safe."
        )
        controls.addWidget(self.tempo_strategy_combo)
        self.beat_sync_check = QCheckBox("Beat sync preview")
        self.beat_sync_check.setChecked(True)
        self.beat_sync_check.toggled.connect(self._apply_beat_sync)
        controls.addWidget(self.beat_sync_check)
        self.quantize_check = QCheckBox("Quantize seeks to 8-beat grid")
        self.quantize_check.setChecked(True)
        self.quantize_check.toggled.connect(self._apply_quantize)
        controls.addWidget(self.quantize_check)
        self.preview_button = QPushButton("▶ Render & audition")
        self.preview_button.setProperty("role", "hero")
        self.preview_button.setToolTip(
            "Render both sources into one sample-accurate phrase-locked WAV, then play it."
        )
        self.preview_button.clicked.connect(self.preview_transition)
        controls.addWidget(self.preview_button)
        self.stop_preview_button = QPushButton("■ Stop")
        self.stop_preview_button.setProperty("role", "secondary")
        self.stop_preview_button.clicked.connect(self.stop_preview)
        controls.addWidget(self.stop_preview_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.sync_status = QLabel("")
        self.sync_status.setProperty("role", "hint")
        layout.addWidget(self.sync_status)

        self.profile_description = QLabel("")
        self.profile_description.setProperty("role", "hint")
        self.profile_description.setWordWrap(True)
        layout.addWidget(self.profile_description)

        self.simulation_view = TransitionSimulationView()
        self.simulation_view.seekRequested.connect(self.seek_preview_fraction)
        layout.addWidget(self.simulation_view)

        self.simulation_status = QLabel(
            "Choose a pair, then Render & audition. Curves are visible before audio is rendered."
        )
        self.simulation_status.setProperty("role", "hint")
        self.simulation_status.setWordWrap(True)
        layout.addWidget(self.simulation_status)

        self.deck_a = Deck("Deck A (outgoing)", "A")
        self.deck_a.annotationCommitted.connect(self.annotationCommitted.emit)
        layout.addWidget(self.deck_a)
        self.deck_b = Deck("Deck B (incoming)", "B")
        self.deck_b.annotationCommitted.connect(self.annotationCommitted.emit)
        layout.addWidget(self.deck_b)
        layout.addStretch(1)

        legend = QLabel(
            "Orange dashed area: engine suggestion · cyan area: your transition correction · "
            "A–H: draggable hot cues · bright grid line: 8-beat quantize boundary"
        )
        legend.setProperty("role", "hint")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.duration_combo.currentIndexChanged.connect(self._on_duration_changed)
        self.tempo_strategy_combo.currentIndexChanged.connect(
            self._on_tempo_strategy_changed
        )
        self._on_profile_changed()

    def set_transition(
        self,
        analysis_a: AnalysisResult,
        analysis_b: AnalysisResult,
        transition: SetTransition,
        config: EngineConfig,
        windows_a: list[TransitionWindow],
        windows_b: list[TransitionWindow],
    ) -> None:
        self._current_pair_key = (analysis_a.track.track_id, analysis_b.track.track_id)
        self._invalidate_preview()
        header = [
            f"<b>{analysis_a.track.title or transition.from_track_id}"
            f"  →  {analysis_b.track.title or transition.to_track_id}</b>",
            f"score {transition.transition_score:.2f} · {transition.harmonic_relation}"
            + (
                f" · {transition.key_from}→{transition.key_to}"
                if transition.key_from
                else ""
            )
            + (
                f" · {transition.bpm_from:.0f}→{transition.bpm_to:.0f} BPM"
                if transition.bpm_from and transition.bpm_to
                else ""
            ),
        ]
        header.extend(f"⚠ {warning}" for warning in transition.warnings)
        if self.blind:
            # validation mode: no engine opinions may anchor the rater
            header = [header[0], "<i>Blind rating — engine opinions hidden. Listen and judge.</i>"]
        self.header_label.setText("<br>".join(header))

        self.deck_a.set_track(analysis_a, config, windows_a, WindowType.mix_out)
        self.deck_b.set_track(analysis_b, config, windows_b, WindowType.mix_in)
        self._apply_requested_duration_to_decks()
        self._apply_quantize(self.quantize_check.isChecked())
        self._apply_beat_sync(self.beat_sync_check.isChecked())
        self.simulation_status.setText(
            f"Ready · exact source IDs A: {analysis_a.track.track_id} · "
            f"B: {analysis_b.track.track_id} · {self._requested_duration_beats()}-beat preview"
        )

    def _apply_quantize(self, enabled: bool) -> None:
        self.deck_a.quantize = enabled
        self.deck_b.quantize = enabled
        if self._preview_result is not None:
            self._invalidate_preview("Quantize changed · render the preview again.")

    def _apply_beat_sync(self, enabled: bool) -> None:
        self.deck_a.set_playback_rate(1.0)
        self.deck_b.set_playback_rate(1.0)
        self._tempo_plan = None
        self.tempo_strategy_combo.setEnabled(enabled)
        if not enabled or self.deck_a.analysis is None or self.deck_b.analysis is None:
            self.sync_status.setText("Beat sync off — both decks play at native tempo.")
            if self._preview_result is not None:
                self._invalidate_preview("Beat sync changed · render the preview again.")
            return
        bpm_a = self.deck_a.analysis.track.bpm_estimate
        bpm_b = self.deck_b.analysis.track.bpm_estimate
        rate = beat_sync_rate(bpm_a, bpm_b)
        if rate is None:
            self.sync_status.setText(
                "Beat sync unavailable — BPM unknown on one of the tracks."
            )
            if self._preview_result is not None:
                self._invalidate_preview("Beat sync unavailable · render settings changed.")
            return

        # Keep the pre-M10 playback clock as the validated audio path. M8-M10
        # remains a shadow recommendation until beat-synchronous M11 validation
        # can measure phase drift instead of trusting two global BPM scalars.
        self.deck_b.set_playback_rate(rate)
        if self._tempo_strategy_id() == "balanced_m10":
            plan, unavailable_reason = self._build_balanced_preview_plan()
            if plan is None:
                self.sync_status.setText(
                    f"Stable sync active · B ×{rate:.4f} follows A at {bpm_a:.2f} BPM · "
                    "M8-M10 shadow unavailable — "
                    + (unavailable_reason or "tempo inputs failed validation")
                    + "."
                )
            elif not plan.within_review_band:
                self._tempo_plan = plan
                self.sync_status.setText(
                    f"Stable sync active · B ×{rate:.4f} follows A at {bpm_a:.2f} BPM · "
                    f"M8-M10 shadow target {plan.target_bpm:.3f} BPM is outside the "
                    f"±{plan.max_rate_delta * 100.0:.1f}% review band."
                )
            else:
                self._tempo_plan = plan
                octave_note = (
                    f" · metrical B 2^{plan.octave_b}={plan.selected_b_bpm:.2f} BPM"
                    if plan.octave_b
                    else ""
                )
                warning_note = f" · {plan.warnings[0]}" if plan.warnings else ""
                self.sync_status.setText(
                    f"Stable sync active · B ×{rate:.4f} follows A at {bpm_a:.2f} BPM · "
                    f"M8-M10 shadow target {plan.target_bpm:.3f} BPM "
                    f"(A ×{plan.rate_a:.4f}, B ×{plan.rate_b:.4f}) · "
                    f"confidence {plan.confidence:.2f}{octave_note}{warning_note}"
                )
            if self._preview_result is not None:
                self._invalidate_preview("Tempo strategy changed · render the preview again.")
            return
        self.sync_status.setText(
            f"Deck B rate ×{rate:.3f} → plays at {bpm_a:.1f} BPM (native {bpm_b:.1f})."
        )
        if self._preview_result is not None:
            self._invalidate_preview("Beat sync changed · render the preview again.")

    def _tempo_strategy_id(self) -> str:
        return str(self.tempo_strategy_combo.currentData() or "follow_outgoing")

    def _on_tempo_strategy_changed(self, _index: int = -1) -> None:
        self._apply_beat_sync(self.beat_sync_check.isChecked())

    def _build_balanced_preview_plan(self) -> tuple[TempoPlan | None, str | None]:
        analysis_a = self.deck_a.analysis
        analysis_b = self.deck_b.analysis
        if analysis_a is None or analysis_b is None:
            return None, "no transition pair is loaded"
        bpm_a = analysis_a.track.bpm_estimate
        bpm_b = analysis_b.track.bpm_estimate
        if not bpm_a or not bpm_b:
            return None, "BPM is missing on one of the tracks"
        grid_a = analysis_a.beatgrid
        grid_b = analysis_b.beatgrid
        if not grid_a or not grid_b or not grid_a.reliable or not grid_b.reliable:
            return None, "reliable beatgrids are required on both tracks"
        candidate_b = nearest_octave_candidate(float(bpm_a), float(bpm_b))
        plan = build_balanced_tempo_plan(
            float(bpm_a),
            float(bpm_b),
            selected_b_bpm=candidate_b.bpm,
            octave_b=candidate_b.octave_exponent,
            beatgrid_reliable_a=grid_a.reliable,
            beatgrid_reliable_b=grid_b.reliable,
            beatgrid_quality_a=grid_a.quality_score,
            beatgrid_quality_b=grid_b.quality_score,
        )
        return plan, None

    def _profile_id(self) -> str:
        return str(self.profile_combo.currentData() or "plain_blend")

    def _requested_duration_beats(self) -> int:
        value = self.duration_combo.currentData()
        return DEFAULT_DURATION_BEATS if value == "auto" else int(value)

    def _apply_requested_duration_to_decks(self) -> None:
        beats = self._requested_duration_beats()
        self.deck_a.set_preview_duration_beats(beats)
        self.deck_b.set_preview_duration_beats(beats)

    def _on_duration_changed(self, _index: int = -1) -> None:
        beats = self._requested_duration_beats()
        self._apply_requested_duration_to_decks()
        self._invalidate_preview()
        self.simulation_view.set_envelope(
            build_transition_envelope(self._profile_id(), duration_beats=beats)
        )
        if self._current_pair_key != ("", ""):
            self.simulation_status.setText(
                f"{beats}-beat phrase selected · Render & audition to hear it."
            )

    def _on_profile_changed(self) -> None:
        envelope = build_transition_envelope(
            self._profile_id(),
            duration_beats=self._requested_duration_beats(),
        )
        self.profile_description.setText(
            envelope.description
            + " Every control knot is locked to an 8-beat boundary; this is an audition model, "
            "not a claim about the transition a DJ actually performed."
        )
        self._invalidate_preview()
        self.simulation_view.set_envelope(envelope)
        if self._current_pair_key != ("", ""):
            self.simulation_status.setText("Mix model changed · Render & audition to hear it.")

    def _invalidate_preview(self, message: str | None = None) -> None:
        self._preview_token += 1
        self._preview_result = None
        self._preview_signature = None
        self._live_curves = {}
        if hasattr(self, "simulation_view"):
            self.simulation_view.clear_audio()
        if self._preview_player is not None:
            self._preview_player.stop()
            self._preview_player.setSource(QUrl())
        self._preview_animation_timer.stop()
        if hasattr(self, "preview_button"):
            self.preview_button.setEnabled(True)
            self.preview_button.setText("▶ Render & audition")
        if message and hasattr(self, "simulation_status"):
            self.simulation_status.setText(message)

    def _ensure_preview_player(self):
        if self._preview_player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._preview_player = QMediaPlayer(self)
            self._preview_audio_output = QAudioOutput(self)
            self._preview_audio_output.setVolume(0.9)
            self._preview_player.setAudioOutput(self._preview_audio_output)
            self._preview_player.positionChanged.connect(self._on_preview_position)
            self._preview_player.playbackStateChanged.connect(self._on_preview_state)
            self._preview_player.errorOccurred.connect(self._on_preview_error)
        return self._preview_player

    def _preview_inputs(
        self,
    ) -> tuple[
        tuple[object, ...],
        dict[str, Any],
        tuple[str, str],
        TransitionDurationPlan,
    ] | str:
        analysis_a = self.deck_a.analysis
        analysis_b = self.deck_b.analysis
        if analysis_a is None or analysis_b is None or self.deck_a.config is None:
            return "no transition pair loaded"
        requested_beats = self._requested_duration_beats()
        cue_a = self.deck_a.preview_cue_sec(duration_beats=requested_beats)
        cue_b = self.deck_b.preview_cue_sec(duration_beats=requested_beats)
        if cue_a is None:
            return "no outgoing transition region; mark one on Deck A"
        if cue_b is None:
            return "no incoming transition region; mark one on Deck B"
        bpm_a = analysis_a.track.bpm_estimate
        if not bpm_a:
            return "outgoing BPM unknown; phrase-locked rendering would be a guess"
        source_a = analysis_a.track.source_path or ""
        source_b = analysis_b.track.source_path or ""
        profile_id = self._profile_id()
        rate_a = self.deck_a.playback_rate if self.beat_sync_check.isChecked() else 1.0
        rate_b = self.deck_b.playback_rate if self.beat_sync_check.isChecked() else 1.0
        tempo_strategy = "native"
        preview_bpm = float(bpm_a)
        if self.beat_sync_check.isChecked():
            selected_strategy = self._tempo_strategy_id()
            tempo_strategy = (
                "follow_outgoing_m10_shadow"
                if selected_strategy == "balanced_m10" and self._tempo_plan is not None
                else "follow_outgoing"
            )

        duration_a = analysis_a.track.duration_sec
        duration_b = analysis_b.track.duration_sec
        if not duration_a or not duration_b:
            return "track duration unknown; source-runway safety cannot be verified"
        available_a_beats = (
            max(float(duration_a) - cue_a, 0.0) / float(rate_a) * preview_bpm / 60.0
        )
        available_b_beats = (
            max(float(duration_b) - cue_b, 0.0) / float(rate_b) * preview_bpm / 60.0
        )
        duration_plan = plan_transition_duration(
            requested_beats,
            available_a_beats=available_a_beats,
            available_b_beats=available_b_beats,
        )
        if duration_plan.selected_beats is None:
            return (
                "less than 32 safe beats remain at the selected cue; move the Deck A "
                "transition region earlier or choose another engine window"
            )
        duration_beats = duration_plan.selected_beats

        from dancelab.storage.cache_manager import cache_manager_for

        config = self.deck_a.config
        cache_dir = cache_manager_for(config).class_dir("temp")
        output_path = transition_preview_cache_path(
            cache_dir,
            source_a=source_a,
            source_b=source_b,
            track_id_a=analysis_a.track.track_id,
            track_id_b=analysis_b.track.track_id,
            cue_a_sec=cue_a,
            cue_b_sec=cue_b,
            preview_bpm=preview_bpm,
            playback_rate_a=rate_a,
            playback_rate_b=rate_b,
            tempo_strategy=tempo_strategy,
            profile_id=profile_id,
            duration_beats=duration_beats,
        )
        pair_key = (analysis_a.track.track_id, analysis_b.track.track_id)
        signature: tuple[object, ...] = (
            *pair_key,
            round(cue_a, 4),
            round(cue_b, 4),
            round(preview_bpm, 6),
            round(rate_a, 6),
            round(rate_b, 6),
            tempo_strategy,
            profile_id,
            duration_beats,
            bool(self.quantize_check.isChecked()),
        )
        render_args = {
            "source_a": source_a,
            "source_b": source_b,
            "cue_a_sec": cue_a,
            "cue_b_sec": cue_b,
            "bpm_master": float(preview_bpm),
            "playback_rate_a": float(rate_a),
            "playback_rate_b": float(rate_b),
            "tempo_strategy": tempo_strategy,
            "profile_id": profile_id,
            "output_path": output_path,
            "sample_rate": int(config.audio.sample_rate),
            "duration_beats": duration_beats,
        }
        return signature, render_args, pair_key, duration_plan

    def preview_transition(self) -> None:
        problems = []
        for name, deck in (("A", self.deck_a), ("B", self.deck_b)):
            issue = deck.playback_problem()
            if issue:
                problems.append(f"deck {name}: {issue}")
        if problems:
            # never fail silently — state exactly what blocks the preview
            message = "⚠ " + " · ".join(problems)
            self.sync_status.setText(message)
            self.simulation_status.setText(message)
            return
        inputs = self._preview_inputs()
        if isinstance(inputs, str):
            self.simulation_status.setText("⚠ " + inputs)
            return
        signature, render_args, pair_key, duration_plan = inputs
        if (
            self._preview_result is not None
            and self._preview_signature == signature
            and self._preview_result.output_path.exists()
        ):
            player = self._ensure_preview_player()
            if player.playbackState() == player.PlaybackState.PlayingState:
                player.pause()
            else:
                if player.source().isEmpty():
                    player.setSource(QUrl.fromLocalFile(str(self._preview_result.output_path)))
                player.play()
            return

        self.deck_a.stop()
        self.deck_b.stop()
        self._preview_token += 1
        token = self._preview_token
        worker = _TransitionRenderWorker(token, pair_key, render_args)
        worker.signals.finished.connect(self._on_transition_rendered)
        self._preview_workers[token] = worker
        self._pending_signatures[token] = signature
        self.preview_button.setEnabled(False)
        self.preview_button.setText("Rendering…")
        duration_beats = int(render_args["duration_beats"])
        duration_sec = duration_beats * 60.0 / float(render_args["bpm_master"])
        shortened = (
            f" · shortened from {duration_plan.requested_beats} to fit source runway"
            if duration_plan.shortened
            else ""
        )
        self.simulation_status.setText(
            f"Rendering one sample-accurate {duration_beats}-beat mix "
            f"(~{duration_sec:.1f}s audio){shortened} · A {pair_key[0]} · B {pair_key[1]}"
        )
        QThreadPool.globalInstance().start(worker)

    def _on_transition_rendered(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        token = int(payload.get("token", -1))
        self._preview_workers.pop(token, None)
        signature = self._pending_signatures.pop(token, None)
        if token != self._preview_token or payload.get("pair_key") != self._current_pair_key:
            return
        self.preview_button.setEnabled(True)
        error = payload.get("error")
        if error:
            self.preview_button.setText("▶ Render & audition")
            self.simulation_status.setText(f"⚠ Transition render failed: {error}")
            return
        result = payload.get("result")
        if not isinstance(result, TransitionRenderResult) or signature is None:
            self.simulation_status.setText("⚠ Transition renderer returned an invalid result.")
            return
        self._preview_result = result
        self._preview_signature = signature
        self._live_curves = sample_transition_envelope(result.envelope, 513)
        self.simulation_view.set_render_result(result)
        player = self._ensure_preview_player()
        player.setSource(QUrl.fromLocalFile(str(result.output_path)))
        player.setPosition(0)
        player.play()
        normalization = (
            f" · safety gain {result.normalization_gain:.2f}"
            if result.normalization_gain < 0.999
            else ""
        )
        self.simulation_status.setText(
            f"Playing exact A→B render · {result.envelope.label} · "
            f"{result.preview_bpm:.3f} BPM · A ×{result.playback_rate_a:.4f} · "
            f"B ×{result.playback_rate_b:.4f} · {result.tempo_strategy} · "
            f"stereo {result.output_subtype}{normalization}"
        )

    def seek_preview_fraction(self, fraction: float) -> None:
        if self._preview_result is None:
            self.simulation_status.setText("Render the transition before seeking the mixed preview.")
            return
        player = self._ensure_preview_player()
        if player.source().isEmpty():
            player.setSource(QUrl.fromLocalFile(str(self._preview_result.output_path)))
        player.setPosition(int(fraction * self._preview_result.duration_sec * 1000.0))
        self.simulation_view.set_playhead_fraction(fraction)

    def stop_preview(self) -> None:
        self._preview_animation_timer.stop()
        if self._preview_player is not None:
            self._preview_player.stop()
        self.preview_button.setText("▶ Audition rendered mix" if self._preview_result else "▶ Render & audition")
        self.simulation_view.set_playhead_fraction(0.0 if self._preview_result else None)

    def _on_preview_position(self, position_ms: int) -> None:
        if self._preview_result is None:
            return
        fraction = min(
            1.0,
            max(0.0, position_ms / max(self._preview_result.duration_sec * 1000.0, 1.0)),
        )
        self.simulation_view.set_playhead_fraction(fraction)
        if self._live_curves:
            index = min(int(round(fraction * 512)), 512)
            beat = fraction * self._preview_result.envelope.duration_beats
            self.simulation_status.setText(
                f"Beat {beat:.1f}/{self._preview_result.envelope.duration_beats} · "
                f"A fader {self._live_curves['fader_a'][index]:.2f} · "
                f"B fader {self._live_curves['fader_b'][index]:.2f} · "
                f"A low {self._live_curves['low_a'][index]:.2f} · "
                f"B low {self._live_curves['low_b'][index]:.2f}"
            )

    def _on_preview_state(self, state) -> None:
        if self._preview_player is None:
            return
        playing = state == self._preview_player.PlaybackState.PlayingState
        if playing:
            self._preview_animation_timer.start()
        else:
            self._preview_animation_timer.stop()
        self.preview_button.setText("⏸ Pause audition" if playing else "▶ Audition rendered mix")

    def _refresh_preview_animation(self) -> None:
        if self._preview_player is not None and self._preview_result is not None:
            self._on_preview_position(self._preview_player.position())

    def _on_preview_error(self, error, message: str) -> None:
        self.simulation_status.setText(f"⚠ Preview playback failed: {message or error}")

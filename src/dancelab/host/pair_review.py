"""Transition review tool: A/B decks, song structure, stems, beat sync.

Everything shown here is engine data, not decoration:
- structure strips paint the ACTUAL segments (intro/build/drop/breakdown/
  groove/outro) and transition windows the analysis produced;
- beat sync computes the playback rate from the two tracks' estimated BPMs
  (half/double-time aware, same octave-folding as the decision layer);
- quantize snaps seeks to the track's tracked beatgrid;
- stem isolation runs real source separation (demucs when installed) or an
  honest DSP fallback (HPSS harmonic/percussive split + low-pass bass) and is
  labeled accordingly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
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
from dancelab.decision.transition_windows import detect_transition_windows
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


def snap_to_grid(
    t_sec: float,
    beat_times: list[float] | None,
    downbeats: list[float] | None = None,
    *,
    bars: bool = False,
) -> float:
    """Snap a position to the nearest tracked beat (or downbeat when bars)."""
    grid = downbeats if bars and downbeats else beat_times
    if not grid:
        return t_sec
    arr = np.asarray(grid, dtype=np.float64)
    return float(arr[int(np.argmin(np.abs(arr - t_sec)))])


def best_window(
    windows: list[TransitionWindow], window_type: WindowType
) -> TransitionWindow | None:
    matching = [w for w in windows if w.window_type == window_type]
    if not matching:
        return None
    return max(matching, key=lambda w: w.score)


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


# ----------------------------------------------------------------- widgets


class StructureStrip(QWidget):
    """Paints waveform envelope + structure + transition windows + playhead."""

    seekRequested = Signal(float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(46)
        self.duration_sec = 0.0
        self.segments = []
        self.windows: list[TransitionWindow] = []
        self.waveform: list[float] = []
        self.playhead_sec: float | None = None

    def set_data(self, *, duration_sec: float, segments, windows, waveform=None) -> None:
        self.duration_sec = max(float(duration_sec or 0.0), 0.0)
        self.segments = list(segments or [])
        self.windows = list(windows or [])
        self.waveform = list(waveform or [])
        self.playhead_sec = None
        self.update()

    def set_playhead(self, sec: float | None) -> None:
        self.playhead_sec = sec
        self.update()

    def _x(self, t: float) -> float:
        if self.duration_sec <= 0:
            return 0.0
        return (t / self.duration_sec) * self.width()

    def mousePressEvent(self, event) -> None:
        if self.duration_sec > 0:
            self.seekRequested.emit(
                float(event.position().x()) / max(self.width(), 1) * self.duration_sec
            )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#17181a"))
        height = self.height()
        width = max(self.width(), 1)

        # Main lane: waveform-like RMS envelope from engine analysis frames.
        lane_top = 12
        lane_bottom = height - 8
        lane_mid = (lane_top + lane_bottom) / 2.0
        lane_half = max((lane_bottom - lane_top) / 2.0 - 2.0, 1.0)
        if self.waveform:
            painter.setPen(QPen(QColor("#d6d7d9"), 1))
            count = len(self.waveform)
            for index, value in enumerate(self.waveform):
                x = int(index / max(count - 1, 1) * width)
                amp = max(1.0, float(value) * lane_half)
                painter.drawLine(x, int(lane_mid - amp), x, int(lane_mid + amp))
            painter.setPen(QPen(QColor("#2f6fcf"), 1))
            painter.drawLine(0, int(lane_mid), width, int(lane_mid))

        # Structure stays visible, but as a thin map below the waveform instead
        # of replacing the waveform with big opaque blocks.
        for segment in self.segments:
            seg_type = getattr(segment.segment_type, "value", str(segment.segment_type))
            color = QColor(SEGMENT_COLORS.get(seg_type, SEGMENT_COLORS["unknown"]))
            color.setAlpha(190)
            x0 = self._x(segment.start_sec)
            x1 = self._x(segment.end_sec)
            painter.fillRect(int(x0), height - 8, max(int(x1 - x0) - 1, 1), 6, color)

        for window in self.windows:
            color = QColor(WINDOW_COLORS.get(window.window_type, QColor("#ffffff")))
            color.setAlpha(180)
            x0 = self._x(window.start_sec)
            x1 = self._x(window.end_sec)
            painter.fillRect(int(x0), 0, max(int(x1 - x0), 2), 12, color)

        if self.playhead_sec is not None and self.duration_sec > 0:
            painter.setPen(QPen(QColor("#f0d0a0"), 2))
            x = int(self._x(self.playhead_sec))
            painter.drawLine(x, 0, x, height)
        painter.end()


class Deck(QWidget):
    """One playable deck: structure strip, transport, stem isolation."""

    def __init__(self, role_label: str):
        super().__init__()
        self.analysis: AnalysisResult | None = None
        self.config: EngineConfig | None = None
        self.windows: list[TransitionWindow] = []
        self.cue_window_type = WindowType.mix_out
        self.quantize = True
        self.playback_rate = 1.0
        self._player = None
        self._audio_output = None
        self._stem_paths: dict[str, str] = {}
        self._stem_thread: QThread | None = None
        self._current_source_label = "Mix"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.title_label = QLabel(role_label)
        self.title_label.setProperty("role", "subtitle")
        layout.addWidget(self.title_label)

        self.strip = StructureStrip()
        self.strip.seekRequested.connect(self.seek)
        layout.addWidget(self.strip)

        transport = QHBoxLayout()
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_button)
        self.cue_button = QPushButton("Cue Window")
        self.cue_button.setToolTip("Jump to the best transition window (snapped to the beatgrid).")
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

    # --- data -----------------------------------------------------------

    def set_track(
        self,
        analysis: AnalysisResult,
        config: EngineConfig,
        windows: list[TransitionWindow],
        cue_window_type: WindowType,
    ) -> None:
        self.stop()
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
        self.strip.set_data(
            duration_sec=track.duration_sec or 0.0,
            segments=analysis.segments,
            windows=windows,
            waveform=waveform_envelope_from_features(analysis),
        )
        self._rebuild_stem_buttons()
        cue = best_window(windows, cue_window_type)
        self.cue_button.setText(
            f"Cue {cue_window_type.value.replace('_', '-')}"
            + (f" ({cue.start_sec:.0f}s)" if cue else " (none found)")
        )
        self.cue_button.setEnabled(cue is not None)

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
        out_root = str(
            Path(self.config.paths.processed_dir).expanduser() / "stem_preview"
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
        return self._player

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
        if self.quantize and self.analysis.beatgrid is not None:
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
        cue = best_window(self.windows, self.cue_window_type)
        if cue is not None:
            self.seek(cue.start_sec)

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
    """Full review tool for one transition: header + deck A + deck B."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.header_label = QLabel("Select a transition to review it.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        controls = QHBoxLayout()
        self.beat_sync_check = QCheckBox("Beat sync (incoming follows outgoing BPM)")
        self.beat_sync_check.setChecked(True)
        self.beat_sync_check.toggled.connect(self._apply_beat_sync)
        controls.addWidget(self.beat_sync_check)
        self.quantize_check = QCheckBox("Quantize seeks to beatgrid")
        self.quantize_check.setChecked(True)
        self.quantize_check.toggled.connect(self._apply_quantize)
        controls.addWidget(self.quantize_check)
        self.preview_button = QPushButton("▶ Preview Transition")
        self.preview_button.setProperty("role", "hero")
        self.preview_button.setToolTip(
            "Cue deck A at its mix-out window, deck B at its mix-in window "
            "(beat-synced) and play both."
        )
        self.preview_button.clicked.connect(self.preview_transition)
        controls.addWidget(self.preview_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.sync_status = QLabel("")
        self.sync_status.setProperty("role", "hint")
        layout.addWidget(self.sync_status)

        self.deck_a = Deck("Deck A (outgoing)")
        layout.addWidget(self.deck_a)
        self.deck_b = Deck("Deck B (incoming)")
        layout.addWidget(self.deck_b)
        layout.addStretch(1)

        legend = QLabel(
            "Structure: intro / build / drop / breakdown / groove / outro · "
            "top markers: transition windows (green mix-in, orange mix-out)"
        )
        legend.setProperty("role", "hint")
        legend.setWordWrap(True)
        layout.addWidget(legend)

    def set_transition(
        self,
        analysis_a: AnalysisResult,
        analysis_b: AnalysisResult,
        transition: SetTransition,
        config: EngineConfig,
        windows_a: list[TransitionWindow],
        windows_b: list[TransitionWindow],
    ) -> None:
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
        self.header_label.setText("<br>".join(header))

        self.deck_a.set_track(analysis_a, config, windows_a, WindowType.mix_out)
        self.deck_b.set_track(analysis_b, config, windows_b, WindowType.mix_in)
        self._apply_quantize(self.quantize_check.isChecked())
        self._apply_beat_sync(self.beat_sync_check.isChecked())

    def _apply_quantize(self, enabled: bool) -> None:
        self.deck_a.quantize = enabled
        self.deck_b.quantize = enabled

    def _apply_beat_sync(self, enabled: bool) -> None:
        self.deck_a.set_playback_rate(1.0)
        if not enabled or self.deck_a.analysis is None or self.deck_b.analysis is None:
            self.deck_b.set_playback_rate(1.0)
            self.sync_status.setText("Beat sync off — both decks play at native tempo.")
            return
        bpm_a = self.deck_a.analysis.track.bpm_estimate
        bpm_b = self.deck_b.analysis.track.bpm_estimate
        rate = beat_sync_rate(bpm_a, bpm_b)
        if rate is None:
            self.deck_b.set_playback_rate(1.0)
            self.sync_status.setText(
                "Beat sync unavailable — BPM unknown on one of the tracks."
            )
            return
        self.deck_b.set_playback_rate(rate)
        self.sync_status.setText(
            f"Deck B rate ×{rate:.3f} → plays at {bpm_a:.1f} BPM (native {bpm_b:.1f})."
        )

    def preview_transition(self) -> None:
        self.deck_a.cue_to_window()
        self.deck_b.cue_to_window()
        self.deck_a.toggle_play()
        self.deck_b.toggle_play()

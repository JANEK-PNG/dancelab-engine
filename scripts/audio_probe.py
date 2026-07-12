"""Audio probe: plays a 2 s tone via QMediaPlayer and reports the backend.

Run twice and note which one you can HEAR:
    PYTHONPATH=src .venv/bin/python scripts/audio_probe.py
    QT_MEDIA_BACKEND=darwin PYTHONPATH=src .venv/bin/python scripts/audio_probe.py
"""

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

import dancelab.host.desktop_app  # noqa: F401 — runs _prepare_qt_runtime (ENV-1 heal)
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

tone_path = Path(tempfile.mkdtemp()) / "probe_tone.wav"
sr = 44100
t = np.arange(sr * 2) / sr
sf.write(tone_path, (0.4 * np.sin(2 * np.pi * 440 * t)).astype("float32"), sr)

out = QAudioOutput()
out.setVolume(1.0)
player = QMediaPlayer()
player.setAudioOutput(out)
player.setSource(QUrl.fromLocalFile(str(tone_path)))

print(f"QT_MEDIA_BACKEND env : {os.environ.get('QT_MEDIA_BACKEND', '(default = ffmpeg)')}")
device = QMediaDevices.defaultAudioOutput()
print(f"output device        : {device.description()!r}")
print(f"output volume        : {out.volume()}")
player.errorOccurred.connect(lambda e, m: print(f"PLAYER ERROR: {e} {m}"))
player.playbackStateChanged.connect(lambda s: print(f"state: {s}"))
player.mediaStatusChanged.connect(lambda s: print(f"media: {s}"))
player.play()

QTimer.singleShot(2500, app.quit)
app.exec()
print("done — did you HEAR a 2-second beep? (tak/nie)")

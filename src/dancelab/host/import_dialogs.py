"""Qt helpers for safe audio import."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QListView,
    QMessageBox,
    QTreeView,
    QWidget,
)

from dancelab.ingestion.preflight import (
    find_suspicious_audio_files,
    format_duration,
    probe_audio_duration_sec,
)


def choose_audio_directories(
    parent: QWidget,
    *,
    title: str,
    start_dir: str,
) -> list[Path]:
    """Folder picker with multi-select enabled through Qt's non-native dialog."""
    dialog = QFileDialog(parent, title, start_dir)
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    for view in [*dialog.findChildren(QListView), *dialog.findChildren(QTreeView)]:
        view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    if not dialog.exec():
        return []
    return [Path(path).expanduser() for path in dialog.selectedFiles()]


def confirm_suspicious_audio_files(
    parent: QWidget,
    files: Sequence[str | Path],
    *,
    duration_probe: Callable[[str | Path], float | None] = probe_audio_duration_sec,
) -> list[Path]:
    """Ask whether unusually short/long files should be included."""
    normalized = [Path(path).expanduser() for path in files]
    suspicious = find_suspicious_audio_files(normalized, duration_probe=duration_probe)
    if not suspicious:
        return normalized

    suspicious_paths = {item.path for item in suspicious}
    normal_files = [path for path in normalized if path not in suspicious_paths]
    details = "\n".join(
        f"{item.path.name} · {format_duration(item.duration_sec)} · {item.reason}"
        for item in suspicious[:80]
    )
    if len(suspicious) > 80:
        details += f"\n... and {len(suspicious) - 80} more"

    message = QMessageBox(parent)
    message.setIcon(QMessageBox.Warning)
    message.setWindowTitle("Review unusual track lengths")
    message.setText(
        f"Found {len(suspicious)} audio file(s) shorter than 2 minutes or longer than 10 minutes."
    )
    message.setInformativeText(
        "These may be samples, loops, radio edits, podcasts, or recorded DJ sets. "
        "Do you want to include them in analysis?"
    )
    message.setDetailedText(details)
    skip_button = message.addButton("Skip suspicious", QMessageBox.AcceptRole)
    include_button = message.addButton("Include all", QMessageBox.DestructiveRole)
    cancel_button = message.addButton("Cancel import", QMessageBox.RejectRole)
    message.setDefaultButton(skip_button)
    message.exec()

    clicked = message.clickedButton()
    if clicked is include_button:
        return normalized
    if clicked is skip_button:
        return normal_files
    if clicked is cancel_button:
        return []
    return normal_files

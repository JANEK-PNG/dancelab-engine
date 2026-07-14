from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dancelab.host import desktop_app as desktop_app_module
from dancelab.host.desktop_app import desktop_available

if desktop_available():
    from PySide6.QtWidgets import QApplication
else:  # pragma: no cover - desktop dependency is optional
    QApplication = None


@lru_cache(maxsize=1)
def _qt_bootstrap_available() -> bool:
    if not desktop_available():
        return False

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen'); "
                "import dancelab.host.desktop_app; "
                "from PySide6.QtWidgets import QApplication; "
                "app = QApplication([]); "
                "print('qt-ok')"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")},
    )
    return probe.returncode == 0 and "qt-ok" in probe.stdout


def test_desktop_entrypoint_no_longer_exposes_visual_graph_editor():
    assert not hasattr(desktop_app_module, "NodeHostWindow")
    assert callable(desktop_app_module.launch_desktop_host)


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_desktop_product_surface_is_simple_mode_only():
    from dancelab.host.simple_mode import SimpleModeWindow

    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()

    assert window.windowTitle().startswith("DanceLab Pro")
    assert not hasattr(window, "open_graph_mode")
    assert not hasattr(window, "open_project_in_graph_mode")

    window.close()

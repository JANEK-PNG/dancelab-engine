"""DanceLab Pro desktop entry point.

The desktop product now exposes the guided Simple Mode workflow only. Engine
runtime adapters remain available as headless integration code, but the former
visual graph editor is intentionally not part of the application surface.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def _prepare_qt_runtime() -> None:
    """Expose bundled plugin directories without modifying installed files."""
    spec = importlib.util.find_spec("PySide6")
    if spec is None or not spec.submodule_search_locations:
        return

    pyside_dir = Path(next(iter(spec.submodule_search_locations)))
    plugins = pyside_dir / "Qt" / "plugins"
    if plugins.is_dir():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugins / "platforms"))
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))

@lru_cache(maxsize=1)
def desktop_available() -> bool:
    """Probe Qt in a child process so a broken plugin cannot abort the caller."""
    if importlib.util.find_spec("PySide6") is None:
        return False
    _prepare_qt_runtime()
    try:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os; "
                    "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen'); "
                    "from PySide6.QtWidgets import QApplication; "
                    "app = QApplication([]); "
                    "print('qt-ok')"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0 and "qt-ok" in probe.stdout


def desktop_requirement_message() -> str:
    return (
        "A working PySide6 desktop runtime is required for DanceLab Pro. "
        "Install it with `pip install .[desktop]` and verify the Qt platform plugin."
    )


def _require_pyside6() -> None:
    if not desktop_available():  # pragma: no cover - environment-dependent
        raise RuntimeError(desktop_requirement_message())


def launch_desktop_host(*, config_path: str | Path = "configs/default.yaml") -> int:
    """Launch the guided DanceLab Pro desktop workflow."""
    _require_pyside6()
    _prepare_qt_runtime()
    from PySide6.QtWidgets import QApplication

    from dancelab.host.simple_mode import SimpleModeWindow

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("DanceLab Pro")
    app.setApplicationDisplayName("DanceLab Pro")
    app.setOrganizationName("DanceLab")

    window = SimpleModeWindow(config_path=config_path)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


def main() -> int:
    return launch_desktop_host()

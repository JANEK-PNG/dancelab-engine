"""DanceLab Pro desktop entry point.

The desktop product now exposes the guided Simple Mode workflow only. Engine
runtime adapters remain available as headless integration code, but the former
visual graph editor is intentionally not part of the application surface.
"""

from __future__ import annotations

from pathlib import Path


def _prepare_qt_runtime() -> None:
    """Make the bundled PySide6 plugin directories visible on macOS."""
    import os
    import subprocess
    import sys

    try:
        import PySide6
    except ModuleNotFoundError:
        return

    pyside_dir = Path(PySide6.__file__).parent
    plugins = pyside_dir / "Qt" / "plugins"
    if plugins.is_dir():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugins / "platforms"))
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))

    if sys.platform != "darwin":
        return
    try:
        subprocess.run(
            ["chflags", "-R", "nohidden", str(pyside_dir)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        subprocess.run(
            ["xattr", "-rd", "com.apple.provenance", str(pyside_dir)],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception:
        # Launch hardening must never prevent the application from starting.
        pass


_prepare_qt_runtime()

try:  # optional desktop dependency
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
    _PYSIDE_IMPORT_ERROR = exc
else:
    _PYSIDE_IMPORT_ERROR = None


def desktop_available() -> bool:
    return _PYSIDE_IMPORT_ERROR is None


def desktop_requirement_message() -> str:
    return (
        "PySide6 is required for the DanceLab Pro desktop app. "
        "Install it with `pip install .[desktop]`."
    )


def _require_pyside6() -> None:
    if _PYSIDE_IMPORT_ERROR is not None:  # pragma: no cover - environment-dependent
        raise RuntimeError(desktop_requirement_message()) from _PYSIDE_IMPORT_ERROR


def launch_desktop_host(*, config_path: str | Path = "configs/default.yaml") -> int:
    """Launch the guided DanceLab Pro desktop workflow."""
    _require_pyside6()
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

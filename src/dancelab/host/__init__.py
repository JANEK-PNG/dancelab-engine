"""DanceLab Pro host package.

Headless modules must remain importable without loading Qt. Desktop helpers are
resolved lazily so API, CLI, validation, and test code never initialize GUI
bindings as a side effect of importing this package.
"""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name in {
        "desktop_available",
        "desktop_requirement_message",
        "launch_desktop_host",
    }:
        from dancelab.host import desktop_app

        return getattr(desktop_app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "desktop_available",
    "desktop_requirement_message",
    "launch_desktop_host",
]

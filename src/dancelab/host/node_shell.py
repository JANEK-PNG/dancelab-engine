"""Serve the external node-host shell HTML.

The shell is intentionally kept outside the engine core. It consumes the
`/contracts/node-host` registry and acts like a control surface attached to the
engine rather than part of the engine itself.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_ASSET_PATH = Path(__file__).resolve().parent / "assets" / "node_host_shell.html"


@lru_cache(maxsize=1)
def load_node_host_shell_html() -> str:
    return _ASSET_PATH.read_text(encoding="utf-8")

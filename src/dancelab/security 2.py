"""Shared output-encoding helpers for untrusted user and track metadata."""

from __future__ import annotations

import json
from typing import Any

_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_safe_value(value: Any) -> Any:
    """Neutralize text that spreadsheet applications may execute as a formula."""
    if not isinstance(value, str):
        return value
    candidate = value.lstrip(" \n")
    if candidate.startswith(_SPREADSHEET_FORMULA_PREFIXES):
        return "'" + value
    return value


def json_for_inline_script(value: Any) -> str:
    """Serialize JSON without allowing data to terminate an HTML script element."""
    payload = json.dumps(value, ensure_ascii=True)
    return (
        payload.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )

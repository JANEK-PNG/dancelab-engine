"""Shared output-encoding helpers for untrusted spreadsheet metadata."""

from __future__ import annotations

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

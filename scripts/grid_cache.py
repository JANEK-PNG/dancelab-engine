"""One place that answers "give me a trustworthy beat grid for this file".

Five scripts had each grown their own copy of this: read a JSON cache, fit the
grid if it is missing, write the cache back, and drop the answer if its confidence
is too low. Four copies is four chances for the confidence threshold to drift apart
and for two scripts to quietly disagree about which records are playable — and one
of them re-read and re-wrote the whole cache file once per track.

The fit itself lives in the engine (`core.rigid_grid`); only the caching is a script
concern, because it writes into experiments_priv.
"""

from __future__ import annotations

import json
from pathlib import Path

import seam_decompose as S
from dancelab.core.rigid_grid import fit_rigid_grid

MIN_CONTRAST = 2.0
PATH = Path(__file__).resolve().parents[1] / "experiments_priv/_cache/rigid_grids.json"

_cache: dict | None = None
_dirty = False


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(PATH.read_text()) if PATH.exists() else {}
    return _cache


def flush() -> None:
    """Write the cache once, rather than once per track."""
    global _dirty
    if _dirty and _cache is not None:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(_cache))
        _dirty = False


def raw(path: str) -> dict | None:
    """The fitted grid as stored — including one that failed its confidence check."""
    global _dirty
    cache = _load()
    key = str(path)
    if key not in cache:
        got = fit_rigid_grid(S.load_mono(path), S.SR)
        cache[key] = ({"bpm": got.bpm, "first": got.first_beat_sec,
                       "contrast": got.contrast} if got else None)
        _dirty = True
        flush()
    return cache[key]


def grid_for(path: str) -> dict | None:
    """Grid for this file, or None when no rigid grid explains it.

    A low score is not a number to report with a caveat — it means the record was
    not made to a fixed tempo, and the honest answer is that we have no grid.
    """
    g = raw(path)
    return g if g and g["contrast"] >= MIN_CONTRAST else None


def bars_for(path: str) -> tuple[float, float, float] | None:
    """(beat period, first beat, bar length) — what the snapping needs."""
    g = grid_for(path)
    if not g:
        return None
    period = 60.0 / g["bpm"]
    return period, float(g["first"]), 4.0 * period

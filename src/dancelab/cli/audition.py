"""Playback you can interrupt, repeat and compare.

Judging a seam is not listening once. It is listening again, listening to the
same thing at a different length, and going back to the previous version to be
sure. A blocking `afplay` gives none of that: the terminal is gone until the
file ends, so every comparison costs a full playthrough and the memory of the
one before.

This keeps the player in the background so the review screen stays alive: replay
on a keystroke, stop on a keystroke, repeat a loop as many times as it takes,
and A/B against whatever was auditioned before.

macOS `afplay` is used deliberately: it ships with the system, so auditioning
adds nothing to install. The module is a thin seam around it — swapping in ffplay
or VLC later means changing _spawn alone.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def player_available() -> bool:
    return shutil.which("afplay") is not None


def _spawn(path: Path, repeats: int) -> subprocess.Popen | None:
    """Start playback in the background. None when no player is installed."""
    if not player_available():
        return None
    if repeats <= 1:
        command = ["afplay", str(path)]
    else:
        # afplay has no repeat, so chain the plays in one shell process; a single
        # process id still stops the whole run.
        quoted = str(path).replace("'", "'\\''")
        command = ["/bin/sh", "-c",
                   f"for i in $(seq {int(repeats)}); do afplay '{quoted}'; done"]
    return subprocess.Popen(command, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


class Audition:
    """One background player plus the memory of what was heard before."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self.current: Path | None = None
        self.previous: Path | None = None

    # ------------------------------------------------------------- transport
    def play(self, path: Path, *, repeats: int = 1) -> bool:
        """Play `path`, replacing whatever is playing. False when unavailable."""
        path = Path(path)
        if not path.exists():
            return False
        self.stop()
        if self.current is not None and self.current != path:
            self.previous = self.current
        self.current = path
        self._process = _spawn(path, repeats)
        return self._process is not None

    def replay(self, *, repeats: int = 1) -> bool:
        """Hear the same thing again — the most-used key when judging."""
        return self.play(self.current, repeats=repeats) if self.current else False

    def back(self, *, repeats: int = 1) -> bool:
        """Return to the previous audition. This is the A/B."""
        if self.previous is None:
            return False
        # swap, so pressing it again returns to where we were: A, B, A, B...
        self.current, self.previous = self.previous, self.current
        target = self.current
        self.stop()
        self._process = _spawn(target, repeats)
        return self._process is not None

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    # ----------------------------------------------------------------- state
    @property
    def playing(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def __del__(self) -> None:  # pragma: no cover - interpreter teardown
        try:
            self.stop()
        except Exception:
            pass

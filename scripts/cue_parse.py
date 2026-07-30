"""Read a rekordbox recording .cue: which record played, from where, when.

rekordbox writes CRLF and quotes paths, and the same record legitimately appears
more than once in a set, so entries are kept as a list in play order rather than
keyed by path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_INDEX = re.compile(r"INDEX\s+01\s+(\d+):(\d+):(\d+)")


@dataclass
class CueEntry:
    n: int
    title: str
    performer: str
    path: str
    marker_sec: float          # when rekordbox logged this record, not when it was audible


def parse_cue(path: str | Path) -> tuple[Path, list[CueEntry]]:
    """Returns (mix wav path, entries in play order)."""
    path = Path(path)
    text = path.read_text(errors="replace").replace("\r", "")
    mix, entries = None, []
    title = performer = src = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('FILE "') and mix is None and "TRACK" not in text[:text.find(s)]:
            mix = path.parent / s.split('"')[1]
        elif s.startswith("TITLE "):
            title = s.split('"')[1] if '"' in s else s[6:]
        elif s.startswith("PERFORMER "):
            performer = s.split('"')[1] if '"' in s else s[10:]
        elif s.startswith('FILE "'):
            src = s.split('"')[1]
        elif (m := _INDEX.search(s)):
            h, mm, ss = (int(x) for x in m.groups())
            # HH:MM:SS, not the cue standard's MM:SS:FF. Checked against a measured
            # seam: the marker 00:33:31 lands on an entry independently aligned at
            # 2010.46 s, which only works if the last field is seconds.
            entries.append(CueEntry(len(entries) + 1, title or "?", performer or "?",
                                    src or "", h * 3600 + mm * 60 + ss))
    return mix, entries


if __name__ == "__main__":
    import sys

    for cue in sys.argv[1:]:
        mix, entries = parse_cue(cue)
        print(f"\n{Path(cue).name}  →  {mix.name if mix else '?'}")
        for e in entries:
            ok = "ok " if Path(e.path).exists() else "BRAK"
            print(f"  {e.n:2d} {e.marker_sec/60:5.2f} min  {ok}  "
                  f"{e.performer} — {e.title}")

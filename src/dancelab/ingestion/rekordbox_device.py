"""Rekordbox device (USB export) reader — real cues, no XML (SPEC §13).

Reads the ANLZ analysis files Rekordbox writes to a performance USB
(`PIONEER/USBANLZ/**/ANLZ0000.{DAT,EXT}`): the track's audio path (PPTH tag)
and its cue lists (PCO2 sections with PCP2 entries). Field layout was
reverse-verified byte-by-byte against a real device export on 2026-07-11
(hot cue slots, point vs loop, times, loop ends all matched the user's
Rekordbox screen), consistent with the community documentation of the
format (Deep Symmetry crate-digger).

This is the honest end of the import story: the DJ's own cue points become
engine data — a `rekordbox_hotcue` B-side source for TransitionCue instead
of a window-only guess.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

ANLZ_GLOB = "PIONEER/USBANLZ/**/ANLZ0000.EXT"


@dataclass(frozen=True)
class DeviceCue:
    list_type: str          # "hot" | "memory"
    hot_slot: int           # 1-8 = A-H for hot cues, 0 for memory cues
    cue_type: str           # "point" | "loop"
    time_ms: int
    loop_end_ms: int | None = None


@dataclass
class DeviceTrackCues:
    source_path: str        # path as stored on the device (PPTH)
    cues: list[DeviceCue] = field(default_factory=list)

    @property
    def hot_cues(self) -> list[DeviceCue]:
        return [c for c in self.cues if c.list_type == "hot"]

    @property
    def memory_cues(self) -> list[DeviceCue]:
        return [c for c in self.cues if c.list_type == "memory"]


def read_ppth(data: bytes) -> str | None:
    """PPTH tag → UTF-16BE audio path stored on the device."""
    i = data.find(b"PPTH")
    if i < 0:
        return None
    head_len, _total_len = struct.unpack(">II", data[i + 4 : i + 12])
    str_len = struct.unpack(">I", data[i + 12 : i + 16])[0]
    raw = data[i + head_len : i + head_len + str_len]
    return raw.decode("utf-16-be", errors="replace").rstrip("\x00")


def read_cues(data: bytes) -> list[DeviceCue]:
    """All PCO2 cue lists (extended cues) in an ANLZ .EXT blob."""
    cues: list[DeviceCue] = []
    i = 0
    while True:
        i = data.find(b"PCO2", i)
        if i < 0:
            break
        if i + 18 > len(data):
            break  # truncated tail — keep what parsed, never crash
        head_len, total_len = struct.unpack(">II", data[i + 4 : i + 12])
        list_type, count = struct.unpack(">IH", data[i + 12 : i + 18])
        j = i + head_len
        for _ in range(count):
            if data[j : j + 4] != b"PCP2":
                break  # malformed tail: keep what parsed, never crash
            _lh, entry_len = struct.unpack(">II", data[j + 4 : j + 12])
            if entry_len < 0x1C or j + entry_len > len(data):
                break
            slot = struct.unpack(">I", data[j + 0x0C : j + 0x10])[0]
            ctype = data[j + 0x10]
            time_ms = struct.unpack(">I", data[j + 0x14 : j + 0x18])[0]
            loop_end = struct.unpack(">I", data[j + 0x18 : j + 0x1C])[0]
            cues.append(
                DeviceCue(
                    list_type="hot" if list_type == 1 else "memory",
                    hot_slot=slot,
                    cue_type="loop" if ctype == 2 else "point",
                    time_ms=time_ms,
                    loop_end_ms=None if loop_end == 0xFFFFFFFF else loop_end,
                )
            )
            j += entry_len
        i += max(total_len, 12)
    return cues


def scan_device(device_root: str | Path) -> list[DeviceTrackCues]:
    """Scan a Rekordbox USB for every track that has cue data.

    Missing/unreadable ANLZ files are skipped, never fatal — a damaged stick
    yields a partial, honest result.
    """
    root = Path(device_root).expanduser()
    results: list[DeviceTrackCues] = []
    for ext_file in sorted(root.glob(ANLZ_GLOB)):
        try:
            data = ext_file.read_bytes()
        except OSError:
            continue
        cues = read_cues(data)
        if not cues:
            continue
        path = read_ppth(data)
        if path is None:
            dat = ext_file.with_suffix(".DAT")
            if dat.exists():
                path = read_ppth(dat.read_bytes())
        if path is None:
            continue
        results.append(DeviceTrackCues(source_path=path, cues=cues))
    return results

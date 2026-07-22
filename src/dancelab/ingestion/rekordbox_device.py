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
MAX_ANLZ_FILE_BYTES = 128 * 1024 * 1024
MAX_PATH_BYTES = 64 * 1024
MAX_CUE_LISTS = 1024
MAX_CUES_PER_LIST = 4096
MAX_TOTAL_CUES = 8192


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
    offset = 0
    while True:
        i = data.find(b"PPTH", offset)
        if i < 0:
            return None
        if i + 16 > len(data):
            return None
        head_len, total_len, str_len = struct.unpack_from(">III", data, i + 4)
        tag_end = i + total_len
        raw_start = i + head_len
        raw_end = raw_start + str_len
        if (
            16 <= head_len <= total_len
            and total_len <= len(data) - i
            and 0 < str_len <= MAX_PATH_BYTES
            and str_len % 2 == 0
            and raw_start <= raw_end <= tag_end
        ):
            raw = data[raw_start:raw_end]
            return raw.decode("utf-16-be", errors="replace").rstrip("\x00")
        offset = i + 4


def read_cues(data: bytes) -> list[DeviceCue]:
    """All PCO2 cue lists (extended cues) in an ANLZ .EXT blob."""
    cues: list[DeviceCue] = []
    i = 0
    cue_lists_seen = 0
    while cue_lists_seen < MAX_CUE_LISTS and len(cues) < MAX_TOTAL_CUES:
        found = data.find(b"PCO2", i)
        if found < 0:
            break
        i = found
        if i + 20 > len(data):
            break  # truncated tail — keep what parsed, never crash
        head_len, total_len, list_type, count = struct.unpack_from(">IIIH", data, i + 4)
        section_end = i + total_len
        if (
            head_len < 20
            or total_len < head_len
            or total_len > len(data) - i
            or list_type not in {0, 1}
            or count > MAX_CUES_PER_LIST
        ):
            i += 4
            continue
        cue_lists_seen += 1
        j = i + head_len
        for _ in range(count):
            if j + 12 > section_end or data[j : j + 4] != b"PCP2":
                break  # malformed tail: keep what parsed, never crash
            entry_header_len, entry_len = struct.unpack_from(">II", data, j + 4)
            if (
                entry_header_len < 12
                or entry_header_len > entry_len
                or entry_len < 0x1C
                or entry_len > section_end - j
            ):
                break
            slot = struct.unpack_from(">I", data, j + 0x0C)[0]
            ctype = data[j + 0x10]
            time_ms = struct.unpack_from(">I", data, j + 0x14)[0]
            loop_end = struct.unpack_from(">I", data, j + 0x18)[0]
            valid_slot = (list_type == 1 and 1 <= slot <= 8) or (
                list_type == 0 and slot == 0
            )
            valid_loop = (
                ctype != 2
                or loop_end == 0xFFFFFFFF
                or loop_end >= time_ms
            )
            if ctype not in {1, 2} or not valid_slot or not valid_loop:
                j += entry_len
                continue
            cues.append(
                DeviceCue(
                    list_type="hot" if list_type == 1 else "memory",
                    hot_slot=slot,
                    cue_type="loop" if ctype == 2 else "point",
                    time_ms=time_ms,
                    loop_end_ms=None if loop_end == 0xFFFFFFFF else loop_end,
                )
            )
            if len(cues) >= MAX_TOTAL_CUES:
                break
            j += entry_len
        i = section_end
    return cues


def _read_anlz_file(path: Path) -> bytes | None:
    try:
        if path.stat().st_size > MAX_ANLZ_FILE_BYTES:
            return None
        return path.read_bytes()
    except OSError:
        return None


def scan_device(device_root: str | Path) -> list[DeviceTrackCues]:
    """Scan a Rekordbox USB for every track that has cue data.

    Missing/unreadable ANLZ files are skipped, never fatal — a damaged stick
    yields a partial, honest result.
    """
    root = Path(device_root).expanduser()
    results: list[DeviceTrackCues] = []
    for ext_file in sorted(root.glob(ANLZ_GLOB)):
        data = _read_anlz_file(ext_file)
        if data is None:
            continue
        cues = read_cues(data)
        if not cues:
            continue
        path = read_ppth(data)
        if path is None:
            dat = ext_file.with_suffix(".DAT")
            if dat.exists():
                dat_data = _read_anlz_file(dat)
                if dat_data is not None:
                    path = read_ppth(dat_data)
        if path is None:
            continue
        results.append(DeviceTrackCues(source_path=path, cues=cues))
    return results

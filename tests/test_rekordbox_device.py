"""Rekordbox device reader — synthetic fixtures per the verified byte layout."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from dancelab.ingestion.rekordbox_device import (
    DeviceCue,
    read_cues,
    read_ppth,
    scan_device,
)


def _pcp2(slot: int, cue_type: int, time_ms: int, loop_end: int | None) -> bytes:
    entry = bytearray(88)
    entry[0:4] = b"PCP2"
    struct.pack_into(">II", entry, 4, 16, 88)          # len_header, len_entry
    struct.pack_into(">I", entry, 0x0C, slot)
    entry[0x10] = cue_type                              # 1=point, 2=loop
    struct.pack_into(">I", entry, 0x14, time_ms)
    struct.pack_into(">I", entry, 0x18, 0xFFFFFFFF if loop_end is None else loop_end)
    return bytes(entry)


def _pco2(list_type: int, entries: list[bytes]) -> bytes:
    body = b"".join(entries)
    head = bytearray(20)
    head[0:4] = b"PCO2"
    struct.pack_into(">II", head, 4, 20, 20 + len(body))
    struct.pack_into(">IH", head, 12, list_type, len(entries))
    return bytes(head) + body


def _ppth(path: str) -> bytes:
    raw = path.encode("utf-16-be") + b"\x00\x00"
    head = bytearray(16)
    head[0:4] = b"PPTH"
    struct.pack_into(">II", head, 4, 16, 16 + len(raw))
    struct.pack_into(">I", head, 12, len(raw))
    return bytes(head) + raw


def _ext_blob(path: str) -> bytes:
    hot = _pco2(1, [
        _pcp2(1, 1, 92_500, None),        # hot A point @ 1:32.5
        _pcp2(6, 2, 256_026, 263_137),    # hot F loop 4:16 → 4:23
    ])
    memory = _pco2(0, [_pcp2(0, 1, 30_800, None)])
    return _ppth(path) + hot + memory


def test_read_cues_and_ppth_roundtrip():
    blob = _ext_blob("/Contents/Muskila/YARAO (Original Mix).mp3")
    assert read_ppth(blob) == "/Contents/Muskila/YARAO (Original Mix).mp3"
    cues = read_cues(blob)
    assert cues == [
        DeviceCue("hot", 1, "point", 92_500, None),
        DeviceCue("hot", 6, "loop", 256_026, 263_137),
        DeviceCue("memory", 0, "point", 30_800, None),
    ]


def test_scan_device_partial_and_malformed_safe(tmp_path):
    anlz_dir = tmp_path / "PIONEER" / "USBANLZ" / "P001" / "0001"
    anlz_dir.mkdir(parents=True)
    (anlz_dir / "ANLZ0000.EXT").write_bytes(_ext_blob("/Contents/A.mp3"))
    broken = tmp_path / "PIONEER" / "USBANLZ" / "P001" / "0002"
    broken.mkdir(parents=True)
    (broken / "ANLZ0000.EXT").write_bytes(b"PCO2garbage")  # malformed → skipped

    tracks = scan_device(tmp_path)
    assert len(tracks) == 1
    assert tracks[0].source_path == "/Contents/A.mp3"
    assert len(tracks[0].hot_cues) == 2
    assert len(tracks[0].memory_cues) == 1


@pytest.mark.skipif(
    not Path("/Volumes/JANTRY/PIONEER/USBANLZ").exists(),
    reason="user's Rekordbox USB not mounted",
)
def test_scan_real_device_ground_truth():
    # Ground truth from the byte-level verification session (2026-07-11).
    tracks = scan_device("/Volumes/JANTRY")
    assert len(tracks) >= 30
    total_hot = sum(len(t.hot_cues) for t in tracks)
    assert total_hot >= 70
    yarao = next(
        (t for t in tracks if "YARAO" in t.source_path), None
    )
    assert yarao is not None
    slots = {c.hot_slot for c in yarao.hot_cues}
    assert {1, 2, 3, 4, 5, 6} <= slots
    point_e = next(c for c in yarao.hot_cues if c.hot_slot == 5)
    assert point_e.cue_type == "point" and point_e.time_ms == 205_804

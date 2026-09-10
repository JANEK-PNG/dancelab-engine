"""ISRC bridge: tag reader, batched catalog resolve, bridge file, identity pass.

Nothing touches the network or the owner's files: tags are written into
throwaway WAV files in ``tmp_path`` and the Apple client gets a fake fetch.
"""

from __future__ import annotations

import json
import unicodedata
import wave

import pytest

from dancelab.core.models import AnalysisResult, Track
from dancelab.ingestion import analysis_enrichment as ae
from dancelab.ingestion import apple_playlist as ap
from dancelab.ingestion import isrc_bridge as ib
from dancelab.ingestion.apple_music_api import AppleMusicClient


def _wav(path, isrc: str | None = None, txxx: bool = False):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 80)
    if isrc is not None:
        from mutagen.id3 import TSRC, TXXX
        from mutagen.wave import WAVE
        f = WAVE(str(path))
        f.add_tags()
        if txxx:
            f.tags.add(TXXX(encoding=3, desc="ISRC", text=[isrc]))
        else:
            f.tags.add(TSRC(encoding=3, text=[isrc]))
        f.save()
    return path


def _a(tid: str, path: str, cid: str | None = None) -> AnalysisResult:
    return AnalysisResult(engine_version="test", track=Track(
        track_id=tid, title=tid, source_path=path, apple_catalog_id=cid))


# ------------------------------------------------------------------ reader

def test_normalize_isrc_accepts_only_the_twelve_character_form():
    assert ib.normalize_isrc("gb-abc-26-00001") == "GBABC2600001"
    assert ib.normalize_isrc(" GB ABC 26 00001 ") == "GBABC2600001"
    assert ib.normalize_isrc("GBABC260001") is None          # 11 characters
    assert ib.normalize_isrc("1BABC2600001") is None         # country must be letters
    assert ib.normalize_isrc(None) is None


def test_read_isrc_from_tsrc_and_txxx_and_nothing(tmp_path):
    assert ib.read_isrc(_wav(tmp_path / "a.wav", "GB-ABC-26-00001")) == "GBABC2600001"
    assert ib.read_isrc(_wav(tmp_path / "b.wav", "USRC17607839", txxx=True)) == "USRC17607839"
    assert ib.read_isrc(_wav(tmp_path / "c.wav")) is None
    assert ib.read_isrc(tmp_path / "missing.aiff") is None


def test_collect_isrcs_counts_per_extension_and_keys_by_nfc(tmp_path):
    nfd = unicodedata.normalize("NFD", "Zażółć.wav")
    _wav(tmp_path / nfd, "GBABC2600001")
    _wav(tmp_path / "bez.wav")
    found, per_ext = ib.collect_isrcs([str(tmp_path / nfd), str(tmp_path / "bez.wav")])
    assert per_ext == {".wav": (1, 2)}
    (key,) = found
    assert key == unicodedata.normalize("NFC", key)


# ---------------------------------------------------------------- resolver

class FakeCatalog:
    """Answers songs-by-ISRC like Apple: several songs per ISRC possible, any order."""

    def __init__(self, table: dict[str, list[str]]):
        self.table = table
        self.calls: list[dict] = []

    def fetch(self, url, params, headers):
        self.calls.append({"url": url, **params})
        wanted = params["filter[isrc]"].split(",")
        data = [{"id": cid, "attributes": {"isrc": isrc, "genreNames": ["Techno", "Music"],
                                           "name": f"n{cid}", "artistName": "a"}}
                for isrc in reversed(wanted) for cid in self.table.get(isrc, [])]
        return 200, {}, json.dumps({"data": data}).encode()


def test_resolve_batches_by_25_and_prefers_the_library_copy():
    isrcs = [f"GBABC26{n:05d}" for n in range(30)]
    table = {i: [f"c{k}"] for k, i in enumerate(isrcs[:20])}
    table[isrcs[0]] = ["other", "c0"]                          # two songs, one in library
    fake = FakeCatalog(table)
    client = AppleMusicClient("dev", "usr", fetch=fake.fetch, sleep=lambda s: None)
    out = ib.resolve_isrcs(client, isrcs + ["garbage"], "pl", library_ids={"c0"})
    assert len(fake.calls) == 2, "30 valid ISRCs → two calls of at most 25"
    assert all(len(c["filter[isrc]"].split(",")) <= ib.ISRC_BATCH for c in fake.calls)
    assert fake.calls[0]["url"].endswith("/v1/catalog/pl/songs")
    assert len(out) == 20
    assert out[isrcs[0]].catalog_id == "c0" and out[isrcs[0]].in_library
    assert out[isrcs[5]].catalog_id == "c5", "keyed by returned ISRC, not request order"


def test_bridge_roundtrip_keys_by_nfc(tmp_path):
    nfd = unicodedata.normalize("NFD", "/m/Zażółć.aiff")
    songs = {"GBABC2600001": ib.ResolvedSong("123", True, ["Techno"], "t", "a")}
    path = tmp_path / "most.json"
    ib.write_bridge(path, "pl", {nfd: "GBABC2600001", "/m/x.mp3": "GBABC2600009"}, songs)
    bridge, note = ib.load_bridge(path)
    assert list(bridge) == [unicodedata.normalize("NFC", nfd)], "unresolved ISRC left out"
    assert bridge[unicodedata.normalize("NFC", nfd)]["catalog_id"] == "123"
    assert "1 plików" in note
    assert ib.load_bridge(tmp_path / "nope.json")[0] == {}


# --------------------------------------------------------- identity + genre

def test_identity_pass_stamps_streams_and_bridged_files_and_counts_twins():
    nfd = unicodedata.normalize("NFD", "/m/Zażółć.aiff")
    pool = [_a("s1", "apple-music:tracks:111"), _a("f1", nfd), _a("f2", "/m/solo.mp3"),
            _a("f3", "/m/brak.wav")]
    bridge = {unicodedata.normalize("NFC", nfd): {"catalog_id": "111"},
              "/m/solo.mp3": {"catalog_id": "222"}}
    rep = ae.attach_apple_identity(pool, bridge=bridge)
    assert [a.track.apple_catalog_id for a in pool] == ["111", "111", "222", None]
    assert (rep.attached, rep.missing) == (3, 1)
    assert any(n.startswith("1 plików lokalnych ma bliźniaka") for n in rep.notes)


def test_bridge_genre_fills_a_gap_but_umbrella_stays_refused(monkeypatch):
    nfd = unicodedata.normalize("NFD", "/m/Zażółć.aiff")
    monkeypatch.setattr(ae, "load_apple_genre_map", lambda: ({}, "lib"))
    monkeypatch.setattr(ae, "load_bridge_genre_map", lambda: (
        {unicodedata.normalize("NFC", nfd): "Deep House", "/m/u.mp3": "Electronic"}, "most"))
    a, u = _a("f1", nfd), _a("f2", "/m/u.mp3")
    rep = ae.attach_apple_genres([a, u])
    assert (a.track.style_label, a.track.style_label_source) == ("Deep House", "apple")
    assert u.track.style_label is None
    assert rep.attached == 1


def test_planner_sends_a_bridged_local_file():
    pool = {"f1": _a("f1", "/m/a.aiff", cid="999"), "f2": _a("f2", "/m/b.wav"),
            "s1": _a("s1", "apple-music:tracks:111", cid="111")}
    plan = ap.plan_apple_playlist(["f1", "f2", "s1"], pool, "T")
    assert plan.catalog_ids == ["999", "111"]
    assert dict(plan.skipped) == {"f2": ap.REASON_LOCAL}


def test_bridge_twin_of_a_stream_is_sent_once():
    pool = {"f1": _a("f1", "/m/a.aiff", cid="111"),
            "s1": _a("s1", "apple-music:tracks:111", cid="111")}
    plan = ap.plan_apple_playlist(["f1", "s1"], pool, "T")
    assert plan.catalog_ids == ["111"]
    assert dict(plan.skipped) == {"s1": ap.REASON_DUPLICATE}


@pytest.mark.parametrize("value", ["", "apple-music:tracks:"])
def test_empty_stream_path_is_not_an_identity(value):
    pool = [_a("x", value or "/m/none.wav")]
    rep = ae.attach_apple_identity(pool, bridge={})
    assert pool[0].track.apple_catalog_id is None and rep.missing == 1

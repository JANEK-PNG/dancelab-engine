"""Rekordbox XML export — schema, beatgrid, cues, playlist order, URI encoding."""

import xml.etree.ElementTree as ET

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    FeatureFrame,
    SetPlan,
    Track,
    TransitionWindow,
    WindowType,
)
from dancelab.export.rekordbox import _location_uri, build_rekordbox_xml


def make_track(tid, title, bpm, key, path, dur=300.0):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=tid, title=title, artist="A", bpm_estimate=bpm,
                    key_estimate=key, source_path=path, duration_sec=dur, sample_rate=44100),
        beatgrid=BeatGrid(bpm=bpm, beat_times_sec=[0.1, 0.5, 0.9], downbeats_sec=[0.1]),
        features=[FeatureFrame(track_id=tid, timestamp_sec=0.0, rms=0.3)],
    )


def test_xml_is_valid_and_has_structure():
    tracks = [make_track("t1", "One", 128, "8A", "/Music/one.mp3"),
              make_track("t2", "Two", 130, "9A", "/Music/two.aiff")]
    xml = build_rekordbox_xml(tracks)
    root = ET.fromstring(xml)
    assert root.tag == "DJ_PLAYLISTS"
    assert root.find("PRODUCT").get("Name") == "DanceLab Engine"
    collection = root.find("COLLECTION")
    assert collection.get("Entries") == "2"
    assert len(collection.findall("TRACK")) == 2


def test_track_carries_bpm_key_beatgrid():
    xml = build_rekordbox_xml([make_track("t1", "One", 128, "8A", "/Music/one.mp3")])
    track = ET.fromstring(xml).find("COLLECTION/TRACK")
    assert track.get("AverageBpm") == "128.00"
    assert track.get("Tonality") == "8A"          # Camelot → Rekordbox Tonality
    tempo = track.find("TEMPO")
    assert tempo.get("Bpm") == "128.00" and tempo.get("Metro") == "4/4"
    assert tempo.get("Inizio") == "0.100"          # first downbeat


def test_transition_windows_become_hot_cues():
    tracks = [make_track("t1", "One", 128, "8A", "/Music/one.mp3")]
    windows = {"t1": [
        TransitionWindow(start_sec=250.0, end_sec=266.0, score=0.9, window_type=WindowType.mix_out),
        TransitionWindow(start_sec=16.0, end_sec=32.0, score=0.7, window_type=WindowType.mix_in),
    ]}
    xml = build_rekordbox_xml(tracks, windows_by_track=windows)
    marks = ET.fromstring(xml).findall("COLLECTION/TRACK/POSITION_MARK")
    assert len(marks) == 2
    assert marks[0].get("Name") == "Mix Out"       # highest score first → Num 0 (hot cue A)
    assert marks[0].get("Num") == "0" and marks[0].get("Start") == "250.000"
    assert marks[0].get("Type") == "0"


def test_set_plan_orders_playlist():
    tracks = [make_track("t1", "One", 128, "8A", "/Music/one.mp3"),
              make_track("t2", "Two", 130, "9A", "/Music/two.mp3"),
              make_track("t3", "Three", 126, "8B", "/Music/three.mp3")]
    plan = SetPlan(track_order=["t2", "t3", "t1"])
    xml = build_rekordbox_xml(tracks, set_plan=plan, playlist_name="My Set")
    root = ET.fromstring(xml)
    pl = root.find("PLAYLISTS/NODE/NODE")
    assert pl.get("Name") == "My Set" and pl.get("Entries") == "3"
    # playlist TRACK refs use collection TrackIDs in set order (t2=1, t3=2, t1=3)
    keys = [tr.get("Key") for tr in pl.findall("TRACK")]
    id_map = {t.get("Name"): t.get("TrackID") for t in root.findall("COLLECTION/TRACK")}
    assert keys == [id_map["Two"], id_map["Three"], id_map["One"]]


def test_location_uri_encodes_spaces():
    uri = _location_uri("/Users/dj/Music/Track Name (Mix).mp3")
    assert uri.startswith("file://localhost/")
    assert "%20" in uri and "Track" in uri


def test_export_without_key_omits_tonality():
    a = make_track("t1", "One", 128, None, "/Music/one.mp3")
    a.track.key_estimate = None
    track = ET.fromstring(build_rekordbox_xml([a])).find("COLLECTION/TRACK")
    assert track.get("Tonality") is None  # honest: no fake key

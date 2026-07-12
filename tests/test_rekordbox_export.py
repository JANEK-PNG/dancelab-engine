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
from dancelab.export.rekordbox import _cue_phrase_division, _location_uri, build_rekordbox_xml


def make_track(tid, title, bpm, key, path, dur=300.0):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=tid, title=title, artist="A", bpm_estimate=bpm,
                    key_estimate=key, source_path=path, duration_sec=dur, sample_rate=44100),
        beatgrid=BeatGrid(bpm=bpm, beat_times_sec=[0.1, 0.5, 0.9], downbeats_sec=[0.1]),
        features=[FeatureFrame(track_id=tid, timestamp_sec=0.0, rms=0.3)],
    )


def make_phrase_track(tid="t1", bpm=120.0):
    beat_period = 60.0 / bpm
    beats = [round(i * beat_period, 6) for i in range(256)]
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=tid,
            title="Phrase Test",
            artist="A",
            bpm_estimate=bpm,
            key_estimate="8A",
            source_path="/Music/phrase.mp3",
            duration_sec=120.0,
            sample_rate=44100,
        ),
        beatgrid=BeatGrid(
            bpm=bpm,
            beat_times_sec=beats,
            downbeats_sec=beats[::4],
        ),
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


def test_default_export_does_not_override_rekordbox_bpm_or_beatgrid():
    xml = build_rekordbox_xml([make_track("t1", "One", 128, "8A", "/Music/one.mp3")])
    track = ET.fromstring(xml).find("COLLECTION/TRACK")
    assert track.get("Tonality") == "8A"          # Camelot → Rekordbox Tonality
    assert track.get("AverageBpm") is None
    assert track.find("TEMPO") is None


def test_diagnostic_export_can_carry_bpm_key_beatgrid_when_explicit():
    xml = build_rekordbox_xml(
        [make_track("t1", "One", 128, "8A", "/Music/one.mp3")],
        export_beatgrid=True,
    )
    track = ET.fromstring(xml).find("COLLECTION/TRACK")
    assert track.get("AverageBpm") == "128.00"
    tempo = track.find("TEMPO")
    assert tempo.get("Bpm") == "128.00" and tempo.get("Metro") == "4/4"
    assert tempo.get("Inizio") == "0.100"          # first downbeat


def test_hot_cues_snap_to_phrase_boundaries_not_third_beat():
    analysis = make_phrase_track(bpm=120.0)
    windows = {
        "t1": [
            # 1.5 s at 120 BPM is beat 3 from the grid anchor; cue must move
            # to beat 4 rather than exporting a third-beat hot cue.
            TransitionWindow(
                start_sec=1.5,
                end_sec=17.5,
                score=0.9,
                window_type=WindowType.mix_in,
            ),
            # Near beat 64: this should preserve the stronger phrase boundary.
            TransitionWindow(
                start_sec=31.7,
                end_sec=47.7,
                score=0.8,
                window_type=WindowType.mix_out,
            ),
        ]
    }

    marks = ET.fromstring(build_rekordbox_xml([analysis], windows_by_track=windows)).findall(
        "COLLECTION/TRACK/POSITION_MARK"
    )
    starts = [float(mark.get("Start")) for mark in marks]

    assert starts == [2.0, 32.0]
    assert _cue_phrase_division(analysis.beatgrid, starts[0]) == 4
    assert _cue_phrase_division(analysis.beatgrid, starts[1]) == 64


def test_unreliable_grid_is_not_exported_or_used_for_cue_snap():
    analysis = make_track("t1", "One", 128, "8A", "/Music/one.mp3")
    analysis.beatgrid = BeatGrid(
        bpm=128.0,
        beat_times_sec=[0.1, 0.5, 0.9],
        downbeats_sec=[0.1],
        reliable=False,
        diagnostic_flags=["grid_drift"],
    )
    windows = {
        "t1": [
            TransitionWindow(
                start_sec=250.2,
                end_sec=266.0,
                score=0.9,
                window_type=WindowType.mix_out,
            )
        ]
    }

    track = ET.fromstring(build_rekordbox_xml([analysis], windows_by_track=windows)).find("COLLECTION/TRACK")
    assert track.find("TEMPO") is None
    assert track.find("POSITION_MARK").get("Start") == "250.200"


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
    assert marks[0].get("Num") == "0" and marks[0].get("Start") == "250.412"
    assert marks[0].get("Type") == "0"


def test_playlist_hot_cues_are_role_aware_and_not_clustered():
    tracks = [make_track("t1", "One", 128, "8A", "/Music/one.mp3")]
    windows = {
        "t1": [
            TransitionWindow(start_sec=250.0, end_sec=266.0, score=0.95, window_type=WindowType.mix_out),
            TransitionWindow(start_sec=252.0, end_sec=268.0, score=0.93, window_type=WindowType.mix_out),
            TransitionWindow(start_sec=16.0, end_sec=32.0, score=0.80, window_type=WindowType.mix_in),
            TransitionWindow(start_sec=120.0, end_sec=136.0, score=0.70, window_type=WindowType.bridge),
        ]
    }
    plan = SetPlan(track_order=["t1"])
    xml = build_rekordbox_xml(tracks, set_plan=plan, windows_by_track=windows)
    marks = ET.fromstring(xml).findall("COLLECTION/TRACK/POSITION_MARK")
    starts = [float(mark.get("Start")) for mark in marks]

    assert len(marks) == 3
    assert [mark.get("Name") for mark in marks] == ["Mix Out", "Mix In", "Bridge"]
    assert 252.0 not in starts
    assert min(abs(a - b) for index, a in enumerate(starts) for b in starts[index + 1:]) >= 32.0


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


def test_location_uri_matches_rekordbox_own_encoding():
    # Verified against a real Rekordbox device library: RB leaves parens,
    # apostrophes etc. literal and only percent-encodes spaces — encoding
    # them (%28/%27) makes RB fail to match the file and drop our hot cues.
    from dancelab.export.rekordbox import _location_uri

    uri = _location_uri("/Volumes/JANTRY/Contents/Bicep/CHROMA 010 (Original Mix).aiff")
    assert uri == (
        "file://localhost/Volumes/JANTRY/Contents/Bicep/CHROMA%20010%20(Original%20Mix).aiff"
    )
    assert "%28" not in uri and "%29" not in uri

    uri = _location_uri("/Music/O'Flynn/Pearl's Girl.aiff")
    assert "'" in uri and "%27" not in uri
    assert "%20" not in _location_uri("/a/plain.wav")

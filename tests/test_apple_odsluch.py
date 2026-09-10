"""Apple Music streams play in the window: the bridge side of it.

The playback itself runs in MusicKit JS inside the window; what the bridge
owes it is (1) the catalog id of a stream when "graj" is pressed, with the
local player silenced, (2) rows that say a stream is playable, and (3) the
tokens, handed over js_api and cached, never fetched when unconfigured.
"""

from __future__ import annotations

import pytest

from dancelab.core.models import AnalysisResult, Track
from dancelab.gui import most as most_mod
from dancelab.gui.most import Most
from dancelab.ingestion import apple_music_api as am


def _a(tid: str, path: str) -> AnalysisResult:
    return AnalysisResult(engine_version="test", track=Track(track_id=tid, title=tid,
                                                             source_path=path))


@pytest.fixture
def most(tmp_path, monkeypatch):
    m = Most(katalog=str(tmp_path / "processed"))
    monkeypatch.setattr(type(m), "PLIK_EDYCJI", str(tmp_path / "edycje.json"))
    m._analizy = {"s1": _a("s1", "apple-music:tracks:111"),
                  "f1": _a("f1", "/nie/ma/takiego/pliku.aiff")}
    return m


def test_graj_on_a_stream_hands_the_catalog_id_to_the_window(most):
    stopped = []
    most._audio.stop = lambda: stopped.append(True) or False
    odp = most.graj("s1")
    assert odp["bez_pliku"] is True and odp["apple_id"] == "111"
    assert stopped, "the local player is silenced so two tracks never play at once"


def test_graj_on_a_missing_file_stays_a_plain_refusal(most):
    odp = most.graj("f1")
    assert odp["bez_pliku"] is True and "apple_id" not in odp


def test_rows_mark_streams_as_apple(most):
    assert most._wiersz("s1", most._analizy)["apple"] == "111"
    assert most._wiersz("f1", most._analizy)["apple"] is None


def test_apple_odtwarzacz_without_config_says_what_is_missing(most, monkeypatch):
    def brak(*_a, **_k):
        raise am.ConfigError("brak konfig.json")
    monkeypatch.setattr(am, "load_config", brak)
    assert most.apple_odtwarzacz() == {"blad": "brak konfig.json"}


def test_apple_odtwarzacz_without_user_token_says_authorize(most, monkeypatch):
    monkeypatch.setattr(am, "load_config", lambda *a: {"klucz": "/k.p8", "key_id": "K",
                                                       "team_id": "TEAM"})
    monkeypatch.setattr(am, "read_user_token", lambda *a: None)
    assert "autoryzuj" in most.apple_odtwarzacz()["blad"]


def test_apple_odtwarzacz_hands_tokens_once_per_hour(most, monkeypatch):
    minted = []
    monkeypatch.setattr(am, "load_config", lambda *a: {"klucz": "/k.p8", "key_id": "K",
                                                       "team_id": "5S3ANAYTCX"})
    monkeypatch.setattr(am, "read_user_token", lambda *a: "USR")
    monkeypatch.setattr(am, "developer_token", lambda *a, **k: minted.append(1) or "DEV")
    monkeypatch.setattr(Most, "_apple_storefront", staticmethod(lambda dev, user: "pl"))
    odp = most.apple_odtwarzacz()
    assert odp == {"ok": True, "dev": "DEV", "user": "USR", "team": "5s3anaytcx",
                   "storefront": "pl"}
    most.apple_odtwarzacz()
    assert minted == [1], "the developer token is reused while it has time left"


def test_storefront_unknown_is_none_not_a_guess(monkeypatch):
    class Pada:
        def __init__(self, *a, **k):
            pass

        def get(self, *a, **k):
            raise RuntimeError("Apple Music API 500")
    monkeypatch.setattr(am, "AppleMusicClient", Pada)
    assert most_mod.Most._apple_storefront("dev", "usr") is None


def test_library_rows_get_the_apple_id_from_the_stream_path():
    assert most_mod._apple_id_sciezki("apple-music:tracks:42") == "42"
    assert most_mod._apple_id_sciezki("/Users/dj/a.aiff") is None
    assert most_mod._apple_id_sciezki(None) is None

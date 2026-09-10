"""Set → Apple Music playlist: the pure plan, the one POST, and the Most guards.

Nothing here touches the network or the owner's library: the client gets a
fake ``post``/``fetch`` pair that records what it was asked and answers like
Apple does (201 on create, the documented delay on the first read-back).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dancelab.core.models import AnalysisResult, Track
from dancelab.gui.most import Most
from dancelab.ingestion import apple_playlist as ap
from dancelab.ingestion.apple_music_api import AppleMusicClient, ConfigError
from dancelab.stan import dziennik


def _analysis(tid: str, source: str) -> AnalysisResult:
    return AnalysisResult(engine_version="test",
                          track=Track(track_id=tid, source_path=source, title=tid))


@pytest.fixture
def analizy():
    return {
        "s1": _analysis("s1", "apple-music:tracks:111"),
        "s2": _analysis("s2", "apple-music:tracks:222"),
        "s2b": _analysis("s2b", "apple-music:tracks:222"),
        "f1": _analysis("f1", "/Users/dj/muzyka/a.aiff"),
    }


# ------------------------------------------------------------------ planner

def test_plan_keeps_order_and_names_every_leftover(analizy):
    plan = ap.plan_apple_playlist(["f1", "s2", "s1", "s2b", "ghost"], analizy, "Test")
    assert plan.catalog_ids == ["222", "111"], "order of the set, streams only"
    reasons = dict(plan.skipped)
    assert reasons["f1"] == ap.REASON_LOCAL
    assert reasons["s2b"] == ap.REASON_DUPLICATE
    assert reasons["ghost"] == ap.REASON_NO_ANALYSIS
    d = plan.to_dict()
    assert d["zgloszone"] == 5 and d["dopasowane"] == 2
    assert len(d["notki"]) == 3


def test_id_map_is_the_isrc_seam(analizy):
    plan = ap.plan_apple_playlist(["f1", "s1"], analizy, "Test", id_map={"f1": "999"})
    assert plan.catalog_ids == ["999", "111"]
    assert plan.skipped == []


def test_catalog_id_of_only_accepts_apple_streams():
    assert ap.catalog_id_of("apple-music:tracks:42") == "42"
    assert ap.catalog_id_of("apple-music:tracks:") is None
    assert ap.catalog_id_of("/a/b.mp3") is None
    assert ap.catalog_id_of(None) is None


# ---------------------------------------------------------------- publisher

class FakeApple:
    """Records the POST, answers 201, then reads back with Apple's delay."""

    def __init__(self, status=201, delay_reads=1, tracks_seen=None):
        self.posts: list[tuple[str, dict, dict]] = []
        self.gets: list[str] = []
        self.status = status
        self.delay_reads = delay_reads
        self.tracks_seen = tracks_seen
        self.slept: list[float] = []

    def post(self, url, body, headers):
        self.posts.append((url, json.loads(body), headers))
        if self.status != 201:
            return self.status, {}, json.dumps(
                {"errors": [{"title": "Forbidden", "detail": "nope"}]}).encode()
        return 201, {}, json.dumps({"data": [{"id": "p.abc", "type": "library-playlists"}]}
                                   ).encode()

    def fetch(self, url, params, headers):
        self.gets.append(url)
        if len(self.gets) <= self.delay_reads:
            return 404, {}, b'{"errors":[{"status":"404"}]}'
        n = self.tracks_seen
        if n is None:
            n = len(self.posts[-1][1]["relationships"]["tracks"]["data"])
        return 200, {}, json.dumps({"data": [{"id": f"i.{k}"} for k in range(n)]}).encode()

    def client(self):
        return AppleMusicClient("dev", "usr", fetch=self.fetch, post=self.post,
                                sleep=self.slept.append)


def test_publish_posts_once_and_reads_back(analizy):
    fake = FakeApple(delay_reads=1)
    plan = ap.plan_apple_playlist(["s1", "s2", "f1"], analizy, "DanceLab test")
    out = ap.publish_apple_playlist(fake.client(), plan)
    assert out["ok"] and out["id"] == "p.abc"
    assert len(fake.posts) == 1, "a write is never retried"
    url, body, headers = fake.posts[0]
    assert url.endswith("/v1/me/library/playlists")
    assert headers["Music-User-Token"] == "usr" and headers["Content-Type"] == "application/json"
    assert body["attributes"]["name"] == "DanceLab test"
    assert body["relationships"]["tracks"]["data"] == [{"id": "111", "type": "songs"},
                                                        {"id": "222", "type": "songs"}]
    assert out["wyslane"] == 2 and out["zweryfikowane"] == 2
    assert fake.gets[0].endswith("/v1/me/library/playlists/p.abc/tracks")
    assert fake.slept, "the 404 right after creation is Apple's delay, waited out"


def test_publish_reports_partial_visibility_honestly(analizy):
    fake = FakeApple(delay_reads=0, tracks_seen=1)
    plan = ap.plan_apple_playlist(["s1", "s2"], analizy, "T")
    out = ap.publish_apple_playlist(fake.client(), plan, verify_attempts=2)
    assert out["ok"] and out["wyslane"] == 2 and out["zweryfikowane"] == 1
    assert any("1 z 2" in n for n in out["notki"])


def test_publish_error_carries_apple_detail(analizy):
    fake = FakeApple(status=403)
    plan = ap.plan_apple_playlist(["s1"], analizy, "T")
    out = ap.publish_apple_playlist(fake.client(), plan)
    assert out["ok"] is False and "403" in out["blad"] and "nope" in out["blad"]


def test_publish_refuses_an_empty_plan(analizy):
    plan = ap.plan_apple_playlist(["f1"], analizy, "T")
    fake = FakeApple()
    out = ap.publish_apple_playlist(fake.client(), plan)
    assert out["ok"] is False and fake.posts == []


# --------------------------------------------------------------------- Most

@pytest.fixture
def most(tmp_path, monkeypatch, analizy):
    m = Most(katalog=str(tmp_path / "processed"))
    monkeypatch.setattr(type(m), "PLIK_EDYCJI", str(tmp_path / "edycje.json"))
    m._analizy = dict(analizy)
    m._kolejnosc = ["s1", "f1", "s2"]
    return m


def test_most_stage_one_is_pure_and_names_the_local_file(most, monkeypatch):
    monkeypatch.setattr(Most, "_apple_token_jest", staticmethod(lambda: False))
    w = most.podglad_playlisty_apple("")
    assert w["ok"] and w["dopasowane"] == 2 and w["zgloszone"] == 3
    assert w["pominiete"][0]["track_id"] == "f1"
    assert w["token"] is False and any("autoryzuj" in n for n in w["notki"])
    s = most.zapis_stan()
    assert s["apple_policzona"] is True and s["apple_token"] is False


def test_most_stage_two_refuses_when_the_set_moved(most, monkeypatch):
    most.podglad_playlisty_apple("X")
    most._kolejnosc = ["s2", "s1"]
    assert most.zapis_stan()["apple_policzona"] is False
    w = most.wyslij_playliste_apple("X")
    assert "zmieniły się" in w["blad"]


def test_most_stage_two_needs_stage_one(most):
    assert "podgląd" in most.wyslij_playliste_apple("")["blad"]


def test_most_stage_two_without_token_says_authorize(most, monkeypatch):
    def brak():
        raise ConfigError("brak tokenu użytkownika — najpierw: autoryzuj")
    monkeypatch.setattr(most, "_klient_apple", brak)
    most.podglad_playlisty_apple("X")
    w = most.wyslij_playliste_apple("X")
    assert "autoryzuj" in w["blad"]


def test_most_stage_two_sends_and_journals(most, monkeypatch, tmp_path):
    fake = FakeApple(delay_reads=0)
    monkeypatch.setattr(most, "_klient_apple", fake.client)
    most.podglad_playlisty_apple("Zestaw")
    w = most.wyslij_playliste_apple("Zestaw")
    assert w["ok"] and w["wyslane"] == 2 and w["zweryfikowane"] == 2
    assert w["werdykt"] and Path(w["werdykt"]).exists()
    rec = json.loads(Path(w["werdykt"]).read_text())
    assert rec["powod"] == "playlista_apple"
    zdarzenia = [json.loads(linia) for linia in
                 (dziennik.KATALOG / dziennik.PLIK_ZDARZEN).read_text().splitlines()]
    typy = [z["typ"] for z in zdarzenia]
    assert "playlista_apple" in typy
    assert "usr" not in json.dumps(zdarzenia) and "usr" not in json.dumps(rec), "no tokens"
    assert most.zapis_stan()["apple_policzona"] is False, "stage one is consumed"

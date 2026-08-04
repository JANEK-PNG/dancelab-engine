"""Ulubione i filary (TUI 2.0, krok b) — magazyn i reguły.

Reguły: przełącznik działa w obie strony i przeżywa zapis/odczyt; limit 10
filarów odmawia Z POWODEM; wpis przeżywa przenosiny pliku (ratunek po
ścieżce); braki wracają po imieniu, nigdy nie znikają po cichu.
"""

from __future__ import annotations

import dancelab.tui.user_store as store
from dancelab.tui.user_store import (
    MAX_FILARY, load_state, resolve_tracks, save_state, toggle_track)


class _T:
    def __init__(self, path):
        self.source_path = path


class _A:
    def __init__(self, path):
        self.track = _T(path)


def test_przelacznik_w_obie_strony_i_trwalosc(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")
    state = load_state()
    added, refuse = toggle_track(state, "ulubione_utwory", "A", "/m/a.mp3")
    assert added and refuse is None
    save_state(state)
    state2 = load_state()
    assert state2["ulubione_utwory"] == [{"track_id": "A", "path": "/m/a.mp3"}]
    added, _ = toggle_track(state2, "ulubione_utwory", "A", "/m/a.mp3")
    assert not added and state2["ulubione_utwory"] == []


def test_limit_filarow_odmawia_z_powodem(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "stan.json")
    state = load_state()
    for i in range(MAX_FILARY):
        added, refuse = toggle_track(state, "filary", f"t{i}", f"/m/{i}.mp3")
        assert added and refuse is None
    added, refuse = toggle_track(state, "filary", "extra", "/m/extra.mp3")
    assert not added and "limit 10" in refuse
    assert len(state["filary"]) == MAX_FILARY
    # zdjęcie jednego zwalnia miejsce
    toggle_track(state, "filary", "t0", "/m/0.mp3")
    added, refuse = toggle_track(state, "filary", "extra", "/m/extra.mp3")
    assert added and refuse is None


def test_wpis_przezywa_przenosiny_pliku():
    state = {"filary": [{"track_id": "stare_id", "path": "/m/a.mp3"}]}
    # nowa pula: id inne (sha1 nowej ścieżki? nie — ta sama ścieżka, inne id)
    by_id = {"nowe_id": _A("/m/a.mp3")}
    ids, missing = resolve_tracks(state["filary"], by_id)
    assert ids == ["nowe_id"] and missing == []
    # a toggle po ścieżce ZDEJMUJE istniejący wpis zamiast dublować
    added, _ = toggle_track(state, "filary", "nowe_id", "/m/a.mp3")
    assert not added and state["filary"] == []


def test_braki_wracaja_po_imieniu():
    entries = [{"track_id": "gone", "path": "/m/znikniety utwor.mp3"}]
    ids, missing = resolve_tracks(entries, {})
    assert ids == [] and missing == ["znikniety utwor"]

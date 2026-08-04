"""Magazyn planów TUI — plan przeżywa zamknięcie okna, braki są głośne.

Reguły: pełny obieg zapis→lista→wczytanie oddaje tę samą kolejność;
utwór nieobecny w puli jest POMIJANY z notką (nigdy zgadywany); zmiana
ścieżki pliku (track_id = sha1 ścieżki) ratowana dopasowaniem po ścieżce;
uszkodzony plik planu widoczny na liście, nie ukryty.
"""

from __future__ import annotations

import dancelab.tui.plan_store as plan_store
from dancelab.tui.plan_store import list_plans, match_order, read_plan, save_plan


class _Track:
    def __init__(self, path):
        self.source_path = path


class _A:
    def __init__(self, path):
        self.track = _Track(path)


def _pool(**paths):
    return {tid: _A(p) for tid, p in paths.items()}


def test_pelny_obieg_zapis_lista_wczytanie(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    by_id = _pool(A="/m/a.mp3", B="/m/b.mp3")
    path = save_plan(["A", "B"], by_id, name="test 130-135",
                     params={"arc": "build", "minutes": 90},
                     engine_order=["B", "A"], edits=[{"typ": "podmiana"}])
    plans = list_plans()
    assert len(plans) == 1
    assert plans[0]["nazwa"] == "test 130-135" and plans[0]["n"] == 2

    rec = read_plan(path)
    order, notes = match_order(rec, by_id)
    assert order == ["A", "B"] and notes == []
    assert rec["plan_silnika"] == ["B", "A"]
    assert rec["edycje"] == [{"typ": "podmiana"}]
    assert rec["parametry"]["minutes"] == 90


def test_brak_w_puli_pomijany_z_notka(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    path = save_plan(["A", "B"], _pool(A="/m/a.mp3", B="/m/b.mp3"),
                     name="x", params={}, engine_order=[], edits=[])
    rec = read_plan(path)
    order, notes = match_order(rec, _pool(A="/m/a.mp3"))   # B zniknęło z puli
    assert order == ["A"]
    assert any("BRAK W PULI" in n and "b" in n for n in notes)


def test_zmiana_sciezki_ratowana_po_path(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    path = save_plan(["A"], _pool(A="/m/a.mp3"), name="x",
                     params={}, engine_order=[], edits=[])
    rec = read_plan(path)
    # nowa pula: inny track_id (bo id = sha1 ścieżki), ta sama ścieżka
    order, notes = match_order(rec, _pool(A2="/m/a.mp3"))
    assert order == ["A2"]
    assert any("po ścieżce" in n for n in notes)


def test_uszkodzony_plik_widoczny_nie_ukryty(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    (tmp_path / "plan_20260804_000000.json").write_text("{to nie json")
    plans = list_plans()
    assert len(plans) == 1
    assert "USZKODZONY" in plans[0]["nazwa"] and plans[0]["n"] == 0

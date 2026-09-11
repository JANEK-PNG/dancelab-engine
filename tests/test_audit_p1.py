"""Regression cases for file boundaries and data loss found in the September audit."""

from __future__ import annotations

import io
import json
import os
import runpy
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from dancelab.stan import dziennik
from dancelab.tui import plan_store


def test_same_second_saves_keep_every_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    monkeypatch.setattr(plan_store.time, "strftime", lambda *_: "20260906_120000")

    def save(index):
        return plan_store.save_plan(
            [], {}, name=str(index), params={}, engine_order=[], edits=[])

    with ThreadPoolExecutor(max_workers=4) as workers:
        paths = list(workers.map(save, range(12)))
    assert len(set(paths)) == 12
    assert {plan_store.read_plan(p)["nazwa"] for p in paths} == {str(i) for i in range(12)}


def test_same_second_verdicts_are_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path)
    monkeypatch.setattr(dziennik.time, "strftime", lambda *_: "20260906_120000")
    first, error = dziennik.zapisz_werdykt({"result": "first"}, skora="gui")
    second, other_error = dziennik.zapisz_werdykt({"result": "second"}, skora="gui")
    assert error is other_error is None
    assert first != second
    assert json.loads(Path(first).read_text())["result"] == "first"


@pytest.mark.parametrize("operation", [plan_store.read_plan, plan_store.delete_plan])
@pytest.mark.parametrize("kind", ["outside", "symlink", "nested", "other_json"])
def test_plan_operations_reject_paths_outside_the_plan_namespace(
    tmp_path, monkeypatch, operation, kind,
):
    root = tmp_path / "plans"
    root.mkdir()
    monkeypatch.setattr(plan_store, "PLANS_DIR", root)
    outside = tmp_path / "plan_private.json"
    outside.write_text('{"private": true}')
    if kind == "outside":
        target = outside
    elif kind == "symlink":
        target = root / "plan_link.json"
        target.symlink_to(outside)
    elif kind == "nested":
        target = root / "nested" / "plan_private.json"
        target.parent.mkdir()
        target.write_text(outside.read_text())
    else:
        target = root / "settings.json"
        target.write_text(outside.read_text())
    with pytest.raises((ValueError, PermissionError)):
        operation(target)
    assert outside.read_text() == '{"private": true}'
    assert target.exists()


def test_trash_rejects_symlink_directory(tmp_path, monkeypatch):
    root = tmp_path / "plans"
    root.mkdir()
    monkeypatch.setattr(plan_store, "PLANS_DIR", root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "kosz").symlink_to(outside, target_is_directory=True)
    plan = root / "plan_old.json"
    plan.write_text("{}")
    with pytest.raises((ValueError, PermissionError)):
        plan_store.delete_plan(plan)
    assert plan.exists()
    assert list(outside.iterdir()) == []


def test_repeated_trash_keeps_both_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    plan = tmp_path / "plan_old.json"
    plan.write_text('{"version": 1}')
    first = plan_store.delete_plan(plan)
    plan.write_text('{"version": 2}')
    second = plan_store.delete_plan(plan)
    assert first != second
    assert json.loads(first.read_text())["version"] == 1
    assert json.loads(second.read_text())["version"] == 2


def test_failed_flush_does_not_publish_a_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)

    def fail(_fd):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="simulated disk failure"):
        plan_store.save_plan([], {}, name="x", params={}, engine_order=[], edits=[])
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def preview_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["serwer.py"])
    # The original script starts the server during import; never bind a real socket.
    monkeypatch.setattr(ThreadingHTTPServer, "__init__", lambda *_a, **_k: None)
    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", lambda *_a: None)
    module = runpy.run_path(str(Path(__file__).parents[1] / "docs/gui/serwer.py"))
    handler = module["Serwer"]
    root = tmp_path / "public"
    root.mkdir()
    (root / "index.html").write_text("preview")
    (tmp_path / "private.txt").write_text("PRIVATE SENTINEL")
    (root / "leak.txt").symlink_to(tmp_path / "private.txt")
    (tmp_path / "audyt-ui.js").write_text("// shared auditor")
    handler.do_GET.__globals__["KATALOG"] = root
    return handler


def _request(handler_class, path):
    handler = handler_class.__new__(handler_class)
    handler.path = path
    handler.wfile = io.BytesIO()
    status = []
    handler.send_response = status.append
    handler.send_header = lambda *_: None
    handler.end_headers = lambda: None
    handler.do_GET()
    return status[0], handler.wfile.getvalue()


@pytest.mark.parametrize("path", ["/../private.txt", "/%2e%2e/private.txt", "/leak.txt"])
def test_preview_does_not_serve_outside_files(preview_handler, path):
    status, body = _request(preview_handler, path)
    assert status in (403, 404)
    assert b"PRIVATE SENTINEL" not in body


def test_preview_keeps_index_and_explicit_shared_asset(preview_handler):
    assert _request(preview_handler, "/?preview=1") == (200, b"preview")
    assert _request(preview_handler, "/audyt-ui.js") == (200, b"// shared auditor")


def test_atomic_create_does_not_clobber_existing_data(tmp_path):
    from dancelab.storage.atomic import write_text_atomic

    path = tmp_path / "plan_existing.json"
    path.write_text('{"original": true}')
    with pytest.raises(FileExistsError):
        write_text_atomic(path, "{}", overwrite=False)
    assert path.read_text() == '{"original": true}'
    assert list(tmp_path.iterdir()) == [path]


def test_failed_pointer_update_keeps_previous_plan(tmp_path, monkeypatch):
    from dancelab.stan import plan

    monkeypatch.setattr(plan_store, "PLANS_DIR", tmp_path)
    monkeypatch.setattr(plan, "WSKAZNIK", tmp_path / "biezacy.json")
    original = plan.zapisz([], {}, nazwa="first", parametry={})

    def fail(_source, _destination):
        raise OSError("simulated publication failure")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError, match="simulated publication failure"):
        plan.zapisz([], {}, nazwa="second", parametry={})
    assert plan.sciezka_biezacego() == original
    assert {p["nazwa"] for p in plan_store.list_plans()} == {"first", "second"}
    assert not list(tmp_path.glob("*.tmp"))

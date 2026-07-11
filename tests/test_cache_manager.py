"""Cache manager (PRODUCT_SPEC §8) — headless persistence tests."""

from __future__ import annotations

import json

import pytest

from dancelab.storage.cache_manager import (
    CACHE_CLASSES,
    CacheError,
    CacheManager,
    format_bytes,
)


def make_manager(tmp_path, **kwargs) -> CacheManager:
    return CacheManager(tmp_path / "cache", **kwargs)


def write_cached(manager: CacheManager, cache_class: str, key: str, size: int = 1024):
    path = manager.class_dir(cache_class) / f"{key}.bin"
    path.write_bytes(b"x" * size)
    return manager.register(cache_class, key, path), path


def test_root_layout_and_register(tmp_path):
    manager = make_manager(tmp_path)
    for cache_class in CACHE_CLASSES:
        assert (manager.root / cache_class).is_dir()
    entry, path = write_cached(manager, "analysis", "track_a", 2048)
    assert entry.bytes == 2048
    # manifest persisted and reloadable
    reloaded = CacheManager(manager.root)
    assert reloaded.entries("analysis")[0].key == "track_a"


def test_register_refuses_files_outside_root(tmp_path):
    manager = make_manager(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x")
    with pytest.raises(CacheError, match="outside cache root"):
        manager.register("analysis", "bad", outside)


def test_usage_reports_real_bytes_per_class(tmp_path):
    manager = make_manager(tmp_path)
    write_cached(manager, "analysis", "a", 1000)
    write_cached(manager, "stems", "b", 5000)
    usage = manager.usage()
    assert usage["analysis"] == 1000
    assert usage["stems"] == 5000
    assert usage["exports"] == 0


def test_clear_never_touches_exports(tmp_path):
    manager = make_manager(tmp_path)
    write_cached(manager, "stems", "s", 100)
    _, export_path = write_cached(manager, "exports", "e", 100)
    assert manager.clear("stems") == 100
    assert not list(manager.class_dir("stems").rglob("*"))
    with pytest.raises(CacheError, match="user data"):
        manager.clear("exports")
    assert export_path.exists()


def test_enforce_limit_lru_evicts_but_spares_exports(tmp_path):
    manager = make_manager(tmp_path, max_bytes=2500)
    old_entry, old_path = write_cached(manager, "stems", "old", 2000)
    manager._manifest.entries[0].last_used_at = 1.0  # force LRU order
    manager._save_manifest()
    write_cached(manager, "analysis", "new", 2000)
    _, export_path = write_cached(manager, "exports", "keep", 4000)

    freed = manager.enforce_limit()
    assert freed >= 2000
    assert not old_path.exists()          # oldest evicted
    assert export_path.exists()           # exports untouched
    assert manager.entries("stems")[0].missing is True  # marked, not silently gone


def test_startup_scan_removes_temp_orphans_and_marks_missing(tmp_path):
    manager = make_manager(tmp_path)
    (manager.class_dir("temp") / "orphan.tmp").write_bytes(b"x")
    _, path = write_cached(manager, "analysis", "gone", 10)
    path.unlink()
    report = manager.startup_scan()
    assert report["temp_removed"] == 1
    assert report["missing_marked"] == 1
    assert manager.entries("analysis")[0].missing is True  # state, not crash


def test_move_root_copy_verify_swap(tmp_path):
    manager = make_manager(tmp_path)
    _, path = write_cached(manager, "analysis", "keep", 512)
    new_root = tmp_path / "relocated"
    old_root = manager.root
    manager.move_root(new_root)
    assert manager.root == new_root
    assert (new_root / "analysis" / "keep.bin").read_bytes() == b"x" * 512
    assert not old_root.exists()          # removed only after verification


def test_move_root_refuses_nonempty_destination(tmp_path):
    manager = make_manager(tmp_path)
    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "file").write_text("x")
    with pytest.raises(CacheError, match="not empty"):
        manager.move_root(dest)


def test_estimate_matches_spec_formulas(tmp_path):
    estimate = CacheManager.estimate(
        new_track_count=6,
        stem_track_durations_sec=[300.0],
        sample_rate=44100,
        stems_per_track=4,
    )
    assert estimate.analysis_bytes == 6 * 256 * 1024
    assert estimate.stems_bytes == int(300 * 44100 * 2) * 4  # ~100 MB, honest math
    assert estimate.total_bytes == estimate.analysis_bytes + estimate.stems_bytes


def test_corrupt_manifest_recovers_empty_not_crash(tmp_path):
    manager = make_manager(tmp_path)
    write_cached(manager, "analysis", "a", 10)
    (manager.root / "cache_manifest.json").write_text("{not json", encoding="utf-8")
    reloaded = CacheManager(manager.root)
    assert reloaded.entries() == []       # rebuilt empty, app keeps running


def test_format_bytes():
    assert format_bytes(512) == "512 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(10 * 1024**3) == "10.0 GB"


def test_engine_config_has_cache_section():
    from dancelab.core.config import EngineConfig

    config = EngineConfig()
    assert config.cache.max_bytes == 10 * 1024**3
    assert config.cache.root == ""
    assert json.dumps(config.cache.model_dump())  # serializable
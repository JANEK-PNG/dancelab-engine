"""Simple Mode wizard (UI/UX audit §18/§20): guided import→analyze→set→export."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track
from dancelab.host.desktop_app import desktop_available
from test_host_qt_app import _qt_bootstrap_available

if desktop_available():
    from PySide6.QtWidgets import QApplication

    from dancelab.host.simple_mode import SimpleModeWindow
else:  # pragma: no cover
    QApplication = None
    SimpleModeWindow = None


def _stub_analysis(path: str | Path, _config) -> AnalysisResult:
    stem = Path(path).stem
    track_id = stem.lower().replace(" ", "_")
    return AnalysisResult(
        engine_version="test-simple-mode",
        track=Track(
            track_id=track_id,
            title=stem,
            source_path=str(path),
            bpm_estimate=124.0 + len(stem),
            key_estimate="8A",
            duration_sec=300.0,
        ),
        beatgrid=BeatGrid(bpm=124.0, beat_times_sec=[0.0, 0.5, 1.0], downbeats_sec=[0.0]),
        features=[
            FeatureFrame(track_id=track_id, timestamp_sec=float(t), rms=0.2 + 0.01 * t)
            for t in range(10)
        ],
    )


def _brief_analysis(tid: str, bpm: float, style: str, rms: float) -> AnalysisResult:
    return AnalysisResult(
        engine_version="test-simple-mode",
        track=Track(
            track_id=tid,
            title=tid,
            source_path=f"/tmp/{tid}.mp3",
            bpm_estimate=bpm,
            key_estimate="8A",
            style_label=style,
            duration_sec=300.0,
        ),
        beatgrid=BeatGrid(bpm=bpm, beat_times_sec=[0.0, 0.5, 1.0], downbeats_sec=[0.0]),
        features=[
            FeatureFrame(
                track_id=tid,
                timestamp_sec=float(t),
                rms=rms,
                low_freq_energy_ratio=0.45,
                bass_energy=50.0,
            )
            for t in range(10)
        ],
    )


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_simple_mode_wizard_end_to_end(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")
    window.analyze_fn = _stub_analysis
    app.processEvents()

    # welcome: wizard starts here, not in a raw graph
    assert window.current_step() == 0
    assert window.next_button.isEnabled()

    # step 1: gated until tracks are imported
    window.go_to_step(1)
    assert not window.next_button.isEnabled()
    files = []
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(f"stub {name}".encode())
        files.append(p)
    window.set_import_files(files)
    assert window.next_button.isEnabled()
    assert "5 track(s)" in window.import_summary.text()

    # step 2: gated until analysis ran
    window.go_to_step(2)
    assert not window.next_button.isEnabled()
    assert window.analyze_button.text() == "▶ Run Initial Check"
    assert window.analysis_depth_combo.count() == 1
    assert window.analysis_depth_combo.currentData() == "normal"
    assert window.analysis_depth_combo.isHidden()
    window.run_analysis(wait=True)
    app.processEvents()
    assert len(window.analyses) == 5
    assert not window.failures
    assert window.next_button.isEnabled()
    assert "Initial Check complete" in window.analyze_status.text()

    # per-track checklist: every row checked off with real results (BPM/key)
    rows = [window.analyze_list.item(i).text() for i in range(window.analyze_list.count())]
    assert len(rows) == 5
    assert all(row.startswith("✓") for row in rows)
    assert all("BPM" in row and "8A" in row for row in rows)
    assert window.analysis_results_stack.currentWidget() is window.analysis_library
    assert window.analysis_library.table.rowCount() == 5

    # step 3: generate a set — free track count (no fixed 5/10/15/20 presets)
    window.go_to_step(3)
    assert not window.next_button.isEnabled()
    window.count_radio.setChecked(True)
    window.count_spin.setValue(4)
    window.generate_set()
    assert window.plan is not None
    assert len(window.plan.track_order) == 4
    assert window.set_list.count() == 4
    assert window.next_button.isEnabled()

    # duration mode: stub tracks are 300 s → 0.5 h ≈ 6 tracks, clamped to the 5 analyzed
    window.duration_radio.setChecked(True)
    window.duration_spin.setValue(0.5)
    window.generate_set()
    assert len(window.plan.track_order) == 5
    assert "h" in window.generate_status.text()  # estimated set duration shown

    # back to explicit count for the export steps
    window.count_radio.setChecked(True)
    window.count_spin.setValue(5)
    window.planner_mode_combo.setCurrentIndex(
        window.planner_mode_combo.findData("harmonic")
    )
    window.generate_set()
    assert len(window.plan.track_order) == 5
    assert window.plan.planner_mode == "harmonic"

    # step 4: real review tool — transition list + A/B decks with structure
    window.go_to_step(4)
    app.processEvents()
    assert window.review_list.count() == 4  # 5 tracks → 4 transitions
    assert window.review_list.currentRow() == 0
    header = window.review_widget.header_label.text()
    assert "score" in header and "→" in header
    # decks carry the engine data: titles + structure strips + beat-sync status
    assert window.review_widget.deck_a.analysis is not None
    assert window.review_widget.deck_b.analysis is not None
    assert "BPM" in window.review_widget.deck_a.title_label.text()
    assert window.review_widget.sync_status.text()  # beat-sync state stated
    assert window.review_widget.deck_a.strip.waveform  # RMS envelope, not only blocks

    # Regression: changing rows must refresh Deck B to the incoming track. A
    # stale stem-button cleanup bug used to leave Deck B on the previous track.
    for row in range(window.review_list.count()):
        window.review_list.setCurrentRow(row)
        app.processEvents()
        transition = window.plan.transitions[row]
        assert window.review_widget.deck_a.analysis.track.track_id == transition.from_track_id
        assert window.review_widget.deck_b.analysis.track.track_id == transition.to_track_id

    # quantized seek snaps to the host's 8-beat grid, not an arbitrary nearest beat.
    window.review_widget.deck_b.quantize = True
    from dancelab.host.pair_review import snap_to_grid

    grid = window.review_widget.deck_b.analysis.beatgrid
    assert snap_to_grid(0.61, grid.beat_times_sec, grid.downbeats_sec) == 0.0

    # step 5: export writes the XML
    window.go_to_step(5)
    out = tmp_path / "exports" / "set.xml"
    window.export_path_edit.setText(str(out))
    window.export_set()
    assert out.exists()
    exported_xml = out.read_text(encoding="utf-8")
    assert "DJ_PLAYLISTS" in exported_xml
    assert "AverageBpm" not in exported_xml
    assert "<TEMPO" not in exported_xml
    assert "hot cue marker" in window.export_status.text()
    assert "Let Rekordbox analyze BPM/beatgrid" in window.export_status.text()
    assert str(out) in window.export_status.text()

    # sidebar shows completed steps
    sidebar = [window.step_list.item(i).text() for i in range(window.step_list.count())]
    assert sidebar[0].startswith("✓")
    assert sidebar[1].startswith("✓")

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_analyzed_library_filters_sorts_and_sets_planner_constraints(tmp_path):
    from dancelab.host.analyzed_library import build_library_rows, filter_library_rows

    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    analyses = [
        _brief_analysis("quiet_garage", 124.0, "uk-garage", 0.15),
        _brief_analysis("bass_driver", 132.0, "bass", 0.55),
        _brief_analysis("slow_bass", 118.0, "bass", 0.30),
    ]
    rows = build_library_rows(analyses)

    assert {row.energy_percent for row in rows} == {0, 37, 100}
    filtered = filter_library_rows(
        rows,
        query="bass",
        style="bass",
        bpm_max=130.0,
        sort_by="energy_desc",
    )
    assert [row.track_id for row in filtered] == ["slow_bass"]

    window.analyses = analyses
    window.analysis_library.set_analyses(analyses)
    window.analysis_results_stack.setCurrentWidget(window.analysis_library)
    assert window.analysis_library.table.rowCount() == 3

    window.analysis_library.search_edit.setText("garage")
    QApplication.processEvents()
    assert window.analysis_library.table.rowCount() == 1
    window.analysis_library.table.selectRow(0)
    track_id = window.analysis_library.selected_track_id()
    assert track_id == "quiet_garage"

    window.analysis_library.must_have_button.click()
    QApplication.processEvents()
    assert track_id in window.must_have_ids
    assert window.analysis_library.table.item(0, 7).text() == "Must Have"

    assert window.toggle_not_tonight(track_id) == "conflict"
    assert track_id in window.must_have_ids
    assert track_id not in window.not_tonight_ids

    window.analysis_library.must_have_button.click()
    window.analysis_library.not_tonight_button.click()
    QApplication.processEvents()
    assert track_id not in window.must_have_ids
    assert track_id in window.not_tonight_ids
    assert window.analysis_library.table.item(0, 7).text() == "Not Tonight"

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_mixability_map_uses_engine_ranking_and_edge_decisions():
    from dancelab.host.mixability_map import build_mix_map_points, camelot_color

    app = QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    analyses = [
        _brief_analysis("quiet_garage", 124.0, "uk-garage", 0.15),
        _brief_analysis("bass_driver", 132.0, "bass", 0.55),
        _brief_analysis("slow_bass", 118.0, "bass", 0.30),
        _brief_analysis("mid_bass", 126.0, "bass", 0.35),
    ]
    points = build_mix_map_points(analyses)
    assert [point.energy_percent for point in points] == [37, 0, 50, 100]
    assert camelot_color("8A") != camelot_color("Unknown")

    window.analyses = analyses
    window.mixability_map.set_analyses(analyses)
    window.not_tonight_ids.add("bass_driver")
    window._sync_generate_controls_visibility()
    window._set_generate_result_view("mixability")
    assert window.generate_result_stack.currentWidget() is window.mixability_map
    assert window.result_card.isVisibleTo(window.result_card.parentWidget())

    window.mixability_map.select_track("quiet_garage")
    window._run_mixability_map("quiet_garage")
    worker = window.mixability_map._worker
    assert worker is not None
    assert worker.wait(15_000)
    app.processEvents()

    recommendation = window.mixability_map._recommendation
    assert recommendation is not None
    ranked_ids = [candidate.track_id for candidate in recommendation.ranking]
    assert "bass_driver" not in ranked_ids
    assert set(ranked_ids) == {"slow_bass", "mid_bass"}
    assert set(window.mixability_map._edges) == set(ranked_ids)
    assert window.mixability_map.candidate_table.rowCount() == 2
    assert "full EdgeDecision" in window.mixability_map.status_label.text()
    assert window.engine_status_chip.text() == "Mix ideas ready"

    window.mixability_map.candidate_table.selectRow(0)
    selected_id = window.mixability_map._selected_candidate_id()
    assert selected_id in ranked_ids
    window.mixability_map.must_have_button.click()
    app.processEvents()
    assert selected_id in window.must_have_ids

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_energy_timeline_preserves_plan_order_and_library_scale():
    from dancelab.core.models import SetPlan, SetTransition
    from dancelab.host.energy_timeline import build_set_energy_points

    app = QApplication.instance() or QApplication([])
    analyses = [
        _brief_analysis("low", 120.0, "deep", 0.10),
        _brief_analysis("middle", 124.0, "garage", 0.30),
        _brief_analysis("high", 130.0, "bass", 0.50),
        _brief_analysis("outside_peak", 134.0, "bass", 0.90),
    ]
    plan = SetPlan(
        track_order=["middle", "low", "high"],
        transitions=[
            SetTransition(
                from_track_id="middle",
                to_track_id="low",
                transition_score=0.48,
                harmonic_relation="same",
            ),
            SetTransition(
                from_track_id="low",
                to_track_id="high",
                transition_score=0.82,
                harmonic_relation="adjacent",
            ),
        ],
        arc="build",
        pinned_track_ids=["middle"],
        locked_positions={2: "low"},
        mean_transition_score=0.65,
    )

    points = build_set_energy_points(plan, analyses)
    assert [point.track_id for point in points] == ["middle", "low", "high"]
    assert [point.energy_percent for point in points] == [25, 0, 50]
    assert [point.transition_score_to_next for point in points] == [0.48, 0.82, None]
    assert points[0].pinned
    assert points[1].locked

    window = SimpleModeWindow()
    window.analyses = analyses
    window.plan = plan
    window._populate_set_list_from_plan()
    path = window.energy_timeline.canvas._curve_path(
        window.energy_timeline.canvas._positions()
    )
    assert all(not path.elementAt(index).isCurveTo() for index in range(path.elementCount()))
    assert window.energy_timeline.isVisibleTo(window.energy_timeline.parentWidget())
    assert "peak #3" in window.energy_timeline.summary_label.text()
    assert window.set_list.currentRow() == 0

    window._select_set_track_from_timeline("high")
    app.processEvents()
    assert window.set_list.currentRow() == 2
    assert "#3 high" in window.energy_timeline.detail_label.text()
    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_simple_mode_project_roundtrip_restores_cached_session(tmp_path):
    from dancelab.storage.repositories import FileAnalysisRepository

    QApplication.instance() or QApplication([])
    processed = tmp_path / "processed"
    cache = tmp_path / "cache"
    files = [tmp_path / f"{name}.mp3" for name in ("Garage A", "Bass B", "Breaks C")]
    for path in files:
        path.write_bytes(str(path).encode())

    analyses = []
    for path, bpm, style, rms in zip(
        files,
        (128.0, 132.0, 134.0),
        ("uk-garage", "bass", "breaks"),
        (0.2, 0.35, 0.48),
        strict=True,
    ):
        result = _brief_analysis(path.stem.lower().replace(" ", "_"), bpm, style, rms)
        result = result.model_copy(
            update={"track": result.track.model_copy(update={"source_path": str(path)})}
        )
        analyses.append(result)
        FileAnalysisRepository(processed).save(result)

    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(processed)
    window.config.cache.root = str(cache)
    window.autosave_path = tmp_path / "autosave" / "recovery.dlproj"
    window.set_import_files(files)
    window.analyses = analyses
    window.analysis_library.set_analyses(analyses)
    window.analysis_results_stack.setCurrentWidget(window.analysis_library)
    window.style_focus_edit.setText("bass, uk-garage")
    window.bpm_max_spin.setValue(135.0)
    window._set_combo_value(window.set_role_combo, "bridge")
    window.count_spin.setValue(3)
    window.must_have_ids.add(analyses[0].track.track_id)
    window.generate_set()
    window.playlist_name_edit.setText("Garden Continuation")
    window.go_to_step(4)
    original_order = list(window.plan.track_order)

    saved = window._save_project_to_path(tmp_path / "garden_continuation")
    assert saved.exists()
    assert window.project_path == saved
    assert not window._project_dirty
    window.close()

    restored = SimpleModeWindow()
    restored.config.paths.processed_dir = str(processed)
    restored.config.cache.root = str(cache)
    restored.autosave_path = tmp_path / "autosave" / "restored_recovery.dlproj"
    assert restored.load_project_from_path(saved) is True
    assert [analysis.track.track_id for analysis in restored.analyses] == [
        analysis.track.track_id for analysis in analyses
    ]
    assert restored.plan is not None
    assert restored.plan.track_order == original_order
    assert restored.current_step() == 4
    assert restored.style_focus_edit.text() == "bass, uk-garage"
    assert restored.bpm_max_spin.value() == 135.0
    assert restored.set_role_combo.currentData() == "bridge"
    assert analyses[0].track.track_id in restored.must_have_ids
    assert restored.analysis_results_stack.currentWidget() is restored.analysis_library
    assert restored.analysis_library.table.rowCount() == 3
    assert restored.save_status_chip.text() == "Saved"
    assert not restored._project_dirty
    restored.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_simple_mode_autosave_can_be_recovered(tmp_path):
    QApplication.instance() or QApplication([])
    source = tmp_path / "Recovery Track.mp3"
    source.write_bytes(str(source).encode())
    autosave = tmp_path / "autosave" / "simple_mode_recovery.dlproj"

    window = SimpleModeWindow()
    window.autosave_path = autosave
    window.set_import_files([source])
    written = window._write_autosave()
    assert written == autosave
    assert autosave.exists()
    window.close()

    recovered = SimpleModeWindow()
    recovered.autosave_path = autosave
    assert recovered.recover_autosaved_project() is True
    assert recovered.files == [source]
    assert recovered.project_path is None
    assert recovered._project_dirty
    assert "Recovered" in recovered.project_name
    recovered._suspend_project_dirty = True
    recovered.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_stop_processing_saves_progress_and_new_selection_works(tmp_path):
    # PRODUCT_SPEC §9 hard rule: after stopping a job, selecting new tracks
    # must always work; processed tracks stay saved; re-run continues.
    app = QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")

    def stopping_stub(path, _config):
        result = _stub_analysis(path, _config)
        thread = window._analysis_thread
        if thread is not None and "Beta" in str(path):
            thread.request_stop()  # stop mid-batch, after 2nd track completes
        return result

    window.analyze_fn = stopping_stub
    files = []
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        files.append(p)
    window.set_import_files(files)
    window.go_to_step(2)
    window.run_analysis(wait=True)
    app.processEvents()

    assert len(window.analyses) == 2          # Alpha + Beta saved
    assert "Stopped" in window.analyze_status.text()
    assert "3 pending" in window.analyze_status.text()
    assert not window.stop_button.isVisible()
    assert window.analyze_button.isEnabled()

    # re-run continues with the remaining tracks — nothing lost, nothing stuck
    window.analyze_fn = _stub_analysis
    window.run_analysis(wait=True)
    app.processEvents()
    assert len(window.analyses) == 5

    # the reported bug: new selection after a stop must start a fresh job
    new_files = []
    for name in ("Zeta", "Eta"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        new_files.append(p)
    window.set_import_files(new_files)
    window.run_analysis(wait=True)
    app.processEvents()
    assert len(window.analyses) == 2
    assert {a.track.title for a in window.analyses} == {"Zeta", "Eta"}

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_import_clear_and_remove_selected(tmp_path):
    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    files = []
    for name in ("Alpha", "Beta", "Gamma"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        files.append(p)
    window.set_import_files(files)
    window.go_to_step(1)
    assert window.next_button.isEnabled()

    # remove one selected track — files on disk untouched
    window.import_list.setCurrentRow(1)  # Beta
    window.remove_selected_imports()
    assert [p.name for p in window.files] == ["Alpha.mp3", "Gamma.mp3"]
    assert "Removed 1" in window.import_summary.text()
    assert files[1].exists()

    # clear whole import → step gating locks again
    window.clear_import()
    assert window.files == []
    assert window.import_list.count() == 0
    assert not window.next_button.isEnabled()
    assert all(p.exists() for p in files)

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_deep_on_demand_upgrades_only_set_tracks(tmp_path):
    # Deep-speed plan #1: stems only for tracks that made the set; second run
    # reuses the deep cache (§7 manifest) with zero compute.
    from dancelab.ingestion.metadata import make_track_id

    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")

    calls = {"n": 0}

    def counting_stub(path, _config):
        calls["n"] += 1
        result = _stub_analysis(path, _config)
        result.track.track_id = make_track_id(str(path))
        for frame in result.features:
            frame.track_id = result.track.track_id
        return result

    window.analyze_fn = counting_stub
    files = []
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        files.append(p)
    window.set_import_files(files)
    window.run_analysis(wait=True)
    QApplication.processEvents()
    assert len(window.analyses) == 6
    quick_calls = calls["n"]

    window.go_to_step(3)
    window.count_radio.setChecked(True)
    window.count_spin.setValue(4)
    window.generate_set()
    assert window.deep_upgrade_button.isEnabled()
    set_ids = set(window.plan.track_order)
    assert len(set_ids) == 4

    window.run_deep_upgrade(wait=True)
    QApplication.processEvents()
    # deep ran ONLY for the 4 set tracks (tier upgrade), not the whole library
    assert calls["n"] == quick_calls + 4
    assert "Deep data ready for 4" in window.deep_status.text()
    assert len(window.analyses) == 6  # library size unchanged, entries merged

    # §7: second deep upgrade — all from deep cache, zero compute
    window.run_deep_upgrade(wait=True)
    QApplication.processEvents()
    assert calls["n"] == quick_calls + 4

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_generate_writes_history_and_respects_variation_mode(tmp_path):
    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")
    window.config.cache.root = str(tmp_path / "cache")
    window.analyze_fn = _stub_analysis
    files = []
    for name in ("Alpha", "Beta", "Gamma", "Delta"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        files.append(p)
    window.set_import_files(files)
    window.run_analysis(wait=True)
    QApplication.processEvents()

    window.go_to_step(3)
    window.count_radio.setChecked(True)
    window.count_spin.setValue(4)
    window.novelty_combo.setCurrentIndex(window.novelty_combo.findData("balanced"))
    window.generate_set()
    history_file = Path(window.config.cache.root) / "history" / "playlists.jsonl"
    assert history_file.exists()
    assert len(history_file.read_text().splitlines()) == 1
    window.generate_set()
    assert len(history_file.read_text().splitlines()) == 2  # fingerprint per run

    # deterministic mode: byte-stable regardless of history
    window.novelty_combo.setCurrentIndex(window.novelty_combo.findData("deterministic"))
    window.generate_set()
    first = list(window.plan.track_order)
    window.generate_set()
    assert list(window.plan.track_order) == first

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_dj_control_pin_lock_rest(tmp_path):
    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")
    window.config.cache.root = str(tmp_path / "cache")
    window.analyze_fn = _stub_analysis
    files = []
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        files.append(p)
    window.set_import_files(files)
    window.run_analysis(wait=True)
    QApplication.processEvents()
    window.go_to_step(3)
    window.count_radio.setChecked(True)
    window.count_spin.setValue(3)

    ids = [a.track.track_id for a in window.analyses]

    # Must Have: pinned into every regenerate, cap enforced
    assert window.toggle_must_have(ids[4]) == "added"      # Epsilon must appear
    window.generate_set()
    assert ids[4] in window.plan.track_order
    assert ids[4] in window.plan.pinned_track_ids
    for j in range(9):
        window.must_have_ids.add(f"fake_{j}")
    assert window.toggle_must_have(ids[0]) == "limit"      # 11th → sacrifice
    window.must_have_ids = {ids[4]}

    # Not Tonight: excluded from the pool; restore works
    assert window.toggle_not_tonight(ids[1]) == "rested"
    window.generate_set()
    assert ids[1] not in window.plan.track_order
    assert window.toggle_not_tonight(ids[1]) == "restored"

    # conflict requires explicit resolution — no silent precedence
    assert window.toggle_not_tonight(ids[4]) == "conflict"
    window.resolve_conflict(ids[4], "skip")
    assert ids[4] in window.not_tonight_ids
    assert ids[4] not in window.must_have_ids
    window.resolve_conflict(ids[4], "clear")

    # Lock: track stays at its slot through a regenerate with a new seed
    window.generate_set()
    target = window.plan.track_order[1]
    window.set_list.setCurrentRow(1)
    window._on_lock_clicked()
    assert window.locked_positions == {2: target}
    window.seed_spin.setValue(0)
    window.generate_set()
    assert window.plan.track_order[1] == target
    assert "🔒" in window.set_list.item(1).text()

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_simple_mode_calm_uk_bass_brief_filters_set(tmp_path):
    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.cache.root = str(tmp_path / "cache")
    window.analyses = [
        _brief_analysis("uk_a", 130, "uk-bass", 0.20),
        _brief_analysis("uk_b", 134, "bass", 0.22),
        _brief_analysis("too_fast", 142, "bass", 0.55),
        _brief_analysis("wrong_style", 124, "deep-house", 0.24),
    ]

    window.go_to_step(3)
    window.set_brief_combo.setCurrentIndex(
        window.set_brief_combo.findData("calm_uk_bass")
    )
    window.count_radio.setChecked(True)
    window.count_spin.setValue(2)
    window.generate_set()

    assert window.plan is not None
    assert set(window.plan.track_order) == {"uk_a", "uk_b"}
    assert window.plan.arc == "flat"
    assert "too_fast" in window.plan.dropped_track_ids
    assert "brief style bass" in window.generate_status.text()
    assert "135" in window.library_profile_label.text()

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_usb_import_brings_user_cues_into_review(tmp_path):
    # §13 E2E: fake Rekordbox USB → import → the DJ's hot cue becomes the
    # verified B start in review (Cue button says "YOUR hot ...").
    from test_rekordbox_device import _ext_blob

    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")
    window.config.cache.root = str(tmp_path / "cache")
    window.analyze_fn = _stub_analysis

    usb = tmp_path / "usb"
    for i, name in enumerate(("Alpha", "Beta", "Gamma")):
        audio = usb / "Contents" / f"{name}.mp3"
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(str(audio).encode())
        anlz = usb / "PIONEER" / "USBANLZ" / "P001" / f"{i:04d}"
        anlz.mkdir(parents=True)
        (anlz / "ANLZ0000.EXT").write_bytes(_ext_blob(f"/Contents/{name}.mp3"))

    imported = window.import_rekordbox_usb(usb)
    assert imported == 3
    assert "hot cues imported" in window.import_summary.text()
    assert len(window.device_cues) == 3
    assert window.device_cues["Beta.mp3"][0].list_type == "hot"

    window.run_analysis(wait=True)
    QApplication.processEvents()
    window.go_to_step(3)
    window.count_radio.setChecked(True)
    window.count_spin.setValue(3)
    window.generate_set()
    window.go_to_step(4)
    QApplication.processEvents()

    # deck B cue button uses the DJ's verified hot cue, not a window guess
    assert "YOUR hot" in window.review_widget.deck_b.cue_button.text()
    assert window.review_widget.deck_b.user_cue_sec is not None
    header = window.review_widget.header_label.text()
    assert "YOUR hot cue" in header or "listen before trusting" in header

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_validation_mode_blind_rating_and_report(tmp_path):
    # Weight-calibration study tooling: blind hides engine opinions, ratings
    # land in CSV, full pass yields an honest engine-vs-rater report.
    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")
    window.config.cache.root = str(tmp_path / "cache")
    window.analyze_fn = _stub_analysis
    files = []
    for name in ("Alpha", "Beta", "Gamma", "Delta"):
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(str(p).encode())
        files.append(p)
    window.set_import_files(files)
    window.run_analysis(wait=True)
    QApplication.processEvents()
    window.go_to_step(3)
    window.count_radio.setChecked(True)
    window.count_spin.setValue(4)
    window.generate_set()
    window.go_to_step(4)
    QApplication.processEvents()

    # blind ON: list rows and header hide engine scores
    window.annotator_edit.setText("Jan Tester")
    window.blind_check.setChecked(True)
    QApplication.processEvents()
    row_text = window.review_list.item(0).text()
    assert "0." not in row_text  # no score like "· 0.82"
    assert "Blind rating" in window.review_widget.header_label.text()
    assert "score" not in window.review_widget.header_label.text()

    # rate all three transitions; auto-advance; report at the end
    window.review_list.setCurrentRow(0)
    for rating in (4, 3, 5):
        window.rate_current_transition(rating)
        QApplication.processEvents()
    assert "Rated 3/3" in window.validation_status.text()
    assert "engine vs you" in window.validation_status.text()

    csv_path = Path(window.config.cache.root) / "validation" / "Jan_Tester_transition_ratings.csv"
    assert csv_path.exists()
    lines = csv_path.read_text().splitlines()
    assert len(lines) == 4  # header + 3 ratings
    assert lines[0].startswith("pair_id,track_id_a,track_id_b,engine_score")
    assert lines[1].endswith(",4,,1")  # rating 4, no comment, blind=1

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_waveform_corrections_map_to_exact_pair_and_restore(tmp_path):
    import csv

    QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    window.config.paths.processed_dir = str(tmp_path / "processed")
    window.config.cache.root = str(tmp_path / "cache")
    window.analyze_fn = _stub_analysis
    files = []
    for name in ("Alpha", "Beta", "Gamma"):
        path = tmp_path / f"{name}.mp3"
        path.write_bytes(str(path).encode())
        files.append(path)
    window.set_import_files(files)
    window.run_analysis(wait=True)
    QApplication.processEvents()
    window.go_to_step(3)
    window.count_radio.setChecked(True)
    window.count_spin.setValue(3)
    window.generate_set()
    window.go_to_step(4)
    QApplication.processEvents()

    window.annotator_edit.setText("Wave Tester")
    window.review_list.setCurrentRow(0)
    transition = window.plan.transitions[0]
    deck_b = window.review_widget.deck_b
    deck_b._on_selection_committed(8.0, 24.0)
    deck_b._on_cue_moved({
        "label": "A",
        "name": "Mix In",
        "source": "engine_transition_window",
        "reference_time_sec": 8.0,
        "previous_time_sec": 8.0,
        "user_time_sec": 16.0,
    })

    csv_path = tmp_path / "cache" / "validation" / "Wave_Tester_transition_edits.csv"
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["action"] for row in rows} == {"transition_region_set", "hot_cue_moved"}
    assert all(row["pair_id"] == f"{transition.from_track_id}__{transition.to_track_id}" for row in rows)
    assert all(row["track_id"] == transition.to_track_id for row in rows)
    assert all(row["deck"] == "B" for row in rows)
    assert rows[0]["quantize_grid_beats"] == "8"

    window.review_list.setCurrentRow(1)
    window.review_list.setCurrentRow(0)
    QApplication.processEvents()
    assert window.review_widget.deck_b.strip.user_selection == (8.0, 24.0)
    window.close()

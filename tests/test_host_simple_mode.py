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
        p.write_bytes(b"stub")
        files.append(p)
    window.set_import_files(files)
    assert window.next_button.isEnabled()
    assert "5 track(s)" in window.import_summary.text()

    # step 2: gated until analysis ran
    window.go_to_step(2)
    assert not window.next_button.isEnabled()
    window.run_analysis(wait=True)
    app.processEvents()
    assert len(window.analyses) == 5
    assert not window.failures
    assert window.next_button.isEnabled()
    assert "Analyzed 5" in window.analyze_status.text()

    # per-track checklist: every row checked off with real results (BPM/key)
    rows = [window.analyze_list.item(i).text() for i in range(window.analyze_list.count())]
    assert len(rows) == 5
    assert all(row.startswith("✓") for row in rows)
    assert all("BPM" in row and "8A" in row for row in rows)

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
    window.analysis_depth_combo.setCurrentIndex(
        window.analysis_depth_combo.findData("deep")
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

    # quantized seek snaps to the stub beatgrid (beats at 0.0/0.5/1.0)
    window.review_widget.deck_b.quantize = True
    from dancelab.host.pair_review import snap_to_grid

    grid = window.review_widget.deck_b.analysis.beatgrid
    assert snap_to_grid(0.61, grid.beat_times_sec, grid.downbeats_sec) == 0.5

    # step 5: export writes the XML
    window.go_to_step(5)
    out = tmp_path / "exports" / "set.xml"
    window.export_path_edit.setText(str(out))
    window.export_set()
    assert out.exists()
    assert "DJ_PLAYLISTS" in out.read_text(encoding="utf-8")
    assert "hot cue marker" in window.export_status.text()
    assert str(out) in window.export_status.text()

    # sidebar shows completed steps
    sidebar = [window.step_list.item(i).text() for i in range(window.step_list.count())]
    assert sidebar[0].startswith("✓")
    assert sidebar[1].startswith("✓")

    # graph handoff: Advanced mode mirrors the wizard pipeline, wired up
    graph = window.open_graph_mode()
    app.processEvents()
    node_ids = {item.model.spec.node_id for item in graph.node_items.values()}
    assert {"engine", "upload_tracks", "build_set", "export_rekordbox"} <= node_ids
    assert len(graph.connection_models) == 4
    upload_item = next(
        item for item in graph.node_items.values() if item.model.spec.node_id == "upload_tracks"
    )
    upload_config = graph.runtime.ensure_node_config(upload_item.model.instance_id)
    assert len(upload_config["paths_text"].splitlines()) == 5
    build_item = next(
        item for item in graph.node_items.values() if item.model.spec.node_id == "build_set"
    )
    build_config = graph.runtime.ensure_node_config(build_item.model.instance_id)
    assert build_config["target_track_count"] == 5
    assert build_config["planner_mode"] == "harmonic"
    engine_item = next(
        item for item in graph.node_items.values() if item.model.spec.node_id == "engine"
    )
    engine_config = graph.runtime.ensure_node_config(engine_item.model.instance_id)
    assert engine_config["analysis_depth"] == "deep"
    assert len(graph.runtime.analysis_index) == 5  # wizard analyses cached
    graph.close()

    window.close()


@pytest.mark.skipif(
    not _qt_bootstrap_available(),
    reason="Qt platform bootstrap unavailable in this shell",
)
def test_simple_mode_opens_graph_mode(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = SimpleModeWindow()
    app.processEvents()

    graph = window.open_graph_mode()
    assert graph is not None
    assert window.open_graph_mode() is graph  # reused, not duplicated
    assert graph.windowTitle().startswith("DanceLab")

    graph.close()
    window.close()


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
        p.write_bytes(b"stub")
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
        p.write_bytes(b"stub")
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
        p.write_bytes(b"stub")
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

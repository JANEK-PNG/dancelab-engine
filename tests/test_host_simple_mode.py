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
    window.generate_set()
    assert len(window.plan.track_order) == 5

    # step 4: review has transition lines with scores
    window.go_to_step(4)
    review = window.review_text.toPlainText()
    assert "score" in review and "→" in review

    # step 5: export writes the XML
    window.go_to_step(5)
    out = tmp_path / "exports" / "set.xml"
    window.export_path_edit.setText(str(out))
    window.export_set()
    assert out.exists()
    assert "DJ_PLAYLISTS" in out.read_text(encoding="utf-8")
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

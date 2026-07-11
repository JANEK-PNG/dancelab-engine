"""Hardware backend policy (PRODUCT_SPEC §18) — honest selection & labels.

torch must NOT be imported in this pytest process: loading torch before
PySide6 creates a QApplication aborts the interpreter on macOS (verified —
Fatal Python error in the Qt suite). Availability is monkeypatched here;
the real-device A/B gate runs in a subprocess.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from dancelab.core import backend
from dancelab.core.backend import backend_label, backend_report, preferred_torch_device


@pytest.fixture(autouse=True)
def _no_device_override(monkeypatch):
    monkeypatch.delenv("DANCELAB_DEVICE", raising=False)


def test_auto_never_selects_unverified_acceleration(monkeypatch):
    # §18 hard rule: MPS failed the A/B gate (cosine 0.61 vs CPU on M4) —
    # auto resolves to CPU until MPS_VERIFIED flips after a passing gate.
    monkeypatch.setattr(backend, "_mps_available", lambda: True)
    assert backend.MPS_VERIFIED is False
    assert preferred_torch_device("auto") == "cpu"


def test_forced_cpu_and_env_override(monkeypatch):
    monkeypatch.setattr(backend, "_mps_available", lambda: True)
    monkeypatch.setenv("DANCELAB_DEVICE", "cpu")
    assert preferred_torch_device("mps") == "cpu"  # env beats argument
    monkeypatch.delenv("DANCELAB_DEVICE", raising=False)
    assert preferred_torch_device("cpu") == "cpu"


def test_explicit_mps_opt_in_is_truthful(monkeypatch):
    monkeypatch.setattr(backend, "_mps_available", lambda: True)
    assert preferred_torch_device("mps") == "mps"
    monkeypatch.setattr(backend, "_mps_available", lambda: False)
    assert preferred_torch_device("mps") == "cpu"  # absent → honest cpu


def test_report_labels_match_selected_device(monkeypatch):
    monkeypatch.setattr(backend, "_mps_available", lambda: True)
    monkeypatch.setattr(backend, "_cuda_available", lambda: False)
    report = backend_report("auto")
    assert report["selected_device"] == "cpu"     # unverified → cpu
    assert report["mps_available"] is True
    assert report["mps_verified"] is False
    assert report["label"] == backend_label("cpu")
    assert "CPU" in report["label"]
    assert "active" not in report["label"]        # no false acceleration claim


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple Silicon gate")
def test_mps_ab_gate_documents_current_divergence():
    """§18 A/B gate, in a subprocess (torch must not load in this process).

    Documents the verified state: torch 2.13 / htdemucs / M4 → MPS diverges
    from CPU. If a future stack fixes it, this test fails loudly as a signal
    to re-run the full gate and reconsider MPS_VERIFIED.
    """
    pytest.importorskip("soundfile")
    script = (
        "import numpy as np, torch, sys\n"
        "from demucs.pretrained import get_model\n"
        "from demucs.apply import apply_model\n"
        "if not torch.backends.mps.is_available(): print('cosine=skip'); sys.exit(0)\n"
        "m = get_model('htdemucs'); m.eval(); sr = m.samplerate\n"
        "t = np.arange(sr*2)/sr\n"
        "a = (0.4*np.sin(2*np.pi*220*t)).astype('float32')\n"
        "w = torch.tensor(np.stack([a,a])[None])\n"
        "import contextlib\n"
        "with torch.no_grad():\n"
        "    c = apply_model(m, w, device='cpu')[0]\n"
        "    g = apply_model(m, w, device='mps')[0].cpu()\n"
        "cos = float(torch.nn.functional.cosine_similarity(c.flatten(), g.flatten(), dim=0))\n"
        "print(f'cosine={cos:.6f}')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0 or "cosine=" not in result.stdout:
        pytest.skip(f"gate subprocess unavailable: {result.stderr[-200:]}")
    value = result.stdout.strip().split("cosine=")[-1]
    if value == "skip":
        pytest.skip("MPS not available")
    if float(value) > 0.999:
        pytest.fail(
            f"MPS now matches CPU (cosine {value}) — re-run the full §18 gate "
            "and consider flipping MPS_VERIFIED."
        )
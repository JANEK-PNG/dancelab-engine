"""Hardware backend detection & selection (PRODUCT_SPEC §18).

Rules:
- detect, never assume: the reported backend is what will actually be used;
- honest labels: "accelerated" only when the accelerated device is really
  selected and available;
- CPU is always a valid fallback and must produce equivalent outputs
  (QC-gated before MPS became the default — see test_backend.py).
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys

_VALID_MODES = ("auto", "cpu", "mps")

# §18 verification gate history (Apple M4 / torch 2.13 / htdemucs):
# - 2026-07-11 first run: cosine 0.61 vs CPU → gate blocked MPS (honest).
# - 2026-07-12 re-gate (triggered by the sentinel test firing): cosine
#   0.999986 across repeated runs on the hard test signal, ×1.55 faster.
#   The first measurement was erroneous (first-run contamination — likely
#   initial MPS kernel compilation mid-benchmark). MPS output is correct.
# Sentinel in test_backend.py now guards the OTHER direction: it fails if a
# future torch/demucs stack makes MPS diverge again.
MPS_VERIFIED = True


def _mps_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.backends.mps.is_available())


def _cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def preferred_torch_device(mode: str = "auto") -> str:
    """Resolve the torch device string actually used by stem separation.

    mode: "auto" (accelerate when available) | "cpu" (forced) | "mps" (forced,
    falls back to cpu with a truthful answer if MPS is absent).
    Env override: DANCELAB_DEVICE=cpu|mps beats the argument (debug/QC knob).
    """
    override = os.environ.get("DANCELAB_DEVICE", "").strip().lower()
    if override in ("cpu", "mps"):
        mode = override
    if mode not in _VALID_MODES:
        mode = "auto"
    if mode == "cpu":
        return "cpu"
    if mode == "auto" and not MPS_VERIFIED:
        # honest default: unverified acceleration never auto-selects
        return "cpu"
    if _mps_available():
        # some ops still lack MPS kernels; explicit fallback keeps runs alive
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        return "mps"
    return "cpu"


def _cpu_brand() -> str:
    if sys.platform == "darwin":
        try:
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, check=False, timeout=2,
            ).stdout.strip() or platform.processor()
        except Exception:
            return platform.processor()
    return platform.processor() or platform.machine()


def backend_report(mode: str = "auto") -> dict:
    """Detection report for the estimate panel / settings (§18)."""
    device = preferred_torch_device(mode)
    cpu = _cpu_brand()
    apple_generation = None
    if "Apple M" in cpu:
        apple_generation = cpu.replace("Apple ", "")
    return {
        "cpu": cpu,
        "machine": platform.machine(),
        "os": f"{platform.system()} {platform.release()}",
        "apple_silicon": apple_generation,
        "mps_available": _mps_available(),
        "mps_verified": MPS_VERIFIED,
        "cuda_available": _cuda_available(),
        "selected_device": device,
        "label": backend_label(device),
    }


def backend_label(device: str) -> str:
    """Honest user-facing label — describes the device actually selected."""
    if device == "mps":
        return "Apple Silicon backend active (MPS)"
    if device == "cuda":
        return "GPU backend active (CUDA)"
    return "Running on CPU — Deep Analysis may be slower"

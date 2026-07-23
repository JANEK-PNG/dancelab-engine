"""E (learned-audio embedding) pass for the ordering model gate — CLAP.

Produces a frozen embedding catalogue (LAION-CLAP, htsat-unfused, 512-dim) for
every track in the ordering dataset, in the exact schema the gate reads
(load_frozen_embedding_catalog): pinned model with sha256, one non-zero vector
per track, shared dimension. Track-level vector = L2-normalised mean over
evenly-spaced 10 s windows. Resumable via a vectors checkpoint.

Usage: PYTHONPATH=src python3 scripts/corpus_e_embeddings.py [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CORPUS_ROOT = Path("/Volumes/MY_PC/DanceLabCorpus")
DATASET = ROOT / "data/reports/corpus_ordering/dataset.json"
CATALOG = ROOT / "data/reports/corpus_ordering/embeddings.json"
CHECKPOINT = ROOT / "data/reports/corpus_ordering/embeddings.partial.json"
MODEL_ID = "laion/clap-htsat-unfused"
SR = 48000
WINDOW_SEC = 10
N_WINDOWS = 5
EMBEDDING_SCHEMA = "ordering-embeddings-v1"


def required_ids() -> tuple[str, ...]:
    data = json.loads(DATASET.read_text())
    ids: set[str] = set()
    for obs in data["observations"]:
        ids.update(obs.get("candidate_track_ids", []))
        ids.update(obs.get("history_track_ids", []))
    return tuple(sorted(ids))


def _model_sha256(model) -> str:
    """Hash the cached weight file so the catalogue pins an exact model."""
    for module_file in Path(model.config._name_or_path).glob("*.safetensors"):
        return _file_sha256(module_file)
    # fall back to hashing the serialised state dict (stable per weights)
    import torch

    digest = hashlib.sha256()
    for _, tensor in sorted(model.state_dict().items()):
        digest.update(tensor.detach().to(torch.float32).cpu().numpy().tobytes())
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def embed_track(path: Path, model, processor, device) -> list[float] | None:
    import librosa
    import torch

    wav, _ = librosa.load(path, sr=SR, mono=True)
    if wav.size < SR:  # under a second → unusable
        return None
    win = WINDOW_SEC * SR
    if wav.size <= win:
        starts = [0]
    else:
        starts = np.linspace(0, wav.size - win, N_WINDOWS, dtype=int)
    clips = [wav[s : s + win].astype(np.float32) for s in starts]
    inputs = processor(audio=clips, sampling_rate=SR, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = model.get_audio_features(**inputs).pooler_output  # [n_windows, 512]
    vec = feats.mean(dim=0).cpu().numpy().astype(np.float64)
    norm = np.linalg.norm(vec)
    if not np.isfinite(norm) or norm <= 1e-9:
        return None
    return (vec / norm).tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import torch
    from transformers import ClapModel, ClapProcessor

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"loading CLAP {MODEL_ID} on {device}…", flush=True)
    model = ClapModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(MODEL_ID)
    model_hash = _model_sha256(model)
    print(f"model sha256: {model_hash[:16]}…", flush=True)

    from dancelab.validation.djmix.model_gate import inspect_audio_inventory

    inv = inspect_audio_inventory(CORPUS_ROOT, required_ids())
    jobs = list(inv.resolved_sources.items())
    if args.limit:
        jobs = jobs[: args.limit]

    vectors: dict[str, list[float]] = {}
    if CHECKPOINT.is_file():
        vectors = json.loads(CHECKPOINT.read_text())
        print(f"resumed {len(vectors)} vectors from checkpoint", flush=True)

    t0 = time.time()
    done = failed = 0
    for track_id, source in jobs:
        if track_id in vectors:
            continue
        try:
            vec = embed_track(CORPUS_ROOT / source.source_relative_path, model, processor, device)
        except Exception as exc:  # keep the batch alive
            print(f"  FAIL {track_id}: {type(exc).__name__}: {exc}"[:160], flush=True)
            failed += 1
            continue
        if vec is None:
            failed += 1
            continue
        vectors[track_id] = vec
        done += 1
        if done % 25 == 0:
            CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")
            rate = done / max(time.time() - t0, 1e-9)
            print(f"[{len(vectors)}/{len(jobs)}] +{done} failed={failed} ({rate:.2f}/s)", flush=True)

    CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")
    catalog = {
        "schema_version": EMBEDDING_SCHEMA,
        "embedding_name": "clap-htsat-unfused-audio",
        "model": {
            "name": MODEL_ID,
            "version": "htsat-unfused",
            "source": "https://huggingface.co/laion/clap-htsat-unfused",
            "license": "apache-2.0",
            "sha256": model_hash,
            "frozen": True,
        },
        "tracks": {k: vectors[k] for k in sorted(vectors)},
        "provenance": {
            "generated_by": "scripts/corpus_e_embeddings.py",
            "windows": N_WINDOWS,
            "window_sec": WINDOW_SEC,
            "sample_rate": SR,
            "aggregation": "L2-normalised mean over windows",
            "device": device,
        },
    }
    CATALOG.write_text(json.dumps(catalog), encoding="utf-8")
    print(f"catalogue: {len(vectors)} vectors, {failed} failed → {CATALOG}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLAP embeddings for the USER's OWN music library (legal, no download).

Fills the CLAP database gap the corpus can't: the corpus 2881 vectors cover a
research subset (no Four Tet, no leftfield). But the user OWNS those tracks —
this embeds their real library so their world enters CLAP-space legally, from
files on their own disk. Same model + schema as scripts/corpus_e_embeddings.py.

Usage: PYTHONPATH=src python3 scripts/library_e_embeddings.py [--limit N]
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

LIBRARY_ROOT = Path("/Users/jantrybus/Music")
EXCLUDE_DIRS = {"GarageBand", "Logic", "Audio Music Apps"}
AUDIO_EXT = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".m4a"}
CATALOG = ROOT / "data/reports/library_embeddings.json"
CHECKPOINT = ROOT / "data/reports/library_embeddings.partial.json"
MODEL_ID = "laion/clap-htsat-unfused"
SR = 48000
WINDOW_SEC = 10
N_WINDOWS = 5
SCHEMA = "library-embeddings-v1"


def library_files() -> list[Path]:
    out = []
    for p in LIBRARY_ROOT.rglob("*"):
        if p.suffix.lower() not in AUDIO_EXT:
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.name.startswith("._"):
            continue
        out.append(p)
    return sorted(out)


def _model_sha256(model) -> str:
    for f in Path(model.config._name_or_path).glob("*.safetensors"):
        h = hashlib.sha256()
        with f.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    return "unknown"


def embed_track(path: Path, model, processor, device) -> list[float] | None:
    import librosa
    import torch

    wav, _ = librosa.load(path, sr=SR, mono=True)
    if wav.size < SR:
        return None
    win = WINDOW_SEC * SR
    starts = [0] if wav.size <= win else np.linspace(0, wav.size - win, N_WINDOWS, dtype=int)
    clips = [wav[s : s + win].astype(np.float32) for s in starts]
    inputs = processor(audio=clips, sampling_rate=SR, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = model.get_audio_features(**inputs).pooler_output
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

    files = library_files()
    if args.limit:
        files = files[: args.limit]
    print(f"biblioteka: {len(files)} plików audio", flush=True)

    vectors: dict[str, list[float]] = {}
    if CHECKPOINT.is_file():
        vectors = json.loads(CHECKPOINT.read_text())
        print(f"wznowiono {len(vectors)} wektorów", flush=True)

    t0 = time.time()
    done = failed = 0
    for path in files:
        rel = str(path.relative_to(LIBRARY_ROOT))
        if rel in vectors:
            continue
        try:
            vec = embed_track(path, model, processor, device)
        except Exception as exc:
            print(f"  FAIL {path.name}: {type(exc).__name__}"[:120], flush=True)
            failed += 1
            continue
        if vec is None:
            failed += 1
            continue
        vectors[rel] = vec
        done += 1
        if done % 20 == 0:
            CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")
            rate = done / max(time.time() - t0, 1e-9)
            print(f"[{len(vectors)}/{len(files)}] +{done} failed={failed} ({rate:.2f}/s)", flush=True)

    CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")
    catalog = {
        "schema_version": SCHEMA,
        "embedding_name": "clap-htsat-unfused-audio",
        "model": {"name": MODEL_ID, "sha256": model_hash, "frozen": True},
        "library_root": str(LIBRARY_ROOT),
        "tracks": {k: vectors[k] for k in sorted(vectors)},
        "provenance": {
            "generated_by": "scripts/library_e_embeddings.py",
            "windows": N_WINDOWS, "window_sec": WINDOW_SEC, "sample_rate": SR,
            "aggregation": "L2-normalised mean over windows", "device": device,
            "note": "user-owned files, no download",
        },
    }
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    print(f"\nkatalog: {len(vectors)} wektorów, {failed} failed → {CATALOG}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLAP embeddings for the FULL downloaded corpus (~12.6k tracks), not just
the 2881-track gate universe.

The original E pass (scripts/corpus_e_embeddings.py) was scoped to the frozen
ordering dataset — a research subset. This walks EVERYTHING in the corpus
tracks/ dir so the sound-space covers all real DJ-played tracks on the drive:
anchors get a 12k-track neighbourhood, master profiles get sound centroids,
and priors can measure sound-similarity of real transitions at full scale.

Writes a SEPARATE catalogue (does not touch Kord's frozen embeddings.json).
Resumable via checkpoint. Features-only (512 floats/track) per CORPUS_ETHICS.

Usage: PYTHONPATH=src python3 scripts/corpus_e_embeddings_full.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TRACKS_DIR = Path("/Volumes/MY_PC/DanceLabCorpus/tracks")
CATALOG = ROOT / "data/reports/corpus_embeddings_full.json"
CHECKPOINT = ROOT / "data/reports/corpus_embeddings_full.partial.json"
MODEL_ID = "laion/clap-htsat-unfused"
SR = 48000
WINDOW_SEC = 10
N_WINDOWS = 5
AUDIO_EXT = {".webm", ".m4a", ".mp3", ".opus", ".ogg"}


def corpus_files() -> list[Path]:
    out = []
    for p in sorted(TRACKS_DIR.iterdir()):
        if p.suffix.lower() in AUDIO_EXT and not p.name.startswith("._") and p.is_file():
            out.append(p)
    return out


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

    # reuse already-computed vectors from the frozen 2881 catalogue (same model)
    vectors: dict[str, list[float]] = {}
    frozen = ROOT / "data/reports/corpus_ordering/embeddings.json"
    if frozen.is_file():
        vectors.update(json.loads(frozen.read_text()).get("tracks", {}))
        print(f"start z {len(vectors)} wektorami z zamrożonego katalogu 2881", flush=True)
    if CHECKPOINT.is_file():
        vectors.update(json.loads(CHECKPOINT.read_text()))
        print(f"wznowiono checkpoint → {len(vectors)} wektorów", flush=True)

    files = corpus_files()
    if args.limit:
        files = files[: args.limit]
    todo = [p for p in files if p.stem not in vectors]
    print(f"korpus: {len(files)} plików | do policzenia: {len(todo)}", flush=True)

    t0 = time.time()
    done = failed = 0
    for path in todo:
        try:
            vec = embed_track(path, model, processor, device)
        except Exception as exc:
            print(f"  FAIL {path.name}: {type(exc).__name__}"[:110], flush=True)
            failed += 1
            continue
        if vec is None:
            failed += 1
            continue
        vectors[path.stem] = vec
        done += 1
        if done % 50 == 0:
            CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")
            rate = done / max(time.time() - t0, 1e-9)
            eta_h = (len(todo) - done) / max(rate, 1e-9) / 3600
            print(f"[{len(vectors)} total] +{done}/{len(todo)} failed={failed} "
                  f"({rate:.2f}/s, ETA {eta_h:.1f}h)", flush=True)

    CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")
    CATALOG.write_text(json.dumps({
        "schema_version": "corpus-embeddings-full-v1",
        "embedding_name": "clap-htsat-unfused-audio",
        "model": {"name": MODEL_ID, "frozen": True},
        "tracks": {k: vectors[k] for k in sorted(vectors)},
        "provenance": {"generated_by": "scripts/corpus_e_embeddings_full.py",
                        "windows": N_WINDOWS, "window_sec": WINDOW_SEC,
                        "sample_rate": SR, "device": device,
                        "note": "features-only per CORPUS_ETHICS; superset of frozen 2881"},
    }, ensure_ascii=False), encoding="utf-8")
    print(f"\nkatalog pełny: {len(vectors)} wektorów, {failed} failed → {CATALOG}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

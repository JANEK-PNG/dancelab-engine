"""DanceLab corpus downloader — djmix-dataset audio fetcher.

Downloads DJ mixes + their identified source tracks from the public
djmix-dataset metadata (mir-aidj, DAFx 2022) for internal research use
(transition alignment, prior calibration). Resumable: re-running skips
anything already in the manifest or on disk.

Priority order:
  1. mixes with timestamps AND >=10 identified tracks, bass-music tags first
     (Drum & Bass / Jungle / Dubstep / UK Garage / Breakbeat)
  2. same quality core, all other genres (House/Techno/Trance/...)
  3. everything else (only if --include-rest)

Usage:
  python3 corpus_downloader.py --root /Volumes/MY_PC/DanceLabCorpus [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

YTDLP = os.path.expanduser("~/.local/bin/yt-dlp")
FFMPEG_DIR = os.path.expanduser("~/.local/bin")  # symlinked ffmpeg lives here
MIN_FREE_GB = 30  # hard stop so we never fill the drive completely
BASS_TAGS = ("drum & bass", "jungle", "dubstep", "uk garage", "breakbeat")
TRACK_WORKERS = 3  # parallel track downloads per mix (YouTube-friendly)

# yt-dlp is retried once per URL; a URL that fails twice is marked dead and
# never blocks the queue. Audio is kept in native format (no re-encode).
COMMON_ARGS = [
    "--no-playlist",
    "--retries", "2",
    "--fragment-retries", "2",
    "--socket-timeout", "30",
    "--no-progress",
    "--no-warnings",
    "-f", "ba/b",
]


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def load_manifest(path: Path) -> dict[str, str]:
    done: dict[str, str] = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                done[row["key"]] = row["status"]
    return done


def append_manifest(path: Path, key: str, kind: str, status: str, dest: str, err: str = "") -> None:
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["key", "kind", "status", "path", "error", "ts"])
        w.writerow([key, kind, status, dest, err[:200], int(time.time())])


def run_ytdlp(url: str, out_tmpl: str, extra: list[str] | None = None) -> tuple[bool, str]:
    env = dict(os.environ, PATH=f"{FFMPEG_DIR}:{os.environ.get('PATH', '')}")
    cmd = [YTDLP, *COMMON_ARGS, *(extra or []), "-o", out_tmpl, url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=env)
    except subprocess.TimeoutExpired:
        return False, "timeout 30min"
    if proc.returncode == 0:
        return True, ""
    tail = (proc.stderr or proc.stdout).strip().splitlines()
    return False, tail[-1] if tail else f"exit {proc.returncode}"


def is_bass(mix: dict) -> bool:
    tags = " ".join(t.get("key", "") for t in mix.get("tags", [])).lower()
    return any(g in tags for g in BASS_TAGS)


def quality_core(mix: dict) -> bool:
    return mix.get("num_timestamps", 0) > 0 and mix.get("num_identified_tracks", 0) >= 10


def ordered_queue(mixes: list[dict], include_rest: bool) -> list[dict]:
    core = [m for m in mixes if quality_core(m)]
    rest = [m for m in mixes if not quality_core(m)]
    by_transitions = lambda m: -m.get("num_available_transitions", 0)  # noqa: E731
    queue = sorted([m for m in core if is_bass(m)], key=by_transitions)
    queue += sorted([m for m in core if not is_bass(m)], key=by_transitions)
    if include_rest:
        queue += sorted(rest, key=by_transitions)
    return queue


def track_ids(mix: dict) -> list[str]:
    return [t["id"] for t in mix.get("tracklist", []) if t.get("id")]


def already_on_disk(dir_: Path, stem: str) -> bool:
    return any(dir_.glob(f"{stem}.*"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--limit", type=int, default=0, help="stop after N mixes (0 = no limit)")
    ap.add_argument("--include-rest", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    mixes_dir, tracks_dir = root / "mixes", root / "tracks"
    mixes_dir.mkdir(parents=True, exist_ok=True)
    tracks_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.csv"

    dataset = json.loads((root / "djmix-dataset.json").read_text())
    done = load_manifest(manifest_path)
    queue = ordered_queue(dataset, args.include_rest)
    print(f"queue: {len(queue)} mixes | already in manifest: {len(done)}", flush=True)

    processed = 0
    for mix in queue:
        if args.limit and processed >= args.limit:
            print("mix limit reached, stopping.", flush=True)
            break
        if free_gb(root) < MIN_FREE_GB:
            print(f"STOP: free space below {MIN_FREE_GB} GB guard.", flush=True)
            return 1

        mid = mix["id"]
        processed += 1
        mix_key = f"mix:{mid}"
        if done.get(mix_key) == "ok" or already_on_disk(mixes_dir, mid):
            if mix_key not in done:
                append_manifest(manifest_path, mix_key, "mix", "ok", f"mixes/{mid}.*", "resumed")
        else:
            ok, err = run_ytdlp(mix["audio_url"], str(mixes_dir / f"{mid}.%(ext)s"))
            append_manifest(manifest_path, mix_key, "mix", "ok" if ok else "dead", f"mixes/{mid}.*", err)
            done[mix_key] = "ok" if ok else "dead"
            print(f"[{processed}] {mid} mix {'OK' if ok else 'DEAD: ' + err} — {mix['title'][:60]}", flush=True)
            if not ok:
                continue  # no mix audio -> its tracks are useless for alignment

        pending = [
            tid for tid in track_ids(mix)
            if done.get(f"track:{tid}") is None and not already_on_disk(tracks_dir, tid)
        ]
        if not pending:
            continue

        def fetch(tid: str) -> tuple[str, bool, str]:
            ok, err = run_ytdlp(
                f"https://www.youtube.com/watch?v={tid}",
                str(tracks_dir / f"{tid}.%(ext)s"),
                extra=["--sleep-interval", "2", "--max-sleep-interval", "6"],
            )
            return tid, ok, err

        with ThreadPoolExecutor(max_workers=TRACK_WORKERS) as pool:
            for fut in as_completed([pool.submit(fetch, t) for t in pending]):
                tid, ok, err = fut.result()
                append_manifest(manifest_path, f"track:{tid}", "track", "ok" if ok else "dead", f"tracks/{tid}.*", err)
                done[f"track:{tid}"] = "ok" if ok else "dead"
        n_ok = sum(1 for t in pending if done.get(f"track:{t}") == "ok")
        print(f"    {mid}: tracks {n_ok}/{len(pending)} OK", flush=True)

    print("queue finished.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

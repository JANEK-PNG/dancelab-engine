"""Batch M11 alignment over the downloaded djmix corpus.

Runs the beat-synchronous mix-to-track subsequence DTW (dancelab.validation.
djmix) across every downloaded mix that has enough of its identified tracks on
disk. One JSON report per mix, plus an appended transitions JSONL for stats.

Independent of the BPM-octave tag bug: corpus rips carry no BPM tags, so the
engine's octave fold fires normally. Alignment matches by chroma/timbre content,
and match_rate / beatgrid_reliable flag any grid that is not trustworthy.

Resumable: a mix whose report already exists is skipped. Parallel across mixes
(each mix is independent); workers capped because each holds ~1h of mix audio.

Usage:
  PYTHONPATH=src python3 scripts/corpus_align.py --root /Volumes/MY_PC/DanceLabCorpus \
      [--limit N] [--workers 3] [--min-tracks 4]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

AUDIO_EXTS = (".mp3", ".m4a", ".opus", ".webm", ".wav", ".flac", ".ogg", ".aac")
WINDOW_MARGIN_SEC = 150.0  # each side of the timestamp estimate before the DTW
WINDOW_FALLBACK_MATCH = 0.30  # windowed result below this → redo full-mix DTW
_TIME_RE = re.compile(r"^\s*\[(\d{1,2}(?::\d{2}){0,2})\]")


def find_audio(dir_: Path, stem: str) -> Path | None:
    for ext in AUDIO_EXTS:
        candidate = dir_ / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    hits = sorted(dir_.glob(f"{stem}.*"))
    return next((h for h in hits if h.suffix.lower() in AUDIO_EXTS), None)


def parse_bracket_seconds(title: str) -> float | None:
    """Leading [MM] / [H:MM] / [H:MM:SS] marker → seconds. None if absent.

    Datasets mix elapsed-minute and wall-clock forms; both are linear, so a
    later relative-to-first subtraction recovers elapsed time either way.
    """
    m = _TIME_RE.match(title or "")
    if not m:
        return None
    parts = [int(p) for p in m.group(1).split(":")]
    if len(parts) == 1:
        return parts[0] * 60.0
    if len(parts) == 2:
        return parts[0] * 3600.0 + parts[1] * 60.0
    return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]


def elapsed_estimates(titles: list[str]) -> list[float | None]:
    """Per-track elapsed-second estimate relative to the first parsed marker.

    Returns all-None (distrust) when markers are missing, non-monotonic, or
    span an implausible range — the caller then falls back to full-mix DTW.
    """
    raw = [parse_bracket_seconds(t) for t in titles]
    known = [v for v in raw if v is not None]
    if len(known) < 2:
        return [None] * len(titles)
    base = known[0]
    rel = [None if v is None else v - base for v in raw]
    ordered = [v for v in rel if v is not None]
    if any(b < a - 1.0 for a, b in zip(ordered, ordered[1:])):  # must be non-decreasing
        return [None] * len(titles)
    if ordered[-1] <= 0 or ordered[-1] > 6 * 3600:  # implausible total span
        return [None] * len(titles)
    return rel


def _slice_features(seq, start_sec: float, end_sec: float):
    """Sub-sequence of beat-synchronous features whose beats fall in the window.

    Returns (sub_sequence, first_beat_index) or None if the window is too thin.
    beat_times stay absolute, so downstream cue seconds need no re-offset.
    """
    from dancelab.validation.djmix.models import BeatFeatureSequence

    bt = seq.beat_times_sec
    idx = [i for i, t in enumerate(bt) if start_sec <= t <= end_sec]
    if len(idx) < 16:
        return None
    i0, i1 = idx[0], idx[-1] + 1
    return (
        BeatFeatureSequence(
            beat_times_sec=bt[i0:i1],
            blocks={k: v[:, i0:i1] for k, v in seq.blocks.items()},
            beatgrid_reliable=seq.beatgrid_reliable,
            beatgrid_quality=seq.beatgrid_quality,
            warnings=seq.warnings,
        ),
        i0,
    )


def align_one_mix(
    mix_id: str,
    mix_path: str,
    track_specs: list[tuple[str, str, float | None]],  # (yt_id, path, approx_start_sec)
    out_path: str,
    sample_rate: int,
    match_threshold: float,
    use_window: bool = False,
) -> dict:
    """M11 per mix. Full-mix DTW by default (canonical); opt-in coarse window.

    Profiling (2026-07-15) showed timestamp-windowing only trims DTW (~half the
    per-track cost) and drifts cue points, so full DTW is the default. The
    windowed path stays available behind use_window for experiments.
    """
    t0 = time.time()
    from dancelab.validation.djmix.__main__ import _feature_sequence
    from dancelab.validation.djmix.alignment import align_feature_sequences
    from dancelab.validation.djmix.confidence import score_cue_candidates
    from dancelab.validation.djmix.cues import extract_cue_candidates
    from dancelab.validation.djmix.identity import identify_audio_file
    from dancelab.validation.djmix.transitions import assemble_transition_evidence

    feature_names = ("chroma", "mfcc")
    mix_identity = identify_audio_file(Path(mix_path))
    mix_features, mix_grid = _feature_sequence(Path(mix_path), sample_rate, feature_names)

    def run_dtw(track_features, mix_seq):
        return align_feature_sequences(
            track_features, mix_seq,
            feature_names=feature_names, key_invariant=True,
            normalization="source_global", match_threshold=match_threshold,
        )

    records = []
    results = []
    windowed_count = 0
    seen_sha: set[str] = set()
    for yt_id, track_path, approx_start in track_specs:
        identity = identify_audio_file(Path(track_path))
        if identity.sha256 in seen_sha:
            continue  # duplicate audio content — skip, do not corrupt the run
        seen_sha.add(identity.sha256)
        track_features, track_grid = _feature_sequence(Path(track_path), sample_rate, feature_names)

        alignment = None
        mix_for_cues = mix_features
        used_window = False
        if use_window and approx_start is not None and track_features.beat_count:
            track_dur = track_features.beat_times_sec[-1] - track_features.beat_times_sec[0]
            sliced = _slice_features(
                mix_features,
                approx_start - WINDOW_MARGIN_SEC,
                approx_start + track_dur + WINDOW_MARGIN_SEC,
            )
            if sliced is not None:
                win_seq, _ = sliced
                candidate = run_dtw(track_features, win_seq)
                if candidate.matched or candidate.match_rate >= WINDOW_FALLBACK_MATCH:
                    alignment, mix_for_cues, used_window = candidate, win_seq, True
        if alignment is None:  # no timestamp, thin window, or weak windowed match
            alignment = run_dtw(track_features, mix_features)
            mix_for_cues = mix_features
        windowed_count += int(used_window)

        cues = extract_cue_candidates(
            alignment.path,
            mix_beat_times_sec=mix_for_cues.beat_times_sec,
            track_beat_times_sec=track_features.beat_times_sec,
        )
        cues = score_cue_candidates(cues, alignment, track=track_features, mix=mix_for_cues)
        records.append((identity, alignment, cues))
        results.append({
            "youtube_id": yt_id,
            "track_id": identity.source_id,
            "display_name": identity.display_name,
            "windowed": used_window,
            "track_beatgrid": {
                "bpm": track_grid.bpm, "reliable": track_grid.reliable,
                "quality_score": track_grid.quality_score,
            },
            "alignment": alignment.as_dict(),
            "cue_candidates": [c.as_dict() for c in cues],
        })

    transitions = []
    for prev, nxt in zip(records, records[1:]):
        p_id, p_al, p_cu = prev
        n_id, n_al, n_cu = nxt
        transitions.extend(assemble_transition_evidence(
            mix=mix_identity, previous_track=p_id, next_track=n_id,
            previous_alignment=p_al, next_alignment=n_al,
            previous_cues=p_cu, next_cues=n_cu,
        ))

    report = {
        "mix_id": mix_id,
        "schema_version": "1.1.0",
        "mix_identity": mix_identity.as_dict(),
        "mix_beatgrid": {"bpm": mix_grid.bpm, "reliable": mix_grid.reliable,
                         "quality_score": mix_grid.quality_score},
        "tracks_aligned": len(results),
        "tracks_windowed": windowed_count,
        "results": results,
        "transitions": [t.as_dict() for t in transitions],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(out_path).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out_path)
    matched = sum(1 for r in results if r["alignment"]["matched"])
    return {"mix_id": mix_id, "tracks": len(results), "matched": matched,
            "windowed": windowed_count,
            "transitions": len(transitions), "elapsed": report["elapsed_sec"]}


def build_jobs(root: Path, min_tracks: int, out_dir: Path) -> list[tuple]:
    dataset = json.loads((root / "djmix-dataset.json").read_text())
    mixes_dir, tracks_dir = root / "mixes", root / "tracks"
    jobs = []
    for mix in dataset:
        mid = mix["id"]
        mix_file = find_audio(mixes_dir, mid)
        if mix_file is None:
            continue
        out_path = out_dir / f"{mid}.json"
        if out_path.exists():
            continue  # resume: already aligned
        tracklist = mix.get("tracklist", [])
        # elapsed estimate is computed over the FULL ordered tracklist so the
        # relative-to-first offset and monotonic check stay valid
        est = elapsed_estimates([entry.get("title", "") for entry in tracklist])
        specs = []
        for entry, approx in zip(tracklist, est):
            yt = entry.get("id")
            if not yt:
                continue
            tf = find_audio(tracks_dir, yt)
            if tf is not None:
                specs.append((yt, str(tf), approx))
        if len(specs) >= min_tracks:
            jobs.append((mid, str(mix_file), specs, str(out_path)))
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--min-tracks", type=int, default=4)
    ap.add_argument("--sample-rate", type=int, default=22050)
    ap.add_argument("--match-threshold", type=float, default=0.4)
    ap.add_argument("--window", action="store_true", help="opt-in timestamp-windowed DTW (experimental)")
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = root / "alignments"
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(root, args.min_tracks, out_dir)
    if args.limit:
        jobs = jobs[: args.limit]
    print(f"alignable mixes (≥{args.min_tracks} tracks on disk, not yet done): {len(jobs)}", flush=True)
    if not jobs:
        print("nothing to do.", flush=True)
        return 0

    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {
            pool.submit(align_one_mix, mid, mp, specs, op, args.sample_rate, args.match_threshold, args.window): mid
            for mid, mp, specs, op in jobs
        }
        for fut in as_completed(futs):
            mid = futs[fut]
            done += 1
            try:
                r = fut.result()
                print(f"[{done}/{len(jobs)}] {mid}: {r['matched']}/{r['tracks']} matched, "
                      f"{r['windowed']} windowed, {r['transitions']} transitions, {r['elapsed']}s", flush=True)
            except Exception as exc:  # keep the batch alive; one bad mix must not kill it
                print(f"[{done}/{len(jobs)}] {mid}: FAILED {type(exc).__name__}: {exc}", flush=True)
                (out_dir / f"{mid}.error.txt").write_text(traceback.format_exc(), encoding="utf-8")

    print("batch finished.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# DanceLab Pro — Next Build Specification (Demo Hardening)

Status: accepted engineering spec · 2026-07-11
Scope: 7 areas raised in product review. Each section states what changes in
the **engine**, **tooling**, **cache/storage**, **UX**, and what **QC** must
verify. Grounded in the current codebase — file references are to real code,
and every "current state" claim below was verified empirically, not assumed.

## Empirical baseline (verified on this repo, 2026-07-11)

- Analysis cache already occupies **180 MB inside the repo** at
  `data/processed/` (~150–270 KB JSON per track, 73 tracks in the
  `smart_playlist/` subcache). The user has no visibility or control. → §2 is
  not hypothetical; the disk problem already exists at 73 tracks.
- Demucs is installed and the htdemucs model (~80 MB) is cached at
  `~/.cache/torch`. Separation runs ~0.34× realtime on CPU.
- The Rekordbox exporter writes **hot cues only** (POSITION_MARK Num 0–7).
  Memory cues (Num −1) are mentioned in the module docstring but never
  written. Loops are not written. Nothing verifies what Rekordbox will
  accept. → §5 gate is required before we claim cue support.
- `build_set` is fully deterministic by design (AUD-M5 made tie-breaks
  sorted). Same library + same settings → **byte-identical playlist every
  time**. → §6 is a real product gap, not a nice-to-have.
- `ingestion/tags.py` requires mutagen, which is **not installed** — the tag
  fallback path is currently dead code. Fix: add `mutagen` to the `[audio]`
  extra and to the default install docs.

---

## 1. Demucs positioning — Stem Separation Worker, not "the engine"

**Decision.** Demucs is a *backend of one pipeline stage*, exactly as the
architecture already treats it: `stems/extractor.py::extract_stems` is the
stage; demucs is one of its methods (`demucs | none`, `auto` resolves by
availability). Nothing in decision logic imports demucs. This is correct and
stays. Any UI or doc text that says "demucs engine" is wrong and must say
**Stem Separation Worker**.

**Canonical data flow (document + enforce):**

```
audio file
  → Stem Separation Worker (demucs backend; HPSS/low-pass DSP fallback)
  → stem cache                (§2: cache class "stems")
  → feature extraction        (stem_energy_ratio_per_frame, stem window features)
  → engine input adapter      (AnalysisResult fields: vocal_density_proxy,
                               stem_window_features, provenance)
  → scoring / decision output (mixability, transition windows, set builder)
```

**Engine changes:** none. **Tooling:** rename user-facing strings ("true
separation (demucs)" stays, anything implying demucs = engine goes).
**Provenance rule (ADR-005):** every stem-derived feature already carries
`StemProvenance`; the adapter must keep `source_status =
fallback_full_mix` visible when the worker fell back — the decision layer
must never look stem-backed when it is not.

**QC (§7-A):** worker-off run produces identical decision outputs to
pre-stem builds except stem-marked fields; worker-on run marks every
stem-derived field with provenance; fallback path emits the fallback
warning end-to-end (pipeline → API → UI inspector).

---

## 2. Cache & storage policy

**Decision.** One cache root, five named cache classes, one manifest. No
silent writes outside the cache root. Default root moves **out of the repo**
to `~/Library/Application Support/DanceLab/cache` (macOS), overridable in
config and UI.

**Cache classes** (each its own subdir + manifest section):

| class | contents | today (to migrate) |
|---|---|---|
| `analysis` | AnalysisResult JSONs | `data/processed/*.json` |
| `stems` | separation wavs (preview + worker) | `data/processed/stem_preview/` |
| `temp` | in-flight worker files | scattered / none |
| `exports` | Rekordbox XML, exported stems | `data/exports/`, user paths |
| `models` | demucs weights | `~/.cache/torch` (report size, never delete without explicit action) |

Source audio is **never** copied into cache; we store paths + content hash.

**New module `storage/cache_manager.py`:**
- `CacheManifest` (JSON at cache root): per-class entries
  `{key, path, bytes, created_at, source_hash, engine_version}`.
- `estimate(job) -> CacheEstimate`: analysis ≈ 0.25 MB/track (measured);
  stems ≈ `duration_sec × sample_rate × 2 bytes × stems` (~40 MB per 5-min
  track for 4 stems) — shown **before** the job runs.
- `usage() -> per-class bytes`, `clear(cache_class)`, `move_root(new_path)`
  (copy-verify-swap, never delete-first), `enforce_limit()` — LRU eviction
  of `analysis`/`stems` only, `exports` are user data and never auto-evicted.
- Config: `paths.cache_root`, `cache.max_bytes` (default 10 GB),
  `cache.low_disk_floor_bytes` (default 2 GB free).

**UX states (Simple Mode settings page + graph File menu → "Cache…"):**
- cache estimate line on Analyze and stem-export steps ("~1.2 GB of stems
  will be written to <path>");
- low-disk banner when free space < floor: block new stem jobs, allow
  analysis with warning;
- Clear Cache (per class, with sizes), Move Cache Location (progress +
  rollback on failure);
- missing-cache state: manifest entry whose file vanished → row shows
  "cache missing — re-run analysis" with a one-click re-run (never a crash,
  never silent re-compute mid-flow).

**QC (§7-B):** kill -9 during stem write leaves no manifest orphans after
restart scan; limit enforcement never evicts exports; move-root with a full
cache is resumable; low-disk state actually blocks the stem worker.

---

## 3. Large sample folders — bulk import handling

**Current state:** Codex's preflight flags <2 min / >10 min files but the
confirm dialog is effectively per-list; a 2 000-loop sample folder would be
unusable.

**Decision.** Preflight returns a *classified batch*, and the dialog becomes
a bulk triage panel.

**Tooling — extend `ingestion/preflight.py`:**
- `classify_batch(files) -> BatchTriage` with buckets: `full_length`
  (2–10 min), `short` (<2 min, likely loops/one-shots), `long` (>10 min,
  likely mixes), `unreadable`; per-folder counts.
- `ImportRule` dataclass `{folder, min_duration_sec, action}` persisted in
  QSettings ("remember rule for this folder").

**UX — replace the per-file dialog with a triage panel:**
- summary line per folder: "Samples/ — 1 840 files: 1 795 under 2 min";
- bulk actions: **Import only full-length tracks** (default when short-share
  > 50 %), **Reject all in folder**, **Reject shorter than [X] s** (editable
  threshold), **Review first 20** (paged list for spot-checking),
  **Apply rule to this folder** + **Remember rule**;
- imports over 500 accepted files ask once more with total analysis-time and
  cache estimates (§2).

**Engine changes:** none — this is all pre-pipeline.

**QC (§7-C):** 2 000-file synthetic folder triages in <2 s (metadata probe
only, no decode); "remember rule" survives restart; unreadable files land in
the failure list, never abort the batch; default suggestion matches the
bucket distribution.

---

## 4. Export selected tracks for separation

**Decision.** Build on the existing `stems/workflow.py::export_stems_for_paths`
(already writes one folder per track + manifest) — surface it as a
user-facing workflow with stem choice and collision policy.

**Tooling — extend `export_stems_for_paths`:**
- `stem_selection: set[StemType]` — export only requested stems (today it
  writes everything the model produced);
- `collision: overwrite | skip_existing` per run;
- `keep_cache: bool` — copy from stem cache vs move; `delete_temp: bool`;
- manifest per output root: source path + hash, model name/signature,
  stems written, config hash, warnings (reuse `stem_manifest_payload`).

**Stem options:** vocals / drums / bass / other — from htdemucs sources
(verified: `['drums','bass','other','vocals']`). Guitar/piano appear **only**
when the selected model variant exposes them (htdemucs_6s); the option list
is generated from `model.sources`, never hardcoded — no advertising stems
the model cannot produce.

**UX — new flow reachable from Step 4/5 and the playlist context menu:**
select tracks (default: current set plan) → output folder → stem checkboxes
(with per-track size estimate from §2) → options (overwrite/skip, keep
cache, delete temp) → progress list reusing the per-track checklist pattern
from the Analyze step (real worker stages, ✓/✗ per track) → done state with
"Reveal in Finder".

**QC (§7-D):** requested-stems-only on disk; skip_existing skips byte-stable
files; manifest lists exactly what was written; mid-run cancel leaves
completed track folders valid + temp cleaned; 6-stem options absent when the
4-stem model is selected.

---

## 5. Rekordbox cue verification gate + edge-level transition cues

**Current state (verified):** exporter writes hot cues 0–7 only; memory
cues and loops are docstring fiction; nothing validates the XML against what
Rekordbox actually imports. We must not claim cue support without a gate.

**Decision A — Cue Import Verification Gate** (`export/rekordbox_verify.py`):
runs on every generated XML before we present "export succeeded":
- re-parse the written file (not the in-memory tree);
- verify per track: cue count ≤ 8 hot cues, `Num` uniqueness and range,
  `Type` values legal, `Start` within `[0, TotalTime]`, cues sorted, hot vs
  memory classification explicit, loop cues (`Type=4`) only when we actually
  wrote loop data;
- verify per transition (edge model below): the B-side cue referenced as a
  transition start **exists in the XML** with a matching timestamp (±10 ms);
- output `CueVerificationReport {passed, per_track_issues, per_edge_issues}`
  attached to the export response and shown in UI. A failed gate downgrades
  the export message to "XML written but cue verification FAILED: …" —
  never a silent green.

**Decision B — edge-level transition cue model.** Rekordbox cues are
track-level; our recommendations are edge-level. New model in
`core/models.py`:

```python
class TransitionCue(SchemaVersionedOutput):
    from_track_id: str
    to_track_id: str
    a_out_start_sec: float          # verified mix_out window start on A
    b_in_start_sec: float           # verified mix_in window start on B
    b_cue_source: Literal["hot_cue", "memory_cue", "window_only"]
    b_cue_num: int | None           # hot cue slot when hot_cue
    mix_duration_beats: int | None  # None when either beatgrid unreliable
    transition_type: str            # from edge decision strategy
    confidence: float
    requires_manual_listen: bool    # True unless both windows verified AND
                                    # both beatgrids reliable
    provenance: OutputProvenance | None
```

Populated by set-plan export: for each `SetTransition`, resolve the best
mix_out window on A and mix_in on B (already computed), map the B window to
the hot cue the exporter wrote (same timestamp), and emit `TransitionCue`
into the export manifest. **Hard rule (ADR-005): no `TransitionCue` may
claim a B start without `b_cue_source != "window_only"` being backed by a
cue actually present in the verified XML; `window_only` edges always set
`requires_manual_listen = True`.** `mix_duration_beats` is None (not a
fabricated number) when `BeatGrid.reliable` is False on either side.

**QC (§7-E):** gate fails on hand-corrupted XML (dup Num, cue past
TotalTime, unsorted); every exported edge has a resolvable B cue or is
explicitly `window_only + requires_manual_listen`; round-trip: re-parse of
written XML reproduces cue set byte-for-byte; unreliable-beatgrid tracks
never produce beat-quantified mix durations.

---

## 6. Playlist uniqueness & controlled repetition

**Current state (verified):** the planner is deterministic — same inputs,
identical playlist forever. DJs will see the tool as a one-trick generator.
Opposite failure (random shuffle) violates our honesty rules. Design:
**relevance first, diversity as soft penalties, seeded variation only as
tie-breaker.**

**New module `decision/history.py` + store
`<cache_root>/history/playlists.jsonl`:**

```python
class PlaylistFingerprint(SchemaVersionedOutput):
    sequence_hash: str      # sha1 of ordered track_ids
    track_set_hash: str     # sha1 of sorted track_ids
    edge_hashes: list[str]  # sha1 per (from_id, to_id) pair
    opening_id: str; peak_id: str | None; closing_id: str
    context_hash: str       # sha1 of (context profile, planner settings)
    seed: int; novelty_mode: str; created_at: str
```

**Planner changes (`set_builder.build_set`):**
- new params `novelty_mode`, `history: list[PlaylistFingerprint] | None`,
  `seed: int | None`, `carryover_allowance: int`;
- scoring adds **soft penalties** (new formula terms, documented in
  `formula_terms.yaml` per the no-anonymous-variables contract):
  - `repeat_edge_penalty` — candidate edge whose hash appears in recent
    history;
  - `repeat_slot_penalty` — same opening / same peak / same closing as the
    previous playlist for the same `context_hash` (configurable per slot);
  - `overuse_penalty` — track appearing in > `carryover_allowance`
    (default 3) of the last N playlists;
- **hard rules stay hard**: BPM gates, harmonic gates, risk suppression are
  never overridden by novelty pressure — penalties apply inside the
  candidate set that already passed the gates;
- **seeded tie-breaking**: when top candidates score within ε (default
  0.02 — inside our honest score resolution), a seeded RNG picks among
  them. Same seed → reproducible; different seed → legitimately different
  playlist with no relevance sacrificed;
- post-build check: if `sequence_hash` equals the most recent history entry
  for the same `context_hash`, re-run once with the next seed and a bumped
  `repeat_edge_penalty`; if it STILL matches (tiny library), keep it and
  attach warning "library too small to vary — identical set returned".
  Honesty over fake shuffling.

**Modes** (planner setting, replaces nothing — composes with Codex's
smart/harmonic/bpm component modes):

| mode | penalties | tie-break | carryover |
|---|---|---|---|
| Deterministic | off | off (fixed order) | ∞ |
| Conservative | low | seeded | 5 |
| Balanced (default) | medium | seeded | 3 |
| Fresh | high | seeded | 1 |
| Seeded variation | medium | user-supplied seed | 3 |
| Exploratory | high + widened ε (0.05) | seeded | 0 |

**UX:** mode picker + seed field (visible in Seeded variation), "why did
this repeat?" — plan warnings list carryover tracks and any history
penalties applied (reasoning stays inspectable, per provenance discipline).

**QC (§7-F/G):** two consecutive Balanced runs on a 30-track library differ
in `sequence_hash` while mean transition score drops ≤ 0.03 vs
Deterministic; Deterministic is byte-stable; carryover never exceeds
allowance; hard-gate violations = 0 across 100 seeded runs; tiny-library
degenerate case returns the honest warning instead of thrashing.

---

## 7. QC pipeline extension

New test modules, one per area — each covers happy path / empty / error /
edge / hard-fail / expected output / regression:

| suite | hard-fail rules (build-blocking) |
|---|---|
| `test_qc_stem_worker.py` (§1) | decision outputs identical with worker off; fallback provenance never lost |
| `test_qc_cache.py` (§2) | no writes outside cache root; exports never auto-evicted; manifest consistent after crash |
| `test_qc_bulk_import.py` (§3) | 2 000-file triage < 2 s; no per-file decode during preflight |
| `test_qc_stem_export.py` (§4) | only requested stems written; cancel leaves valid partial output |
| `test_qc_cue_verify.py` (§5) | corrupted XML fails gate; no edge claims an unverified B cue |
| `test_qc_uniqueness.py` (§6) | hard gates unviolated across seeds; Deterministic byte-stable |
| `test_qc_repetition.py` (§6) | carryover ≤ allowance; repeated-sequence warning on degenerate libraries |

Regression harness: every QC suite runs in the standard pytest run (no
separate CI stage yet); each suite seeds its own tmp cache root so QC never
touches the developer's real cache.

---

## Build order (dependency-driven)

1. **§2 cache manager** — everything else writes through it.
2. **§5 cue gate + TransitionCue** — demo credibility: exported sets must
   verifiably load in Rekordbox.
3. **§6 uniqueness** — demo "wow": regenerate gives a genuinely different,
   equally good set.
4. **§3 bulk import** — extends Codex's preflight; small.
5. **§4 stem export workflow** — mostly surfacing existing code.
6. **§1** — documentation/labeling pass, no engine work.
7. **§7 QC suites** — written alongside each item, not after.

Plus one hygiene fix found during this review: add `mutagen` to the
`[audio]` extra — the tag-fallback path is currently dead code without it.

# DanceLab Pro — Product / Engineering Specification

Status: accepted · 2026-07-11 · supersedes and absorbs `NEXT_BUILD_SPEC.md`
Authored against the real codebase; every "current state" claim was verified
in-repo, not assumed. Labels used throughout: CONFIRMED REQUIREMENT,
PRODUCT DECISION, TECHNICAL ASSUMPTION, NEEDS VERIFICATION, HARD QC RULE,
OPEN QUESTION, NEEDS SOURCE VERIFICATION.

## 1. Executive Summary

DanceLab Pro answers one question: **"Does this next track make sense right
now?"** The engine (BPM/key/groove/stem-aware risk/transition windows/
sequence planning) is largely built and honest by design (ADR-005: never
fabricate). The gaps for a credible demo are **workflow and control**, not
scoring: users cannot tell what to click, what analysis costs, where cache
goes, whether cancel is safe, how to force or ban tracks, why two runs give
identical playlists, and whether exported cues actually work in Rekordbox.

This build: a 10-step guided workflow with a strict state model; Quick vs
Deep(Overnight) analysis tiers with honest runtime estimates; incremental
re-use with checksum/version invalidation; a visible, bounded cache; safe
cooperative cancellation; Demucs formalized as a **Stem Separation Worker**
(not "the engine"); selected-stem export; a Rekordbox cue verification gate
plus an edge-level transition-cue model; relevance-preserving playlist
variation; a full DJ control layer (pins, Must Have, Overplayed); Apple
Silicon backend policy (M4 first); and a QC pipeline with release-blocking
hard rules.

Claim boundary (CONFIRMED REQUIREMENT): crowd response is never predicted.
`crowd_response_prediction_allowed = false` until a real crowd-response
dataset exists. Allowed copy: "Crowd response prediction blocked — no real
crowd-response dataset." Forbidden: any phrasing implying predicted crowd
reaction.

## 2. Product Diagnosis

Verified current state (this repo, 2026-07-11):

| Area | State | Evidence |
|---|---|---|
| Guided flow | 5-step wizard exists (Import→Analyze→Generate→Review→Export) with gating + per-track checklist + A/B review decks | `host/simple_mode.py`, `host/pair_review.py` |
| Analysis modes | Codex added `analysis_depth` combo; semantics not formalized | `simple_mode._config_for_analysis_depth` |
| Incremental reuse | Cache-by-track_id exists (`_load_or_analyze`), **no checksum, no version invalidation, no quick/deep tiering** | `workflows/smart_playlist.py` |
| Cache | **180 MB already inside the repo** at `data/processed/` (~0.25 MB/track), invisible to user, no limits | measured |
| Cancel | **No cancel at all** — `_AnalysisWorker` loop is uninterruptible; UI guard `if thread.isRunning(): return` blocks new runs. User-reported bug "cancel → select new folder → nothing happens" is this exact mechanism | `simple_mode.run_analysis` |
| Demucs | Installed; htdemucs cached (80 MB); runs `device="cpu"` hardcoded in 2 sites | `stems/extractor.py:133`, `features/vocals.py:96` |
| Hardware | M4 verified: torch 2.13, `mps.is_available()==True`, 4P+6E cores; **nothing uses MPS, nothing reports backend** | verified in venv |
| Rekordbox | **Export only** — writes hot cues 0–7; memory cues/loops are docstring fiction; **no XML import exists at all**; nothing verifies output | `export/rekordbox.py` |
| Uniqueness | Planner fully deterministic (AUD-M5) → identical playlist every run | `decision/set_builder.py` |
| Pin/lock | Engine + API complete (`pinned_track_ids`, `locked_positions`); **zero UI** | verified |
| Must Have / Overplayed | Do not exist anywhere | grep |
| Tags | mutagen now installed (was dead code) | fixed this session |

Core user problem: the engine outruns the product shell. Every failure the
user listed (where to start, what runs, what it costs, what cancel does,
why playlists repeat) is a shell/state-model gap, not an engine gap.

## 3. Architecture Decision: Engine vs Tool

PRODUCT DECISION — **Demucs is a Stem Separation Worker, a preprocessing
tool. It is not, and must never be labeled, "the engine."**

The engine already has the stem input contract this prompt asks for:
`stems/extractor.py::extract_stems(signal, track_id, config) → StemBundle
{channels: dict[StemType, AudioSignal], result: StemExtractionResult}` with
full `StemProvenance` (model name/variant/signature, config hash,
extraction status, fallback flags) and downstream consumers
(`stem_energy_ratio_per_frame`, `build_stem_window_features`, vocal density,
stem-aware risk). CONFIRMED REQUIREMENT: **no scoring-engine rewrite for
Demucs.** Work is integration tooling: worker lifecycle, cache, export, UI,
backend selection.

Canonical data flow (enforced wording in all UI/docs):

```
audio file
  → Stem Separation Worker (demucs backend | DSP fallback: HPSS + bass band)
  → stem cache                      (§8, cache class "stems")
  → stem feature extractor          (window features, energy ratios)
  → engine input adapter            (AnalysisResult fields + StemProvenance)
  → scoring / decision engine       (mixability, windows, set builder)
  → UI output / export
```

Engine changes in this build (small, additive): planner novelty penalties
(§14), TransitionCue model (§13), analysis-tier field on stored results
(§7). Everything else is tooling/shell.

## 4. Guided Workflow Model

PRODUCT DECISION — extend the existing 5-step wizard to the 10-step model.
Existing steps are reused, not rebuilt. Universal step states:
`locked / ready / active / running / complete / error / needs_review /
skipped / cached`. Sidebar stepper shows number, title, status icon, short
status, result count. The status bar always answers "what do I click now"
(pattern already shipped: `Next: …` hints).

| # | Step | Exists today | Work |
|---|---|---|---|
| 1 | New Project | partial (graph `.dlproj`; wizard has none) | bind wizard to project model: name, location, recent, saved-state, last-saved |
| 2 | Import Tracks / Rekordbox XML | audio folder/files + preflight ✓; **XML import missing**; analyzed-library source missing | add XML importer (§13), "Choose From Analyzed Library" source, duplicate + missing-path reporting |
| 3 | Choose Analysis Mode | combo exists, semantics undefined | formalize Quick/Deep (§6), estimates (§5) |
| 4 | Analyze Library | ✓ checklist w/ real stages | add pre-run estimate panel, Stop Processing (§9), cached/new split |
| 5 | Choose Current Track | engine has `select_track`; wizard doesn't | searchable analyzed list (BPM/key/status/tier) |
| 6 | Set DJ Intent | planner accepts context/prefs; **no UI** | Must Have (§16), Overplayed (§17), BPM range, key behavior, venue/hour/role/style, novelty, carryover — as DJ control panel, not settings form |
| 7 | Generate Mix Ideas | engine `recommend_next` complete w/ reasons+risks | surface candidates: edge score, transition type, `standard_blend_allowed`, positive/risk reasons, confidence, crowd-blocked notice. Never score alone |
| 8 | Review Transitions | ✓ A/B decks, structure, beat-sync, stems | add review verdicts: Accepted / Accepted-with-strategy / Rejected / Needs-manual-listen / Needs-annotation; verdicts persist and bind the planner (§15.8) |
| 9 | Build Set Sequence | ✓ planner + modes | show segments, bridges, rejected/review edges, accumulated risk, energy arc, pins/Must-Have/Overplayed markers |
| 10 | Export / Save | ✓ XML + project save | add JSON/report/pilot-CSV exports, stem export entry (§11), cue gate (§13) |

Each step ships with: purpose, required input, primary CTA, secondary
actions, empty/running/error states, completion summary, next-action line
(details per user's step text — adopted verbatim as CONFIRMED REQUIREMENT;
copy in §20).

HARD QC RULE: no step's primary CTA is enabled while its required input is
missing; the disabled CTA always names the missing input.

## 5. Analysis Runtime Model

Pre-run estimate panel (before Run Analysis is armed):

```
Mode: Deep Analysis            Backend: Apple Silicon (MPS) — calibrated
Tracks: 24 (6 new, 18 cached — reused, not reprocessed)
Total audio: 2h previously measured
Estimated time: 2h 40m – 3h 30m   ← observed-throughput based
Estimated cache: ~2.1 GB stems + ~6 MB analysis
Free disk: 42 GB ✓
Recommended: run overnight
```

PRODUCT DECISION — estimates come from **observed throughput, not
hardware theory**. `PerformanceCalibration` record per (backend, mode):
seconds-of-audio-per-second, updated after every job (EMA). First-ever run:
one 30 s calibration slice on the first track, marked "first-run estimate —
will improve". Estimate updates live when mode/backend/track-set changes.

TECHNICAL ASSUMPTION: throughput is stable enough per (machine, backend,
mode) for ±30 % estimates after one job. NEEDS VERIFICATION on user's M4
with a real library.

Running state (already shipped, kept): progress bar, per-track checklist
with **real pipeline stages** (Loading audio → Key detection → Beat
tracking → …, engine-emitted via `on_stage`, never simulated), processed
count, ETA from calibration, Stop Processing, collapsed details/log.
CONFIRMED REQUIREMENT: never a bare spinner.

Completion: summary line (`24/24 processed · 3 need review`) + optional
soft completion sound after Deep runs — short, subtle, vinyl/platter
character, off-by-default-able. OPEN QUESTION: sound asset source.

## 6. Quick Analysis vs Deep / Overnight Analysis

PRODUCT DECISION — two user modes mapping to engine config (builds on
Codex's `analysis_depth`):

| | Quick | Deep / Overnight |
|---|---|---|
| Stem worker | off (`stems.enabled=false`) | on (demucs; DSP fallback labeled) |
| Vocal proxy | HPSS | stem-derived |
| Descriptors | full standard set (cheap) | + stem window features, stem-aware harmonic risk |
| Beatgrid/key/onsets/segments/windows | yes | yes (identical code path) |
| Metadata/tags reuse | yes | yes |
| Cost (TECHNICAL ASSUMPTION, calibrate) | ~5–15 s/track CPU | dominated by separation: ~0.3–0.5× realtime CPU, target ≥2× faster on MPS (NEEDS VERIFICATION §18) |

Rules:
- Deep supersedes Quick per track; Quick never downgrades stored Deep data.
- A Deep-analyzed track is fully usable in Quick sessions (cache reuse).
- Steering copy (CONFIRMED REQUIREMENT): "Playing soon? Use Quick Analysis
  now. Run Deep Analysis overnight for better stem-aware results."
- If estimated Deep time > 45 min → inline "Best started overnight" banner
  + one-click "switch to Quick for now".
- Deep Analysis **never auto-exports stems** (§8/§11). Copy: "Deep Analysis
  prepares data for recommendations. It does not automatically export stem
  files."

## 7. Incremental Analyzed Library and Cache Reuse

CONFIRMED REQUIREMENT — a track is never reprocessed while its stored
analysis is valid.

Track states: `not_analyzed / quick_analyzed / deep_analyzed /
partially_analyzed / needs_reanalysis / failed / cached_ready`.

Stored per track (extends AnalysisResult + manifest): `source_checksum`
(xxhash64 of file bytes — TECHNICAL ASSUMPTION: fast enough to hash on
import; verify on network drives), `analysis_tier`, `engine_version`,
`DANCELAB_SCHEMA_VERSION` (exists), `formula_version` (weights file hash),
`analyzed_at`, `failure` record.

Re-analysis triggers (exhaustive): checksum changed · path changed AND
checksum unavailable · engine/schema/formula version changed ·
requested tier exceeds stored tier (Quick→Deep upgrade analyzes **only the
stem layer**, reusing base features — engine change, small) · previous run
failed · explicit user request.

Import-time reuse: importer matches by checksum first, path second. Match →
"18 tracks already analyzed and ready", state `cached_ready`, zero
processing. "Choose From Analyzed Library" source lets a playlist be built
with no import/analyze at all.

HARD QC RULE: two consecutive identical Deep runs on an unchanged library
perform **zero** track computations on the second run.

## 8. Cache and Storage Policy

CONFIRMED REQUIREMENT — no silent large writes; user sees, bounds, moves,
and clears everything.

PRODUCT DECISION — global cache root (per-machine), project-level manifest
views into it. Default `~/Library/Application Support/DanceLab/cache`
(macOS), user-relocatable. Layout:

```
DanceLab Cache/
  cache_manifest.json      # every entry: {class, key, path, bytes, source_hash,
                           #   engine_version, created_at, last_used_at, project_ids}
  analysis/                # AnalysisResult JSONs (~0.25 MB/track, measured)
  waveforms/               # strip envelopes (small)
  stems/                   # separation wavs (~40 MB per 5-min track / 4 stems)
  features/                # stem-derived feature caches
  temp/                    # in-flight only; startup scan deletes orphans
  models/                  # size REPORTED (demucs 80 MB in ~/.cache/torch);
                           #   deleted only by explicit user action
```

Projects (`*.dlproj` + wizard project) reference cache keys; **project
opens fine with missing cache** → affected tracks flip to
`needs_reanalysis`, UI offers "Reprocess missing features". Never a crash,
never a silent recompute.

Controls (Settings + File→Cache…): location (visible path, Move… with
copy-verify-swap, resumable), per-class usage bars, per-class Clear, max
cache limit (default 10 GB) with LRU eviction of `analysis/stems/features`
**never `exports/` or user files**, keep/delete-temp toggle, low-disk
floor (default 2 GB free) — below floor: stem jobs blocked, quick analysis
allowed with warning.

Pre-job copy: "Estimated cache for this job: ~8.4 GB · Available disk:
42 GB · Deep Analysis may create large temporary files."

Stem cache policy per §6: options — keep stem cache for faster future
analysis (default ON for Deep) · delete temporary stems after feature
extraction ("Temporary stems will be deleted after feature extraction.") ·
clear cache after export.

HARD QC RULES: no writes outside cache root + user-chosen export folders;
kill -9 mid-write leaves no manifest orphans after startup scan; eviction
never touches exports; missing cache → reprocess prompt, not crash.

## 9. Cancel / Stop Processing Behavior

Verified bug (CONFIRMED): there is no cancel; worker loop is
uninterruptible; `if thread.isRunning(): return` guard makes any subsequent
selection appear dead. This is the user-reported "cancel then nothing
happens".

PRODUCT DECISION — cooperative cancellation:
- `AnalysisJob` gains a `stop_requested` flag + `stop_mode`
  (`after_current | now`); `analyze_files` checks between tracks (already
  per-track structured); `now` additionally interrupts the demucs call
  boundary (TECHNICAL ASSUMPTION: demucs call itself is not interruptible
  mid-model; `now` = abandon current track, mark `pending`, discard partial
  temp files. NEEDS VERIFICATION whether torch MPS op cancellation is safe
  — until verified, `Stop Now` on a stem job = stop after current model
  chunk).
- Completed tracks are already committed to cache per-track (verified —
  `repo.save` per track) → nothing to lose on stop.
- After stop: queue cleared; processed stay `cached_ready`; unprocessed
  stay `pending`; UI returns to import/select state; **new folder selection
  always works** (guard replaced by state check on job object, not thread
  aliveness).

Wording (CONFIRMED REQUIREMENT — avoid over-repeating "analysis"):
button **Stop Processing**; modal title "Stop this job?"; body "DanceLab
will stop after the current track. Tracks already processed will be saved
and will not need to be processed again."; buttons Keep Running · Stop
After Current Track · Stop Now.

HARD QC RULE: after cancel, selecting new tracks/folders must always start
a new job. Regression test simulates cancel → new selection → run.

## 10. Demucs / Stem Separation Integration

Worker contract (`stems/` — mostly exists, formalized):

- **Inputs**: source path, track_id, EngineConfig (model variant, device
  §18), requested stems (default: all model sources).
- **Outputs**: `StemBundle` in-memory + cached wavs
  `cache/stems/<track_id>/<stem>.wav`, `StemExtractionResult` with
  provenance (model name/variant/signature, config hash, status, fallback,
  warnings) — exists.
- **File naming**: `<stem_type>.wav` under track_id dir; preview/export
  naming identical so caches are shared.
- **Failure modes**: model load failure → per-track failure record, batch
  continues; OOM → retry once on CPU backend (§18) then fail-with-reason;
  unreadable audio → failure record. Never aborts the whole batch
  (pattern exists in `analyze_files`).
- **Retry**: single automatic retry on transient failure; manual re-run
  from failure list otherwise. No infinite retries.
- **Model/version metadata**: recorded in provenance + export manifests
  (exists: `model_signature`, `config_hash`).
- **Adapter**: unchanged — `StemBundle` → window features/vocal density.
  Fallback visibility (HARD QC RULE): when worker falls back to full-mix,
  `source_status=fallback_full_mix` must survive pipeline→API→UI; decision
  output must never appear stem-backed when it is not.

## 11. Export Selected Tracks for Stem Separation

Flow (builds on existing `export_stems_for_paths`, which already writes
per-track folders + manifests): select tracks (default: current set plan)
→ Export Stem Separations → destination folder → stem checkboxes → format →
options → per-track progress checklist (same live-stage pattern) → report.

- Stem list generated from `model.sources` at runtime — vocals/drums/bass/
  other for htdemucs (verified); guitar/piano appear **only** with a
  6-source model selected. Never advertise stems the model lacks.
- Formats: WAV (default) · MP3 · FLAC. TECHNICAL ASSUMPTION: encode via
  soundfile/ffmpeg availability — NEEDS VERIFICATION which encoder ships;
  WAV is the guaranteed baseline.
- Options: one folder per track (default on) · include original metadata ·
  include manifest (default on) · skip existing / overwrite · keep stem
  cache · delete temporary full separation after export.
- CONFIRMED REQUIREMENT: model may need full internal separation even when
  user picks 2 stems; only requested stems are exported/kept unless "keep
  all stems in cache".

Manifest per track (contract):

```json
{
  "track_id": "…", "title": "…", "artist": "…",
  "source_audio_path": "…", "source_checksum": "…",
  "selected_stems": ["vocals", "drums"],
  "model": "htdemucs", "model_signature": "…",
  "output_format": "wav", "created_at": "…",
  "source_project": "…", "warnings": []
}
```

HARD QC RULES: only requested stems on disk; skip_existing leaves files
byte-stable; cancel mid-batch leaves completed folders valid + temp clean;
manifest exactly matches directory contents.

## 12. Large Sample Folder Handling

Builds on shipped preflight (<2 min flag). Add pack detection heuristics:
majority of files <30–60 s · folder name matches
`samples|loops|one[- ]?shots|drums|fx` · repetitive pack-style filenames ·
no full-track structure. Any strong signal → bulk decision screen instead
of per-file dialog:

"This folder appears to contain 1,042 short audio files. Most are shorter
than 45 seconds. How should DanceLab handle them?"

Actions: Reject all samples · Import only full-length tracks (default
suggestion when short-share >50 %) · Reject shorter than [X] s · Review
first 20 (paged) · Apply rule to this folder · Remember rule (persisted) ·
Ignore this folder in the future · Import as reference material (flagged,
excluded from set planning) · Move to separate bin · Review later.

CONFIRMED REQUIREMENT: suggest, never auto-delete/auto-reject without
confirmation; override always available.

HARD QC RULES: 1 000-sample folder → bulk screen, zero per-file clicks
required; triage is metadata-probe only (no decode), <2 s for 2 000 files;
remembered rules survive restart.

## 13. Rekordbox XML / Cue Verification

Verified: export writes hot cues 0–7 only; memory cues/loops unwritten;
**no importer exists**. Two workstreams:

**A. Importer** (`ingestion/rekordbox_import.py`, new): parse DJ_PLAYLISTS
XML → tracks (Location→path, resolving missing paths with report), hot
cues (Num 0–7), memory cues (Num −1), loops (Type 4 + End), labels/colors
when present (NEEDS SOURCE VERIFICATION: exact attribute semantics across
Rekordbox 6/7 exports — build the QC fixture library below and verify
against real exports before claiming support). Missing files listed, never
silently dropped.

**B. Verification Gate** (`export/rekordbox_verify.py`): re-parses every
*written* XML before "export succeeded": cue count ≤ slots, Num
range/uniqueness, legal Type values, `0 ≤ Start ≤ TotalTime`, order, hot vs
memory classification, loops only when loop data real, labels/colors
round-trip when written. Failure downgrades UI message to "XML written but
cue verification FAILED: …" — never silent green.

**Edge-level transition cue model** (engine change, `core/models.py`):

```json
{
  "edge_id": "trackA__trackB",
  "from_track_id": "track_a", "to_track_id": "track_b",
  "transition_type": "smooth_blend",
  "a_out_start_sec": 134.5, "b_in_start_sec": 72.5,
  "a_window_source": "dancelab_transition_window",
  "b_cue_source": "rekordbox_hotcue_A | dancelab_written_hotcue | window_only",
  "b_cue_num": 0,
  "mix_duration_beats": 32,
  "phrase_alignment": "aligned | unknown",
  "confidence": 0.82,
  "requires_manual_listen": false
}
```

HARD QC RULES: no edge claims "start Track B here" unless `b_cue_source ≠
window_only` AND the cue exists in verified XML with timestamp match
(±10 ms); `window_only` ⇒ `requires_manual_listen=true`;
`mix_duration_beats=null` (never fabricated) when either `BeatGrid.reliable`
is false; imported cue timestamps round-trip export→import bit-exact.

QC fixture library (CONFIRMED REQUIREMENT): real Rekordbox exports with
hot cues A–H, memory cues, loops, no cues, renamed cues, colored cues —
imported and field-compared.

## 14. Playlist Uniqueness and Controlled Repetition

Verified: planner is deterministic → identical playlist every run. Fix
without fake randomness. Principle: **maximize useful variation, not
randomness**; relevance first, diversity as soft penalties, seeded
tie-breaks last.

Mechanics (engine change, `decision/history.py` + planner params):
- History store `<cache_root>/history/playlists.jsonl` of fingerprints:

```json
{
  "playlist_id": "…",
  "track_ids_ordered": ["id1","id2"],
  "track_set_hash": "…", "ordered_sequence_hash": "…",
  "edge_hashes": ["…"],
  "opening_id": "…", "peak_id": "…", "closing_id": "…",
  "context_hash": "venue|hour|style|prefs|planner-settings",
  "created_at": "…", "engine_version": "…",
  "random_seed": "…", "novelty_mode": "balanced",
  "carryover_limit": 3,
  "pinned_ids": [], "locked_positions": {}
}
```

- Soft penalties (registered in `formula_terms.yaml` — no anonymous
  variables): `repeat_edge_penalty`, `repeat_slot_penalty` (opening/peak/
  closing vs same `context_hash`, per-slot configurable), `overuse_penalty`
  (track in > carryover_limit of last N playlists).
- **Hard rules stay hard**: penalties apply only inside the
  gate-passing candidate set; BPM/key/groove/risk gates never bend.
- **Seeded tie-breaking only**: when candidates score within ε=0.02
  (honest score resolution), seeded RNG picks. Same seed reproducible.
- Same-sequence guard: if result's `ordered_sequence_hash` equals the last
  entry for this `context_hash` → one re-run with next seed + bumped edge
  penalty; still identical (tiny library) → keep + warning "library too
  small to vary — identical set returned". Honesty over shuffle.
- Carryover: 2–3 repeats are normal DJ practice — allowance configurable
  0/1/2/3/5; Must Have and pinned tracks are **intentional carryover**,
  exempt from overuse penalties.

Modes: Conservative (low penalties, carryover 5) · Balanced (default,
carryover 3) · Fresh (high, carryover 1) · Deterministic (all off,
byte-stable) · Seeded variation (user seed) · Exploratory (high + ε=0.05,
carryover 0).

NEEDS SOURCE VERIFICATION (research task, before claiming method
pedigree): Maximal Marginal Relevance, diversity-aware recommendation,
Determinantal Point Processes, sequence diversity penalties. The shipped
mechanism (penalties + ε tie-break) stands on its own; literature labels
attach only after source review.

## 15. Track Pinning / Locking System

Engine has 1 & 2 today (`pinned_track_ids`, `locked_positions` — validated,
tested, zero UI). Full control set:

1. **Pin Anywhere** — must appear, engine places (exists).
2. **Pin to Position** — exact slot / opener / closer (exists via
   `locked_positions`); named slots opener=1, closer=len(set); "peak" =
   slot of energy-arc maximum (engine change: resolve symbolic slots).
3. **Pin Current Deck A** — recommendation start fixed (exists as
   `current_track_id` in recommend_next; wire to wizard Step 5).
4. **Pin Transition Pair A→B** — new planner constraint: edge preserved
   unless it violates a hard rule (then loud failure, never silent drop).
5. **Pin Segment A→B→C** — contiguous locked subsequence; planner builds
   around it (new; implement as consecutive locked positions once anchor
   slot chosen by engine).
6. **Pin Opener / Peak / Closer** — sugar over 2.
7. **Exclude Track** — per-generation ban (feeds §17 machinery).
8. **Protect Reviewed Decision** — Review verdicts (§4.8) bind: Rejected
   edge never reappears; Accepted-with-strategy keeps its strategy.
9. **Regenerate Only Unpinned Slots** — pins+locks+protected edges fixed;
   remainder re-planned (new planner entry point).
10. **Carryover Pins** — pinned repeats exempt from repetition penalties
    (§14).

HARD QC RULES: pinning is a constraint, not decoration — it overrides
novelty/diversity penalties but **never** hard rules (missing
transition_type, impossible BPM jump without strategy, unverified cue
claim, missing analysis, crowd-claim block). Risky pinned track is never
silently removed — UI: "This pinned track creates a transition risk" with
options: keep + reset/hard-cut/bridge strategy · move to safer slot ·
unpin · mark for manual review.

## 16. Must Have Tracks

Product label: **Must Have** (microcopy flourish: "I Can't Live Without
You"). Marked from analyzed library search (Step 6) or any track row.

Engine behavior: Must Have ⇒ `pinned_track_ids` (Pin Anywhere) + intent
metadata. Appears in every generated playlist unless a hard rule blocks —
then the §15 risk dialog, never silent drop. Overrides novelty/repetition
penalties; counts as intentional carryover; visually badged everywhere;
risks still shown honestly.

PRODUCT DECISION — limit **10**. Rationale: beyond ~10 forced tracks in a
10–20 track set, the optimizer has no degrees of freedom left; "everything
is essential" = nothing is optimizable. Copy at #11: "You have to make a
sacrifice. You can only have 10 Must Have tracks. Choose wisely."
(alt: "Even legends need limits. Remove one Must Have track before adding
another.")

Removal confirmation (playful, allowed — low-risk preference action):
track "speaks": **"Don't you love me?"** → buttons: Keep as Must Have ·
Remove from Must Have. Explicit note: removes the flag only, never the
audio file.

HARD QC RULES: cap enforced at 10 with the limit message; Must Have present
in output or risk-dialog raised; flag removal touches no files.

## 17. Overplayed / Not Tonight Tracks

Product label: **Overplayed / Not Tonight**. Copy: "I've played it too many
times." / "Keep this one out of tonight's set." / "Give this track a rest."

Modes per track: exclude from this playlist only · exclude 7 days ·
exclude 30 days · lower priority but allow if needed (soft penalty) ·
remove from list. Stored with timestamps in the project/intent store;
timed exclusions auto-expire.

Engine behavior: exclusion = removed from candidate pool pre-gates; "lower
priority" = soft penalty term (registered in formula_terms). Never deletes
or hides the file from the library.

Conflict rule (CONFIRMED REQUIREMENT): track both Must Have and Overplayed
→ explicit modal, no silent precedence: "This track is both Must Have and
Not Tonight. Which intention should DanceLab follow?" → Keep as Must Have ·
Keep out tonight · Remove both labels.

HARD QC RULES: excluded track absent from output unless explicit
override-mode allows; expiry restores automatically; conflict always
surfaces the modal.

## 18. Apple Silicon / Hardware Acceleration Policy

Verified on target machine: **Apple M4, 4P+6E cores, torch 2.13,
`torch.backends.mps.is_available() == True`** — and both demucs call sites
hardcode `device="cpu"` (`stems/extractor.py:133`,
`features/vocals.py:96`). M4 is the first optimization target.

PRODUCT DECISION — backend module `core/backend.py`:
- Detection report: CPU model, RAM, OS, Apple Silicon generation, MPS
  availability, CUDA availability (Win/Linux), selected backend, fallback
  state. Shown in the estimate panel and Settings.
- Selection: `preferred_torch_device()` → `mps` when available+enabled,
  else `cpu`. Both demucs sites take the device parameter. Env
  `PYTORCH_ENABLE_MPS_FALLBACK=1` set for op-fallback safety (TECHNICAL
  ASSUMPTION: htdemucs runs on MPS with occasional CPU op fallback —
  NEEDS VERIFICATION with an A/B QC run comparing output correctness and
  wall-clock vs CPU before "accelerated" label ships).
- Performance Mode: Auto (default) · Fast (MPS + all P-cores) · Battery
  Saver (CPU, ≤2 workers) · CPU only (debug/verification).
- Parallelism (CPU-bound librosa analysis): process pool across tracks,
  default workers = performance-core count (4 on M4); stem jobs stay
  serialized on one MPS queue (TECHNICAL ASSUMPTION: concurrent MPS demucs
  gives no win and risks memory pressure — verify).
- Honest labels (CONFIRMED REQUIREMENT): "Apple Silicon backend active" ·
  "Running on CPU — Deep Analysis may be slower" · "Backend unavailable,
  using CPU fallback". Never claim acceleration that is not active —
  the label reads from the *actual* device used by the last job, not the
  setting.
- Estimates use per-backend calibration (§5).

HARD QC RULES: CPU fallback produces identical decision outputs to MPS
(within float tolerance) — else MPS ships disabled; backend label matches
the device actually used; low-memory path degrades to CPU without crash;
long-batch (100+ tracks) stability run required before enabling MPS by
default.

## 19. UI State Model

Layout (Simple Mode, default): LEFT stepper (10 steps, status icons +
counts) · CENTER active-step workspace (title, description, required
input, primary CTA, secondary actions, running state, results, errors,
next-step line) · RIGHT context panel (what this step does, why, required
input, expected output, common mistakes, engine status, cache status, next
action) · TOP bar minimal: DanceLab Pro · project name · saved/unsaved ·
New/Open/Save · Run/Stop when relevant. Advanced Graph Mode hidden behind
"Open Advanced Graph Mode" (exists; keeps session handoff).

Step-state transitions:

```
locked → ready            (prerequisites met)
ready → active            (user enters step)
active → running          (primary CTA)
running → complete        (success)
running → error           (failure; retry preserves state)
running → ready           (Stop Processing; partials saved)
complete → needs_review   (items flagged)
any → cached              (results already available; step skippable)
ready → skipped           (optional steps: DJ Intent)
```

Global engine states (exists, extend): idle · waiting_for_input · ready ·
running · complete · error · needs_review — always paired with a "Next: …"
instruction.

HARD QC RULE: every state above is reachable and rendered in QC
walkthrough; no state renders without a next-action instruction.

## 20. User-Facing Copy Examples

Adopted verbatim (CONFIRMED REQUIREMENT): mode steering, overnight
recommendation, stop-modal, cache estimates, Deep-no-export line, sample
folder prompt, Must Have limit/removal, Overplayed lines, conflict modal,
crowd blocker — as given in the product brief and quoted in §5–§17.

Tone: professional dark pro-audio with sparse personality. Playful copy
**only** on low-risk preference actions (Must Have limit/removal, optional
completion sound). Never playful on destructive actions, data loss, failed
analysis, missing files, export errors. Renames shipped already: Run
Analysis, Extract Stems, Evaluate Context Fit, Pair Review Flow, Classify
Track Role (no Feed Engine / Extract Streams / Context Evaluate / Set
Function anywhere).

Claim-boundary strings (HARD QC RULE — exact): allowed "Crowd response
prediction blocked — no real crowd-response dataset."; forbidden any of
"Crowd will like this", "Predicted crowd response", "Dancefloor reaction
score". QC greps the UI string table for forbidden patterns.

## 21. Data Contracts / JSON Examples

Given in-line: cache manifest entry (§8), stem export manifest (§11),
TransitionCue (§13), PlaylistFingerprint (§14). Additional:

`TrackAnalysisState` (library/manifest):

```json
{
  "track_id": "…", "source_path": "…", "source_checksum": "xxh64:…",
  "state": "deep_analyzed",
  "analysis_tier": "deep", "engine_version": "0.1.0",
  "schema_version": "1.0.0", "formula_version": "sha1:…",
  "analyzed_at": "…", "failure": null,
  "cache_keys": {"analysis": "…", "stems": "…", "waveform": "…"}
}
```

`DJIntent` (Step 6):

```json
{
  "must_have_ids": ["…"], "overplayed": [{"track_id": "…", "mode": "days_7",
    "since": "…"}],
  "bpm_range": [122, 128], "key_behavior": "camelot_adjacent",
  "venue": "club", "hour": "01:00", "set_role": "peak",
  "style_focus": ["techno"], "novelty_mode": "balanced",
  "carryover_limit": 3, "seed": null
}
```

Mix-idea candidate (Step 7 — engine fields exist):

```json
{
  "track_id": "…", "title": "…", "artist": "…", "bpm": 126.0, "key": "8A",
  "edge_score": 0.82, "transition_type": "smooth_blend",
  "standard_blend_allowed": true,
  "positive_reasons": ["…"], "risk_reasons": ["…"],
  "confidence": 0.82,
  "crowd_response_prediction_allowed": false
}
```

## 22. QC Testing Pipeline

18 areas (per brief). Each suite defines happy path / empty / error / edge
cases / hard-fail rules / expected output / regression tests; all run in
standard pytest; each seeds its own tmp cache root.

| # | Suite | Key hard-fail (build-blocking) |
|---|---|---|
| 1 | Guided Workflow | no enabled CTA with missing input; every state renders with next-action |
| 2 | Project Save/Open | roundtrip restores full state; missing cache → reprocess prompt |
| 3 | Quick vs Deep | Deep never re-runs cached Deep tracks; Quick never downgrades Deep |
| 4 | Runtime Estimate | updates on mode/backend/track-set change; accounts for cached tracks; overnight banner threshold |
| 5 | Cancel/Stop | post-cancel new selection always works; processed tracks saved; queue never stuck |
| 6 | Incremental Reuse | unchanged library reruns = zero computations; checksum/version triggers work |
| 7 | Demucs Integration | fallback provenance survives to UI; worker-off decision outputs unchanged; manifest has model/version |
| 8 | Cache/Storage | no out-of-root writes; eviction spares exports; crash leaves no orphans |
| 9 | Large Sample Folder | 1 000 samples → bulk screen, zero forced per-file clicks; probe-only <2 s |
| 10 | Stem Export | requested-only on disk; safe filenames; manifest==directory; skip/overwrite honored |
| 11 | Rekordbox Cue | fixture library round-trips (hot/memory/loops/none/renamed/colored); no unverified B-start claims |
| 12 | Playlist Uniqueness | no identical consecutive sequence (except honest tiny-library warning); hard gates unviolated across 100 seeds |
| 13 | Track Pinning | all 10 pin modes; risky pin → dialog, never silent drop; regenerate-unpinned preserves pins |
| 14 | Must Have | cap 10 + message; presence or risk-dialog; no file deletion |
| 15 | Overplayed | exclusion honored; expiry restores; conflict modal forced |
| 16 | Hardware Backend | label==actual device; CPU fallback identical outputs; no false acceleration claims |
| 17 | Export | XML gate passes; JSON/report schemas valid; claim boundaries present in report |
| 18 | Regression | full prior suite (292 tests today) stays green; determinism mode byte-stable |

## 23. Hard Rules

Engine-enforced, non-overridable (consolidated):

1. No output without input — no tracks: Analyze disabled, "Import tracks
   first."
2. No Mix Ideas without analysis — "Run Quick Analysis or Deep Analysis
   first."
3. `standard_blend_allowed=false` ⇒ `transition_type ≠ smooth_blend`.
4. Large effective-BPM jump ⇒ transition_type ∈ {reset, hard_cut,
   tempo_ramp, bridge_transition, not_recommended}.
5. Risky harmonic relation ⇒ stem-aware risk explanation required.
6. Good tempo + good key + low groove similarity ⇒ edge is
   review_or_reject.
7. `crowd_response_prediction_allowed = false` — always, until real data.
8. No sequence passes with any missing `transition_type`.
9. Pins/Must Have never override rules 1–8 or 11.
10. Overplayed track absent unless explicit override mode allows.
11. No "start Track B here" claim without verified cue source + timestamp.
12. (ADR-005 house rule) No fabricated values anywhere: unknown → None +
    warning, unreliable → flagged, fallback → labeled.

## 24. Open Questions / Needs Verification

- NEEDS VERIFICATION: htdemucs on MPS — correctness (A/B vs CPU) and real
  speedup on M4; concurrent-MPS behavior; Stop-Now safety mid-model.
- NEEDS SOURCE VERIFICATION: Rekordbox XML attribute semantics for memory
  cues, loops, labels, colors across RB 6/7 — fixture library first.
- NEEDS SOURCE VERIFICATION: MMR / DPP / diversity-recommendation
  literature before labeling §14's method with those names.
- NEEDS VERIFICATION: checksum hashing cost on large/networked libraries;
  calibration-estimate accuracy (±30 % target) on the M4 with real tracks.
- OPEN QUESTION: completion-sound asset (license/source); FLAC/MP3 encoder
  availability for stem export.
- OPEN QUESTION: history retention (how many fingerprints; proposal: last
  50 per context_hash).
- OPEN QUESTION: symbolic "peak" slot definition when energy arc is flat.

## 25. Implementation Checklist

Dependency order (P = prerequisite of later items):

1. **Cache manager + manifest + relocation** (P for everything) — §8.
2. **Cancel/stop + job state machine** (fixes shipped bug) — §9.
3. **Incremental states + checksum/version invalidation** — §7.
4. **Backend module + MPS wiring + calibration estimates (M4 first)** —
   §18/§5.
5. **Quick/Deep formalization on Codex's depth combo** — §6.
6. **Uniqueness: history, penalties, seeded ε tie-break, modes** — §14.
7. **DJ control: pin modes 3–10 UI+planner, Must Have, Overplayed,
   conflict modal** — §15–§17.
8. **Wizard extension to 10 steps (current track, DJ intent, mix ideas,
   review verdicts)** — §4.
9. **Rekordbox importer + verification gate + TransitionCue** — §13.
10. **Stem export workflow surface** — §11.
11. **Bulk sample triage on preflight** — §12.
12. **QC suites 1–18** — written alongside each item, not after.

## 26. Release Gate

Build ships only when: all §22 hard-fail rules green · all §23 hard rules
covered by at least one test each · cancel-regression (bug §9) green ·
cache QC proves no out-of-root writes · cue gate green on the RB fixture
library · uniqueness QC green across 100 seeds · backend label honesty
test green on both CPU and MPS · full regression suite green.

---

**What must be implemented now:** checklist items 1–8 — cache, cancel,
incremental, M4 backend, Quick/Deep, uniqueness, DJ control layer, wizard
extension. These are demo-blocking and user-visible.

**What can wait:** Rekordbox *import* breadth (labels/colors), MP3/FLAC
stem encoding, pin-segment (mode 5) if planner work runs long, completion
sound, Exploratory mode tuning.

**What must be verified with real data:** MPS demucs correctness+speedup
on the M4; Rekordbox cue semantics via the fixture library; estimate
accuracy after calibration; uniqueness quality (score drop ≤0.03 vs
Deterministic) on a real 30+ track library; any recommender-literature
labels before public claims.

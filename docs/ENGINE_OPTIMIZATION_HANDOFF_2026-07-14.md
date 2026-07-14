# Engine Optimization And Handoff Checkpoint - 2026-07-14

## Executive Status

DanceLab is a working local Python/PySide6 product, not a Sprint 0 skeleton.
The supported desktop surface is Simple Mode. Its production path can import a
library, analyze audio, build a constrained set, review transitions, and export
Rekordbox XML. Engine decisions remain candidate models with explicit warnings
and provenance.

At this checkpoint:

- full test suite: **428 passed, 1 skipped, 7 warnings**;
- Ruff: clean;
- Python byte compilation: clean;
- installed dependency consistency: clean;
- real-audio analyze-to-export integration: passing;
- 240-record set planning is deterministic after optimization;
- no production formula, weight, gate, or tie-break rule changed in the
  optimization pass;
- final UI polishing is intentionally paused for product-owner input.

## Checkpoint History

| Commit | Meaning |
|---|---|
| `4120749` | Simple Mode and transition-validation checkpoint |
| `fc755c0` | real-audio end-to-end verification |
| `5948df0` | offline M11 transition validation |
| `36d73f9` | validated Raveform duration-prior artifact |
| `4ca7746` | tempo precision validation and refinement |

The optimization and handoff changes described here are the next checkpoint.

## Measured Optimization

### Problem

Profiling `build_set` over 240 real cached analyses showed that pair ranking
recomputed pair-invariant means for every candidate edge. A profiled no-context
run made about 3.6 million calls, including about 3.1 million repeated
attribute reads. With context, `track_context_score` was also recomputed for
the same track across many pairs.

### Change

`MixabilityPrecomputation` now exists only for one `build_set` invocation. It
computes the following once per candidate track:

- mean RMS;
- mean low-frequency energy ratio;
- mean vocal-density proxy;
- mean tension proxy;
- context score, only when a context profile is present.

Window-specific tension/release calculations remain pair/window-specific.
Nothing is persisted to analysis JSON or global state.

### Result

Seven timed runs were made after one warm-up with a 20-track target over all
240 valid JSON analyses in `data/processed/smart_playlist`.

| Scenario | Before median | After median | Improvement |
|---|---:|---:|---:|
| no context | about 0.249 s | 0.0786 s | about 3.2x |
| full context, no style prefilter | about 0.914 s | 0.1530 s | about 6.0x |

Every repeated post-change run returned the same serialized plan. A dedicated
unit test also compares the complete `MixabilityOutput` payload with and without
precomputation and requires exact equality.

## Safe Cleanup Performed

The following files were importable placeholders that had no callers and could
only raise `NotImplementedFeature`; they were removed rather than presented as
real architecture:

- `context/style_profile.py`;
- `decision/risk.py` (the active risk system is `decision/rules.py` plus edge
  and sequence risk handling);
- `descriptors/prediction_error.py`;
- `preprocessing/audio_preprocess.py`;
- `storage/database.py`;
- `visualization/plots.py`;
- `visualization/report.py`.

The unused placeholder functions `kick_alignment` and `masking_penalty` were
removed from `features/bass.py`. The active pipeline's bass/masking descriptors
remain intact.

This cleanup does not remove:

- JSON repositories, cache manager, manifests, or artifact storage;
- active decision reports or waveform galleries;
- transition and sequence risk logic;
- beatgrid, segmentation, Demucs, or deep analysis;
- the tested headless node-host contract and runtime adapters.

## Architecture To Preserve

```text
PySide6 Simple Mode --------+
CLI / FastAPI --------------+--> workflows --> engine layers --> JSON/export
project/cache I/O -----------+                         |
                                                       v
                                             offline validation only
```

Important boundaries:

1. UI orchestrates; it does not own mathematical scoring formulas.
2. Production engine modules do not import PySide6, FastAPI, Typer, or
   validation packages.
3. Validation reads evidence and writes reports; it does not silently tune
   weights or mutate cached analyses.
4. Preview beat-sync/quantize state is transient and is not exported as track
   BPM or a Rekordbox tempo grid.
5. Deferred ideas are documentation, not fake-ready runtime functions.

See `docs/architecture.md` for the current layer map and
`docs/architecture/diagnostic-boundary.md` for diagnostic contracts.

## Validation And Scientific Boundaries

### Tempo And Beatgrid

The 142-track exact-path operational benchmark reports:

- raw median BPM error: 0.386%;
- raw p90 BPM error: 1.204%;
- refined median BPM error: 0.013%;
- refined p90 BPM error: 0.051%.

Twelve metric-level errors above 2% remain. No arbitrary ratio correction was
added for them. Downbeat phase remains insufficiently validated: 73/142 first
tracked beats align with reference beat 1, and only 11/142 tracks have p90 grid
phase error at or below 0.05 beat. `BeatGrid.downbeat_phase_verified` therefore
stays false and Rekordbox TEMPO export stays disabled by default.

### M11 DJ-Mix Alignment

The M11 package is an offline measurement add-on for mix-to-track alignment,
boundary confidence, and cue evidence. Its confidence is diagnostic, not a
calibrated probability and not a production ranking term.

### Raveform

The deterministic artifact uses 24,558 adjacent transitions from 4,911 mixes.
Genre conditioning improves held-out negative log-likelihood from 1.70125 to
1.66449. Section-pair conditioning is rejected because usable section coverage
is only 1.7143%. The artifact remains explicitly marked
`eligible_for_engine_influence=false` until a production-facing evaluation is
approved. See `docs/RAVEFORM_PRIORS.md`.

## Data And Storage Snapshot

- Python source: 33,522 lines under `src/dancelab` at audit time.
- `src/`: about 3.5 MB.
- `tests/`: about 2.5 MB.
- `docs/`: about 204 KB before this report.
- working `data/`: about 266 MB.
- tracked files under `data/`: 44,497,339 bytes.
- current 240-track processed cache: about 61 MB.

Two design-system ZIP files and `tmp/` are untracked user/research material and
were deliberately not modified or committed.

## Known Technical Debt

### High Priority

- `host/simple_mode.py` is about 3,500 lines. Split by screen only after adding
  characterization tests around navigation and project-state transitions.
- `validation/review_ui/swipe_review.py` is about 3,400 lines of legacy HTML
  generation. Keep it isolated; do not merge it into the product host.
- Beatgrid/downbeat evidence is not yet strong enough for Rekordbox grid export.
- The Raveform prior is useful evidence but not yet a calibrated production
  preference model.

### Medium Priority

- `contracts/node_host.py` is a large declarative registry. It is not loaded by
  Simple Mode startup; refactor it only for a concrete integration consumer.
- `decision/sequence.py` and `decision/set_builder.py` have complex planner
  functions. Freeze golden outputs before extraction.
- The macOS editable install may require `PYTHONPATH=src` because of the known
  hidden `.pth`/provenance environment issue.

### Expected Test Noise

- Five warnings originate from librosa/audioread fallback and Python 3.13-bound
  audio modules in a synthetic USB-import test.
- Two warnings are expected short-signal `n_fft` warnings in a synthetic
  parallel-analysis test.
- The slowest test is the documented MPS A/B divergence gate at about 5.1 s.

## Verification Commands

Run from the repository root:

```bash
PYTHONPATH=src ./.venv/bin/pytest --durations=15
./.venv/bin/ruff check src tests
./.venv/bin/python -m compileall -q src tests
./.venv/bin/python -m pip check
```

Expected checkpoint result:

```text
428 passed, 1 skipped, 7 warnings
All checks passed!
No broken requirements found.
```

## First 60 Minutes For The Next Developer

1. Read `README.md`, this file, `docs/architecture.md`, and
   `docs/formulas.md`.
2. Run the four verification commands above before editing anything.
3. Launch Simple Mode with
   `PYTHONPATH=src ./.venv/bin/dancelab-host`.
4. Run the existing real-audio integration test and inspect one generated
   Rekordbox XML before changing export code.
5. Treat `data/processed` and `data/reports` as derived artifacts, not source
   code.
6. Do not enable Raveform influence, downbeat export, or automatic BPM export
   without a new explicit validation gate.
7. Ask the product owner for the pending UI-polish direction before changing
   Simple Mode visual hierarchy.

## Deliberately Deferred

- final Simple Mode UI polish: waiting for product-owner input;
- DDJ-FLX4 control capture: a separate future application, no code in this
  engine;
- SQL/PostgreSQL storage: no current product need;
- prediction-error and learned style profiles: research ideas without a valid
  production implementation;
- visual node editor: deprecated product surface; headless compatibility
  contracts remain.

## Audit Method

The optimization was selected from measurements, not intuition. Python's
official profiling documentation distinguishes profiling from benchmarking and
recommends `cProfile` for most users; cumulative time was used to locate the
algorithm-level repetition:

- https://docs.python.org/3/library/profile.html
- https://docs.python.org/3/library/tracemalloc.html

Static checks were treated as evidence, not an automatic deletion command.
Vulture explicitly documents false positives and confidence levels for dynamic
Python code. Only symbols with no source/test/docs callers and placeholder-only
behavior were removed:

- https://github.com/jendrikseipp/vulture
- https://docs.astral.sh/ruff/linter/

The handoff favors correctness and maintainability over speculative cleanup, in
line with Google's published code-review standard:

- https://google.github.io/eng-practices/review/reviewer/standard.html

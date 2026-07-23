# Corpus Save, Safe Stop, and Feature Cache Protocol

Status: accepted checkpoint protocol; cache implementation is gated and not active.

## Decision

The currently running full-DTW corpus batch remains on the canonical legacy
path. It must not be interrupted to introduce a feature cache. Measurements on
2026-07-16 show that first-pass cache reuse is too small to justify that risk:

- current downloaded corpus: 11,555 track occurrences, 10,634 unique IDs,
  7.97% theoretical global feature-cache hit ceiling;
- complete 1,857-mix queue: 31,007 occurrences, 27,212 unique IDs, 12.24% hit
  ceiling;
- projected first-pass saving at a 10-30% source-feature runtime share:
  26-79 minutes over approximately 35.7 wall-clock hours at three workers;
- completed atomic reports already preserve 14.83 worker-hours, approximately
  4.94 wall-clock hours at three workers, across a restart.

The feature cache is therefore a rerun optimization, not a reason to stop the
current first pass. It may become valuable during repeated equation, scoring,
or validation experiments, where decoded beat-synchronous features remain
unchanged.

## Save Slot

`scripts/corpus_save.py` creates an incremental save slot without copying audio:

```bash
./.venv/bin/python scripts/corpus_save.py save \
  --label before-feature-cache \
  --engine-mode legacy \
  --pipeline-command "PYTHONPATH=src ./.venv/bin/python scripts/corpus_align.py --root /Volumes/MY_PC/DanceLabCorpus --workers 3 --min-tracks 4"
```

Each slot contains:

- a compressed snapshot of `src/`, `scripts/`, `tests/`, configuration, and
  package metadata, including untracked pipeline code;
- Git commit, branch, status, staged and unstaged patches, and untracked paths;
- hashes of the corpus dataset and downloader manifest;
- the exact list of completed reports at the save boundary;
- a separate list of in-flight `.json.tmp` files, which are never considered
  complete;
- SHA-256 and byte-size verification for every save artifact.

Verify a slot before relying on it:

```bash
./.venv/bin/python scripts/corpus_save.py verify data/checkpoints/corpus/<slot>
```

A slot is immutable by convention. Creating another save never modifies an
older one and never duplicates the source audio. This is the corpus equivalent
of an incremental Save As operation.

## Safety Key

The existing implementation is named `legacy` and remains canonical. The
future cache must be opt-in behind one explicit mode boundary:

```text
DANCELAB_CORPUS_ENGINE_MODE=legacy          # bypass cache completely
DANCELAB_CORPUS_ENGINE_MODE=cache-experiment
```

Until the A/B gate passes, an absent variable means `legacy`. Cache corruption,
schema mismatch, memory pressure, or a failed read must fall back to recomputing
features; it must never alter source audio or promote a partial report.

The cache key must include at least:

```text
audio SHA-256 + sample rate + feature names + beatgrid configuration
+ feature/formula code version + cache schema version
```

RAM is a bounded LRU front tier. Disk is the durable content-addressed tier.
macOS memory pressure overrides the target size, and at least 10% of physical
RAM remains outside the cache. DTW matrices stay transient; persisting them is
not part of this optimization.

## Safe Stop Contract

The current active batch does not yet implement a safe-stop request and must not
be sent a stop marker. Its atomic reports make a crash resumable, but force-
killing a worker can discard that worker's current mix.

After the active batch reaches a natural checkpoint, the coordinator may be
upgraded with this contract:

1. Keep at most `workers` mix jobs in flight instead of submitting the full
   queue at once.
2. A stop request prevents scheduling another mix.
3. Existing workers finish their current mixes and atomically promote their
   `.json.tmp` reports.
4. The coordinator creates a verified save slot.
5. The coordinator exits successfully and prints the restart command.
6. An emergency force stop remains separate and is never labelled safe.

This is a hard pipeline stop at safe mix boundaries, not an OS-level hard kill.

## A/B Activation Gate

Run after the current batch, on a frozen representative set containing short,
long, unique, and repeated tracks:

1. Save a verified `legacy` slot.
2. Run a cold legacy benchmark.
3. Run a cold cache benchmark and then a warm cache benchmark.
4. Compare every output except timing and cache telemetry: identities,
   beatgrids, alignment costs and paths, cue candidates, and transitions must be
   identical.
5. Confirm no cache run crosses the memory reserve, grows swap materially, or
   crashes a worker.
6. Activate cache mode only if the warm benchmark saves at least 10% wall time
   or at least two projected hours per full rerun.

If any correctness or resource gate fails, keep `legacy`, retain the failed
experiment for diagnosis, and restore code only into a separate review
directory from `source_snapshot.tar.gz`; never overwrite the working tree
blindly.

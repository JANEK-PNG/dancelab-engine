# Handoff: Klaris → Kord, 2026-07-17

Branch **`calibration/same-octave-preference`** (3 commits, NOT merged to main).
First measured engine weights from the frozen DJ-mix corpus + Janek's ratings.

## New commits

```
b68a191 Add whole-set coherence report (arc adherence + tempo continuity)
050e1f2 De-duplicate byte-identical audio in build_set
61713cd Favour same tempo octave in bpm_score (first corpus-calibrated weight)
```

## What changed in the engine (things you can step on)

1. **`bpm_score` now prefers the same tempo octave.** New module constant
   `set_builder.SAME_OCTAVE_PREFERENCE = 0.9`: octave-equivalent matches
   (e.g. 90↔180) now score `base * 0.1`, not full. Grounded in corpus (DJs keep
   one octave 99.1%, n=6142) + calibrated on Janek's 35 ratings (rho 0.30→0.34).
   → any test/logic assuming 140↔70 scores 1.0 must expect ~0.1 now.

2. **`build_set` de-dups byte-identical audio.** New `decision/dedup.py`
   `dedupe_by_audio(analyses) -> (unique, warnings)` (blake2b file bytes; exact
   duplicates only, zero false positives; missing files never merged). Effect:
   a set can now be SHORTER than the input if duplicates exist; a warning
   "removed N duplicate audio file(s) (same bytes): dup→kept" appears in
   `SetPlan.warnings`. Closes Janek's "dwa te same utwory".
   → **TEST FIXTURE RULE (new):** multi-track fixtures must write BYTE-DISTINCT
   bytes per file, else dedup collapses them and counts drop. Fixed in
   test_host_simple_mode.py + test_smart_playlist_workflow.py (per-path content).

3. **`SetPlan.set_coherence: SetCoherence | None`** (new model in
   `core/models.py`: overall, arc_adherence, tempo_continuity, note).
   Computed by `set_builder.compute_set_coherence(...)`. Whole-set shape as one
   number. **Report only — does NOT change ranking.** Free for the UI to show
   ("this set: arc 0.84, tempo 0.92"). This is the set-level "does it hang
   together" signal, distinct from pairwise transition scores.

## State / do-not-touch

- **Corpus is FROZEN** (~163 GB on `/Volumes/MY_PC/DanceLabCorpus`, 801 aligned
  mixes, 23644 transitions). Downloader + aligner stopped on purpose (YouTube
  bot-block + "we have enough"). Do not restart. See docs/CORPUS_RUNBOOK.md.
- Prediction verdicts + calibration record: docs/corpus_predictions.md.
- Positive-framing rule: name mechanisms by what they FAVOUR, never "penalty".
- Full test suite green (1 skip) on this branch.

## Not done (next, if you pick it up — coordinate with Janek first)

- 5-rater validation study prep: ranking metric with decoys from INDEPENDENT
  metadata (not our audio pipeline — avoids circularity).
- Texture / energy-arc as actual ranking SIGNALS (coherence is only a report).
- Backlog: docs/CORPUS_V2_BACKLOG.md (transition reverse-engineering; 2022-26
  via 1001Tracklists). Art: docs/PRZEJSCIA_ART_PROJECT.md.

## Uncommitted in tree (separate concerns, not mine to commit)

Your corpus checkpoint/save work (validation/djmix/checkpoint.py,
scripts/corpus_save.py, docs/CORPUS_SAVE_AND_CACHE_PROTOCOL.md), my corpus
scripts (scripts/corpus_*.py) and docs, design zips, tmp/, outputs/. Left
untouched — commit under your own logical units.

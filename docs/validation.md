# Validation (from Validation Plan + Validation and Dataset Roadmap)

Goal: turn candidate models into testable hypotheses. v0 is a
**research-grade implementation**, not final production AI.

## Order of work

1. Pilot dataset: 20–30 tracks (Sprint 0), grow toward v0 minimum (100 tracks,
   300 mixability pairs — see dataset plan).
2. Compute basic features; compare against reference libraries
   (librosa/madmom/mir_eval) and public MIR benchmarks (beat, onset, segmentation,
   key/tempo, vocal activity).
3. Compare descriptors against manual annotations (DJ + listener ratings:
   groove, tension/release, transition windows, mixability pairs, set function).
4. Tune formulas and weights (`configs/descriptor_weights.yaml`, versioned).
5. Only then move to ML.

## Outputs per validation round

- agreement metrics vs human ratings,
- error cases catalog,
- improvement list,
- versioned experiment results (weights version ↔ results version).

For pair-level pilot review, `dancelab decision-report` now emits:

- `edge_decision_review.csv` for fast DJ review / comments,
- `edge_decision_payloads.jsonl` for batch validation and experiment logging.

For the current analyzed corpus, `dancelab validation-pack` now emits:

- filtered review sheets for the active processed subset,
- a coverage summary showing what is and is not labeled yet,
- metrics only where DJ labels already exist,
- a Markdown + JSON report that stays honest about partial completion,
- a `swipe_review/` bundle with small, card-based review decks for pairs,
  transition windows, and set function.

Example:

```bash
dancelab validation-pack data/phase2_refresh_lekcja5/processed \
  --output-dir data/reports/validation_pack_lekcja5 \
  --annotations-dir data/annotations \
  --report-dir data/reports/phase2_refresh_lekcja5
```

## Annotation sheet per track (Real Data Sources plan)

style, BPM, 3–8 segments, 1–3 best transition windows, groove rating,
tension rating, release rating, set-function label.

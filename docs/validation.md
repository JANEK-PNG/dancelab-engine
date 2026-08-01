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

## DJ benchmark before tuning

Do not tune pair weights from a single listening pass. A single CSV is a useful
bug report, but it is not enough evidence to change the engine.

Minimum benchmark gate:

- 5 independent transition-rating sessions,
- at least 30 rated transitions per session,
- comments encouraged for ratings 1–2 and surprising 5s,
- one session may be open review, but at least one should use blind rating mode,
- export every session as `*_transition_ratings.csv`.

Keep these user-authored files outside the engine cache, for example:

```bash
data/annotations/dj_sessions/
```

After each pass, aggregate the benchmark:

```bash
dancelab validation-benchmark
```

or point it at explicit files/directories:

```bash
dancelab validation-benchmark \
  "/path/to/Janek_transition_ratings.csv" \
  "/path/to/another_validation_folder"
```

The report is written to `data/reports/dj_benchmark/` and stays deliberately
diagnostic: it reports correlations, rating distribution, issue topics, repeated
pairs, and high-confidence false positives. Tuning should begin only when the
report says `READY FOR TUNING`.

Recommended 5-pass design:

1. Calm / UK bass / <=135 BPM continuation set.
2. Similar BPM preference set.
3. Similar key / harmonic preference set.
4. Style-constrained set with artist and album diversity pressure.
5. Blind review pass over mixed-confidence transitions.

For pair-level pilot review, `dancelab decision-report` now emits:

- `edge_decision_review.csv` for fast DJ review / comments,
- `edge_decision_payloads.jsonl` for batch validation and experiment logging.

For the current analyzed corpus, `dancelab validation-pack` now emits:

- filtered review sheets for the active processed subset,
- a coverage summary showing what is and is not labeled yet,
- metrics only where DJ labels already exist,
- a Markdown + JSON report that stays honest about partial completion.

The command is headless. Review sheets are ordinary CSV files that can be
opened in a spreadsheet editor, annotated, and passed back into the next
validation round.

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

# Corpus Ordering Dataset v1

Status: immutable real-corpus ordering snapshot built and verified; the
learned five-model evaluation is blocked on missing feature evidence, not
failed.

This work turns the aligned DJ-mix corpus into a leakage-resistant experiment
about track ordering. It does not tune or modify the DanceLab production
planner.

## The question this dataset can answer

The corpus shows tracks that appeared in a performed mix and their observed
order. It can therefore estimate:

```text
P(next track | tracks observed in this run, performed history)
```

It cannot identify:

```text
P(track selected | every track the DJ could have played)
```

The DJ's complete library, rejected candidates, intent and venue constraints
are unknown. Results describe ordering inside an observed crate. They are not
causal proof of why a DJ selected a track.

## Dataset construction

Implementation:

- `src/dancelab/validation/djmix/ordering.py`
- `tests/test_djmix_ordering.py`

The builder reads the frozen corpus metadata and per-mix alignment reports. It
does not write to the corpus.

For each mix it:

1. Requires an explicit catalogue ID and audio-content ID.
2. Requires a matched alignment, finite normalized cost and configurable
   minimum match rate.
3. Requires a reliable track beatgrid by default.
4. Breaks the sequence at missing, rejected or duplicate audio. It never
   connects tracks across an evidence gap.
5. Emits observations only from contiguous runs of at least three tracks.
6. Uses the already played tracks as history and the remaining tracks in that
   run as the choice set.
7. Sorts candidate IDs canonically, so candidate-array position cannot reveal
   the answer.
8. Excludes the final one-candidate choice because it carries no ranking
   information.
9. Stores source hashes, rejection counts, configuration and a deterministic
   dataset fingerprint.

DJ identity may come only from a separately supplied trusted mapping. Titles
and filenames are never parsed to invent an identity.

Genre labels follow the same fail-closed policy. They are accepted only from
the explicit `genres` field in the source schema. The general MixesDB `tags`
bag may also contain DJs, venues, events and radio shows, so it is never
silently reclassified as genre evidence.

## Feature evidence

Implementation:

- `src/dancelab/validation/djmix/ordering_features.py`
- `tests/test_djmix_ordering_features.py`

### H: handcrafted DanceLab descriptors

`H` is deterministically derived from existing `AnalysisResult` files:

- BPM and duration;
- circular Camelot position, mode and key confidence;
- mean, standard deviation, 10th percentile, 90th percentile and missing
  fraction for implemented frame descriptors;
- segment count and structural-duration fractions.

The core measurements `rms`, `spectral_flux`, `low_freq_energy_ratio`,
`onset_density` and `bass_energy` must be complete. Candidate measurements
such as pulse clarity, syncopation, tension, release and vocal density carry an
explicit missing-fraction feature. The builder never uses full-dataset median
imputation.

The analysis index explicitly maps corpus catalogue IDs to relative
`AnalysisResult` paths. Absolute paths and traversal outside the analysis root
are rejected.

### E: frozen learned-audio embeddings

`E` must be supplied as precomputed vectors from one pinned, frozen model. Its
manifest requires:

- model name and version;
- model source and license;
- lowercase SHA-256;
- `frozen: true`;
- finite, non-zero vectors of one dimension.

The preparation command does not download or execute a model. MFCC, chroma,
DTW costs and match rates from corpus alignment are not accepted under the
name "learned embedding".

### Trusted DJ mapping

The mapping has a separate schema and provenance. Every mix in the evaluation
universe must have a trusted DJ ID. Partial feature or identity coverage blocks
the five-model comparison rather than silently selecting an easier subset.

## Five models

Implementation:

- `src/dancelab/validation/djmix/ordering_models.py`
- `tests/test_djmix_ordering_models.py`

All models use the exact same held-out observations and candidate sets:

```text
L0    expected loss of uniform random choice
LH    handcrafted descriptors
LE    frozen learned-audio embeddings
LHE   handcrafted + embedding features
LHEI  LHE + regularized DJ-specific feature interactions
```

For observation `t`, candidate `j` and risk set `R_t`, the fitted models use a
conditional logit:

```text
s_tj = beta^T x_tj
P(y_t = j | R_t) = exp(s_tj) / sum(k in R_t) exp(s_tk)
NLL = -sum(t) log P(y_t | R_t)
```

`x_tj` contains candidate descriptors plus differences to the current track
and performed-history mean. The embedding block uses cosine similarities and
negative Euclidean distances to the same two references.

`LHEI` adds a regularized DJ-specific weight vector. For a DJ absent from
training it falls back to global `LHE` weights; it never fabricates an
identity.

Whole mixes, not transitions, are assigned to deterministic 70/15/15
train/validation/test partitions. This prevents transitions from one mix from
leaking across partitions. Every loss carries one evaluation hash covering the
dataset, features, test observations and split. The decomposition refuses
mismatched hashes.

The decomposition is defined in
`docs/DJ_SET_RULE_DECOMPOSITION.md`.

## Command sequence

The editable-install issue `ENV-1` still requires `PYTHONPATH=src` in the
current shell.

Build the fail-closed readiness report and exact handcrafted-analysis queue
before running any expensive work:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering gate \
  /Volumes/MY_PC/DanceLabCorpus \
  --expect-dataset dac3ef5dc7735b613994d61e311d6aa63ea33d016ebdebdd434f4793031ce9b1 \
  --output data/reports/corpus_ordering/model_gate.json \
  --queue-output data/reports/corpus_ordering/h_analysis_queue.json \
  --report-only
```

The gate:

- rebuilds and fingerprints the immutable ordering universe;
- resolves every required catalogue track ID to exactly one local source file;
- ignores AppleDouble sidecars and rejects symlinks, missing files and
  ambiguous duplicate paths;
- validates existing `H`, frozen `E` and trusted `DJ` evidence independently;
- writes an all-or-nothing `H` queue without downloading, transcoding,
  analyzing or mutating audio;
- exits with code 2 under `--strict` whenever the five-model experiment is not
  ready.

Prepare a complete source-backed feature catalogue:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering prepare-features \
  /path/to/analysis-results \
  --analysis-index /path/to/analysis-index.json \
  --embeddings /path/to/frozen-embeddings.json \
  --dj-map /path/to/trusted-dj-map.json \
  --output data/reports/corpus_ordering/features.json
```

Build the immutable ordering snapshot:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering build \
  /Volumes/MY_PC/DanceLabCorpus \
  --features data/reports/corpus_ordering/features.json \
  --output data/reports/corpus_ordering/dataset.json
```

Run the readiness gate:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering check \
  /Volumes/MY_PC/DanceLabCorpus \
  --features data/reports/corpus_ordering/features.json
```

Run all five models only after `check` reports `READY`:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering evaluate \
  /Volumes/MY_PC/DanceLabCorpus \
  --features data/reports/corpus_ordering/features.json \
  --output data/reports/corpus_ordering/five_model_report.json
```

## Current checkpoint

Completed:

- leakage-safe dataset builder and audit;
- deterministic feature contracts and provenance;
- five-model conditional-logit ladder;
- whole-mix splitting and shared evaluation hash;
- known/unseen DJ behavior;
- decomposition report;
- unit, integration, lint and security checks.
- mounted corpus frozen at metadata SHA-256
  `5f585a1a0f3a28ffa029afb19fc7b2bd0a5f0075485807f5b792779c6aec6b44`;
- 801 completed alignment reports, zero in-flight reports and zero error
  reports;
- 1,604 ordering observations from 709 contiguous runs in 433 mixes;
- 2,881 unique tracks required by the immutable choice universe;
- deterministic dataset fingerprint
  `dac3ef5dc7735b613994d61e311d6aa63ea33d016ebdebdd434f4793031ce9b1`;
- persisted fail-closed model-gate report:
  `data/reports/corpus_ordering/model_gate.json`, gate fingerprint
  `210d927531773a00706c076c68a42104eaa62c2f6912b736ba13de1d3bce29c2`;
- persisted deterministic `H` queue:
  `data/reports/corpus_ordering/h_analysis_queue.json`, queue fingerprint
  `05cc91a8cf32f97ec1f22c7603cc63c9acfd5ec0dd4b1a9e937ecdcf192b3b31`;
- source-audio preflight resolved 2,881/2,881 required catalogue IDs
  with zero missing and zero ambiguous paths; 12,672 AppleDouble sidecars
  were ignored;
- byte-identical output from independent rebuilds;
- deterministic whole-mix split: 303/65/65 mixes and 1,125/243/236
  train/validation/test observations;
- held-out uniform baseline `L0`: mean NLL 1.0898, expected top-1 36.53% and
  expected MRR 0.6225.

Current real-run blockers:

1. The 2,881 required tracks do not yet have complete indexed DanceLab
   `AnalysisResult` coverage for `H`. Every required catalogue ID resolves to
   exactly one source file, but the frozen sources are 2,573 `.webm` files and
   308 `.m4a` files. The production loader does not currently declare those
   formats, so the generated `H` queue correctly remains blocked rather than
   silently omitting or relabeling them.
2. The repository has no approved frozen learned-audio embedding extractor,
   local model weights or precomputed embedding catalogue for `E`.
3. The legacy corpus manifest has no explicit DJ identity field. The raw
   MixesDB tag order is not treated as a trusted identity mapping.
4. The legacy manifest also lacks the explicit `genres` field in the newer
   Raveform schema, so genre-stratified conclusions remain blocked even though
   aggregate ordering observations are valid.

The engine does contain rich handcrafted features, MFCC/chroma alignment and
Demucs separation. None of these is relabeled as a learned similarity
embedding. No model will be downloaded without a separate explicit decision.

A read-only smoke probe confirmed that the current local Librosa/Audioread and
FFmpeg installation can decode one representative `.webm` and one
representative `.m4a` file. That is useful implementation evidence, but it is
not promoted to a corpus-wide decoder contract. The next bounded `H` step is a
versioned validation-only decoder adapter with explicit provenance and
regression tests; the source corpus must remain untouched.

## Promotion gates

Before any learned result can influence the production planner:

1. Freeze the exact corpus, analysis, embedding model and DJ mapping hashes.
2. Pre-register evaluation metrics and acceptance thresholds before looking
   at held-out test results.
3. Confirm 100% H/E/DJ coverage for the immutable evaluation universe.
4. Confirm all five losses share one evaluation hash.
5. Report total and mean NLL, expected-random baseline, top-1, MRR and
   known/unseen-DJ counts.
6. Refit all five models in whole-set bootstrap replicates for uncertainty.
7. Check style and BPM strata instead of trusting only one aggregate.
8. Replicate on a second frozen split or corpus.
9. Keep a result that fails to generalize as evidence; do not tune against the
   held-out test set.
10. Integrate only a bounded, versioned inference artifact after review.

Until these gates pass, this package remains a measurement add-on. It does not
change set ordering, mixability, hot cues, BPM, beatgrid or Rekordbox export.

## Revealed-repertoire extension

The separately gated historical-pool proxy is documented in
`docs/REVEALED_REPERTOIRE_V1.md`. It uses only reviewed earlier solo sets by
the same DJ, labels historical non-selected tracks as unlabelled rather than
negative, and remains outside production runtime.

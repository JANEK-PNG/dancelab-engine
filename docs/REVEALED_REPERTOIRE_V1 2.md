# Revealed Repertoire v1

Status: offline fail-closed validation gate. It does not tune or modify the
DanceLab production engine.

## What this adds

The original ordering experiment can measure:

```text
P(next track | tracks observed in one performed run, performed history)
```

It cannot measure selection from a DJ's complete library because the real
event crate and rejected candidates are not observed.

`revealed-repertoire-v1` adds a bounded proxy. For DJ `d` and target mix `t`:

```text
R_d(t) = union of identified tracks in approved solo mixes by d
         with performed_on strictly earlier than t

S_d(t) = identified tracks observed in target mix t

U_hat_d(t) = R_d(t) union S_d(t)

A_d(t) = R_d(t) minus S_d(t)
```

`S_d(t)` contains observed positives. `A_d(t)` contains **unlabelled
alternatives**, not confirmed negatives. The target mix contributes positives
only and is never allowed to enlarge its own history.

The estimand is therefore:

```text
P(identified target subset | tracks revealed in earlier approved solo sets)
```

It is explicitly not:

```text
P(track selected | DJ true event crate)
```

This is selection-proxy / positive-unlabelled evidence. The project does not
assume that every historical track was available at the later event, and it
does not claim the SCAR assumptions used by some positive-unlabelled learning
methods. Background reference:

- Charles Elkan and Keith Noto, *Learning Classifiers from Only Positive and
  Unlabeled Data*:
  <https://cseweb.ucsd.edu/~elkan/posonly.pdf>

## Trust boundary

Legacy titles and the first MixesDB category tag can be useful as a review
queue, but they are not trusted identity evidence.

The flow is deliberately two-stage:

1. `revealed-repertoire-candidates-v1` generates untrusted hints.
2. A human review explicitly approves or excludes every mix in the frozen
   ordering universe.
3. `revealed-repertoire-gate-v2` compares the review to the exact candidate
   fingerprint.
4. Only a complete, fingerprint-matched review can produce
   `revealed-repertoire-v1`.

There is no partial fallback. Missing, extra or invalid review entries block
the dataset instead of silently selecting an easier subset.

An approved review entry requires:

```json
{
  "status": "approved",
  "dj_id": "canonical-reviewed-id",
  "performed_on": "2020-01-31",
  "performance_role": "solo",
  "evidence": ["review note or source"]
}
```

An excluded entry requires:

```json
{
  "status": "excluded",
  "reason": "b2b / multi-actor / ambiguous identity / imprecise date"
}
```

The complete review file uses:

```json
{
  "schema_version": "revealed-repertoire-review-v1",
  "candidate_report_fingerprint": "<sha256 from candidates.json>",
  "mixes": {
    "mix0001": {
      "status": "approved",
      "dj_id": "frankie-knuckles",
      "performed_on": "1991-08-04",
      "performance_role": "solo",
      "evidence": ["manually checked against source metadata"]
    }
  },
  "provenance": {
    "reviewer": "name",
    "reviewed_at": "ISO timestamp",
    "method": "manual identity/date adjudication"
  }
}
```

## Leakage and quality guards

The implementation:

- freezes the eligible mixes to the immutable ordering dataset;
- accepts only reviewed solo performances and exact ISO day dates;
- uses only dates strictly earlier than the target;
- prevents same-day mixes from becoming history for one another;
- never uses future mixes or the target mix as alternatives;
- reports unidentified target slots and applies a pre-registered minimum
  identification fraction;
- excludes target mixes with duplicate catalogue IDs because a fixed-size
  subset model requires unique items;
- fingerprints metadata, ordering universe, candidate report, review,
  configuration and every emitted observation;
- requires complete `H` and frozen `E` evidence for the exact proxy track
  universe before model evaluation is marked ready.

The v2 gate reports four controls separately:

- local source-audio resolution for the exact proxy universe;
- handcrafted descriptor coverage (`H`);
- frozen learned-audio embedding coverage (`E`);
- the joined model catalogue containing both families.

Explicit `--analysis-root` plus `--analysis-index` and `--embeddings` sources
take precedence. A validated joined `--features` catalogue is also sufficient
evidence for both families because its schema requires non-empty `H` and `E`
vectors for every included track. Source audio is diagnostic rather than a
retroactive requirement: already frozen, source-backed complete features do
not become invalid merely because an original audio file is later offline.

Default pre-registered gates:

```text
minimum prior tracks             20
minimum prior mixes               1
minimum selected tracks          10
minimum unlabelled alternatives  10
minimum identified fraction      80%
minimum observations            100
minimum DJs                       20
```

These are protocol thresholds, not tuned production weights. They may be
changed only explicitly through CLI options and become part of the dataset and
gate fingerprints.

## Model boundary

Once the gate opens, the existing fixed-size subset likelihood can be applied
to `U_hat_d(t)`:

```text
P(S | U, |S| = m) =
  exp(sum(i in S) s_i) /
  sum(T subset U, |T| = m) exp(sum(j in T) s_j)
```

The exact log-partition is already implemented in
`validation/djmix/decomposition.py` in `O(|U| * m)`.

That equation does not make the pool true. It only gives a mathematically
correct likelihood conditional on the declared proxy universe. Results must
continue to be labelled `revealed-repertoire proxy`.

## Commands

Generate the untrusted review queue:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering repertoire-candidates \
  /Volumes/MY_PC/DanceLabCorpus \
  --expect-ordering-dataset \
  dac3ef5dc7735b613994d61e311d6aa63ea33d016ebdebdd434f4793031ce9b1 \
  --output data/reports/revealed_repertoire/candidates.json \
  --review-template-output \
  data/reports/revealed_repertoire/review.template.json
```

Every generated template row has `status: pending`, which the gate rejects.
It is a worksheet, not an auto-approved identity map.

Run the gate after review:

```bash
PYTHONPATH=src ./.venv/bin/dancelab corpus-ordering repertoire-gate \
  /Volumes/MY_PC/DanceLabCorpus \
  --review /path/to/review.json \
  --analysis-root /path/to/analysis-json \
  --analysis-index /path/to/analysis-index.json \
  --embeddings /path/to/frozen-embeddings.json \
  --features data/reports/corpus_ordering/features.json \
  --expect-ordering-dataset \
  dac3ef5dc7735b613994d61e311d6aa63ea33d016ebdebdd434f4793031ce9b1 \
  --candidate-output data/reports/revealed_repertoire/candidates.json \
  --dataset-output data/reports/revealed_repertoire/dataset.json \
  --output data/reports/revealed_repertoire/gate.json \
  --strict
```

`--report-only` writes evidence while blocked. `--strict` exits with code 2
unless review, sample-size and H/E gates all pass.

## Runtime boundary

Implementation:

- `src/dancelab/validation/djmix/repertoire.py`
- `src/dancelab/cli/corpus_ordering.py`
- `tests/test_djmix_repertoire.py`

The module is an offline measurement add-on. It is not imported by
`decision/`, the desktop host, API routes, Rekordbox export or set planning.

## Frozen checkpoint: 2026-07-20

The current source-record adjudication is complete:

```text
reviewed mixes       433 / 433
approved solo mixes  337
excluded mixes        96
review fingerprint   a3f2cf1cb7096f3a35070467642706f29bae484ff123c44512a0ad531894d841
```

The resulting immutable proxy contains:

```text
observations          86
DJs                   31
tracks              2809
dataset fingerprint  bd8d78710acb63af2257eda4a9abc2dfa43b7f472e5d97db22bd077d8215a30b
```

The pre-registered sample gate remains closed because 100 observations are
required. The threshold was not lowered after seeing the result.

The v2 evidence audit reports:

```text
local source audio  2497 / 2809
missing audio        312
ambiguous paths        0
H coverage             0 / 2809
E coverage             0 / 2809
joined H/E catalogue   0 / 2809
```

All 312 missing sources belong to the proxy-only extension of the track
universe; none belongs to the earlier 2881-track ordering universe. Of the
2497 resolved proxy sources, 2275 are WebM and 222 are M4A. Spot checks confirm
that local ffmpeg can decode both formats, but the production engine loader
does not currently admit them, and no frozen learned-audio embedding extractor
has been approved for `E`.

Current gate fingerprint:

```text
e52c21e5c0f25db06b8755174edc8cd8f8ecd61388fd6584d413ea531d890764
```

No proxy model experiment has been run. Opening the gate requires both the
pre-registered sample-size condition and complete, source-backed H/E evidence
for this exact 2809-track universe.

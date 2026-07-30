# Advanced Tutorial: Validation and Review

## Goal

Evaluate DanceLab as a measurable recommendation system. Human judgments stay
outside the engine and are returned as versioned CSV evidence.

## 1. Build a bounded validation pack

```bash
dancelab validation-pack "/path/to/work/processed" \
  --output-dir "/path/to/work/validation_pack" \
  --annotations-dir "/path/to/annotations" \
  --report-dir "/path/to/work/decision_report"
```

Expected outputs include filtered review sheets, coverage summaries, and
Markdown/JSON reports. Metrics appear only where labels exist.

Pass check:

- labeled and unlabeled coverage are distinguished,
- missing evidence is not reported as success,
- output rows preserve stable track and pair identity.

## 2. Record human judgment

Review the CSV sheets in a spreadsheet editor. For each transition, keep the
machine fields unchanged and add the requested rating and comment fields.

Useful failure labels:

- `wrong candidate pool`
- `wrong current context`
- `wrong timing window`
- `wrong transition strategy`
- `musically legal but weak`
- `technically blocked`
- `good recommendation`

Store complete sessions separately, for example:

```text
data/annotations/dj_sessions/2026-07-28_session_01_transition_ratings.csv
```

## 3. Aggregate independent sessions

```bash
dancelab validation-benchmark \
  "/path/to/ratings/session_01_transition_ratings.csv" \
  "/path/to/ratings/session_02_transition_ratings.csv" \
  --output-dir "/path/to/work/dj_benchmark"
```

The tuning gate requires at least five independent sessions and at least 30
rated transitions in each complete session.

Pass check:

- repeated pairs and high-confidence false positives are visible,
- correlations and issue topics are reported,
- tuning begins only when the report says `READY FOR TUNING`.

## 4. Verify export on a copy

Before a native Rekordbox cue write:

1. close Rekordbox,
2. copy `master.db` together with matching `-wal` and `-shm` files,
3. run a dry plan,
4. write only to the copied bundle,
5. reopen the copy and verify playlist and cue rows,
6. prove the live bundle hashes did not change.

The engine must refuse unsafe path, identity, schema, or transaction states.

## Completion Criteria

An advanced validation round is complete only when its inputs, configuration,
engine version, outputs, ratings, and export verification can be reproduced.

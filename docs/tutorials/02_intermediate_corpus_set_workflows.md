# Intermediate Tutorial: Corpus, Set, and Export

## Goal

Use DanceLab like a real working tool:

- load a processed corpus
- build a set plan
- ask for a next-track recommendation
- export a Rekordbox artifact

## What You Touch

- corpus bridge
- set-building flow
- recommend-next flow
- export node

## Before You Start

This tutorial assumes:

- the corpus has already been analyzed
- the processed repository is visible to the host
- you already understand the beginner flow

## Workflow A: Load Corpus

### Graph

`Load Corpus -> Build Set`

### Steps

1. Add `Load Corpus`.
2. Point it to the processed directory.
3. Choose a load mode:
   - `Track IDs + Manifest`
   - `Track IDs + Analyses + Manifest`
4. Connect `Load Corpus` to `Build Set`.

Pass check:

- `Load Corpus` returns a manifest
- you can see track count and processed path in the inspector output

## Workflow B: Build Set

### Graph

`Load Corpus -> Build Set`

### Steps

1. Select `Build Set`.
2. Choose an arc:
   - `build`
   - `flat`
   - `peak`
3. Optionally pick a start track.
4. Run the flow.

Expected output:

- a `SetPlan`
- track order
- mean transition score

Pass check:

- `Build Set` finishes cleanly
- the output contains an ordered track list
- changing the arc can change the plan

## Workflow C: Recommend Next

### Graph

`Load Corpus -> Select Track -> Recommend Next`

Optional:

`Select Context -> Recommend Next`

### Steps

1. Use `Load Corpus` as the candidate pool source.
2. Use `Select Track` to choose the current track.
3. Add `Recommend Next`.
4. If needed, choose `arc_mode` and add recent history in the inspector.
5. Optionally wire `Select Context`.
6. Run the flow.

Expected output:

- current track id
- ranked candidates
- recommendation policy
- warnings or suppressed ids when applicable

Pass check:

- current track is not returned as its own best candidate
- the ranking is visible in the inspector
- changing context or arc mode can change the recommendation

## Workflow D: Export Rekordbox

### Graph

`Load Corpus -> Build Set -> Export Rekordbox`

### Steps

1. Add `Export Rekordbox`.
2. Set playlist name.
3. Set output XML path.
4. Connect:
   - `Load Corpus.analysis` or `Load Corpus.track_ids`
   - `Build Set.set_plan`
5. Run the flow.

Expected output:

- XML preview in the inspector
- written artifact path on disk

Pass check:

- the output file exists
- playlist name is correct
- track count matches the expected set

## Intermediate Skill Check

The user passes this level when they can:

- bridge a repository into the graph
- build a set without re-uploading raw audio
- ask for a contextual next-track suggestion
- export something they can use outside DanceLab

## Common Failure Signals

- `Build Set needs upstream analyses or repository-backed track IDs`
  Cause: corpus not connected or not visible
- `Recommend Next needs candidate tracks to rank`
  Cause: candidate pool is empty or miswired
- `Export Rekordbox needs upstream analyses or repository-backed track IDs`
  Cause: export node has no track source

## What To Do Next

Move to [03_advanced_validation_review.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/03_advanced_validation_review.md).

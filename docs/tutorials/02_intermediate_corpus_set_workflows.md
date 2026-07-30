# Intermediate Tutorial: Shape and Inspect a Real Set

## Goal

Build a playlist for a concrete event, compare planning modes, inspect every
adjacent decision, and prepare a safe Rekordbox export.

## 1. Express the set intent

The one-command workflow supports:

- `--count 5|10|15|20`,
- `--arc build|peak|flat`,
- `--planner-mode smart|harmonic|bpm`,
- `--context` from `configs/context_profiles.yaml`,
- `--analysis-depth normal|deep`.

Example:

```bash
dancelab smart-playlist "/path/to/music" \
  --count 10 \
  --arc build \
  --planner-mode smart \
  --context festival_daytime \
  --analysis-depth normal \
  --processed-dir "/path/to/work/processed" \
  --output "/path/to/work/event_set.xml"
```

Pass check:

- hard limits are respected,
- repeated artists are separated when the library permits it,
- context and planner mode change ranking rather than track identity.

Deep analysis is intentionally explicit. Use it when stem-aware evidence is
worth the additional time and storage; normal analysis remains the fast default.

## 2. Inspect pair decisions

```bash
dancelab decision-report "/path/to/work/processed" \
  --output-dir "/path/to/work/decision_report" \
  --context festival_daytime
```

Review:

- `edge_decision_review.csv`,
- `edge_decision_payloads.jsonl`,
- the generated Markdown and JSON summaries.

Pass check: every row keeps stable track IDs, source paths, score components,
warnings, and proposed timing.

## 3. Audition the seams

Render important adjacent pairs with more than one profile:

```bash
dancelab preview "track_a.wav" "track_b.wav" \
  --profile bass_swap --beats 64 --output "a_b_bass_swap.wav"

dancelab preview "track_a.wav" "track_b.wav" \
  --profile contour_blend --beats 128 --output "a_b_contour.wav"
```

Pass check:

- A and B always resolve to the displayed files,
- cues land on the engine's reliable phrase grid,
- preview tempo adjustment never leaks into exported metadata.

## 4. Export safely

Rekordbox XML is the normal interoperability path:

```bash
dancelab export-rekordbox "/path/to/work/processed" \
  --output "/path/to/work/final_set.xml" \
  --name "Event Set" \
  --arc build \
  --planner-mode smart \
  --context festival_daytime
```

Native cue writing is a separate advanced operation. It is dry-run by default,
uses a verified copy-and-swap path by default, and must first be tested against
a copied `master.db` bundle:

```bash
dancelab cues write --help
```

Never use `--allow-live` during an exploratory test.

Continue with [Validation and review](03_advanced_validation_review.md).

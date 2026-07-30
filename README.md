# DanceLab Pro / Engine 0.1.1

DanceLab is a local, terminal-first DJ-intelligence engine for analyzing a
music library, building a context-aware set sequence, inspecting proposed
transitions, and exporting results for Rekordbox.

The product question is:

```text
Does this track make sense next, in this set and in this context?
```

## Current Product Workflow

The supported product surface is the `dancelab` command-line application:

1. Analyze one track, a folder, or a prepared corpus.
2. Build a constrained smart playlist from the analyzed library.
3. Generate headless decision artifacts for pair and transition review.
4. Optionally collect DJ ratings and build a validation pack.
5. Export a Rekordbox-compatible XML playlist.
6. Plan, review, and apply hot cues through the safe Rekordbox writer.

There is no supported graphical application. The former desktop and visual
node interfaces were removed so engine behavior can be stabilized and tested
without a second product layer.

## Implemented Capabilities

- WAV, MP3, AIFF, and FLAC ingestion with deterministic track identity.
- Tempo, beat times, key, structure, energy, bass, onset, pulse, vocal,
  syncopation, microtiming, groove, tension, release, breakdown, and drop
  candidate descriptors.
- Optional Demucs separation into vocals, bass, drums, and other, including
  stem export. Full-mix fallback remains available when separation is disabled
  or fails quality checks.
- Pair mixability, transition-window candidates, transition strategy,
  edge-decision rules, next-track ranking, and bounded set sequencing.
- Set constraints for track count, BPM range, style focus, energy arc, venue,
  time, set role, pinned tracks, locked positions, artist diversity, and
  playlist-history novelty.
- Rekordbox XML export plus a guarded cue writer with dry-run review, database
  bundle backups, WAL/SHM handling, and safe atomic replacement.
- Offline validation tools for tempo/beatgrid, real-audio end-to-end paths,
  DJ-mix alignment (M11), and Raveform population priors.

## Honesty Boundaries

- Decision models are marked `candidate` or `hypothesis`; they are not claims
  about crowd response or guaranteed live transitions.
- Beat-sync and tempo adjustment are preview-only. Rekordbox export does not
  overwrite track BPM or export a tempo grid by default.
- Beat timing is validated more strongly than downbeat phase. The current
  downbeat proxy is explicitly unverified and must not be treated as Rekordbox
  ground truth.
- The Raveform duration model is an offline validation artifact. It is not yet
  eligible to influence production ranking weights.
- Missing descriptors are surfaced through confidence and warnings rather than
  replaced with fabricated measurements.

## Install And Launch

Python 3.11+ is required. From a repository checkout:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e ".[dev,audio,rekordbox]"
PYTHONPATH=src ./.venv/bin/dancelab --help
```

Optional deep analysis and stem export:

```bash
./.venv/bin/python -m pip install -e ".[stems]"
```

## CLI And API

```bash
# Analyze one track or a directory
PYTHONPATH=src ./.venv/bin/dancelab analyze path/to/track.wav --output out.json
PYTHONPATH=src ./.venv/bin/dancelab batch path/to/music/

# Build a 10-track set from a folder
PYTHONPATH=src ./.venv/bin/dancelab smart-playlist path/to/music/ \
  --count 10 --output data/reports/my_set.xml

# Generate decision-review artifacts
PYTHONPATH=src ./.venv/bin/dancelab decision-report data/processed \
  --output-dir data/reports/decision_report

# Inspect the guarded cue workflow
PYTHONPATH=src ./.venv/bin/dancelab cues --help

# Local API / OpenAPI. Public binding is intentionally unsupported.
PYTHONPATH=src ./.venv/bin/uvicorn dancelab.api.main:app \
  --host 127.0.0.1 --port 8000
```

The cue writer is dry-run by default. Never target the live Rekordbox database
for an experiment; validate writes on a copied DB bundle first. Install the
`rekordbox` extra before using direct database cue writing.

## Verification

```bash
PYTHONPATH=src ./.venv/bin/pytest
./.venv/bin/ruff check src tests
./.venv/bin/python -m compileall -q src tests
./.venv/bin/python -m pip check
```

## Repository Layout

```text
configs/             engine settings, weights, formula metadata
data/                examples, processed analyses, reports, validation artifacts
docs/                architecture, product, validation, design, handoff guides
src/dancelab/
  core/              domain models, config, pipeline, provenance
  ingestion/         audio, tags, preflight, Rekordbox-device inputs
  preprocessing/     tempo/beatgrid, tempo precision, segmentation
  features/          measured frame-level audio features
  descriptors/       candidate higher-level descriptor curves
  stems/             Demucs extraction, quality checks, stem exports
  context/           context profiles and context-fit scoring
  decision/          pair, transition, recommendation, and sequence logic
  workflows/         user-level smart-playlist orchestration
  export/            Rekordbox XML output
  storage/           JSON repositories, cache and manifest management
  validation/        headless measurement, review, and evidence artifacts
  preview/           optional audio transition rendering
  api/ and cli/      integration surfaces over engine/workflow functions
tests/               unit, contract, integration, security, and real-audio tests
```

Start with [docs/architecture.md](docs/architecture.md) for the current system
map and [docs/tutorials/README.md](docs/tutorials/README.md) for the guided test
path.

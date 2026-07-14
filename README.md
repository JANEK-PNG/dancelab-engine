# DanceLab Pro / Engine 0.1.1

DanceLab is a local DJ-intelligence application for analyzing a music library,
building a context-aware set sequence, reviewing proposed transitions, and
exporting a Rekordbox-compatible playlist.

The product question is:

```text
Does this track make sense next, in this set and in this context?
```

## Current Product Workflow

The supported desktop surface is **Simple Mode**:

1. Import one or more folders or a Rekordbox XML library.
2. Run the Initial Check over the selected tracks.
3. Define set length, style, BPM, role, energy, and context preferences.
4. Generate and optionally deep-analyze the proposed set.
5. Review A/B transitions with waveforms, quantized cue candidates, and the
   transition simulation.
6. Export the playlist and hot cues to Rekordbox XML or save the project.

The deprecated visual node editor is not a product entry point. Headless
contracts in `contracts/` and `host/runtime.py` remain as tested integration and
diagnostic adapters.

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
- Rekordbox XML export with playlist order and quantized hot-cue candidates.
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
./.venv/bin/python -m pip install -e ".[dev,audio,desktop]"
PYTHONPATH=src ./.venv/bin/dancelab-host
```

Optional deep analysis and stem export:

```bash
./.venv/bin/python -m pip install -e ".[stems]"
```

The desktop app can also be built with the `desktop-build` extra. See
[docs/DESKTOP_HOST.md](docs/DESKTOP_HOST.md) for the macOS packaging path and
known platform constraints.

## CLI And API

```bash
# Analyze one track or a directory
PYTHONPATH=src ./.venv/bin/dancelab analyze path/to/track.wav --output out.json
PYTHONPATH=src ./.venv/bin/dancelab batch path/to/music/

# Build the guided smart-playlist artifact path
PYTHONPATH=src ./.venv/bin/dancelab smart-playlist path/to/music/

# Generate decision-review artifacts
PYTHONPATH=src ./.venv/bin/dancelab decision-report data/processed \
  --output-dir data/reports/decision_report

# API / OpenAPI
PYTHONPATH=src ./.venv/bin/uvicorn dancelab.api.main:app --reload
```

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
  validation/        separate measurement and evidence tools
  visualization/     decision reports and waveform galleries
  host/              PySide6 Simple Mode desktop application
  api/ and cli/      integration surfaces over engine/workflow functions
tests/               unit, contract, desktop, integration, and real-audio tests
```

Start with [docs/architecture.md](docs/architecture.md) for the current system
map and [docs/tutorials/README.md](docs/tutorials/README.md) for the guided test
path.

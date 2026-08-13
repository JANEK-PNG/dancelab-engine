# DanceLab Pro / Engine 0.1.1

DanceLab is a local, terminal-first DJ-intelligence engine for analyzing a
music library, building a context-aware set sequence, inspecting proposed
transitions, and exporting results for Rekordbox.

The product question is:

```text
Does this track make sense next, in this set and in this context?
```

## Quickstart: See It Work In Ten Minutes

Verified end to end from a clean clone on macOS, 2026-08-01.

**Before you start.** You need **Python 3.11+** — macOS ships 3.9, which will not
work. Get 3.12 with `brew install python@3.12`, `uv python install 3.12`, or
pyenv.

**Bring your own music.** This repository ships no audio, deliberately: source
audio is never redistributed (see [docs/CORPUS_ETHICS.md](docs/CORPUS_ETHICS.md)).
Copy **5–10 electronic tracks** — MP3, WAV, AIFF or FLAC — into a folder first.

```bash
git clone https://github.com/JANEK-PNG/dancelab-engine.git
cd dancelab-engine
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev,audio,rekordbox,tui]"

# 1. Does it run?
./.venv/bin/dancelab version

# 2. Analyze one track  (~2 min for a 3-minute track, single-threaded)
./.venv/bin/dancelab analyze "/path/to/one-track.mp3" --output track.json

# 3. The whole point: a folder in, a sequenced set out  (~2 min per track)
./.venv/bin/dancelab smart-playlist /path/to/your/folder --count 5 --output set.xml

# 4. The test suite  (~2 min, no audio needed)
./.venv/bin/python -m pytest -q
```

**What you should see.** Step 2 writes an `AnalysisResult`: tempo, beat times,
downbeats, grid-quality score, segments, descriptor curves, and a `notes` array
naming which descriptors are proxies rather than validated measurements. Step 3
prints a line like `Playlist: DanceLab Smart Set · 5 tracks · mean transition
0.63` and writes a Rekordbox XML carrying key, tempo and named cue markers
(`Mix In`, `Mix Out`, `Bridge`) — import it into Rekordbox to see the decisions
on the pads.

**Where the research is.** The measured results, the baselines, the negative
findings and the numbers this project withdrew from its own work are in
[docs/EVALUATION.md](docs/EVALUATION.md). Those numbers are computed from a
corpus that is not redistributable, so they are not reproducible from a clone —
that document says so explicitly and names the script behind each figure.

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
./.venv/bin/python -m pip install -e ".[dev,audio,rekordbox,tui]"
PYTHONPATH=src ./.venv/bin/dancelab --help
```

Optional deep analysis and stem export:

```bash
./.venv/bin/python -m pip install -e ".[stems]"
```

The `PYTHONPATH=src` prefix used in the examples below is a fallback: macOS can
hide the editable-install marker so `import dancelab` fails at runtime (ENV-1 in
`pyproject.toml`). On a clean clone `./.venv/bin/dancelab` works without it —
add the prefix only if you hit `ModuleNotFoundError: dancelab`.

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

## Documentation

| If you want to | Read |
|---|---|
| See the engine work | The quickstart at the top of this file |
| Understand the system | [docs/architecture.md](docs/architecture.md) |
| Check the research claims | [docs/EVALUATION.md](docs/EVALUATION.md) |
| Know why it is built this way | [docs/DECISIONS.md](docs/DECISIONS.md) |
| Read the computation spec | [docs/formulas.md](docs/formulas.md) |
| Use the HTTP surface | [docs/api.md](docs/api.md) |
| Know how corpus data may be used | [docs/CORPUS_ETHICS.md](docs/CORPUS_ETHICS.md) |
| Work in the repository | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Write documentation for it | [docs/DOCUMENTATION_STANDARD.md](docs/DOCUMENTATION_STANDARD.md) |

Documentation is treated as code: it lives beside the source, changes in the same
commit as the behaviour it describes, and the part that can be measured —
docstring coverage of modules, classes and public callables — is ratcheted in CI
by `scripts/docstring_coverage.py`.

## Support

Questions and bug reports belong in
[GitHub issues](https://github.com/JANEK-PNG/dancelab-engine/issues). There is no
other support channel; this is a research engine, not a product with an SLA.

## License

**Source-available, not open source.** You may read this code, run it on your own
machine, and modify it locally for personal, academic, journalistic or evaluation
purposes. Commercial use and redistribution require written permission. See
[LICENSE](LICENSE).

The distinction is deliberate. The point of publishing the engine is that its
methods and its failures can be inspected; that does not require giving away the
right to build a product on it.

# Current Architecture

DanceLab separates the production engine from user interfaces and from offline
validation. Simple Mode, CLI, and API call the same workflow and engine
functions; validation packages consume outputs but do not mutate production
weights or cached analyses.

```text
                         +----------------------+
                         | PySide6 Simple Mode  |
                         +----------+-----------+
                                    |
       +-------------+      +-------v-------+      +-------------+
       | CLI / API   +----->| workflows/    |<-----+ project I/O |
       +-------------+      +-------+-------+      +-------------+
                                    |
  ingestion -> preprocessing -> features/descriptors -> context -> decision
                                    |
                         +----------v-----------+
                         | JSON cache / export  |
                         +----------+-----------+
                                    |
                         +----------v-----------+
                         | offline validation   |
                         +----------------------+
```

## Production Layers

| Layer | Responsibility | Current state |
|---|---|---|
| `core/` | Pydantic contracts, config, pipeline, normalization, phrasing, provenance | active |
| `ingestion/` | Audio loading, metadata, preflight, deterministic identity, Rekordbox-device input | active |
| `preprocessing/` | Beat/tempo estimation, 32-beat tempo refinement, structural segmentation | active; downbeat phase remains unverified |
| `features/` | Frame-level measured audio features | active |
| `descriptors/` | Groove, bass salience, tension, release, breakdown/drop candidate curves | active candidate layer |
| `stems/` | Optional Demucs extraction, quality control, stem-window features and export | active optional worker |
| `context/` | Explicit context profiles and context-fit scoring | active candidate layer |
| `decision/` | Transition windows, mixability, rules, strategies, next-track and sequence planning | active candidate layer |
| `workflows/` | User-level smart-playlist orchestration | active |
| `storage/` | JSON repositories, cache manager, library manifest, artifact store | active; no SQL database |
| `export/` | Rekordbox-compatible XML playlist and cue export | active |
| `visualization/` | Decision reports and pair-waveform galleries | active |
| `host/` | PySide6 Simple Mode, project state, library views, transition review/simulation | product desktop surface |
| `api/`, `cli/` | Integration gateways over production functions | active |

## Validation Boundary

`validation/` is deliberately outside production scoring:

- `validation/tempo/` benchmarks tempo and beat timing against operational
  references.
- `validation/djmix/` implements offline M11 mix-to-track alignment and cue
  evidence.
- `validation/raveform/` trains and evaluates transition-duration priors from a
  local public Raveform archive.
- `validation/review_ui/` builds bounded review artifacts.

Validation outputs live in report directories. They may become engine inputs
only after a documented held-out evaluation and an explicit product decision.
The current Raveform artifact has `eligible_for_engine_influence=false`.

## Desktop And Diagnostic Boundary

The supported desktop entry point imports `SimpleModeWindow`. The former visual
node editor is deprecated and not launched. `contracts/node_host.py` and
`host/runtime.py` remain headless, tested compatibility adapters; they are not
on the Simple Mode startup path and deleting them would remove integration
capability without improving desktop startup.

See [architecture/diagnostic-boundary.md](architecture/diagnostic-boundary.md)
for the stricter sensor/diagnostic contract.

## Dependency Rules

- `core`, `features`, `descriptors`, `context`, `decision`, `ingestion`,
  `preprocessing`, and `workflows` must not import FastAPI, Typer, or PySide6.
- The production engine must not import `validation/`.
- UI code may orchestrate engine/workflow functions but must not duplicate
  scoring formulas.
- Heavy audio and desktop dependencies remain optional or lazy where practical.
- Every persisted engine result is JSON-serializable and versioned.
- Missing evidence produces warnings/confidence changes, not invented values.

## Data And Cache Ownership

- Source audio remains outside the engine repository unless explicitly added as
  a test fixture.
- Processed analyses are immutable JSON records keyed by deterministic track ID.
- Library manifests map user-visible files to those records.
- Stem renders, waveforms, reports, and validation artifacts are derived data
  and may be regenerated.
- Preview beat-sync state is not written back into analysis JSON or Rekordbox
  tempo metadata.

## Known Technical Debt

- `host/simple_mode.py` is a large UI module and should be split by screen only
  under characterization tests; it is not a runtime bottleneck.
- `validation/review_ui/swipe_review.py` contains legacy monolithic HTML
  generation and should remain isolated from the product host.
- `contracts/node_host.py` is a large declarative registry; refactor only if an
  external integration actually needs it.
- Sequence and set-planning functions are complex and need further extraction,
  but mathematical behavior must be frozen with golden-result tests first.
- Downbeat phase and Rekordbox tempo-grid export remain intentionally disabled
  pending stronger real-library validation.

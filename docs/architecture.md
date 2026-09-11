# Current Architecture

DanceLab separates the engine from its desktop, terminal and API delivery
layers and from offline validation. The desktop GUI calls `stan/` through an
in-process pywebview bridge; the TUI shares these operations. The CLI and local
HTTP API expose engine/workflow functions. Validation consumes exported outputs
but does not automatically change production weights or cached analyses.

```text
 GUI / TUI -> stan/ --------+
 CLI / API -> workflows/ --+
                           v
 ingestion -> preprocessing -> features/descriptors -> context -> decision
          |                                                        |
          +--------------------> storage/export <-------------------+
                                      |
                                      v
                              offline validation
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
| `storage/` | JSON repositories, cache manager, library manifest, atomic artifact publication | active |
| `catalog/` | Optional PostgreSQL/pgvector identity catalog | active; separate from JSON artifact storage |
| `stan/` | Shared application operations, current set and decision journal | active; still wraps some TUI persistence |
| `gui/`, `tui/` | pywebview desktop and Textual interfaces | active; GUI bridge calls `stan/` directly |
| `export/` | Rekordbox XML plus guarded cue planning/writing | active |
| `preview/` | Optional headless A/B transition audio rendering | active optional layer |
| `api/`, `cli/` | Local integration gateways over production functions | active product surfaces |

## Validation Boundary

`validation/` is deliberately outside production scoring:

- `validation/tempo/` benchmarks tempo and beat timing against operational
  references.
- `validation/djmix/` implements offline M11 mix-to-track alignment and cue
  evidence.
- `validation/raveform/` trains and evaluates transition-duration priors from a
  local public Raveform archive.
- `validation/decision_report.py` builds CSV/JSONL review artifacts.

Validation outputs live in report directories. They may become engine inputs
only after a documented held-out evaluation and an explicit product decision.
The current Raveform artifact has `eligible_for_engine_influence=false`.

## Product And Diagnostic Boundary

The supported product entry point is `dancelab`. The FastAPI application is a
localhost-only integration surface. Neither layer owns scoring formulas; both
delegate to workflows and engine modules.

The earlier Qt and node-graph interfaces are retired. The current desktop GUI
is under `gui/`; local HTML preview tools under `docs/` are separate diagnostics.
New diagnostics must consume explicit manifests or versioned artifacts rather
than reaching into undocumented runtime state. See [ADR-007](DECISIONS.md#adr-007--desktop-and-terminal-share-application-operations).

See [architecture/diagnostic-boundary.md](architecture/diagnostic-boundary.md)
for the stricter sensor/diagnostic contract.

## Dependency Rules

- `core`, `features`, `descriptors`, `context`, `decision`, `ingestion`,
  `preprocessing`, and `workflows` must not import FastAPI or Typer.
- The production engine must not import `validation/`.
- CLI/API code may orchestrate workflows but must not duplicate scoring
  formulas.
- Heavy audio and stem dependencies remain optional or lazy where practical.
- Every persisted engine result is JSON-serializable and versioned.
- Missing evidence produces warnings/confidence changes, not invented values.
- The API binds only to `127.0.0.1`; public exposure is outside the supported
  threat model.

## Data And Cache Ownership

- Source audio remains outside the engine repository unless explicitly added as
  a test fixture.
- Processed analyses are immutable JSON records keyed by deterministic track ID.
- Library manifests map user-visible files to those records.
- Stem renders, previews, reports, and validation artifacts are derived data and
  may be regenerated.
- Preview beat-sync state is not written back into analysis JSON or Rekordbox
  tempo metadata.
- Rekordbox writes operate on the database bundle (`master.db`, WAL, SHM) and
  require a recoverable backup plus validation before replacement.

## Known Technical Debt

- Sequence and set-planning functions are complex and need further extraction,
  but mathematical behavior must be frozen with golden-result tests first.
- Downbeat phase and Rekordbox tempo-grid export remain intentionally disabled
  pending stronger real-library validation.
- The cue writer still requires a final real-library E2E on a copied Rekordbox
  database bundle before live use can be recommended.
- Packaging, runtime data locations and first-run recovery still need a clean-profile
  validation outside the author's prepared library.

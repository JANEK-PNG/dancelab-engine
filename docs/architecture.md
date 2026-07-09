# Architecture — module responsibilities

Pipeline (System Architecture for Implementation):

```text
Client / UI / Notebook / CLI
        ↓
ingestion → preprocessing → features → descriptors → context → decision
        ↓
storage / api / visualization
```

## Module map

| Module | Responsibility | Team owner (15-person model) | Status |
|---|---|---|---|
| `core/models.py` | Pydantic domain models; all JSON contracts | Principal Systems Architect | done (v0) |
| `core/config.py` | YAML → typed config; versioned weights | Principal Systems Architect | done (v0) |
| `core/errors.py` | Error hierarchy incl. `NotImplementedFeature` | Principal Systems Architect | done (v0) |
| `core/pipeline.py` | Orchestration; single entry for CLI + API | Principal Systems Architect | working candidate pipeline |
| `ingestion/` | Audio load (wav/mp3/aiff/flac), track metadata, deterministic track_id | Audio DSP Engineer | done (needs [audio] extra) |
| `preprocessing/` | Normalize, beatgrid, structural segmentation | Audio DSP Engineer + MIR Scientist | beatgrid + segmentation working (candidate labels) |
| `features/` | RMS ✅, spectral flux ✅, LFER ✅, bass energy ✅, onset density ✅, pulse clarity proxy ✅, vocals ✅, key ✅, syncopation ✅, microtiming ✅ | Audio DSP Engineer + MIR Scientist | candidate coverage |
| `descriptors/` | Groove ✅, bass salience ✅, tension ✅, release ✅, breakdown/drop ✅, prediction error, mixability | MIR Scientist + Music Cognition Researcher | candidate coverage |
| `context/` | Style profiles, context profiles ✅, conditioning (`X_eff = X_audio · C_fit` ✅) | Music Cognition + DJ Domain Expert | partial |
| `decision/` | Transition windows, mixability, transition strategy, edge decision, set function, next-track ranking, risk | ML/Recommendation Engineer + DJ Expert | candidate pair stack + next-track working |
| `core/provenance.py` | Sprint 3 source-grounding: model cards → OutputProvenance on every decision output; guardrail warnings; E4/to_validate cap | Research Lead + QA | done (v0) |
| `api/` | FastAPI gateway; honest 501 for unimplemented computation | Backend Engineer | done (v0 wiring) |
| `storage/` | DB (SQLite→Postgres), repositories, artifact store (JSON ✅) | Data Engineer | partial |
| `visualization/` | Descriptor plots, reports, waveform pair galleries (minimal outputs only — UI is a client) | Data Engineer | candidate reports working |
| `cli/` | `dancelab analyze / batch / version` | SDK/Integration Engineer | done (v0 wiring) |

## Dependency rules (enforced by review; ADR-003)

- `core`, `features`, `descriptors`, `context`, `decision`, `ingestion`, `preprocessing`
  MUST NOT import `fastapi`, `typer`, or anything from `api/` / `cli/`.
- `api/` and `cli/` call `core/pipeline.py` only — both surfaces return identical results.
- Heavy audio deps (`librosa`, `scipy`) are imported lazily inside functions so the
  engine skeleton installs and tests without them.

## Future layering (Universal Engine Architecture)

Current repo = `dancelab-core` + thin `api`/`cli`. When services (queues, cache,
Postgres) arrive, they become `dancelab-services` without touching core. SDK is
generated from OpenAPI + a thin Python client wrapping `core.pipeline`.

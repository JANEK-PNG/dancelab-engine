# DanceLab Engine v0

Universal analytical engine for electronic music and DJ decision support.

**Core question the engine answers:**

```text
Czy ten track ma sens teraz? / Does this track make sense right now?
```

**Pipeline:**

```text
audio → features → descriptors → style/context conditioning → decision outputs
```

## Principles (from Architecture Decision Records)

- **ADR-001 Engine-first** — engine before UI; UI is only a client.
- **ADR-002 Python-first** — Python 3.11+ for correctness; native acceleration later for bottlenecks.
- **ADR-003 Core independent of API** — `dancelab.core`, `features`, `descriptors`, `context`, `decision` must not import FastAPI or any frontend.
- **ADR-004 JSON everywhere** — every engine output is JSON-serializable (Pydantic models).
- **ADR-005 Candidate formulas** — models marked `candidate` / `planned` / `draft` are experimental, not production truth. Every decision output carries `status`, `explanation` and `confidence` fields.
- **ADR-006 API as integration gateway** — FastAPI/OpenAPI is the first integration surface (UI, plugin, notebook, SDK later).

## Install

```bash
# minimal (schemas, config, API skeleton, CLI):
pip install -e ".[dev]"

# full audio stack (librosa, scipy, pandas, scikit-learn):
pip install -e ".[dev,audio,viz]"

# optional stem-aware preprocessing (Demucs + torch):
pip install -e ".[dev,audio,stems]"
```

## Usage

```bash
# CLI
dancelab analyze path/to/track.wav --output out.json
dancelab batch path/to/directory/
dancelab decision-report data/processed --output-dir data/reports/decision_report

# API
uvicorn dancelab.api.main:app --reload
# then: http://127.0.0.1:8000/docs
```

`decision-report` writes the full pair report plus annotation-ready
`edge_decision_payloads.jsonl` and a human-review `edge_decision_review.csv`
alongside the waveform gallery.

To enable the stem-aware candidate layer, set `stems.enabled: true` in
[`configs/default.yaml`](/Users/jantrybus/Desktop/AI/dancelab-engine/configs/default.yaml)
or in your runtime config override. The engine will attempt
`vocals` / `bass` / `drums` / `other` separation, surface provenance and
warnings in `AnalysisResult.stem_extraction`, and fall back to full-mix
descriptors when separation quality is insufficient.

## Learn the Product

For a user-facing learning path that doubles as a practical test series, start
with the tutorial library:

- [docs/tutorials/README.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/README.md)

## Repository layout

```text
configs/        default engine config, descriptor weights, context profiles
data/           raw / processed / annotations / examples (example JSON output here)
docs/           architecture, api, formulas, validation, test plan, assumptions, risks
src/dancelab/
  core/         config loading, domain models (Pydantic), errors, pipeline orchestration
  ingestion/    audio file + metadata loading
  preprocessing/ resample/normalize, beatgrid, segmentation
  features/     RMS, spectral flux, onset density, bass, pulse, microtiming, vocals
  descriptors/  groove, bass salience, tension, release, prediction error, mixability
  context/      style profiles, context profiles, conditioning (C_fit)
  decision/     set function, transition windows, next track ranking, risk
  api/          FastAPI app + routes + API schemas
  storage/      database, repositories, artifact store
  visualization/ plots, reports
  cli/          analyze, batch
tests/
```

## Status

This is the **Sprint 0 skeleton + first working features**: architecture, schemas,
API/CLI wiring, configs, tests, and real extraction of the implemented features
(RMS, spectral flux, LFER, bass energy, onset density, pulse clarity proxy,
vocal density proxy) aggregated to 1-second frames. `analyze` now also enriches
candidate descriptor proxies / curves for syncopation, bass salience,
microtiming, tension, release, groove density, and breakdown/drop likelihood.
Non-edge segment labels are also refined by the breakdown/drop candidate layer.
Decision outputs are still omitted — they remain on-demand and never fabricated
in storage.
Remaining formulas are documented in [docs/formulas.md](docs/formulas.md);
their endpoints return HTTP 501 with an explanation instead of fake numbers.

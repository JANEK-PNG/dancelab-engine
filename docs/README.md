# DanceLab Documentation

DanceLab is currently a terminal-first engine. There is no supported desktop,
browser, or node-graph product surface. This page separates current operating
documentation from retained research and design history.

## Current Product Documentation

- [Repository overview](../README.md) — supported workflow, installation, CLI,
  API, and honesty boundaries.
- [Architecture](architecture.md) — current package boundaries and execution
  paths.
- [API](api.md) — local API contract. The supported bind address is
  `127.0.0.1`.
- [Rekordbox import and cue writing](rekordbox_import.md) — XML import and the
  guarded, copy-first database workflow.
- [Validation](validation.md) — evidence artifacts and human review data.
- [Tutorials](tutorials/README.md) — beginner through advanced terminal
  workflows.
- [Test plan](test_plan.md) — verification scope.

## Active Research Protocols

These documents describe bounded research inputs and model gates. They do not
override the product workflow or its safety rules.

- [Tempo validation](TEMPO_VALIDATION.md)
- [DJ-mix validation](DJMIX_VALIDATION.md)
- [Raveform priors](RAVEFORM_PRIORS.md)
- [Corpus ordering dataset](CORPUS_ORDERING_DATASET_V1.md)
- [Revealed repertoire](REVEALED_REPERTOIRE_V1.md)
- [NAINA catalog pipeline](NAINA_CATALOG_PIPELINE.md)
- [Warehouse catalog pipeline](WAREHOUSE_CATALOG_PIPELINE.md)

## Historical Material

Files describing Simple Mode, Terrain, desktop hosting, motion systems, node
graphs, or dated handoffs are retained as design and decision history. They
are not current build, launch, or QA instructions. In particular:

- `SIMPLE_MODE_DESIGN_SYSTEM.md`
- `TERRAIN_*.md`
- `DESIGN_CODE_COVERAGE_AUDIT_*.md`
- `ENGINE_*_HANDOFF_*.md`
- `ROADMAP_*.md`

When a historical document conflicts with the repository overview,
architecture, tests, or executable CLI help, the current executable contract
wins.

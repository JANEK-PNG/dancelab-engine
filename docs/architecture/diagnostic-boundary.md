# Diagnostic Boundary

DanceLab should behave like a clean engine with external diagnostics.

## Rule

- The engine computes descriptors, scores, rules, windows, pair decisions, and sequence recommendations.
- The engine may emit telemetry artifacts and pointers to them.
- Review UIs, swipe decks, plugins, test harnesses, and experimental tooling must live outside the engine path and consume exported telemetry as read-only input.

## Practical meaning

- Keep core logic in `core/`, `decision/`, `features/`, `descriptors/`, `preprocessing/`.
- Keep diagnostic tooling in validation/review surfaces such as `validation/` and external add-ons.
- Do not place test UI behavior inside engine modules.
- Do not make review tooling depend on undocumented internal paths when a manifest/contract can be used.

## Desktop product boundary

- DanceLab Pro exposes the guided Simple Mode workflow only.
- The former visual graph editor and its HTML shell are removed from the product.
- `host/runtime.py` and `contracts/node_host.py` remain headless compatibility
  adapters for machine clients and diagnostics. They are not a second user
  interface.
- Do not reintroduce a canvas, visual node library, or Graph Mode entry point
  without a new product decision and a demonstrated end-user need.

## Current telemetry contract

- `decision_summary.json` is the external telemetry manifest for one decision-report run.
- It points to artifacts like:
  - `analysis_summary`
  - `mixability_pairs`
  - `edge_decisions`
  - `edge_decision_payloads`
  - `edge_decision_review`
  - `waveform_overview`
  - `waveform_index`

Diagnostic tools should prefer this manifest over guessing file layout.

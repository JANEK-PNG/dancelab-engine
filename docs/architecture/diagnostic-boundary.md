# Diagnostic Boundary

DanceLab should behave like a clean engine with external diagnostics.

## Rule

- The engine computes descriptors, scores, rules, windows, pair decisions, and sequence recommendations.
- The engine may emit telemetry artifacts and pointers to them.
- Review tools, plugins, test harnesses, and experimental tooling must live outside the engine path and consume exported telemetry as read-only input.

## Practical meaning

- Keep core logic in `core/`, `decision/`, `features/`, `descriptors/`, `preprocessing/`.
- Keep diagnostic tooling in `validation/` and external add-ons.
- Do not place test behavior inside engine modules.
- Do not make review tooling depend on undocumented internal paths when a manifest/contract can be used.

## Product boundary

- DanceLab Pro exposes a terminal workflow and an optional localhost API.
- The former desktop, visual graph editor, and HTML review surfaces are removed.
- Do not reintroduce a GUI without a new product decision and a demonstrated
  end-user need.
- API clients receive versioned data contracts, not direct access to mutable
  engine state.

## Current telemetry contract

- `decision_summary.json` is the external telemetry manifest for one decision-report run.
- It points to artifacts like:
  - `analysis_summary`
  - `mixability_pairs`
  - `edge_decisions`
  - `edge_decision_payloads`
  - `edge_decision_review`

Diagnostic tools should prefer this manifest over guessing file layout.

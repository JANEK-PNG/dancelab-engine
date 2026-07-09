# API (v0 skeleton — API Contract Draft)

Base: `uvicorn dancelab.api.main:app` → http://127.0.0.1:8000 (OpenAPI at `/docs`).

| Endpoint | Status | Notes |
|---|---|---|
| `GET /health` | working | engine + weights versions |
| `GET /model-cards` | working | Sprint 3 model cards; every decision output's `provenance.model_card_id` resolves here |
| `GET /formula-terms` | working | per-component formula-term metadata (no anonymous variables); every weighted score term resolves here |
| `GET /contexts/profiles` | working | example context profiles from configs |
| `POST /tracks/analyze` | working | low-level features + beatgrid + structural segments + candidate descriptor proxies/curves (syncopation, bass salience, microtiming, tension, release, groove, breakdown/drop); non-edge segment labels are refined by candidate breakdown/drop detectors; decision outputs still omitted |
| `GET /tracks/{track_id}` | working | file-based repository over data/processed (404 if not analyzed) |
| `POST /tracks/{track_id}/transition-windows` | working (candidate) | Transition Windows Model v0.1 (Sprint 2); confidence scaled by input coverage; prev/next track accepted but unused (warned) |
| `POST /pairs/mixability` | working (candidate) | Mixability Model v0.1 (Sprint 2 Final); needs both tracks analyzed (404 else); confidence scaled by coverage; payload now also exposes shared pair-rule flags / hard-block metadata plus recommendation policy (`allow` / `review_only` / `suppress`) |
| `POST /pairs/edge-decision` | working (candidate) | Unified pair decision: windows + mixability + context fit + strategy + warnings |
| `POST /tracks/{track_id}/set-function` | working (candidate) | Set Function Model v0.1 (Sprint 2 Final); rule-based; context shifts scores (C010) |
| `POST /contexts/evaluate` | working (candidate) | Context Evaluation v0.1; role-conditioned `C_fit` heuristic with fit/risk/provenance |
| `POST /sets/recommend-next` | working (candidate) | Next Track v0.1; ranks candidates from mixability, context fit, role fit, energy-step suitability, groove continuity, and recent-history heuristics over energy, tempo and role progression; recent-history tracks are removed from the candidate pool; shared pair-rule penalties / hard blocks now also affect ranking, and confidence floors can suppress candidates from the returned list |
| `POST /sets/recommend-sequence` | working (candidate) | Sequence v0.1; draft continuation planner that beam-searches a few branches and scores them by pair quality plus explicit local/global energy-arc fit under `build` / `flat` / `peak` / `closing`; planner now also uses continuation lookahead, terminal arc reachability, and a bounded set-memory score over recent set-function progression and tension/release history, and payload carries these scores alongside sequence guardrail flags and recommendation policy / suppressed-transition counts; API horizon supports up to `12` |

## Honest-501 contract

Unimplemented computation returns:

```json
{
  "error": "not_implemented",
  "feature": "mixability",
  "formula_status": "planned",
  "detail": "M_ix(x,y) — spec §8; requires per-track analyses from storage."
}
```

Rationale: ADR-005 — candidate/planned formulas must not pretend to be production
truth; endpoints must never return fabricated scores.

## Error mapping

| Engine error | HTTP |
|---|---|
| `NotImplementedFeature` | 501 |
| `IngestionError` | 422 |
| `ConfigError` | 400 |
| `MissingDependencyError` | 503 |

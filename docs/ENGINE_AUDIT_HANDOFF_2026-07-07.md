# Engine Audit Handoff - 2026-07-07

> Refreshed after Phase 1 + Phase 2 completion and the 15-track
> `phase2_refresh_lekcja5` rerun.

## Executive Summary

No - the engine still does **not** implement everything described in
`/Users/jantrybus/Desktop/DJ Set Song Analysis.pdf`.

But it is also no longer a thin skeleton. Current state is:

- **implemented at candidate level**: ingestion, beatgrid, segmentation, low-level
  features, key/Camelot compatibility, stem-aware preprocessing, syncopation,
  microtiming, groove, bass salience, tension/release, phrase-aware windows,
  breakdown/drop detectors, transition windows, mixability, transition strategy,
  unified `EdgeDecision`, context evaluation, set function, next-track ranking
  with shallow history modelling, shared pair-rule gating, confidence-floor
  policy (`allow` / `review_only` / `suppress`), draft sequence planning with
  local/global arc fit, continuation lookahead, terminal arc reachability, and
  hard sequence guardrails, report generation, waveform visualization,
  provenance/model-card guardrails
- **partial**: context-conditioning depth, confidence calibration, heuristic set
  builder, PDF parity of the edge payload
- **missing**: deep sequence/global energy-arc engine, exact PDF-style `SequenceDecision` layer,
  crowd-response blocker, DJ validation/calibration loop

This repo is now best described as a **candidate DJ decision engine with working
pair-level coverage and partial next-track intelligence**.

## Project Policy Update (2026-07-08)

After the current Phase 3 work, the project direction is now explicitly:

- keep implementing new functionality only when it is source-backed,
  mathematically expressible, and a natural extension of the current data/model
- avoid inventing planner depth or behavioral claims that cannot be grounded in
  literature, the PDF, or existing analyzable signals
- stop broadening the engine once it reaches a usable candidate state
- treat tuning, calibration, and weight adjustment as a later activity on top
  of a structurally complete engine, not something done while the engine is
  still being invented

In practice, this means the next build work should be bounded and decision-path
oriented, while Phase 5 becomes the place for calibration and empirical tuning.

## Verified Repo State

Verified locally on `2026-07-07`:

- `./.venv/bin/ruff check .` -> passed
- `./.venv/bin/pytest -q` -> `200 passed`; remaining warnings are existing
  `TestClient/httpx` deprecation + small synthetic-audio `librosa` warnings

## What Was Actually Run

Current reproducible Phase 2 artifacts live inside the repo:

- processed analyses for `15` tracks:
  `/Users/jantrybus/Desktop/AI/dancelab-engine/data/phase2_refresh_lekcja5/processed/`
- refreshed decision-layer report:
  `/Users/jantrybus/Desktop/AI/dancelab-engine/data/reports/phase2_refresh_lekcja5/`
- waveform gallery:
  `/Users/jantrybus/Desktop/AI/dancelab-engine/data/reports/phase2_refresh_lekcja5/waveforms/index.html`

Observed from the refreshed report:

- `track_count = 15`
- `ordered_pair_count = 210`
- refreshed JSONs keep stable `track_id == output filename stem`
- top pair under the current model:
  `Mala, Magugu - Militant Don (Vocal)` ->
  `TSVI, Josi Devil - M.e.S (feat. TSVI) (feat. TSVI)` with
  `mixability_score = 0.7281`

## Coverage Vs PDF

### Status Legend

- `Implemented`: present in code and exercised in tests or real runs
- `Partial`: candidate/proxy coverage exists, but the full PDF layer is not matched
- `Missing`: absent or still deferred

| PDF area | Status | Notes |
|---|---|---|
| 1. Core scoring layer (`F001`, `F002`) | Partial | Score families exist, but not as one registry-driven universal engine. |
| 2. Groove / onset / rhythm (`F003`-`F015`) | Partial | Onset density, pulse clarity proxy, syncopation, microtiming, and groove descriptor exist as candidate layers. Full validation and some richer similarity logic are still absent. |
| 3. Bass layer (`F016`, `F017`) | Partial | Bass energy, bass salience, and conflict proxy exist. Full bass-conflict decomposition is still simplified. |
| 4. Tension / release (`F018`-`F020`) | Partial | Candidate `tension` and `release` descriptors are implemented and persisted, but not validated against DJ labels. |
| 5. Transition window layer (`F021`-`F023`) | Partial | Real window scoring, local maxima, top-k windows, phrase awareness, and compatible-context heuristics exist. |
| 6. Tempo / BPM layer (`F024`-`F029`) | Partial | BPM estimate, half/double-time tolerant tempo fit, transition-strategy feasibility, and shared BPM hard blocks/penalties now exist. Thresholds are still heuristic. |
| 7. Harmonic / Camelot layer (`F030`-`F037`) | Partial | Key detection and Camelot compatibility exist. Stem harmonic risk / overlap depth is still limited. |
| 8. Breakdown / drop layer (`F038`-`F042`) | Partial | Candidate breakdown/drop likelihood curves exist and refine segment labels, but there is no full breakdown-quality / drop-trajectory family yet. |
| 9. Mixability / edge layer (`F043`-`F049`) | Partial | Mixability, pair windows, harmonic/bass/vocal/tension handling, unified `EdgeDecision`, and shared pair-rule gating now exist. Calibration is still missing. |
| 10. Transition type layer (`F050`-`F052`) | Partial | A candidate transition strategy classifier exists, but it is heuristic rather than DJ-validated. |
| 11. Set function layer (`F053`-`F057`) | Partial | Rule-based set-function classifier exists, but it is still lighter than the PDF. |
| 12. Decision confidence / risk (`F058`, `F059`) | Partial | Confidence and risk fields exist in outputs, and a shared suppression/review policy now exists, but calibration is still heuristic. |
| 13. Bridge / segmentation (`F060`-`F062`) | Partial | Segmentation exists and feeds decisions; bridge logic remains heuristic. |
| 14. Global energy arc / sequence (`F063`-`F071`) | Partial | Draft sequence planning exists with explicit local/global arc fit, bounded set-memory over recent role/tension history, continuation lookahead over remaining-pool fit, terminal reachability, and hard guardrails for cumulative risk/BPM drift/energy plateau, but there is still no full long-range energy-arc scorer or accumulated multi-edge planning logic. |
| 15. Crowd response blocker (`F072`-`F074`) | Missing | Guardrails prevent fake claims, but there is no explicit crowd-readiness blocker output. |
| 16. Final decision output layer (`F075`-`F077`) | Partial | `EdgeDecision` exists and a draft `SequenceDecision` now exists, but it is not yet the exact PDF payload. |
| 17. Hard engine rules (`R001`-`R008`) | Partial | A shared `rules.py` now enforces BPM/harmonic/vocal/bass hard blocks across mixability, edge, next-track, and sequence, but thresholds remain heuristic and not DJ-calibrated yet. |
| 18. Minimum required payload | Partial | Edge-level payload is close in spirit; sequence payload parity is still missing. |

## Phase 2 Outcome

Phase 2 is now effectively closed at **candidate coverage** level:

- `analyze` persists descriptor proxies/curves for:
  `syncopation_proxy`, `bass_salience`, `microtiming_proxy`, `tension_proxy`,
  `release_proxy`, `groove_density`, `breakdown_likelihood`, `drop_likelihood`
- phrase-awareness uses beatgrid anchors plus structural snapping fallback
- non-edge segment labels are refined after segmentation using the
  breakdown/drop detector layer
- mixability and next-track no longer depend on neutral placeholders for the
  main Phase 2 descriptor family

## Biggest Remaining Gaps

1. Global energy-arc scoring beyond short-horizon beam search.
2. Stronger recent-history modeling than the current shallow energy/tempo/role heuristic.
3. Explicit crowd-response blocker layer beyond the current confidence-floor policy.
4. DJ validation, calibration, and confidence tuning.
5. Longer-range sequence/global-arc planning.

## Suggested Next Steps

1. Expose sequence planning through API/report artifacts before adding more UI.
2. Deepen sequence planning only along source-backed, mathematically explicit set-history logic.
3. Add an explicit crowd-response blocker layer only if it can be supported by existing descriptors/rules rather than speculative crowd inference.
4. Build a small validation pack around the refreshed 15-track corpus plus DJ review sheets.

## Short Answer For Claude Code

When Claude Code returns, the shortest accurate summary is:

> The engine now has working candidate coverage for the pair stack plus the
> main Phase 2 descriptor family: key/Camelot, syncopation/microtiming, groove,
> bass salience, tension/release, phrase-aware transition windows,
> breakdown/drop detectors, mixability, transition strategy, unified
> `EdgeDecision`, context evaluation, next-track ranking, a shared `rules.py`
> for pair/sequence guardrails plus confidence floors, and a draft sequence
> planner with lookahead/terminal arc scoring and hard guardrails. The biggest remaining gaps are deeper
> sequence/global-arc logic, crowd blockers, and DJ validation/calibration.

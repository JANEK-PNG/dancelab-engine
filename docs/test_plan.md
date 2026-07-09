# Test plan

## Layers

1. **Unit — math** (`test_features.py`): implemented DSP on synthetic signals with
   analytic ground truth (constant → RMS exact; sine → amp/√2; 60 Hz sine → LFER>0.9;
   stationary signal → flux≈0). Deterministic, no audio files, no librosa needed.
2. **Unit — schemas** (`test_schemas.py`): JSON round-trips (ADR-004), field
   constraints, mandatory explanation+confidence on decision scores,
   **example JSON in data/examples validates against `AnalysisResult`** — the example
   can never drift from the schema.
3. **Unit — config** (`test_descriptors.py`, `test_decision.py`): weights file loads,
   is versioned, all groups carry non-stable status (ADR-005 guard), context profiles
   resolve.
4. **Contract — API** (`test_api.py`): all contracted endpoints exist in OpenAPI;
   validation errors → 422; unimplemented computation → honest 501 with formula status.
5. **Contract — honesty**: every stub raises `NotImplementedFeature` with correct
   status; tests pin this so a half-implemented function can't silently return junk.

## Sprint 1 additions (when computation lands)

- Golden-file regression: fixed WAVs in `data/examples/` → committed feature JSONs;
  byte-stable within tolerance (determinism requirement).
- Reference cross-check: our RMS/flux vs librosa equivalents on the same frames.
- Beat/onset accuracy vs public MIR benchmarks (mir_eval metrics).
- Property tests: descriptor outputs bounded [0,1] after normalization; conditioning
  monotone in C_fit.
- API integration: analyze real file end-to-end, response == CLI output (Repo
  Blueprint DoD: same result through both surfaces).

## CI (Sprint 1)

pytest + ruff on push; matrix: {core}, {core+audio}; Docker build check.

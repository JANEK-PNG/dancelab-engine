# Risks (deliverable 10)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Candidate formulas fail validation** — groove/tension composites may not correlate with human ratings | high | high | ADR-005 discipline; weights versioned; validation loop before any product claim; formulas pluggable |
| R2 | **No annotated dataset yet** — everything downstream of features is untestable against ground truth | high | high | Sprint 0 pilot: 20–30 own tracks + annotation sheet; dataset plan §minimum v0 |
| R3 | **Normalization ambiguity** — composite descriptors meaningless if input scales mismatch | high | medium | explicit Sprint 1 decision (assumptions.md #5); property tests bounding outputs |
| R4 | **Beat tracking errors cascade** — pulse clarity, microtiming, kick alignment, transition windows all depend on beatgrid | medium | high | accept user BPM/beatgrid hints (Implementation Brief); validate vs MIR benchmarks; report beatgrid confidence |
| R5 | **librosa install friction** (numba/llvmlite, broken Homebrew on dev machine) | medium | medium | `[audio]` optional extra; Docker path; lazy imports with clear errors |
| R6 | **Style-conditioning subjectivity** — style profiles from intuition instead of data | medium | high | status `draft`; profiles must come from annotated dataset; DJ Domain Expert review gate |
| R7 | **Scope creep toward UI** | medium | medium | ADR-001/003; API is the only surface; visualization limited to plots |
| R8 | **Performance on full tracks** (7-min WAV, frame-level features) | low (v0) | medium | Python-first for correctness; profile before optimizing; numba/Rust later (ADR-002) |
| R9 | **Copyright constraints on dataset audio** | medium | medium | own library for pilot; store features not audio where possible; document licensing per source |
| R10 | **Fake-certainty regression** — future code returning scores without confidence/explanation | medium | high | `ScoredOutput` makes fields mandatory (schema-level); tests pin honest-501; review checklist |
| R11 | **Single-developer bus factor / AI-generated code drift** | medium | medium | 15-person role matrix as review lens; docs/architecture.md dependency rules; tests as contract |
| R12 | **BPM octave errors** — beat tracker locked half/double time (house ~124 → 62; DnB ~175 → 88); degrades phrase alignment | medium | medium | RESOLVED: octave-folding into [90,180) with phase-preserving beat refit (`preprocessing/beatgrid.py`); `--bpm` hint overrides folding |
| R13 | **Set-function priors miscalibrated** — library distribution builder 92 / bridge 81 / peak 5, zero openers/closers/resets; implausible for real sets | high | medium (v0 only) | hand-set priors explicitly `TO BE FIT against EXP011 labels`; weakest of 3 decision engines; needs DJ labels before any use |

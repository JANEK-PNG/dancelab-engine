# Architectural Decision Records

The decisions that constrain everything else in this engine. Each record states
the decision, why it was taken, and — most usefully — what it forbids.

**Provenance of this index.** ADR-001 through ADR-006 were referenced across the
source, the tests and the specifications (ADR-005 alone is cited 71 times) but
had never been written down in one place. This file was reconstructed on
2026-08-01 from the points where each decision is actually enforced, which are
listed under each record. Reconstructing from enforcement rather than from memory
means the records describe what the code really does; where a record is thinner
than the decision that produced it, that is why.

Records are never deleted. A superseded record is marked superseded and points at
its replacement.

---

## ADR-001 — The engine has one surface: the API and the CLI

**Status:** accepted · **Enforced in:** `docs/risks.md` (R7), repository layout

**Decision.** The engine exposes its behaviour through the command line and the
HTTP API. There is no supported graphical application; visualization is limited
to generated plots and review artifacts.

**Why.** A second product layer competes for attention with engine correctness.
The desktop and node-graph interfaces that once existed were removed so behaviour
could be stabilised and tested without maintaining a UI in parallel.

**Forbids.** Adding a user interface as a way of avoiding an engine problem;
letting a display concern reach into the decision layer.

---

## ADR-002 — Python first, for correctness; optimise only after measuring

**Status:** accepted · **Enforced in:** `docs/risks.md` (R8)

**Decision.** The engine is written in Python and prioritises correctness and
legibility. Performance work happens after profiling, and native acceleration
(numba, Rust) is a later step, not a starting assumption.

**Why.** Frame-level feature extraction over full-length tracks is slow enough to
tempt premature optimisation, and optimised code is harder to prove right. A
research engine that is wrong quickly has no value.

**Forbids.** Restructuring the computation for speed before a profile shows where
the time goes.

---

## ADR-003 — The core stays framework-free

**Status:** accepted · **Enforced in:** `src/dancelab/core/` (import rules),
`docs/architecture.md`, dependency tests

**Decision.** `core` depends on Pydantic and the standard library only. It never
imports FastAPI, Typer, or any other delivery framework. Dependencies point
inward: delivery layers depend on the core, never the reverse.

**Why.** The analytical layer must outlive whatever serves it. A core that
imports its transport cannot be tested, reused or replaced independently.

**Forbids.** Importing a web or CLI framework anywhere under `core`; letting an
HTTP concern such as a status code shape a domain model.

---

## ADR-004 — Every engine output is a serialisable Pydantic model

**Status:** accepted · **Enforced in:** `tests/test_schemas.py`, every model in
`src/dancelab/core/models.py`, the examples in `data/examples/`

**Decision.** All engine outputs are Pydantic models and therefore JSON by
construction. JSON is the primary exchange format. Round-trips are tested, and
the example payloads in `data/examples/` are validated against the live schema.

**Why.** A schema that only exists in the writer's head drifts from its readers.
Validating the shipped examples against the current models means the examples can
never quietly go stale.

**Forbids.** Returning ad-hoc dictionaries or tuples from an engine boundary;
shipping an example payload that the current schema would reject.

---

## ADR-005 — Honesty: the engine never fabricates a result

**Status:** accepted · **Enforced in:** 71 citations across `src/`, `tests/` and
`docs/` — including `core/errors.py`, the `ScoredOutput` model, the descriptor
docstrings marked `STATUS: candidate`, and the honest-501 API tests

The load-bearing decision of the project.

**Decision.**

1. Every formula carries a status. `candidate` and `hypothesis` are experimental
   and say so in the docstring and in the output.
2. A computation that is specified but not implemented **raises an error** — HTTP
   501, exit code 3 — instead of returning a plausible number.
3. An unknown value leaves the engine as `None` with a warning. It is never
   replaced by a default that looks like a measurement. A measurement below the
   noise floor is reported as unmeasurable.
4. Every decision output is a `ScoredOutput` with a **mandatory** explanation and
   confidence, and carries provenance: the model card, the strength of evidence,
   and what the result may not be used to claim.
5. Stem-derived features keep their `StemProvenance`. When separation fell back
   to the full mix, the decision layer must still be able to see that.
6. **Predicting crowd response is prohibited outright.**

**Why.** The engine's only real asset is that its outputs can be trusted. A
single fabricated default destroys that for every other number in the system, and
the failure is silent — a wrong value looks exactly like a right one.

**Forbids.** Filling a gap with a default; softening an unimplemented path into a
neutral score; returning a score without an explanation and a confidence;
implying stem backing that does not exist; any claim about how an audience will
react.

---

## ADR-006 — The HTTP API is an integration gateway, not a second engine

**Status:** accepted · **Enforced in:** `src/dancelab/api/main.py` and the route
modules

**Decision.** The FastAPI service is the first integration gateway over existing
engine and workflow functions. It must not fork the data model or hold logic of
its own.

**Why.** The moment an API layer starts reshaping domain objects, there are two
definitions of every concept and they diverge under deadline.

**Forbids.** Defining request or response models that duplicate core models with
different fields; implementing decision logic in a route handler.

---

## Recording a new decision

Add the next number in sequence with the same four parts — decision, why,
enforcement point, and what it forbids. Cite it as `ADR-0NN` at the place in the
code where it binds, so that the constraint is discoverable from the code rather
than only from this file. Two categories are always worth recording: constraints
on what an output may claim, and retreats — a measurement that was wired in and
then withdrawn, with the reasoning that withdrew it. See
[`DOCUMENTATION_STANDARD.md`](DOCUMENTATION_STANDARD.md) §3.

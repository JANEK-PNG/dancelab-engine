# Documentation Standard

How this repository documents itself, why each rule exists, and how the rules are
enforced. The structure follows the four documentation types and five practices
set out in IBM's guide to code documentation, applied to a research engine rather
than an enterprise service.

The short version: **documentation is code**. It lives in version control beside
what it describes, it is reviewed in the same pull request, and the parts that can
be measured are measured in CI.

---

## 1. Language

**English, everywhere, without exception.** Source, docstrings, comments, commit
messages, documentation, schema descriptions and error strings.

The project is developed bilingually and some working notes were written in
Polish. Those are being converted; `docs/CORPUS_ETHICS.pl.md` is the one
deliberate exception, kept as a preserved original beside its canonical English
version and named so that the exception is visible.

A reader who cannot read a document cannot review it. That is the whole argument.

---

## 2. The four types, and where each one lives here

### Low-level — comments and docstrings

| Element | Requirement |
|---|---|
| Module | Docstring stating what the module is for. **Required.** |
| Public class | Docstring stating what it models. **Required.** |
| Public function or method | Docstring stating what it does and what the caller gets. **Required.** |
| Private helper (`_name`) | Docstring optional when the name and type annotations already carry the meaning. |
| Inline comment | Only where intent cannot be read off the code: a non-obvious algorithm, a measured constant, a deliberate deviation. |

**Parameters and return values are documented by type annotations, not by prose.**
96% of arguments and 95% of return values are annotated. Restating an annotated
argument in text duplicates a fact that the type checker already enforces, and
IBM's own guidance is explicit that overdocumentation hinders readability.

Prose about a parameter is required only where the type cannot express the
contract:

- **units and ranges** — `bpm: float` does not say whether 0.5 means half-speed
  or an error; a beat index does not say whether it is 0- or 1-based;
- **provenance and trust** — whether a value is measured, refined, or a
  documented proxy;
- **side effects and ownership** — whether the callee mutates the argument, and
  who owns a file handle or a database connection.

This repository's real risk is not undocumented arguments. It is a number whose
origin nobody can reconstruct. Document origins.

### High-level — architecture and design

- [`architecture.md`](architecture.md) — the system map: audio → features →
  descriptors → context conditioning → decisions.
- [`formulas.md`](formulas.md) — the computation specification.
- [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) — what the product is and is not.
- [`EVALUATION.md`](EVALUATION.md) — the evaluation protocol, the baselines, the
  measured results and the results that were withdrawn.
- [`DECISIONS.md`](DECISIONS.md) — the index of architectural decision records.

### Internal — conventions and process

- This document.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — environment setup, the quality
  gate, and what a change is expected to carry.
- [`../PROJECT_LEDGER.md`](../PROJECT_LEDGER.md) — the running record of what was
  done, what was decided and what is open.
- [`test_plan.md`](test_plan.md) and [`risks.md`](risks.md).

### External — the reader who arrives from outside

- [`../README.md`](../README.md) — what the engine is, the verified quickstart,
  capabilities, honesty boundaries, CLI, layout.
- [`api.md`](api.md) — the HTTP surface.
- [`CORPUS_ETHICS.md`](CORPUS_ETHICS.md) — how corpus data may and may not be used.

---

## 3. Documenting decisions

Every decision that constrains future work is written down as an **ADR** —
architectural decision record — and indexed in [`DECISIONS.md`](DECISIONS.md).

An ADR states the decision, the reason, and what it forbids. It is not deleted
when it is superseded; it is marked superseded and the replacement points back at
it. The history of why a constraint exists is more valuable than a tidy list.

Two categories of decision are recorded even when they feel obvious at the time:

1. **Honesty constraints** — what an output may not claim, what happens when a
   value is unknown, which computations refuse to guess. These are the reason the
   engine can be trusted at all, and they are easy to erode silently.
2. **Retreats** — a measurement wired into behaviour and then withdrawn, a
   hypothesis refuted by a control, a feature that made results worse. The
   reasoning is kept in code and in `EVALUATION.md` so that the next attempt
   starts from the measurement rather than from a repeat of the mistake.

---

## 4. Keeping it accurate

Documentation drifts silently, so the parts that can be checked are checked
automatically as part of the same quality gate that runs the tests.

```bash
python scripts/docstring_coverage.py            # report
python scripts/docstring_coverage.py --check    # enforce the floors
```

The floors are a **ratchet**: they are set to the level the tree already meets,
so the gate fails on regression, never on standing still. When a change improves
coverage, raise the floor in the same pull request.

Current floors, measured on `main`:

| Kind | Coverage | Floor |
|---|---|---|
| Modules | 91.4% | 90% |
| Classes | 45.4% | 45% |
| Public callables | 50.1% | 49% |

Class and callable coverage are low, and stating so here is deliberate: an
honest baseline that goes up is worth more than an aspirational number nobody
meets. The priority order for raising them is the surface a reader touches
first — `cli/`, `api/`, then `decision/`.

Beyond the ratchet:

- **Review.** A change that alters behaviour updates the documentation that
  describes that behaviour, in the same commit.
- **Claims carry evidence.** A number in any document names the script or the
  artifact it came from. A number that cannot be traced is removed, not softened.
- **Superseded means labelled.** Out-of-date documents are marked or deleted.
  A confidently wrong document is worse than a missing one.

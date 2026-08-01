# Working in this repository

How to set up an environment, what the quality gate checks, and what a change is
expected to carry. Conventions for writing the documentation itself live in
[docs/DOCUMENTATION_STANDARD.md](docs/DOCUMENTATION_STANDARD.md).

> **Contributions from outside the project** are not being accepted. The engine
> is source-available rather than open source: it may be read, run and modified
> locally for non-commercial purposes, but it is not a shared codebase. See
> [LICENSE](LICENSE). Issues and questions are welcome.

---

## Environment

Python 3.11 or newer is required; macOS ships 3.9, which will not work.

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev,audio,rekordbox]"
./.venv/bin/dancelab version
```

`uv` is used for the locked environment that CI runs:

```bash
uv sync --locked --extra dev --extra audio --extra rekordbox
```

If `import dancelab` fails at runtime on macOS, see the ENV-1 note in
`pyproject.toml`: the system can hide the editable-install marker, and
`PYTHONPATH=src` is the documented fallback.

---

## The quality gate

CI runs these on every push. Run them before you commit, and expect a red build
if you skip them.

```bash
./.venv/bin/python -m pytest                                    # tests
./.venv/bin/ruff check src tests scripts                        # lint
./.venv/bin/python scripts/docstring_coverage.py --check        # documentation
./.venv/bin/python -m compileall -q src tests                   # syntax
./.venv/bin/python -m pip check                                 # dependency sanity
```

CI additionally runs the suite across Python 3.11 and 3.12, a security regression
job (`bandit`, `pip-audit`), and a wheel build with a clean-install check.

---

## What a change carries

**Tests.** Behaviour that can be verified is verified. A bug fix arrives with the
test that would have caught it.

**Documentation, in the same commit.** If a change alters behaviour, the document
that describes that behaviour changes with it. Public modules, classes and
callables carry docstrings; the docstring coverage gate is a ratchet, so a change
may raise the floors but never lower them.

**A decision record, when the change constrains future work.** Add an ADR to
[docs/DECISIONS.md](docs/DECISIONS.md) and cite it at the point in the code where
it binds. This is especially true for anything touching what an output is allowed
to claim.

**Evidence for every number.** A figure in a document or a commit message names
the script or artifact it came from. A number that cannot be traced back is
removed rather than softened — see [docs/EVALUATION.md](docs/EVALUATION.md) for
the numbers this project has withdrawn from its own work, and why.

---

## Two rules that are not negotiable

**Never fabricate a result.** ADR-005 is the load-bearing decision of the
project: unimplemented computations raise instead of returning a plausible
number, unknown values leave as `None` with a warning, and every decision output
carries an explanation, a confidence and its provenance. Read
[docs/DECISIONS.md](docs/DECISIONS.md) before touching the decision layer.

**No audio in the repository.** Source audio is never committed and never
redistributed; the extracted features are what the project keeps. `.gitignore`
blocks audio formats on every path — that rule is format-scoped rather than
path-scoped because a path-scoped version failed once. See
[docs/CORPUS_ETHICS.md](docs/CORPUS_ETHICS.md).

---

## Language

English, everywhere: code, docstrings, comments, commit messages, documentation.
See [docs/DOCUMENTATION_STANDARD.md](docs/DOCUMENTATION_STANDARD.md) §1.

# Stage A — Engine safety and preparation UX

Date: 2026-09-06. Owner: Jan. Implementation branch: `codex/audit-stage-a`.
Baseline: `67cd961`. This is the first implementation increment of the
[post-audit plan](../../audits/2026-09-06/PLAN_PRACY.md), not completion of all
five workstreams.

## Delivered

- Unique, atomic publication of saved plans and verdicts; atomic current-plan
  pointer updates. A failed publication preserves the previous pointer.
- Plan read/delete boundaries and trash collision protection. Plan formats and
  existing filename prefixes remain compatible.
- Literal rendering of backend errors at the audited GUI entry points;
  traversal and external symlink rejection in the documentation preview server.
- Proper PostgreSQL identifier quoting for catalog counts. Fixed queries replace
  unnecessary dynamic table-name interpolation in catalog matching.
- Full `src tests scripts` Ruff gate restored; CI includes preview-server lint,
  JavaScript security regressions, syntax and dependency consistency checks.
  Pre-commit uses the Ruff version in the lockfile. Only pip was upgraded in the
  lockfile, from 26.1.2 to 26.2.1.
- [Product brief](PRODUCT_BRIEF.md), [design system v0.1](DESIGN_SYSTEM.md), and
  [interactive prototype](ux/index.html) for personal-library set preparation.
  Audience confirmed by the owner; UX effectiveness remains a hypothesis.
- README and architecture/decision records now describe the actual desktop GUI,
  shared state and optional catalog rather than a purely terminal-first product.

## Open the prototype

From the repository root:

```bash
.venv/bin/python -m http.server 8874 --bind 127.0.0.1 \
  --directory docs/workstreams/2026-09-06-stage-a/ux
```

Open http://127.0.0.1:8874/. The banner labels all tracks as demo data. Save and
resume use a separate browser storage key. Export produces a marked demo JSON,
without audio or writes to Rekordbox. See [observed checks](UX_QA.md).

## Verification

Evidence is in [evidence/](evidence/). Commands were run locally on macOS,
Python 3.12; these results do not assert a completed remote CI matrix.

| Check | Result | Evidence |
| --- | --- | --- |
| Full pytest suite | 1087 passed, 1 skipped, 5 warnings | `pytest-final.log` |
| New Python safety regressions | 20 passed | `p1-regressions.log` |
| Actual GUI script, minimal DOM / Node test runner | 5 passed | `gui-security.log` |
| Regression baseline before fixes | 15 failed / 2 passed Python; 4 failed JS | `p1-before.log`, `gui-security-before.log` |
| Ruff, including preview server | Clean | `ruff.log` |
| Docstring coverage ratchet | Passed | `docstrings.log` |
| Existing environment dependency consistency | Passed | `pip-check.log` |
| Bandit at CI medium/high confidence/severity threshold | No findings | `bandit.json` |
| Locked dependency audit, dev/audio/rekordbox/tui | No known vulnerabilities found | `dependency-audit.log` |
| Python syntax, src/tests/scripts | Passed | `syntax.log` |
| Wheel build and isolated base installation | Passed | `wheel-build.log`, `clean-install.log` |

The initial full-suite log predates three additional tests; `pytest-final.log`
is authoritative. Trailing whitespace in console logs is normalized for Git.
The baseline regression run also predates later added cases,
so its total is smaller than the final new-test total.

## Recovery and remaining work

A verified all-refs Git bundle and copies of pre-existing non-ignored untracked
files were saved in the session artifact backup directory before editing.
This is a local recovery point, not an off-machine or complete runtime-data
backup. The old branch and pre-existing audit/UX documents are preserved.

Next Engine/DATA increment: inventory runtime data locations and ownership,
choose an off-machine backup destination, rehearse restore using disposable
copies, and complete locked installation checks for the supported profiles.
Then classify the document registry using the audited disposition proposals;
no bulk deletion is part of this increment.

Next UX increment: observe the brief's tasks with target DJs, resolve terminology
and workflow findings, then integrate one production journey through the existing
bridge. The current prototype supplies the reviewable starting point.

TWIN/TouchDesigner follows its separate event capture/replay prototype; ML follows
dataset/version/evaluation preparation and a justified benchmark. Neither was
started or silently integrated here. Keep the plan's limit of two active areas.

Remaining safety validation includes the native WKWebView bridge, remaining
metadata-to-HTML paths, an evaluated production CSP, concurrent hostile filesystem
mutation, and device/audio operation. Atomic publication is not a power-loss
recovery or backup guarantee. Static scans and minimal DOM regressions are not a
penetration test or proof that a computer cannot be compromised.

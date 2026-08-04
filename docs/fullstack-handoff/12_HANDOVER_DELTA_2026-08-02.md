# Handover delta — 2026-08-02

Read this **before** `02_CURRENT_STATE.md`. That document is a snapshot from the
handoff baseline; the items below were measured against the working tree on
2026-08-02 and correct it.

Repository: `~/Developer/dancelab-engine` · `main` @ `3d80f50` · 181 commits ·
590 tests green from a clean clone · CI green.

---

## 1 · Corrections to `02_CURRENT_STATE.md`

| It says | Measured truth |
|---|---|
| Stem-aware analysis — "CURRENT, optional" | **Disabled in every config**, including `configs/default.yaml` (`stems.enabled: false`). `features/vocals.py` is the only consumer and silently falls back to a full-mix proxy. Reads as available; is not. |
| — (not mentioned) | **`core/rigid_grid.py` is not wired into the analysis pipeline.** It is imported only by `scripts/`. The pipeline still uses dynamic beat tracking. `core/tempo_refine.py` *is* wired (`preprocessing/beatgrid.py`). |
| — (not mentioned) | **No CLI command produces the cue-export bundle.** `dancelab cues write` consumes `{set_plan, analyses, windows}` JSON, which only `scripts/cue_export_e2e.py` can build, and only from a pre-populated analysis cache. |
| Audio handling | `mono: true` in every config. All analysis is mono. |

Also true and unchanged: 8 modules are imported nowhere (5 `api/routes_*`,
`data/dataset_manifest`, 2 `__main__` shims). The API routes are likely
registered dynamically — verify before deleting anything.

---

## 2 · Work items, in priority order

### T1 — `dancelab cue-plan` (the missing seam)

**Problem.** The product has a proven first mile (analyse → set) and a proven
last mile (write hot cues into `master.db` with conflict resolution), and no
command connecting them. This is why the README teaches the XML path — and the
XML path is documented as failing for the real use case in
`docs/RND_CUE_DELIVERY_USE_CASE.md`: Rekordbox does not overwrite entries already
in the user's collection, so the DJ sees none of the exported cues.

**Build.** A command that takes analysed tracks (a directory of `AnalysisResult`
JSON, or a folder of audio it analyses itself) and writes the cue-export bundle
that `dancelab cues write` already consumes. Reuse `scripts/cue_export_e2e.py` —
it already does this correctly with `build_set` + `detect_transition_windows`.

**Done when:** `dancelab cue-plan <dir> --output bundle.json` followed by
`dancelab cues write --set bundle.json` runs with no script and no manual step,
and the two commands appear in the README quickstart.

### T2 — `entry_point` default (blocked on the owner)

`render_set.entry_point` scans up to 45% of a track for the "best" entry. Measured
on the owner's 21 real seams: in 18 of 21 he starts the record from the top, and
on 15 tracks the rule would pick a different point than he used in 14 cases.

**Do not change this without his answer.** It is question #16 in
`PROJECT_LEDGER.md`. The proposed change: return the phrase-aligned start by
default, and scan only when the start fails a "must be playable" floor — behind
a switch, not by deleting the scan.

### T3 — Decide the stem and grid wiring

Two capabilities are built and not reachable from the product: Demucs separation
(disabled in all configs) and the rigid beat grid (scripts only). Either wire
them into the pipeline or state in the docs that they are research-only. Right
now the documentation implies availability that does not exist.

### T4 — Seam feasibility in set ordering

The set builder scores pairs on track properties. Whether the seam can actually
be executed — entry point, outgoing runway, achievable blend length — does not
participate in ordering. This is the difference between a playlist to be mixed
and a set designed at the seam. Design work, not a bug fix.

---

## 3 · Constraints that must not be broken

These are enforced in code and in tests. Read `docs/DECISIONS.md` first.

- **ADR-003** — `core/` imports Pydantic and the standard library only. Never
  FastAPI, never Typer. Dependencies point inward.
- **ADR-004** — every engine output is a Pydantic model; examples in
  `data/examples/` are validated against the live schema.
- **ADR-005** — the engine never fabricates. Unimplemented computations raise
  (HTTP 501 / exit 3); unknown values leave as `None` with a warning; every
  decision carries an explanation, a confidence and provenance. Predicting crowd
  response is prohibited.
- **Cue writer invariant** — writes `DjmdCue` rows only. Never BPM, never the
  beat grid. Default is plan-only; `--write` is explicit, `--allow-live` is
  required for the live library, and it refuses while Rekordbox is running.
- **No audio in the repository**, on any path. `.gitignore` is format-scoped
  because a path-scoped version failed once. See `docs/CORPUS_ETHICS.md`.

---

## 4 · Running it

```bash
python3.12 -m venv .venv                                   # 3.11+ required; macOS ships 3.9
./.venv/bin/python -m pip install -e ".[dev,audio,rekordbox]"
./.venv/bin/dancelab --help                                # 13 commands
```

Quality gate, all of which CI runs:

```bash
./.venv/bin/python -m pytest                               # 590 tests
./.venv/bin/ruff check src tests scripts/verify_clean_install.py scripts/docstring_coverage.py
./.venv/bin/python scripts/docstring_coverage.py --check   # ratcheted floors
```

`ruff` is pinned to `>=0.15,<0.16` deliberately: `uv.lock` pins 0.15.22 and CI
runs that, while 0.16 widened its default rule set. Raise the pin and the lock
together or a clean install will report hundreds of findings the gate does not.

---

## 5 · Where the rest is

- `docs/fullstack-handoff/01`–`11` — product scope, target architecture,
  transition plan contract, API and frontend, production plan, runbook, risks,
  research context, player flow, DDJ-FLX4 control map.
- `docs/EVALUATION.md` — measured results, baselines, the negative findings and
  the numbers withdrawn from the project's own work.
- `docs/DECISIONS.md` — the six ADRs and what each forbids.
- `docs/RAPORT_STANU_2026-08-02.md` — owner-facing audit (Polish) this delta was
  extracted from. Not required reading for implementation.
- `PROJECT_LEDGER.md` — the owner's decision queue. **12 open questions**;
  #14 (logging accept/reject of engine proposals) and #16 (entry point) are the
  two that block work.

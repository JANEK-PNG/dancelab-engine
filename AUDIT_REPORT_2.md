# DanceLab Engine — Audit #2 (Delta / Remediation Verification)

**Date:** 2026-07-08 · **Baseline reference:** `AUDIT_REPORT.md` (Audit #1)
**Method:** ticket-by-ticket verification of Audit #1 backlog + 1 dedicated QA reviewer on the new desktop/host surface. Read-only; no code changed. (Environment was repaired minimally to run tests: removed a corrupt stale `dancelab` copy from site-packages.)

---

## 0. Headline

**Codex did not work the Audit #1 backlog. It built forward instead** (Qt desktop app, node-shell, desktop bundle, new host routes, 4 new runtime executors). Result: **~0/18 backlog tickets fixed directly** (C1 partially closed as a side effect), all 7 HIGH bugs still live, **plus 2 new HIGH defects shipped in the new surface behind a silently-skipping test suite**.

### Test/lint baseline

| Metric | Audit #1 | Audit #2 |
|---|---|---|
| Tests | 224 pass / 1 env-fail / 1 skip | **233 pass / 1 env-fail / 7 skip** |
| Skips | 1 | 7 — **all Qt UI tests silently skip** (see NEW-M1) |
| Ruff | clean | **3 errors** (all in new `host/desktop_app.py`) |
| Git | none | **STILL NONE** (at ~21k LOC now) |

---

## 1. Audit #1 backlog — ticket status

| Ticket | Status | Evidence |
|---|---|---|
| **ENV-1** editable install | ❌ **WORSE** | `.pth` hidden again; venv rebuilt on **Homebrew Python 3.12** whose global `sitecustomize` shadows the local workaround; a corrupt stale `dancelab` copy (folders `api 2`, `data 3` — Finder-dup corruption) sat in site-packages shadowing `src` (removed during this audit). Tests still need `PYTHONPATH=src`. |
| **ENV-2** demucs test | ❌ open | `test_vocals.py:128` still hard-asserts `_demucs_available() is True`. |
| **AUD-C1** node-host 40 vs 8 | 🟡 **PARTIAL** | Runtime grew to 12 executors incl. the DJ path (`build_set`, `export_rekordbox`, `recommend_next`) — and they **reuse the same engine functions as the CLI** (verified, no fork). But: 41 contract nodes → 12 runnable, 8 `planned`, **21 ghost** (declared, not runnable, not planned); several ghosts are marked `implemented` in the contract JSON. **No contract==runtime test** (DoD unmet). See NEW-M3. |
| **AUD-H1** Camelot `-2`→risky | ❌ open | `harmonic.py:73-74` unchanged (`(nb-na)%12==2` only). |
| **AUD-H2** microtiming no-op filter | ❌ open | `microtiming.py:61` still `tolerance = 0.5 * beat_period`. |
| **AUD-H3** API drops `bpm_hint` | ❌ open | No `bpm_hint` anywhere in `routes_tracks.py`. |
| **AUD-H4** kendall τ (0.0 + τ-a) | ❌ open | `dj_decision_metrics.py:88` unchanged; zero-variance still yields `0.0`. |
| **AUD-H5** no API build/export + no e2e test | 🟡 partial | Still **no** `POST /sets/build` / `/sets/export-rekordbox`. However `test_host_runtime.py` now chains real `build_set → build_rekordbox_xml` (a genuine integration test at the host level — the real-audio e2e T-2 still missing). |
| **AUD-H6** schema_version | ❌ open | zero grep hits. |
| **AUD-H7** "swap"/locks | ❌ open | `set_builder.py` has no lock/pin/re-solve. |
| **AUD-M1** vocals silence-gate median | ❌ open | `vocals.py:127` unchanged. |
| **AUD-M2** beatgrid fabricates 120 | ❌ open | `beatgrid.py:101` unchanged. |
| **AUD-M3** key "C major" on degenerate | ❌ open | docstring-only mitigation, unchanged. |
| **AUD-M4** normalization crashes on empty | ❌ open | no guard added. |
| **AUD-M5** set_builder tie non-determinism | ❌ open | `for cand in remaining:` (unsorted set) unchanged. |
| **AUD-M6** sequence weights 1.24 + clip | ❌ open | verified live: positive weights still sum 1.24; `np.clip(raw,0,1)` still saturates. |
| **AUD-M7** artifact_store no utf-8 | ❌ open | no `encoding=` in `artifact_store.py`. |
| **AUD-M8** decision-layer duplication | ❌ open | triplicated BPM logic + `next_track`/`sequence` twin toolkits unchanged. |
| **AUD-M9** dead params (`context_id`, `title/artist`, `random_seed`) | ❌ open | all still threaded/accepted and unused. |
| **AUD-M10** formula_terms gaps | ❌ open | 0 hits for sequence/set_builder component keys. |
| **T-1…T-13** test gaps | ❌ open | none added (T-2 partially mitigated by host runtime chain test, synthetic-data only). |

**Score: 0 fixed · 2 partial (as side effects of new features) · 19 open · ENV-1 regressed.**

---

## 2. NEW findings (the surface Codex built since Audit #1)

New mass: `host/` 3,769 LOC (desktop_app.py **2,433** LOC single file, runtime 809, bundle 493), `api/routes_host.py`, `api/routes_contracts.py`, changed `sequence/edge_decision/blend_profile/pilot_pack/swipe_review/decision_report`.

### HIGH

#### NEW-H1 — `desktop_app.py:1600,1606` — `AnalysisResult` used but never imported → guaranteed `NameError`
`_track_choices_for_input` does `isinstance(payload, AnalysisResult)` but the module never imports it (ruff F821). Called from inspector-building code (lines 1786, 1861, 1903, 1933, 1970) on every `_sync_inspector()`. After any flow runs, upstream ports hold real `AnalysisResult` objects.
**Scenario:** run upload→analyze→select_pair, click the `select_pair`/`recommend_next` node → inspector rebuild → `NameError`, inspector dies. Ships untested because the Qt suite silently skips (NEW-M1).
**Fix:** `from dancelab.core.models import AnalysisResult`. **DoD:** ruff F821 clean; a Qt test exercises the inspector after a flow.

#### NEW-H2 — `desktop_app.py:2392-2416` — graph execution blocks the Qt UI thread
No `QThread`/`QRunnable`/`QThreadPool` anywhere in the file. `run_flow` calls one `processEvents()` **before** work, then `self.runtime.run(...)` inline — which drives `analyze_track` (seconds-to-minutes per track).
**Scenario:** 10 tracks → Analyze → Run: UI frozen for minutes, macOS "app not responding", no progress, no cancel.
**Fix:** move `runtime.run` to a worker thread + progress signal + cancel. **DoD:** UI stays responsive during a multi-track analysis; a test asserts the worker path is used.

### MEDIUM

#### NEW-M1 — `test_host_qt_app.py:38-59` — Qt tests silently skip even with PySide6 installed
The bootstrap probe imports `PySide6.QtWidgets` directly and never imports `dancelab.host.desktop_app` — the only place `QT_PLUGIN_PATH` is configured (desktop_app.py:25-31). Probe fails (`offscreen` plugin not found) → **all 7 UI tests skip**, on the exact surface carrying NEW-H1/H2. PySide6 6.11.1 is present; `desktop_available()` returns True; suite still reports `sssssss`.
**Fix:** probe must reuse desktop_app's Qt env setup; CI should fail (not skip) when PySide6 is present but the probe dies. **DoD:** the 7 tests run headless (offscreen) on this machine.

#### NEW-M2 — AUD-M6 regression persists in changed file
`sequence.py` was modified in this period yet the 1.24-sum + clip saturation was not touched. (Tracked above; listed here because the file was actively edited around it.)

#### NEW-M3 — contract `status` semantics drift (extends AUD-C1)
- `telemetry_screen` marked `adapter_needed` yet fully executable (contract **understates**).
- `recommend_sequence`, `transition_windows`, `mixability`, `context_evaluate`, `set_function`, `decision_report`, `validation_pack`, 7 `*_sensor` nodes marked `implemented` yet **not host-executable** → runtime raises "does not execute node X yet" (contract **overstates**; `/contracts/node-host` JSON misleads consumers).
- No test references `SUPPORTED_NODE_IDS`.
Mitigation: the UI itself honestly shows "runtime does not execute this node". The lie is in the contract JSON, not the UI.
**Fix:** add a host-executability field (or align statuses) + a test: every node is runnable, `planned`, or explicitly `engine_only`. **DoD:** contract==runtime test green.

### LOW

- **NEW-L1** `desktop_app.py:64` — `QSpinBox` unused import (F401). (Note: `QTreeWidgetItem` **is** used — Audit-brief guess corrected.)
- **NEW-L2** `desktop_bundle.py:316` — hardcoded `/tmp/{stem}.__sanitized__.app` salvage path (world-writable, predictable). Use `tempfile.mkdtemp()`.

### Verified clean on the new surface (do not "fix")

- **ADR-003 holds in reverse:** no core/decision/feature module imports Qt/FastAPI/`dancelab.host`; host depends inward only; no circular imports.
- **Runtime executors reuse engine functions** (`build_set`, `build_rekordbox_xml`, `recommend_next`) — no forked logic; honest `RuntimeError` surfacing.
- **`test_host_runtime.py` is a real behavioral test** (chains actual build_set→XML; asserts payloads/config/XML).
- **`/host/node-shell` + `/contracts/node-host`:** fixed developer-authored asset, no user input in path/HTML → no traversal/injection.

---

## 3. Systemic / machine-level observation (for IT, not Codex)

The corrupt `dancelab` copy in site-packages contained Finder-style duplicate folders (`api 2`, `data 3`) — the **same " 2" duplication pattern** previously found (and cleaned) in the Obsidian vault. Combined with macOS instantly re-applying `UF_HIDDEN` to freshly created `.pth`/`sitecustomize.py` files (com.apple.provenance), this machine has a sync/provenance process actively corrupting dev artifacts. Recommend: identify the sync agent (iCloud Desktop sync is the prime suspect — the repo lives on `~/Desktop`), and/or **move the repo off `~/Desktop`**, and put the venv outside any synced folder. This is the root cause behind ENV-1 recurring three times.

---

## 4. Recommended order for the next work session

1. **`git init` + baseline commit. Non-negotiable now.** Three audits, ~21k LOC, zero version control, on a machine with an active file-corruption pattern.
2. **Move repo/venv off the synced folder** (kills the ENV-1 family at the root).
3. **NEW-H1, NEW-H2** — the two shipping defects in the new app (one-line import; threading refactor).
4. **NEW-M1** — un-skip the Qt suite (it would have caught NEW-H1).
5. **Then execute Audit #1 backlog in its original order** (§5 of AUDIT_REPORT.md) — it is still 100% valid: H1–H4 result-changing bugs, H5–H7 v1 blockers, M1–M10.
6. Rule going forward: **no new feature layers until the HIGH backlog is empty** (this period added 2 new HIGHs while fixing 0).

*End of Audit #2.*

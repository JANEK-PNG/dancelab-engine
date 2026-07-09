# DanceLab Engine — Engineering Audit & Remediation Backlog

**Audience:** implementation agent (Codex) + IT
**Type:** read-only audit → actionable ticket backlog
**Date:** 2026-07-08
**Repo:** `/Users/jantrybus/Desktop/AI/dancelab-engine`
**Method:** 5 independent read-only reviewers (4 QA by domain + 1 staff full-stack). Every finding below was verified against running code.

> This document changes **nothing**. It is a work order. Do not start fixing until you have read "How to work this backlog" at the bottom.

---

## 0. Baseline (measured at audit time)

| Metric | Value |
|---|---|
| Tests | **224 passed, 1 failed (env-only), 1 skipped** |
| Lint | `ruff check src tests` → clean |
| Source | 98 `.py` files, ~17.7k LOC |
| Tests | 37 files, ~4.8k LOC |
| VCS | **no git repo** (initialize one before remediation) |

The single failing test is environment-coupled, not a code defect (see ENV-1).

---

## 1. Environment issues (fix FIRST — they block clean CI)

### ENV-1 — Editable install is broken; tests only run with `PYTHONPATH=src`
- **Symptom:** `.venv/bin/python -m pytest` fails to import `dancelab` unless `PYTHONPATH=src` is set. 2 of 5 reviewers hit this independently.
- **Root cause:** macOS re-applies `UF_HIDDEN` (com.apple.provenance) to uv's editable `.pth` in `.venv/lib/.../site-packages`; Python 3.12 `site.py` silently skips hidden `.pth`. A prior `sitecustomize.py` workaround was wiped by a Codex venv reinstall.
- **Fix:** recreate the editable install cleanly, OR re-add `sitecustomize.py` in site-packages that inserts the `src` path (immune to file flags), OR switch to a `src`-layout install that doesn't rely on the flagged `.pth`. Add a `conftest.py`/CI step that guarantees import without env hacks.
- **DoD:** `.venv/bin/python -m pytest` passes from repo root with no `PYTHONPATH` override.

### ENV-2 — `demucs`/`torch` not installed → 1 test fails
- **Symptom:** `tests/test_vocals.py::test_auto_method_prefers_demucs_when_available` asserts `_demucs_available() is True`; fails when the `[vocals]` extra is absent.
- **Fix:** the test asserts machine state, not behavior — gate it with `pytest.importorskip("demucs")` or mark it optional. (Also see L-07.)
- **DoD:** suite is green whether or not `[vocals]` is installed.

---

## 2. Findings — severity-ranked ticket backlog

Severity: **CRITICAL** (blocks product goal / contract lie) · **HIGH** (wrong result or broken guarantee) · **MEDIUM** (edge-case honesty / consistency) · **LOW** (polish).

---

### CRITICAL

#### AUD-C1 — Node-host contract declares 40 nodes; runtime implements 8
- **Component:** desktop host / contracts
- **Files:** `src/dancelab/contracts/node_host.py` (declares `analyze_tracks, build_set, export_rekordbox, recommend_next, recommend_sequence, mixability, transition_windows, decision_report, edge_decision` + ~30 sensor/screen/filter nodes); `src/dancelab/host/runtime.py` (handlers only for `analyze_tracks, edge_decision, engine, select_context, select_pair, select_track, telemetry_screen, upload_tracks`).
- **Problem:** the desktop host **cannot run its own advertised `build_set → export_rekordbox` flow** — the exact DJ product goal. Contract-vs-runtime overclaim; `tests/test_node_host_contract.py` does not assert runtime coverage, so nothing flags it. This is an ADR-005 violation in spirit (advertising capability that does not run).
- **Fix (choose one):**
  1. Implement the missing DJ-path handlers (`build_set`, `export_rekordbox`, `recommend_next`, `recommend_sequence`) in `host/runtime.py`; **or**
  2. Mark undelivered nodes `status: planned` in the contract and add a test asserting **every declared node is either executable or explicitly `planned`**.
- **DoD:** a test proves contract == runtime (no node is declared-but-silently-dead). If DJ-path nodes are implemented, an integration test runs `build_set`→`export_rekordbox` through the host.

---

### HIGH

#### AUD-H1 — Camelot `-2` move mis-classified as `risky` (asymmetric with `+2`)
- **Component:** decision / harmonic
- **File:** `src/dancelab/decision/harmonic.py:74-75`
- **Problem:** `harmonic_relation` tags only `(nb - na) % 12 == 2` as `cautious`; the mirror move (`na - nb == 2`, distance-2 downward) falls through to `risky`.
  - `8A→6A` → `risky`, score **0.15**, risk **0.80**
  - `6A→8A` → `cautious`, score **0.60**, risk **0.40**
  Both are `camelot_distance == 2`. `risky` is documented as "large jump / clash" — distance-2 is neither.
- **Blast radius:** feeds `mixability.S_harmonic`, `set_builder.transition_score` (harmonic is the **highest-weighted term, 0.35**), `next_track`, `edge_decision`/`rules` harmonic gate + "risky key change" warning.
- **Repro:** `build_set` on a library where the good next track sits at `-2` (8A→6A) — scored ~0.16 below the identical `+2` neighbor, can flip the greedy pick, emits false "echo-out" warning.
- **Fix:** treat both distance-2 same-mode moves symmetrically. Decide intent: if `-2` is an energy-drop analog of `+2`'s energy-lift, both should be `cautious` (or a documented `energy_drop`/`energy_boost` pair) with matched magnitude — not one at 0.60 and the mirror at 0.15.
- **DoD:** `harmonic_relation("8A","6A")` and `("6A","8A")` are symmetric in class/score/risk (or the asymmetry is intentional and documented). Add the missing `-2` test (see AUD-H1-T).

#### AUD-H2 — Microtiming off-beat filter is a no-op
- **Component:** features / DSP
- **File:** `src/dancelab/features/microtiming.py:61`
- **Problem:** `tolerance = 0.5 * beat_period`; mask keeps onsets with `|deviation| <= tolerance`. For a regular grid the nearest-beat distance is **always** ≤ `0.5·beat_period`, so the filter admits everything — including exact off-beats. Docstring claims "keep only near-beat events"; it does the opposite.
- **Verified:** onsets exactly on off-beats (0.25, 0.75, …) vs beats (0.0, 0.5, …) → 7/7 kept, deviation 0.25s each. In `microtiming_profile` (line 100, tolerance `0.18·beat_period`) those `0.5·bp` deviations divide to >2.0 and **saturate the proxy to 1.0**.
- **Impact:** any track with strong off-beat hats/stabs reports maximal, meaningless microtiming variance.
- **Fix:** near-beat gate needs tolerance ~`0.1–0.2·beat_period` (not 0.5).
- **DoD:** off-beat-only onsets are excluded; a syncopated track no longer saturates the proxy. Add test "offbeat onsets are excluded" (AUD-H2-T).

#### AUD-H3 — API `/tracks/analyze` silently drops `bpm_hint` → API ≠ CLI
- **Component:** api
- **Files:** `src/dancelab/api/routes_tracks.py:57-62` (does not forward `request.bpm_hint`); `src/dancelab/cli/analyze.py:49-51` (does pass `bpm_hint`); `src/dancelab/api/schemas.py:30` (field validated then discarded).
- **Problem:** a BPM hint changes beat tracking → BPM/beatgrid/features. So **API analyze ≠ CLI analyze whenever a hint is supplied**, violating the pipeline DoD ("CLI and API return identical results").
- **Repro:** `POST /tracks/analyze {source_path, bpm_hint: 174}` vs `dancelab analyze x.wav --bpm 174` → different `beatgrid.bpm`.
- **Fix:** forward `request.bpm_hint` (and see AUD-M9 for `title`/`artist`) into `analyze_track`.
- **DoD:** add a test asserting API-analyze == CLI-analyze for the same inputs incl. a hint (AUD-H3-T).

#### AUD-H4 — `kendall_tau`: fabricates `0.0` on zero variance + uses τ-a on tied ratings
- **Component:** validation / metrics
- **File:** `src/dancelab/validation/dj_decision_metrics.py:88-105`
- **Problem A (honesty):** constant input → all pairs tied → `concordant==discordant==0` → returns `0.0`. `spearman_rho` and `rating_correlation` correctly return `None` for the same input. Docstring claims "None when undefined." A DJ who rates every pair the same makes `kendall_tau` report `0.0` ("no association") while ρ correctly abstains.
- **Problem B (wrong variant):** τ-a (denominator `½·n(n−1)` counts ties) systematically attenuates toward 0 on tied data. Verified vs scipy on tied ratings: impl `0.7857` vs scipy τ-b `0.8981`. `pilot_pack._build_mixability_metrics` feeds integer 1–5 DJ ratings (many ties) → reported τ understates agreement.
- **Fix:** return `None` on zero variance (match ρ); switch to **τ-b** (tie-corrected denominator) or rename the output as τ-a and document.
- **DoD:** `kendall_tau([3,3,3,3],[1,2,3,4]) is None`; tied-data τ matches τ-b within tolerance. Add tied + constant tests (AUD-H4-T).

#### AUD-H5 — DJ product loop (set-build + export) is CLI-only; no API, no end-to-end test
- **Component:** api / integration / tests
- **Files:** `build_set` reachable only via `cli/analyze.py::export_rekordbox`; `api/routes_sets.py` exposes only `recommend-next`/`recommend-sequence` (no build/export). No test chains `analyze_track → build_set → build_rekordbox_xml` — `tests/test_set_builder.py:22`, `test_rekordbox_export.py:18`, `test_sequence.py:43` all build `AnalysisResult` by hand.
- **Problem:** the critical path is unit-tested on synthetic data and integration-tested nowhere; the two product surfaces (CLI, API) are not at parity.
- **Fix:** add `POST /sets/build` and `POST /sets/export-rekordbox` delegating to the **same** `set_builder`/`export` functions the CLI uses.
- **DoD:** API and CLI produce identical set + XML for the same corpus; one real end-to-end test exists (AUD-H5-T: two short real audio files → analyze → build_set → XML → assert valid XML with cues).

#### AUD-H6 — No schema versioning / migration for stored analyses
- **Component:** storage
- **Files:** `src/dancelab/storage/repositories.py`, `artifact_store.py:24` (bare `model_cls.model_validate(json.loads(...))`); `pipeline.py:315` writes `engine_version`/`weights_version` but load never checks them; decision-layer feature fields keep being added via `model_copy` (`pipeline.py:150-161`).
- **Problem:** any new **required** field silently breaks every previously-analyzed track (defeats the whole "no re-analysis" promise); any new **optional** field = silent capability drift with no warning. No `schema_version`, no migration.
- **Fix:** add `schema_version` to `AnalysisResult`; `FileAnalysisRepository.get` warns/migrates on mismatch.
- **DoD:** loading an old-schema JSON produces a clear warning or migration, never a silent crash/drift. Test with a fixture of an older payload.

#### AUD-H7 — "Swap" (a headline product verb) does not exist
- **Component:** decision / product
- **Files:** `src/dancelab/decision/set_builder.py` (pure greedy chain, only `start_track_id` override); the only `swap` tokens are `bass_swap`/`tops_swap` blend enums (`core/models.py:172`).
- **Problem:** product goal is "upload → order → **swap** → export." There is no reorder/lock/pin/re-solve capability, and no re-export-after-edit path. v1 as described cannot ship.
- **Fix:** `build_set` accepts locked positions (`{index: track_id}`) and re-solves free slots; expose re-export without re-analysis.
- **DoD:** given a set + a locked swap, the engine returns a valid re-ordered set honoring the lock; API/CLI can re-export it.

---

### MEDIUM

#### AUD-M1 — Vocals silence-gate fails when >50% of frames are silent
- **File:** `src/dancelab/features/vocals.py:127`
- **Problem:** `floor = 0.05 * np.median(m_energy)`; if >50% frames are silent, `median==0` → `floor==0` → gate never fires → returns ratio **1.0** across the silent tail (the exact fake peak the gate exists to kill).
- **Fix:** use percentile-of-nonzero or an absolute floor.
- **DoD:** a 90%-silent mix returns ~0 in silent regions. Add test with median==0.

#### AUD-M2 — Beatgrid fabricates 120 BPM on untrackable/silent audio (ADR-005)
- **File:** `src/dancelab/preprocessing/beatgrid.py:90-101`
- **Problem:** `bpm = round(bpm,2) if bpm>0 else 120.0`. Silence → `BeatGrid(bpm=120.0, beat_times=[], downbeats=[])`. A confident 120.0 with zero beats is a fake number; `BeatGrid` has no confidence/`unknown` flag so downstream can't distinguish it from a real 120.
- **Fix:** signal unknown (e.g. `bpm=None` or a confidence field) when no beats found.
- **DoD:** silence → beatgrid marked unknown, not 120. Add test.

#### AUD-M3 — Key detection returns "C major / 8B" on degenerate/zero chroma
- **File:** `src/dancelab/features/key.py:50-56`
- **Problem:** all-zero correlation → stable sort leaves root-0/major first → `("C major","8B",0.0)`. Mitigated by `confidence==0.0`, but `key_name` is still a positive claim.
- **Fix:** return a neutral sentinel (e.g. `None`/"unknown") when confidence is ~0, or require callers to check confidence and add a test enforcing it.
- **DoD:** zero chroma → key is unknown/None, not "C major".

#### AUD-M4 — `normalization` crashes on empty input (breaks "never NaN" promise)
- **File:** `src/dancelab/core/normalization.py:20-35`
- **Problem:** `minmax_01(np.array([]))` → `ValueError`; `robust_01(np.array([]))` → `IndexError`. Empty descriptor series (short/edge tracks) crash instead of returning empty/neutral.
- **Fix:** guard empty input → return empty array.
- **DoD:** both functions handle `np.array([])` without raising. Add test.

#### AUD-M5 — `build_set` non-deterministic on score ties (contradicts docstring)
- **File:** `src/dancelab/decision/set_builder.py:103,126-135`
- **Problem:** docstring says "Deterministic for fixed input order," but inner loop iterates `for cand in remaining` (a `set` of strings) with strict `if score > best_score`. Set iteration order varies with `PYTHONHASHSEED` (verified: same 5 ids → 3 different orders across seeds).
- **Fix:** iterate `sorted(remaining)` or break ties explicitly (e.g. by track_id).
- **DoD:** identical output across `PYTHONHASHSEED` values on tied inputs. Add determinism test.

#### AUD-M6 — Weight-sum normalization inconsistencies
- **Files:** `configs/descriptor_weights.yaml:98-106` + `src/dancelab/decision/sequence.py:587-597` (positive terms sum **1.24**, then `np.clip(raw,0,1)` → saturation, loses resolution); `src/dancelab/descriptors/bass_salience.py:41-46` (positive terms sum **0.90** → output caps at 0.9, can't reach 1.0).
- **Problem:** inconsistent with `mixability` (1.0), `transition_window`/`set_builder`/`groove`/`tension` (1.0). `sequence` saturates; `bass_salience` is compressed.
- **Fix:** renormalize both to positive-sum 1.0 (or document why they differ).
- **DoD:** a weight-sum invariant test covers every config group.

#### AUD-M7 — `artifact_store` omits `encoding="utf-8"` → crash on non-UTF-8 locale
- **File:** `src/dancelab/storage/artifact_store.py:19,24`
- **Problem:** `write_text`/`read_text` without `encoding`. `model_dump_json` emits raw non-ASCII/emoji (`Café`, `🎵`). On Windows cp1252 (common DJ/Rekordbox platform) `save_json` raises `UnicodeEncodeError` — breaks CLI `analyze -o`, `batch`, and API `save()`. `write_rekordbox_xml` already pins utf-8; this store does not.
- **Fix:** add `encoding="utf-8"` to both.
- **DoD:** round-trip of an emoji/accented title works regardless of locale. Add test.

#### AUD-M8 — Duplicated logic across decision modules (Codex sprawl)
- **Files:**
  - BPM half/double implemented **3×**: `set_builder.py:38 bpm_score`, `next_track.py:173 _tempo_continuity_score` (identical math), `rules.py:87 best_bpm_relation` / `rules.py:104 best_effective_bpm`.
  - `next_track.py` & `sequence.py` each define `_dedupe, _mean_feature, _weighted_mean, _series_slope, _role_stage, _transition_windows` + an identical `_ROLE_STAGE` dict; role-progression scoring near-identical. `sequence.py` (977 LOC) grew from `next_track.py` (598 LOC) by copy-paste.
- **Problem:** a tempo-policy change must be made in 3 places or they diverge; maintenance hazard.
- **Fix:** make `rules.py` the canonical BPM home; extract shared helpers into `decision/_common.py`.
- **DoD:** one implementation each; call sites updated; tests still green.

#### AUD-M9 — Dead parameters: `context_id`, `title`/`artist`, `random_seed`
- **Files:** `pipeline.py:329-343` + `cli/analyze.py:43,50` (`context_id` threaded in, never used — analyze-time conditioning `X_eff = X_audio·C_fit` is a no-op; conditioning only happens at decision time); `api/schemas.py:26-27` (`title`/`artist` accepted, `analyze_track` has no such params → always filename-derived); `core/config.py:44` (`random_seed` never consumed — no `np.random.seed` anywhere; determinism relies on being seed-free).
- **Problem:** three advertised knobs are silent no-ops (misleading contract).
- **Fix:** either wire each through or remove it and document. For conditioning: decide analyze-time vs decision-time and make the flag match reality.
- **DoD:** no accepted parameter is silently ignored.

#### AUD-M10 — `formula_terms.yaml` misses `set_builder`/`sequence` components (anonymous variables)
- **Files:** `configs/formula_terms.yaml` vs `configs/descriptor_weights.yaml`
- **Problem:** contract says "every weighted component resolves to an entry here." Missing: `set_builder.weights` keys `bpm`, `mixability`; all `sequence.weights` keys (`pair_score, local_arc, global_arc, lookahead_arc, terminal_arc, set_memory, transition_quality, risk_penalty`). Nothing enforces the mapping.
- **Fix:** add term entries for meta/orchestration scores, or document a "meta-score exemption" and add a test enforcing coverage of non-exempt groups.
- **DoD:** a test asserts formula_terms covers every non-exempt descriptor_weights key.

---

### LOW

- **AUD-L1** `preprocessing/segmentation.py:65-90` — tail-merge can drop the `outro` label when the last edge segment is shorter than `min_len_sec` (folded without relabel). `test_preprocessing.py:96` passes only because its tail is large.
- **AUD-L2** `mixability.py:332`, `transition_windows.py:150-152`, `set_builder.py:87` — direct `w[name]` lookups (not `.get`) → `KeyError` at scoring time if a config key is dropped. Contrast `sequence._sequence_weights` (merges over defaults).
- **AUD-L3** `export/rekordbox.py:79 vs 90` — `AverageBpm` (`track.bpm_estimate`) and `TEMPO Bpm` (`beatgrid.bpm`) can diverge under a bpm_hint → confusing grid in Rekordbox.
- **AUD-L4** `export/rekordbox.py:76` — `TotalTime` uses `int()` truncation (300.9→"300"); `round()` is more faithful. Cosmetic.
- **AUD-L5** `export/rekordbox.py:37-42` — empty `Location` when `source_path` is None; Rekordbox silently skips. Edge-only.
- **AUD-L6** `export/rekordbox.py:87` — single `TEMPO` node (constant-tempo assumption); wrong for tempo-automated tracks, undocumented in the exporter.
- **AUD-L7** `context/conditioning.py:122-128` — `_infer_role` dead branch (`hour<1` unreachable under the `0–2==peak` catch); hours `3:00–3:59` fall through to `builder`.
- **AUD-L8** `next_track.py:531-546` / `models.py:451-459` — per-candidate `ScoredOutput` has `status`+`confidence`+`explanation` but no `cannot_claim`/provenance (only at the enclosing recommendation object). Honesty-thin if surfaced alone.
- **AUD-L9** `descriptors/release.py:44` — `np.gradient(tension, times)` unguarded against duplicate/non-monotonic `times` (inf/NaN). Latent; callers pass monotonic times.
- **AUD-L10** `annotation_loader.py:139-142` — blank `segment_type`/`window_type` becomes `""` not the model default `"unknown"`.
- **AUD-L11** `false_positive_rate` (`dj_decision_metrics.py:49-61`) returns `0.0` for empty `engine_windows` (arguably-undefined case returns a value).

---

## 3. Test-coverage gaps (add alongside fixes)

| ID | Gap |
|---|---|
| T-1 | No API-analyze == CLI-analyze test (masked AUD-H3) |
| T-2 | No end-to-end analyze→build_set→export on real audio (AUD-H5) |
| T-3 | Camelot `-2` direction untested (`test_set_builder.py:47` only tests `+2`) — masked AUD-H1 |
| T-4 | No `build_set` determinism test despite docstring claim (AUD-M5) |
| T-5 | No weight-sum invariant test for any config group (masked AUD-M6) |
| T-6 | `kendall_tau`/`spearman_rho` honest-None + tie paths untested (masked AUD-H4) |
| T-7 | `cohen_kappa` has **no unit test at all** |
| T-8 | Only `example_track_analysis.json` is schema-tested; mixability/set_function/transition_windows examples untested |
| T-9 | `microtiming_profile`/`syncopation_profile` untested (masked AUD-H2) |
| T-10 | Silence/empty paths untested (masked AUD-M1/M2/M4) |
| T-11 | No non-ASCII/emoji round-trip test for `save_json` (masked AUD-M7) |
| T-12 | No formula_terms↔weights coverage test (masked AUD-M10) |
| T-13 | No node-host contract==runtime test (masked AUD-C1) |

---

## 4. What is confirmed CORRECT (do not "fix")

- ADR-003 layering: `core/features/descriptors/context/decision/ingestion/preprocessing/stems` import **zero** FastAPI/typer/api/cli. Lazy audio imports respected.
- Single-entry pipeline (`core/pipeline.py::analyze_track`) used by CLI + API.
- ADR-005 provenance/501/E4 discipline at top-level outputs (all 10 engine keys have model cards, capped E4/`to_validate`); no overclaim strings emitted.
- DSP math verified: RMS (`amp/√2`), half-wave spectral flux + cross-block stitching, LFER/bass band ratios, Krumhansl `np.roll` direction, full 24-entry Camelot map (bijective), `_refit_beats` phase-preserving subdivide/decimate, pulse autocorrelation.
- Core metrics verified vs scipy: Cohen κ, Spearman ρ (rank-transform+Pearson), Pearson r, IoU/overlap, top-k.
- **Rekordbox XML is import-safe** (schema, `file://localhost/` URI + percent-encoding incl. emoji/`#`/accents, cue `Num` 0–7 with ≤8 cap, XML escaping, `Tonality` omitted when key is None). Verified end to end.
- Heavy-work gating: `stems.enabled=false` default → no torch/demucs on the default path; `vocal_method=hpss` default keeps analyze fast.

---

## 5. Recommended remediation order

1. **ENV-1, ENV-2** — green CI without env hacks (prerequisite for everything).
2. **AUD-C1 + AUD-H5** — contract==runtime; API `POST /sets/build` + `/export`; **one real end-to-end test**.
3. **AUD-H1, AUD-H2, AUD-H4** — the three real result-changing bugs (Camelot `-2`, microtiming no-op, Kendall τ).
4. **AUD-H3** — API `bpm_hint` parity.
5. **AUD-M1–M4** — edge-case honesty (silence/empty → unknown, never fabricate).
6. **AUD-H6, AUD-H7** — `schema_version` + "swap": the two v1 blockers.
7. **AUD-M5–M10** — determinism, normalization consistency, encoding, de-duplication, dead params.
8. **LOW** — batch as cleanup.

Add the corresponding T-* test with each fix (TDD: write the failing test first).

---

## 6. How to work this backlog

- **Init git first.** `git init`, commit the current state as the audited baseline, branch per ticket.
- **One ticket = one small PR.** Reference the AUD-ID in the commit.
- **TDD:** each fix lands with the T-* test that would have caught it (write it failing first).
- **Preserve honesty discipline (ADR-005):** never replace a missing/degenerate result with a confident fake — return `unknown`/`None`/neutral + warning. Several HIGH/MEDIUM findings are the same theme.
- **Don't expand the decision tower** until pair scores have a validation signal (docs/risks.md R1/R13). Fix and de-duplicate what exists; hold new layers.
- **After each ticket:** `ruff check src tests` + full `pytest` must stay green.

*End of report.*

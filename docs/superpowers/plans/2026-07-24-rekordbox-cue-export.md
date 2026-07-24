# Rekordbox Cue Export (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Executor here is Klaris, inline, **stopping for Janek's approval after each STAGE**.

**Goal:** Write DanceLab transition intelligence into Rekordbox as hot cues, via a pure planner + a safety-owning writer + a CLI, built on the proven `master.db` write path.

**Architecture:** Two layers. `decision/cue_plan.py` (pure: SetPlan + analyses → CuePlan, no I/O) and `ingestion/rekordbox_cue_writer.py` + `ingestion/rb_backup.py` (all I/O + safety). CLI `dancelab cues` ties them. Reuses `decision/transition_cues.py` for mix-in/out points.

**Tech Stack:** Python 3.12, pydantic v2, pyrekordbox 0.4.4, typer, pytest, PyYAML, uv.

## Global Constraints

- Export NEVER writes BPM or beatgrid — cues only. (Invariant test required.)
- ADR-005 honesty: never fabricate a point. `window_only` → placed but flagged unverified; never silently dropped, never silently faked. No beat-count when a beatgrid is unreliable.
- Writer never touches live automatically; live swap is the DJ's own hand (harness blocks `~/Library/Pioneer/` writes). Tests run only on throwaway copy DBs.
- Rekordbox MUST be closed for any write. Writer aborts if a rekordbox process is running.
- Pad↔Kind mapping (proven): memory cue Kind=0; pads A/B/C = Kind 1/2/3; pad D..H = pad_index+1 (Kind=4 reserved).
- Run tests with `.venv/bin/pytest` from `~/Developer/dancelab-engine`.
- Commit style ends with the Co-Authored-By trailer.

---

## File Structure

- Create `src/dancelab/decision/cue_export_models.py` — enums + pydantic models (PlannedCue, TrackCuePlan, CuePlan, CueContentMode, ConflictAction).
- Create `src/dancelab/decision/cue_labels.py` — default label map + YAML loader + comment render.
- Create `configs/cue_labels.yaml` — shipped defaults (colors + comment templates).
- Create `src/dancelab/decision/cue_plan.py` — the pure planner.
- Create `src/dancelab/ingestion/rb_backup.py` — rolling/capped/dedup backups + manifest + restore.
- Create `src/dancelab/ingestion/rekordbox_cue_writer.py` — apply CuePlan to a master.db (safety, atomic, verify).
- Create `src/dancelab/cli/cues.py` — `dancelab cues write|restore` typer app.
- Modify `src/dancelab/cli/__init__.py` (or main app) — register the `cues` sub-app.
- Tests: `tests/test_cue_export_models.py`, `tests/test_cue_labels.py`, `tests/test_cue_plan.py`, `tests/test_cue_conflict.py`, `tests/test_rb_backup.py`, `tests/test_rekordbox_cue_writer.py`.

---

## STAGE 1 — Foundations (models, pad mapping, labels config)

### Task 1: Enums + models + pad mapping

**Files:**
- Create: `src/dancelab/decision/cue_export_models.py`
- Test: `tests/test_cue_export_models.py`

**Interfaces:**
- Produces: `CueContentMode`, `ConflictAction`, `PlannedCue`, `TrackCuePlan`, `CuePlan`, `pad_index_to_kind(int)->int`, `kind_to_pad_index(int)->int|None`, `PAD_NAMES`.

- [ ] **Step 1: Write failing test**
```python
# tests/test_cue_export_models.py
from dancelab.decision.cue_export_models import (
    pad_index_to_kind, kind_to_pad_index, PlannedCue, CueContentMode,
)

def test_pad_kind_mapping_reserves_kind4():
    assert [pad_index_to_kind(i) for i in range(1, 9)] == [1, 2, 3, 5, 6, 7, 8, 9]
    assert kind_to_pad_index(5) == 4
    assert kind_to_pad_index(4) is None  # reserved

def test_planned_cue_defaults_confident_true():
    c = PlannedCue(content_id="1", position_ms=1000, kind=1, pad_label="A",
                   color=-1, comment="MIX IN", cue_type="mix_in")
    assert c.confident is True
```

- [ ] **Step 2: Run — expect FAIL** (`.venv/bin/pytest tests/test_cue_export_models.py -v`) → ModuleNotFoundError.

- [ ] **Step 3: Implement**
```python
# src/dancelab/decision/cue_export_models.py
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

PAD_NAMES = "ABCDEFGH"

class CueContentMode(str, Enum):
    none = "none"
    in_out = "in_out"
    structural = "structural"

class ConflictAction(str, Enum):
    skip = "skip"
    replace = "replace"
    merge = "merge"

def pad_index_to_kind(pad_index: int) -> int:
    """pad_index 1..8 (A..H) → Rekordbox Kind. Kind=4 reserved."""
    if not 1 <= pad_index <= 8:
        raise ValueError(f"pad_index out of range: {pad_index}")
    return pad_index if pad_index <= 3 else pad_index + 1

def kind_to_pad_index(kind: int) -> int | None:
    """Inverse of pad_index_to_kind; None for reserved/memory kinds (0, 4)."""
    if kind in (0, 4):
        return None
    return kind if kind <= 3 else kind - 1

class PlannedCue(BaseModel):
    content_id: str
    position_ms: int = Field(ge=0)
    kind: int
    pad_label: str
    color: int = -1
    comment: str = ""
    cue_type: str = "mix_in"     # mix_in|mix_out|drop|breakdown|phrase|unverified
    confident: bool = True
    reasoning: list[str] = Field(default_factory=list)

class TrackCuePlan(BaseModel):
    content_id: str
    track_title: str = ""
    cues: list[PlannedCue] = Field(default_factory=list)

class CuePlan(BaseModel):
    mode: CueContentMode = CueContentMode.in_out
    tracks: list[TrackCuePlan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run — expect PASS**.
- [ ] **Step 5: Commit** `feat(cues): cue-export models + pad/kind mapping`.

### Task 2: cue_labels config + loader + comment render

**Files:**
- Create: `src/dancelab/decision/cue_labels.py`, `configs/cue_labels.yaml`
- Test: `tests/test_cue_labels.py`

**Interfaces:**
- Produces: `load_cue_labels(path: Path | None = None) -> dict[str, dict]`, `render_comment(template: str, beats: int | None) -> str`, `DEFAULT_CUE_LABELS`.
- Note: default `color` values start at `-1` (RB default, proven safe). Real palette values are derived from the DJ's own DB in Task 11 (Stage 5) and written into `configs/cue_labels.yaml` then — no fabricated RGBs here.

- [ ] **Step 1: Write failing test**
```python
# tests/test_cue_labels.py
from dancelab.decision.cue_labels import load_cue_labels, render_comment, DEFAULT_CUE_LABELS

def test_render_comment_omits_beats_when_none():
    assert render_comment("MIX OUT → next{beats}", None) == "MIX OUT → next"
    assert render_comment("MIX OUT → next{beats}", 32) == "MIX OUT → next (32 beats)"

def test_defaults_have_all_cue_types():
    for t in ("mix_in", "mix_out", "drop", "breakdown", "phrase", "unverified"):
        assert t in DEFAULT_CUE_LABELS
        assert "color" in DEFAULT_CUE_LABELS[t] and "comment" in DEFAULT_CUE_LABELS[t]

def test_user_override_wins(tmp_path):
    import yaml
    p = tmp_path / "labels.yaml"
    p.write_text(yaml.safe_dump({"mix_in": {"comment": "IN!!!"}}))
    labels = load_cue_labels(p)
    assert labels["mix_in"]["comment"] == "IN!!!"
    assert labels["mix_out"]["comment"] == DEFAULT_CUE_LABELS["mix_out"]["comment"]  # untouched
```

- [ ] **Step 2: Run — expect FAIL**.

- [ ] **Step 3: Implement**
```python
# src/dancelab/decision/cue_labels.py
from __future__ import annotations
from pathlib import Path
import yaml

DEFAULT_CUE_LABELS: dict[str, dict] = {
    "mix_in":     {"color": -1, "comment": "MIX IN"},
    "mix_out":    {"color": -1, "comment": "MIX OUT → next{beats}"},
    "drop":       {"color": -1, "comment": "DROP"},
    "breakdown":  {"color": -1, "comment": "BREAKDOWN"},
    "phrase":     {"color": -1, "comment": "PHRASE"},
    "unverified": {"color": -1, "comment": "⚠ check by ear"},
}

def render_comment(template: str, beats: int | None) -> str:
    if "{beats}" not in template:
        return template
    return template.replace("{beats}", f" ({beats} beats)" if beats is not None else "")

def load_cue_labels(path: Path | None = None) -> dict[str, dict]:
    merged = {k: dict(v) for k, v in DEFAULT_CUE_LABELS.items()}
    if path is not None and Path(path).exists():
        user = yaml.safe_load(Path(path).read_text()) or {}
        for cue_type, overrides in user.items():
            merged.setdefault(cue_type, {})
            merged[cue_type].update(overrides or {})
    return merged
```
```yaml
# configs/cue_labels.yaml — DanceLab cue label defaults (editable).
# color: Rekordbox hot-cue color; -1 = Rekordbox default. Real palette values
# are pinned from the user's own DB during implementation (plan Task 11).
mix_in:     { color: -1, comment: "MIX IN" }
mix_out:    { color: -1, comment: "MIX OUT → next{beats}" }
drop:       { color: -1, comment: "DROP" }
breakdown:  { color: -1, comment: "BREAKDOWN" }
phrase:     { color: -1, comment: "PHRASE" }
unverified: { color: -1, comment: "⚠ check by ear" }
```

- [ ] **Step 4: Run — expect PASS**.
- [ ] **Step 5: Commit** `feat(cues): cue_labels config + loader + comment render`.

**⛔ STAGE 1 CHECKPOINT — stop, report, await "dalej".**

---

## STAGE 2 — Planner: in-out mode

### Task 3: `plan_cues` for in-out mode (with honesty)

**Files:**
- Create: `src/dancelab/decision/cue_plan.py`
- Test: `tests/test_cue_plan.py`

**Interfaces:**
- Consumes: `SetPlan` (`.transitions: list[SetTransition]`), a `dict[str, AnalysisResult]` by track_id, per-track `list[TransitionWindow]`, `cue_labels` dict, `CueContentMode`.
- Produces: `plan_cues(set_plan, *, analyses, windows_by_track, labels, mode) -> CuePlan`.
- Reuses: `decision.transition_cues.build_transition_cue` → `TransitionCue` (fields `a_out_start_sec`, `b_in_start_sec`, `b_cue_source`, `mix_duration_beats`, `requires_manual_listen`, `confidence`).
- Pad rule (in-out): MIX IN → pad A (index 1, Kind 1); MIX OUT → pad B (index 2, Kind 2).

- [ ] **Step 1: Write failing test** (fixtures build a 2-track SetPlan; A has a mix_out window, B a mix_in window; both beatgrids reliable):
```python
# tests/test_cue_plan.py
from dancelab.core.models import (
    SetPlan, SetTransition, TransitionWindow, WindowType, AnalysisResult, BeatGrid,
)
from dancelab.decision.cue_plan import plan_cues
from dancelab.decision.cue_labels import DEFAULT_CUE_LABELS
from dancelab.decision.cue_export_models import CueContentMode

def _analysis(track_id, reliable=True):
    return AnalysisResult(track_id=track_id,
                          beatgrid=BeatGrid(bpm=120.0, reliable=reliable))

def _set():
    return SetPlan(track_order=["A", "B"],
                   transitions=[SetTransition(from_track_id="A", to_track_id="B",
                                              transition_score=0.8, harmonic_relation="adjacent")])

def test_in_out_places_mixout_on_A_and_mixin_on_B():
    windows = {
        "A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
        "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.9, window_type=WindowType.mix_in)],
    }
    plan = plan_cues(_set(), analyses={"A": _analysis("A"), "B": _analysis("B")},
                     windows_by_track=windows, labels=DEFAULT_CUE_LABELS,
                     mode=CueContentMode.in_out)
    by_track = {t.content_id: t for t in plan.tracks}
    a_out = [c for c in by_track["A"].cues if c.cue_type == "mix_out"]
    b_in = [c for c in by_track["B"].cues if c.cue_type == "mix_in"]
    assert a_out and a_out[0].pad_label == "B" and a_out[0].position_ms == 300000
    assert b_in and b_in[0].pad_label == "A" and b_in[0].position_ms == 30000

def test_window_only_is_flagged_unverified_not_dropped():
    windows = {"A": [TransitionWindow(start_sec=300.0, end_sec=316.0, score=0.9, window_type=WindowType.mix_out)],
               "B": [TransitionWindow(start_sec=30.0, end_sec=46.0, score=0.5, window_type=WindowType.mix_in)]}
    plan = plan_cues(_set(), analyses={"A": _analysis("A"), "B": _analysis("B")},
                     windows_by_track=windows, labels=DEFAULT_CUE_LABELS, mode=CueContentMode.in_out)
    b_in = [c for c in next(t for t in plan.tracks if t.content_id == "B").cues if c.cue_type == "mix_in"][0]
    assert b_in.confident is False
    assert "check by ear" in b_in.comment
```
(If `AnalysisResult`/`BeatGrid` require more mandatory fields, the test fixtures add them minimally — verify actual required fields with `grep -n "class AnalysisResult\|class BeatGrid" -A20 src/dancelab/core/models.py` before writing.)

- [ ] **Step 2: Run — expect FAIL**.

- [ ] **Step 3: Implement** `plan_cues` (in-out branch only for now):
```python
# src/dancelab/decision/cue_plan.py
from __future__ import annotations
from dancelab.core.models import SetPlan, TransitionWindow, WindowType, AnalysisResult
from dancelab.decision.transition_cues import build_transition_cue
from dancelab.decision.cue_labels import render_comment
from dancelab.decision.cue_export_models import (
    CuePlan, TrackCuePlan, PlannedCue, CueContentMode, pad_index_to_kind, PAD_NAMES,
)

def _mk_cue(content_id, position_sec, pad_index, cue_type, labels, confident, beats=None):
    label = labels.get(cue_type, {})
    base = label.get("comment", cue_type)
    comment = render_comment(base, beats) if confident else \
        labels.get("unverified", {}).get("comment", "⚠ check by ear")
    color = label.get("color", -1) if confident else labels.get("unverified", {}).get("color", -1)
    return PlannedCue(
        content_id=str(content_id), position_ms=int(round(position_sec * 1000)),
        kind=pad_index_to_kind(pad_index), pad_label=PAD_NAMES[pad_index - 1],
        color=color, comment=comment, cue_type=cue_type, confident=confident,
    )

def plan_cues(set_plan: SetPlan, *, analyses: dict[str, AnalysisResult],
              windows_by_track: dict[str, list[TransitionWindow]],
              labels: dict, mode: CueContentMode) -> CuePlan:
    plan = CuePlan(mode=mode, tracks=[], warnings=[])
    if mode == CueContentMode.none:
        return plan
    cues_by_track: dict[str, list[PlannedCue]] = {tid: [] for tid in set_plan.track_order}

    for tr in set_plan.transitions:
        a, b = tr.from_track_id, tr.to_track_id
        an_a, an_b = analyses.get(a), analyses.get(b)
        if an_a is None or an_b is None:
            plan.warnings.append(f"missing analysis for {a}->{b}; skipped")
            continue
        tc = build_transition_cue(
            tr, analysis_a=an_a, analysis_b=an_b,
            windows_a=windows_by_track.get(a, []), windows_b=windows_by_track.get(b, []),
            user_cues_b=None,
        )
        if tc.a_out_start_sec is not None:
            cues_by_track.setdefault(a, []).append(
                _mk_cue(a, tc.a_out_start_sec, 2, "mix_out", labels,
                        confident=tc.mix_duration_beats is not None, beats=tc.mix_duration_beats))
        if tc.b_in_start_sec is not None:
            confident = tc.b_cue_source == "rekordbox_hotcue" or not tc.requires_manual_listen
            cues_by_track.setdefault(b, []).append(
                _mk_cue(b, tc.b_in_start_sec, 1, "mix_in", labels, confident=confident))

    for tid in set_plan.track_order:
        title = getattr(analyses.get(tid), "title", "") or ""
        plan.tracks.append(TrackCuePlan(content_id=str(tid), track_title=title,
                                        cues=cues_by_track.get(tid, [])))
    return plan
```

- [ ] **Step 4: Run — expect PASS**.
- [ ] **Step 5: Commit** `feat(cues): pure planner, in-out mode with honesty flags`.

**⛔ STAGE 2 CHECKPOINT.**

---

## STAGE 3 — Planner: structural mode

### Task 4: structural landmarks (drop / breakdown / phrase)

**Files:**
- Modify: `src/dancelab/decision/cue_plan.py`
- Test: `tests/test_cue_plan.py` (add cases)

**Interfaces:**
- Consumes: `AnalysisResult.segments` (verify shape via `grep -n "class Segment\|segments" -A8 src/dancelab/core/models.py`). Structural cues occupy pads C.. (index 3+), after in-out on A/B.
- Produces: structural branch inside `plan_cues` when `mode == CueContentMode.structural`.

- [ ] **Step 1: Write failing test** — a track whose analysis has a labeled "drop" segment yields a `drop` cue on pad C at the segment start; in-out cues still present.
```python
def test_structural_adds_drop_on_pad_C():
    # build analyses where "B" has a segment labeled drop at 60s; reuse _set()/_analysis
    # assert a cue with cue_type=="drop", pad_label=="C" at 60000ms exists on B
    ...
```
(Fill segment construction from the real `Segment` model discovered above.)

- [ ] **Step 2: Run — expect FAIL**.
- [ ] **Step 3: Implement** structural branch: after in-out placement, for each track iterate its analysis segments, map segment kind → cue_type (drop/breakdown/phrase), assign next free pad index starting at 3, skip if pads exhausted (append warning). Beat-count never fabricated.
- [ ] **Step 4: Run — expect PASS**.
- [ ] **Step 5: Commit** `feat(cues): structural-mode landmarks`.

**⛔ STAGE 3 CHECKPOINT.**

---

## STAGE 4 — Conflict engine + report

### Task 5: conflict detection + resolution (skip/replace/merge, dedup, empty-pad)

**Files:**
- Create: `src/dancelab/decision/cue_conflict.py`
- Test: `tests/test_cue_conflict.py`

**Interfaces:**
- Consumes: a `CuePlan`, plus `existing_by_track: dict[str, list[ExistingCue]]` where `ExistingCue` = `{pad_index:int|None, position_ms:int, comment:str}` (a plain pydantic model defined here; the writer adapts DjmdCue rows into it).
- Produces: `ExistingCue`, `ConflictItem`, `ConflictReport`, `resolve_conflicts(plan, existing_by_track, *, action: ConflictAction, review: bool, pos_tolerance_ms: int = 750) -> tuple[CuePlan, ConflictReport]`.
- Rules: conflict = target pad occupied OR our cue within `pos_tolerance_ms` of an existing cue. `merge` relocates ours to next free pad, and dedups (drops ours) when position matches an existing within tolerance. `skip` drops ours on conflict. `replace` marks the existing pad for overwrite (report only; writer performs deletion). `review=True` marks ALL cues (even clean) as `needs_decision` in the report.

- [ ] **Step 1: Write failing tests**
```python
# tests/test_cue_conflict.py
from dancelab.decision.cue_conflict import resolve_conflicts, ExistingCue
from dancelab.decision.cue_export_models import CuePlan, TrackCuePlan, PlannedCue, ConflictAction

def _plan_one(pad_label="A", kind=1, pos=30000):
    return CuePlan(tracks=[TrackCuePlan(content_id="B", cues=[
        PlannedCue(content_id="B", position_ms=pos, kind=kind, pad_label=pad_label, cue_type="mix_in")])])

def test_merge_relocates_to_free_pad_on_pad_conflict():
    existing = {"B": [ExistingCue(pad_index=1, position_ms=15000, comment="INTRO")]}
    plan2, report = resolve_conflicts(_plan_one(), existing, action=ConflictAction.merge, review=False)
    cue = plan2.tracks[0].cues[0]
    assert cue.pad_label != "A" and cue.kind != 1     # moved off pad A
    assert report.conflict_count == 1

def test_merge_dedups_same_position():
    existing = {"B": [ExistingCue(pad_index=2, position_ms=30200, comment="mine")]}
    plan2, report = resolve_conflicts(_plan_one(pos=30000), existing, action=ConflictAction.merge, review=False)
    assert plan2.tracks[0].cues == []                 # ours dropped as duplicate

def test_skip_drops_our_cue():
    existing = {"B": [ExistingCue(pad_index=1, position_ms=15000, comment="INTRO")]}
    plan2, _ = resolve_conflicts(_plan_one(), existing, action=ConflictAction.skip, review=False)
    assert plan2.tracks[0].cues == []

def test_no_conflict_passes_through():
    plan2, report = resolve_conflicts(_plan_one(), {"B": []}, action=ConflictAction.merge, review=False)
    assert len(plan2.tracks[0].cues) == 1 and report.conflict_count == 0
```

- [ ] **Step 2: Run — expect FAIL**.
- [ ] **Step 3: Implement** `cue_conflict.py`: `ExistingCue`/`ConflictItem`/`ConflictReport` pydantic models; `resolve_conflicts` iterating each track's planned cues against existing (occupied pad indices + positions), applying the action, choosing next free pad for merge via `pad_index_to_kind`, dedup within tolerance, populating the report (`conflict_count`, `overwrite_count`, per-item detail, `needs_decision` when review).
- [ ] **Step 4: Run — expect PASS**.
- [ ] **Step 5: Commit** `feat(cues): conflict resolution (skip/replace/merge + dedup)`.

### Task 6: conflict report renderer

**Files:**
- Modify: `src/dancelab/decision/cue_conflict.py` (add `render_report(report) -> str`)
- Test: `tests/test_cue_conflict.py` (add)

- [ ] **Step 1: Test** — `render_report` produces the OS-style block: track name, pad wanted, existing cue, action options, and a summary line `N cues to write · M conflicts · K overwrites`.
- [ ] **Step 2: Run — FAIL**. **Step 3: Implement** the string renderer. **Step 4: PASS**. **Step 5: Commit** `feat(cues): conflict report renderer`.

**⛔ STAGE 4 CHECKPOINT.**

---

## STAGE 5 — Writer + backups + safety

### Task 7: backup manager (rolling, capped, dedup, manifest, restore)

**Files:**
- Create: `src/dancelab/ingestion/rb_backup.py`
- Test: `tests/test_rb_backup.py`

**Interfaces:**
- Produces: `backup_master(db_path, backup_dir, *, cap=10, timestamp: str, meta: dict) -> Path | None` (None if dedup skip), `list_backups(backup_dir) -> list[dict]`, `restore_backup(backup_dir, db_path, *, timestamp: str) -> Path`.
- `timestamp` is passed in (never `Date.now()` inside) for testability. Dedup via sha256 vs newest backup. Cap prune deletes oldest `master_*.db` beyond `cap`. Manifest is `backup_dir/manifest.json` (list of `{timestamp, file, sha256, meta}`).

- [ ] **Step 1: Tests** — (a) first backup creates file + manifest entry; (b) second identical backup returns None (dedup); (c) after >cap distinct backups, oldest files pruned and manifest trimmed; (d) restore copies the chosen backup over db_path.
```python
# tests/test_rb_backup.py — uses tmp_path, writes small fake db bytes
def test_dedup_skips_identical(tmp_path):
    from dancelab.ingestion.rb_backup import backup_master
    db = tmp_path / "master.db"; db.write_bytes(b"AAAA")
    bdir = tmp_path / "bk"
    assert backup_master(db, bdir, timestamp="20260724_1200", meta={}) is not None
    assert backup_master(db, bdir, timestamp="20260724_1201", meta={}) is None
```

- [ ] **Step 2: Run — FAIL**. **Step 3: Implement** (shutil.copy2, hashlib.sha256, json manifest, sorted prune). **Step 4: PASS**. **Step 5: Commit** `feat(cues): rolling capped dedup backups + manifest`.

### Task 8: cue insert primitive (pyrekordbox, on copy)

**Files:**
- Create: `src/dancelab/ingestion/rekordbox_cue_writer.py` (part 1)
- Test: `tests/test_rekordbox_cue_writer.py` (part 1)

**Interfaces:**
- Produces: `insert_hot_cue(db, *, content_id, content_uuid, position_ms, kind, color, comment) -> int` (returns new cue ID). Uses the proven recipe: clone-free construction via `tables.DjmdCue`, `db.generate_unused_id`, `InFrame=round(position_ms*0.15)`, `OutMsec=-1`, `db.autoincrement_usn(set_row_usn=True)`, `db.commit()`.
- Test precondition: needs a real Rekordbox DB. Use a **session-scoped copy** of `~/Library/Pioneer/rekordbox/master.db` into `tmp_path` — SKIP the test (pytest.skip) if that file is absent (so CI without RB still passes).

- [ ] **Step 1: Test** — copy master.db to tmp, insert one cue on the first track, reopen fresh, assert cue present with correct InMsec/InFrame/Kind. `pytest.importorskip("pyrekordbox")` + skip if no master.db.
- [ ] **Step 2: Run — FAIL/skip-aware**. **Step 3: Implement** `insert_hot_cue`. **Step 4: PASS**. **Step 5: Commit** `feat(cues): pyrekordbox hot-cue insert primitive`.

### Task 9: apply CuePlan with safety (guard, backup, atomic, verify, restore)

**Files:**
- Modify: `src/dancelab/ingestion/rekordbox_cue_writer.py`
- Test: `tests/test_rekordbox_cue_writer.py` (add)

**Interfaces:**
- Produces: `is_rekordbox_running() -> bool`, `write_plan(plan: CuePlan, *, db_path: Path, backup_dir: Path, timestamp: str, safe_swap: bool = False) -> WriteResult` where `WriteResult` reports `written`, `backup_path`, `verified`, `restored`.
- Behavior: abort (raise) if `is_rekordbox_running()`; backup first; open db; apply all cues; on any exception rollback (`db.rollback()`) and restore newest backup; verify post-write cue count == pre + planned; checkpoint WAL. `replace` deletions (from conflict resolution) executed here. `safe_swap=True` → operate on a temp copy then `shutil.move` over db_path.

- [ ] **Step 1: Tests** (on tmp copy) — (a) `write_plan` adds N cues and `verified is True`; (b) forcing a failure (monkeypatch insert to raise on 2nd cue) leaves cue count unchanged (atomic rollback) and `restored is True`; (c) `is_rekordbox_running` monkeypatched True → raises before any write/backup.
- [ ] **Step 2: Run — FAIL**. **Step 3: Implement**. **Step 4: PASS**. **Step 5: Commit** `feat(cues): safe atomic write_plan with verify + auto-restore`.

### Task 10: invariant test — never writes BPM/beatgrid

**Files:** Test: `tests/test_rekordbox_cue_writer.py` (add)
- [ ] **Step 1: Test** — after `write_plan` on a tmp copy, the target track's `BPM`/beatgrid-related fields (`DjmdContent` bpm, `DjmdBeatGrid` if touched) are byte-identical to pre-write snapshot. **Step 2: FAIL if regression**. **Step 3: (already satisfied by design; assert it)**. **Step 4: PASS**. **Step 5: Commit** `test(cues): assert export never writes BPM/beatgrid`.

### Task 11: pin real Rekordbox color palette into cue_labels.yaml

**Files:** Modify: `configs/cue_labels.yaml`; Test: `tests/test_cue_labels.py` (add a value-sanity check)
- [ ] **Step 1:** Query distinct `Color`/`ColorTableIndex` values from the DJ's existing colored cues in a master.db copy; map DanceLab cue-types to distinct RB-valid colors (mix_in/out one, structural another, unverified a third). **Step 2:** Write them into `configs/cue_labels.yaml`. **Step 3:** Test asserts each cue-type color is an int and distinct across the semantic groups. **Step 4: PASS**. **Step 5: Commit** `feat(cues): pin Rekordbox color palette for cue labels`.

**⛔ STAGE 5 CHECKPOINT.**

---

## STAGE 6 — CLI + end-to-end

### Task 12: `dancelab cues write|restore` CLI

**Files:**
- Create: `src/dancelab/cli/cues.py`
- Modify: register sub-app (verify main app location: `grep -rn "typer.Typer\|add_typer" src/dancelab/cli/`)
- Test: `tests/test_cli_cues.py`

**Interfaces:**
- Consumes: everything above. Produces typer commands:
  - `write --set <file> --mode in-out --on-conflict merge [--review] [--dry-run] [--safe-swap] [--labels <yaml>] [--db <path>]`
  - `restore --list` / `restore --to <timestamp>`
- `--dry-run` renders the plan + conflict report, writes nothing. Default `--db` = live master.db path, but the command NEVER writes it unless invoked without `--dry-run`; even then the harness blocks live writes, so real use is `--db <copy>` or the DJ runs the printed swap. Loads SetPlan from `--set` (reuse existing set serialization; verify format).

- [ ] **Step 1: Test** — `CliRunner` invokes `write --dry-run --set <fixture>` and asserts the plan/report text appears and no DB is created/modified.
- [ ] **Step 2: Run — FAIL**. **Step 3: Implement** the typer app + registration. **Step 4: PASS**. **Step 5: Commit** `feat(cues): dancelab cues write/restore CLI`.

### Task 13: end-to-end on a copy (manual verification gate)

- [ ] **Step 1:** Build a small SetPlan from Janek's real library (reuse `four_tet_playlist` selection), run `dancelab cues write --db <copy> --mode in-out --on-conflict merge`, then Janek swaps the copy into live (his hand) and confirms cues appear in Rekordbox on the set's tracks.
- [ ] **Step 2:** Restore. **Step 3: Commit** `docs(cues): phase-1 end-to-end verified` + ledger DZIENNIK entry + update memory.

**⛔ STAGE 6 CHECKPOINT — Phase 1 done.**

---

## Self-Review notes
- Spec §4 modes → Tasks 3,4 (none handled in Task 3 early-return). §5 conflict skip/replace/merge + dedup + empty-pad/review → Tasks 5,6. §6 honesty → Task 3 (window_only flag) + Task 4 (no fabricated beats). §7 labels/colors/override → Tasks 2,11. §8 backups → Task 7. §9 write flow A + safe-swap → Task 9. §10 testing → every task + Task 10 invariant. §3 CLI → Task 12.
- Type consistency: `PlannedCue`, `CuePlan`, `ConflictAction`, `pad_index_to_kind` used identically across Tasks 1→12. `resolve_conflicts` returns `(CuePlan, ConflictReport)` consumed by CLI dry-run.
- Cleanup noticed (out of scope, flag only): stray iCloud conflict file `src/dancelab/cli/corpus_ordering 2.py`.

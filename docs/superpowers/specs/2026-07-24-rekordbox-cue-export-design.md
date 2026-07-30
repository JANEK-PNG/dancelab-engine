# Rekordbox Cue Export — Design Spec

**Date:** 2026-07-24
**Author:** Klaris (Claude) + Jan Trybus
**Status:** Design approved, pre-implementation
**Related:** `docs/RND_CUE_DELIVERY_USE_CASE.md`, memory `dancelab-cue-write-proven`, `decision/transition_cues.py` (SPEC §13)

---

## 1. Purpose

Write DanceLab's transition intelligence directly into the DJ's Rekordbox library as
hot cues, so the DJ reviews and plays the engine's plan inside Rekordbox with zero
import/USB steps.

**Proven precondition (2026-07-24):** writing hot cues into `master.db` via pyrekordbox
works end-to-end — Rekordbox itself opens the modified DB and displays the cue, no
"repair library" prompt. USN bookkeeping and SQLCipher are handled by pyrekordbox. See
memory `dancelab-cue-write-proven` for the verified recipe. This spec builds the product
layer on top of that proven primitive.

**Hard invariant (unchanged):** export NEVER writes BPM or beatgrid. Cues only.

---

## 2. Scope

### In scope (this spec — Phase 1)
- Content modes: **none**, **in-out**, **structural**
- Conflict actions (OS-style): **skip**, **replace**, **merge** (default)
- Write flow **A** (backup + atomic in-place) with **B** (`--safe-swap`) as a flag
- Rolling, capped, deduplicated backup management with a manifest
- Configurable color-label + auto-description system (defaults + user override)
- Target: **hot-cue pads** (memory-cue target is a later option)

### Out of scope (separate later specs)
- **Tips mode** (mode 4): coaching content ("echo before the drop", "break the pattern"),
  including cues *within* a track, not just between tracks. This is a rules + content
  system of its own — its own spec after Phase 1 ships.
- Memory-cue target (waveform markers instead of pads).
- Simple-Mode UI wiring (Kord's Terrain) — this spec exposes a clean engine + CLI
  contract that the UI can call later.

---

## 3. Architecture — two layers + CLI

Split rationale: **planning is pure, safe, reusable; writing touches the live library and
is dangerous.** Never mix them.

### Layer 1 — Planner (pure, no I/O) · `decision/cue_plan.py`
- **Input:** a built set (ordered tracks + transitions), track analyses, `content_mode`,
  `on_conflict` action (skip / replace / merge), and the resolved `cue_labels` config.
- **Output:** a `CuePlan` — for each track: a list of planned cues
  (`ContentID`, `position_ms`, `pad`/`Kind`, `color`, `comment`, `confidence` flag).
- Reuses `decision/transition_cues.py` (mix-in / mix-out points) and structure segments
  for the structural mode.
- Zero DB access. Fully unit-testable.

### Layer 2 — Writer (I/O, isolated) · `ingestion/rekordbox_cue_writer.py`
- **Input:** a `CuePlan` + a target `master.db` path.
- Applies the plan via pyrekordbox using the proven recipe.
- **Owns ALL safety:** refuse if Rekordbox is running; take a rolling backup first;
  write inside one transaction (atomic); checkpoint WAL; enforce `write_policy` against
  existing cues; verify cue-count delta; auto-restore newest backup on verify failure.
- Never invoked against live automatically — the live swap is the DJ's own hand
  (the harness also blocks writes to `~/Library/Pioneer/`).

### CLI · `dancelab cues …`
- `dancelab cues write --set <file> --mode in-out --on-conflict merge [--review] [--dry-run] [--safe-swap]`
- `--dry-run` prints the plan (what WOULD be written), zero DB touch. The default first
  step every time.
- `dancelab cues restore --list` → shows backup manifest.
- `dancelab cues restore --to <timestamp>` → restores that backup.

### Rejected alternatives
- Bolting cue-writing onto the existing XML script (`four_tet_playlist.py`): muddles
  pure/IO, not reusable by the UI, hard to test.
- XML-import route: direct `master.db` write is proven and removes the import step. Keep
  XML only as a fallback exporter.

---

## 4. Content modes

| Mode | What it writes |
|------|----------------|
| **none** | Nothing (feature off). |
| **in-out** | Per track: MIX IN (pad A) + MIX OUT (pad B). The seam. |
| **structural** | in-out cues PLUS structural landmarks (drop, breakdown, phrase) on later pads. |
| ~~tips~~ | *(Phase 2)* coaching lines; may sit inside a track. |

**Pad mapping (in-out):** Pad **A** = MIX IN, Pad **B** = MIX OUT. Structural landmarks
occupy later pads (C…). Exact pad↔Kind mapping uses the proven table: memory cue Kind=0;
hot pads A/B/C = Kind 1/2/3; pad D+ = Kind+1 (Kind=4 reserved).

---

## 5. Conflict handling (OS file-copy metaphor)

A **conflict** = a pad we want (e.g. pad A for MIX IN) already holds one of the DJ's
cues, OR our cue lands at ~the same position as an existing one.

On conflict, three actions — modeled on the OS "copy with same name" dialog:

| Action | Behavior |
|--------|----------|
| **skip** | Pad occupied → our cue is not placed there. The DJ's cue stays untouched. |
| **replace** | Overwrite the DJ's cue on that pad with ours. |
| **merge** *(default)* | Keep the DJ's cue; place ours on the next free pad. **Never duplicates:** if our cue equals an existing one (~same position), we do not add a copy — the existing cue stands. |

`merge` is "keep old + add only new" — NOT "keep both copies." Same-position dedup is
part of merge, so re-running the same set never spawns duplicate cues.

The chosen action is the **global default**; each conflict can be overridden individually
(like the OS "apply to all" vs per-file choice).

**Empty pad (no conflict)** — two behaviors, the DJ's choice:
- **auto** *(default)* — empty pad → our cue is written automatically, no prompt.
- **review** (`--review`) — even clean, non-conflicting cues are presented for
  approve/skip before writing. The dry-run report then lists the **whole plan** (clean
  cues + conflicts), each toggleable on/off — a review mode for the cautious or for
  learning. `auto` only prompts on conflicts.

**Same-position tolerance** for dedup/conflict detection: a small window (exact value
pinned in implementation, order of ~0.5–1 s) so a re-run recognizes "already there."

**Conflict report** — surfaced in `--dry-run` first (zero DB touch), so the DJ decides
before anything is written:

```
⚠ CONFLICTS (2 tracks):

  "Skee Mask — Rio Dur"
     pad A  ← want: MIX IN @ 0:32
     pad A  already: your "INTRO" @ 0:15
     → [skip]  [replace]  [merge → pad C]

  "O'Flynn — Tru"
     all pads A–H occupied → merge impossible
     → [skip]  [replace pad B]

Summary: 12 cues to write · 2 conflicts · 0 overwrites at current choice (merge)
```

---

## 6. Honesty rules (ADR-005 — never fabricate)

- Engine confident on an exact point → normal cue.
- Engine has only a *window*, not a precise point (`window_only`) → **still place the cue,
  but with a distinct "unverified" color + comment `⚠ check by ear`.** Never silently
  pretend it is exact; never silently omit it (the DJ would miss the transition).
- Beatgrid unreliable → no beat-count in the comment (no fabricated "32 beats").
- Every planned cue carries a `confidence` flag so the writer and any UI can surface it.

---

## 7. Color-label + auto-description system

A configurable map, shipped with sensible defaults, **fully user-editable** (config file
now; UI later).

**`configs/cue_labels.yaml`** — per cue-type:
```yaml
mix_in:      { color: <rb_color>, comment: "MIX IN" }
mix_out:     { color: <rb_color>, comment: "MIX OUT → next{beats}" }   # {beats} omitted if grid unreliable
drop:        { color: <rb_color>, comment: "DROP" }
breakdown:   { color: <rb_color>, comment: "BREAKDOWN" }
phrase:      { color: <rb_color>, comment: "PHRASE" }
unverified:  { color: <rb_color>, comment: "⚠ check by ear" }
# effect / tip types reserved for Phase 2
```

Principles:
- **Consistent semantic colors** — the same cue-type is always the same color (effects one
  color, mix-in/out their color, unverified its own). A visual language, later aligned
  with the Prism design system.
- **Auto-descriptions** — the engine fills the comment automatically from the template,
  substituting tokens (`{beats}`) only when the underlying data is reliable.
- **User override** — the DJ can edit any color or comment template. Their edits win.

**Rekordbox color constraint:** hot-cue color is stored in `DjmdCue.Color` /
`ColorTableIndex`. Rekordbox supports a fixed small palette; the default map pins to
Rekordbox-valid color values (exact palette confirmed during implementation).

---

## 8. Backup management

**Dedicated folder** (never touches Rekordbox's own `master.backup*.db` rotation):
`~/Library/Pioneer/rekordbox/DanceLab_backups/`

- **Timestamped, not numbered:** `master_YYYYMMDD_HHMM.db`. Natural time sort, no rename
  chains.
- **Rolling cap (default 10, configurable):** after each write, auto-delete the oldest
  beyond the cap. Never infinite.
- **Checksum dedup:** if live `master.db` is byte-identical to the newest backup, skip
  making a duplicate (no spam from re-runs).
- **`manifest.json`:** logs each backup — when · which set · which mode/policy · cue count.
  Restore is "the one before the Four-Tet set at 12:30," not a guess.

---

## 9. Write flow

### A — Backup + atomic in-place (default)
1. Rekordbox running? → **abort** if yes.
2. Snapshot live `master.db` → rolling backup (capped, dedup).
3. Inject the `CuePlan` into live inside **one transaction** (SQLite atomic: crash before
   commit = zero change).
4. Checkpoint WAL; verify cue-count delta matches the plan.
5. Verify fails → **auto-restore newest backup**.

### B — Copy + verify + swap (`--safe-swap`)
Inject into a temp copy, verify on the copy, then swap over live. One extra step, maximum
caution. Recommended for the first real sets. Always takes the rolling backup first too.

---

## 10. Testing

- **Planner (`cue_plan.py`)** — pure unit tests: each mode → expected cue list; each
  policy vs pre-existing cues; honesty flags fire; color/comment resolution incl. user
  overrides and `{beats}` omission. No DB.
- **Writer (`rekordbox_cue_writer.py`)** — against a throwaway copy DB (like the spike):
  backup created; cap pruning; dedup skip; atomic rollback on forced failure; policy
  honored; RB-running guard. Never touches live.
- **Invariant test:** no BPM/beatgrid field is ever written.

---

## 11. Open items (confirm during implementation, not blocking)
- Exact Rekordbox color palette values for the default `cue_labels`.
- Structural-mode pad budget (how many landmarks before pads run out; interaction with
  `merge`).
- Set-file input format the CLI consumes (reuse `set_builder` / `four_tet_playlist`
  output).

# DanceLab Full-Stack Handoff

Status: production-planning baseline

Prepared: 2026-07-28

Repository: `dancelab-engine`

Verified baseline: branch `feature/rekordbox-cue-export`, commit `a9d1b22`

## Start here

This folder is the implementation handoff for the next full-stack build of
DanceLab. It treats the product as one connected system:

1. **DanceLab Pro** prepares the musical decision: brief, analysis, ordered
   `SetPlan` and reviewed `TransitionPlan` revisions.
2. **DanceLab Player** executes an ordered queue automatically. It is available
   as an embedded DanceLab workspace and as a full standalone window.
3. Both Player views control the same `PlaybackSession`, audio device, deck
   state and playhead. They are not separate playback engines.

The Player is source-agnostic. A set may come from DanceLab, a user playlist,
selected files, a folder or a supported external playlist. The Player does
not ask for a brief and does not silently choose or reorder the repertoire.

The architectural invariant is:

> Before playback, **WITH WHAT** comes from Set Architect or explicit user
> order, while the transition layer resolves **WHERE + HOW**. The result is an
> ordered `PlaybackSet` with versioned `TransitionPlan` revisions. Preview,
> live playback, offline rendering and Rekordbox export consume those plans
> without silently re-deciding the repertoire.

## Reading order

| Document | Purpose |
|---|---|
| [01_PRODUCT_SCOPE.md](01_PRODUCT_SCOPE.md) | Product vision, modes and boundaries |
| [02_CURRENT_STATE.md](02_CURRENT_STATE.md) | Verified codebase baseline and gaps |
| [03_TARGET_ARCHITECTURE.md](03_TARGET_ARCHITECTURE.md) | Target modules and dependency rules |
| [04_TRANSITION_PLAN_CONTRACT.md](04_TRANSITION_PLAN_CONTRACT.md) | Canonical execution contract |
| [05_API_AND_FRONTEND.md](05_API_AND_FRONTEND.md) | API, job model and client workspaces |
| [06_PRODUCTION_PLAN.md](06_PRODUCTION_PLAN.md) | Ordered implementation milestones |
| [07_RUNBOOK_AND_TESTS.md](07_RUNBOOK_AND_TESTS.md) | Setup, verification and acceptance gates |
| [08_DECISIONS_AND_RISKS.md](08_DECISIONS_AND_RISKS.md) | Fixed decisions, open questions and risks |
| [09_RESEARCH_CONTEXT.md](09_RESEARCH_CONTEXT.md) | Demucs, Vocos and commercial reference context |
| [10_PLAYER_PRODUCT_FLOW.md](10_PLAYER_PRODUCT_FLOW.md) | Canonical embedded/standalone Player flow and diagrams |
| [11_DDJ_FLX4_CONTROL_MAP.md](11_DDJ_FLX4_CONTROL_MAP.md) | FLX4-based deck, mixer, FX and control-ownership map |

## Delivery target

The first vertical slice is intentionally narrow:

```text
two analyzed local tracks
  -> one EdgeDecision
  -> one persisted TransitionPlan
  -> one rendered preview
  -> one live playback of the same plan
  -> one user revision
  -> one Rekordbox-compatible export
```

The slice is complete only when preview and live playback agree on cue
positions, duration, tempo rates and automation knots, and when opening the
standalone Player preserves the active embedded session without starting a
second audio engine.

## Source-of-truth rule

This handoff distinguishes:

- **CURRENT** — verified in the repository at the baseline above;
- **TARGET** — accepted architecture for implementation;
- **LATER** — intentionally outside the first production slice.

When an older document conflicts with this folder for the AutoMix/player
build, this folder owns the target architecture. Existing model honesty and
validation rules in `docs/architecture.md`, `docs/PRODUCT_SPEC.md` and model
cards remain binding.

# Advanced Tutorial: Validation and Review

## Goal

Use DanceLab as an evaluation system, not just a generator.

At this level the user should be able to:

- inspect engine recommendations
- review them through dedicated host-side surfaces
- compare machine output with human judgment
- produce feedback without polluting the engine itself

## Core Principle

Review tools are external diagnostic surfaces.

They read engine outputs.
They do not redefine the engine.

## Validation Pack

The validation pack is the best advanced entry point because it bundles:

- filtered review sheets
- coverage summary
- honest metrics where labels already exist
- swipe review surfaces

Reference:

- [validation.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/validation.md)

## Workflow A: Build a Validation Pack

Run:

```bash
dancelab validation-pack <processed_dir> --output-dir <output_dir> --annotations-dir <annotations_dir> --report-dir <report_dir>
```

Expected output:

- `validation_pack_summary.json`
- `validation_pack_summary.md`
- `swipe_review/`

Pass check:

- the summary exists
- review sheets are generated
- the report is honest about labeled vs unlabeled coverage

## Workflow B: Review Pair Decisions

Use the generated review bundle to inspect:

- pair candidates
- transition windows
- set-function views

At this stage the user is not trying to "trust the score blindly."
They are trying to answer:

- does the recommendation make sense
- where does it feel wrong
- what kind of wrong is it

Pass check:

- the user can reject a pair even when the engine likes it
- the user can explain whether the issue is energy, timing, harmony, or context

## Workflow C: Listen Board

The listen board is a host-side diagnostic surface for A/B comparison.

Use it when you want to judge:

- whether a transition feels right
- whether the candidate entry point is plausible
- whether the recommendation is technically okay but musically weak

Pass check:

- the user can compare at least several recommended pairs
- the user can mark which ones feel truly mixable versus only technically legal

## Workflow D: Control Center

The control center is the live dashboard mindset:

- watch outputs
- inspect warnings
- understand what the system is surfacing

Use it to answer:

- what is the engine producing right now
- which nodes are active
- which outputs look healthy
- where the flow is blocked

Pass check:

- the user can identify whether the issue is an input problem, a flow problem, or a weak recommendation

## Advanced Skill Check

The user passes this level when they can:

- generate a validation pack
- inspect recommendations without confusing host screens with engine logic
- produce structured feedback for later tuning

## Recommended Feedback Buckets

When reviewing advanced outputs, classify failures into one of these:

- `wrong candidate pool`
- `wrong current context`
- `wrong timing window`
- `wrong transition strategy`
- `musically legal but weak`
- `technically blocked`
- `good recommendation`

These buckets are more useful than vague comments like "feels off."

## Next Expansion

When we add more user-facing lessons later, the most natural next advanced
topics are:

- locked re-order / swap workflows
- structured A/B comparison sessions
- export verification against downstream DJ tools

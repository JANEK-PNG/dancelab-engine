# DanceLab Tutorial Library

This folder is the user-facing learning path for DanceLab.

The goal is not only to explain the product, but to let the user verify that
the engine and host behave correctly through guided exercises.

Each tutorial doubles as a bounded test:

- the user performs one concrete workflow
- the engine or host emits a visible result
- the tutorial defines what "pass" looks like
- the user can stop at a level that matches their skill and patience

## Design Rule

Tutorials should move from:

`see -> touch -> run -> judge -> compare -> export`

not from:

`read docs -> read more docs -> maybe run something later`

## Lesson Format

Every lesson in this library should contain:

- `Goal`
- `What you touch`
- `Input`
- `Steps`
- `Expected output`
- `Pass check`
- `Common failure signals`

That keeps the material useful both as onboarding and as regression testing.

## Levels

## Beginner

Beginner lessons teach the mental model:

- what the engine is
- what the guided desktop workflow does
- where analysis is cached
- how to build, review, save, and export a first set

The beginner should not need to understand formulas, weighting, validation
theory, or annotation logic.

## Intermediate

Intermediate lessons teach operational use:

- constrain the analyzed library
- express event and DJ intent
- deep-analyze a shortlist
- validate transitions and export a tangible artifact

This is where DanceLab stops being a demo and starts acting like a real tool.

## Advanced

Advanced lessons teach review and validation:

- inspect pair and window recommendations
- use the listen board and control center
- compare engine suggestions against human judgment
- prepare feedback that can improve the system later

This layer is about disciplined use, not just button-clicking.

## Current Curriculum

| Lesson | Level | Focus | Status |
|---|---|---|---|
| `01_beginner_first_flow.md` | Beginner | First guided set, review, save, export | Ready now |
| `02_intermediate_corpus_set_workflows.md` | Intermediate | Library constraints, intent, deep analysis, validation | Ready now |
| `03_advanced_validation_review.md` | Advanced | Validation pack, review boards, human audit loop | Ready now |

## Recommended User Journey

1. Start with [01_beginner_first_flow.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/01_beginner_first_flow.md).
2. Move to [02_intermediate_corpus_set_workflows.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/02_intermediate_corpus_set_workflows.md).
3. Finish with [03_advanced_validation_review.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/03_advanced_validation_review.md).

## Boundary Reminder

The engine stays clean and headless.

- engine = computes signals and decisions
- DanceLab Pro = guided control surface
- review boards = diagnostics and testing surfaces

That means tutorial material should never imply that a review board is "the
engine." It is a window into the engine.

## Related Docs

- [README.md](/Users/jantrybus/Desktop/AI/dancelab-engine/README.md)
- [DESKTOP_HOST.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/DESKTOP_HOST.md)
- [validation.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/validation.md)

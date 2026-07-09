# Beginner Tutorial: First Flow

## Goal

Understand the difference between the engine, the node host, and a runnable
graph by completing the first working DanceLab flow.

## What You Touch

- the Qt desktop host
- the node library
- the inspector
- one minimal graph

## What You Learn

- the engine is the core, not the UI
- input nodes bring tracks into the system
- compute nodes ask the engine for decisions
- screen nodes display results without changing the engine

## Flow

`Upload Tracks -> Analyze Tracks -> Select Pair -> Edge Decision -> Telemetry Screen`

## Input

Use two short tracks you already know well.

Good beginner choice:

- two tracks with stable 4/4 pulse
- similar tempo range
- clear intros or outros

## Steps

### Exercise 1: Open the host

Run:

```bash
dancelab-host
```

Pass check:

- you see the graph canvas
- the `Engine` node is visible
- the left node library and right inspector are visible

### Exercise 2: Add the first flow

Create or build the minimal graph:

- `Upload Tracks`
- `Analyze Tracks`
- `Select Pair`
- `Edge Decision`
- `Telemetry Screen`

Connect them in order.

Pass check:

- each connection is valid
- no node shows an error before the run

### Exercise 3: Queue two tracks

Select `Upload Tracks`.

Use the inspector to:

- click `Choose Files`, or
- paste one server-visible path per line

Pass check:

- the inspector confirms that 2 files are queued

### Exercise 4: Run the graph

Run the flow from the host.

Expected output:

- `Analyze Tracks` completes
- `Select Pair` resolves `Track A` and `Track B`
- `Edge Decision` produces a decision payload
- `Telemetry Screen` shows score, strategy, profile, and warning summary

Pass check:

- node states end at `done`
- the telemetry screen shows a pair label
- the telemetry screen shows a compatibility score instead of `--`

### Exercise 5: Change the pair

Select `Select Pair` and switch `Track A` and `Track B`.

Run again.

Pass check:

- the graph re-runs cleanly
- the decision can change when the order changes
- you understand that pair direction matters

## What Success Means

The beginner has passed this tutorial when they can explain:

- where tracks enter the system
- which node asks the engine for pair logic
- which node only visualizes output

## Common Failure Signals

- `Upload Tracks is empty`
  Cause: no audio paths were queued
- `Analyze Tracks needs upstream track files`
  Cause: missing connection from `Upload Tracks`
- `Select Pair needs at least two analyzed tracks`
  Cause: only one track was analyzed or analysis failed
- telemetry shows `--`
  Cause: downstream decision did not complete

## What To Do Next

Move to [02_intermediate_corpus_set_workflows.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/02_intermediate_corpus_set_workflows.md).

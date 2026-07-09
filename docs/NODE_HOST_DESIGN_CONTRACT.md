# Node Host Design Contract

## Purpose

This document turns the July 8 designer package into an implementation contract for the DanceLab node host.

The package is a strong fit for the intended direction:

- Blender / Nuke style graph host
- fixed engine core
- attachable nodes and screens
- external diagnostics instead of engine-embedded UI

It should guide the host layer, not redefine engine behavior.

## Source Package

Reviewed package:

- `Engine Graph Concept.dc.html`
- `docs/Design System - Signal Graph.md`
- `docs/Node Interactions - Developer Spec.md`
- `support.js`

## Accepted As-Is

These parts align well with the existing architecture and should be treated as the default direction.

### Visual Language

- Dark, disciplined, professional tool aesthetic
- `IBM Plex Sans` + `IBM Plex Mono`
- restrained single accent strategy
- clear category colors for node families
- dense but readable pro-tool layout

### Host Layout

- top runtime bar
- left node library
- center infinite graph canvas
- right inspector / info panel
- fixed engine node as graph anchor

### Interaction Philosophy

- pan / zoom / drag should feel direct and 1:1
- no soft, floaty, dashboard-like motion
- graph editing should feel closer to DCC tools than to a web report
- typed connections and compatibility hints are core behavior

### Node Taxonomy

The proposed families are correct for the MVP direction:

- `Input`
- `Engine Ops`
- `Sensors`
- `Screens`
- `Utility`

## Required Architectural Corrections

The mockup is very close, but these points must be adjusted to match the DanceLab boundary.

### 1. Boot State

On startup, the canvas should show only the fixed `Engine` node.

Do not pre-place track-specific workflow nodes by default.

This means:

- no auto-mounted `Upload Tracks`
- no implied active session
- no baked-in track list on load

The user should attach an input node when they want to start a run.

### 2. Engine Stays Clean

The node host is a control surface and diagnostics shell.

The engine:

- computes descriptors
- computes pair / edge / sequence decisions
- emits signals, telemetry, and artifact references

The host:

- attaches nodes
- caches session outputs outside the engine
- renders screens
- stores graph state outside the engine

### 3. Screens Are External

`Telemetry Screen`, `Listen Screen`, waveform review, swipe review, and future control-center views must remain host-side screens.

They are not engine modules.

### 4. Placeholder Nodes Need Backend Contracts

Some nodes visible in the design are valid directionally but should be treated as planned placeholders until backed by a stable contract:

- `Blend Curve`
- `Load Corpus`
- `Live Input`
- `Merge`
- `Gate`

They may appear visually in the host library, but only nodes backed by current engine capability should be runnable in the first usable build.

## Mapping To Current Engine Capabilities

The strongest part of the package is that most of the graph already maps to real DanceLab concepts.

### Already Backed

- `Analyze Tracks`
  - maps to the current track analysis pipeline
- `Select Pair`
  - maps to pair selection / validation selection flow
- `Edge Decision`
  - maps to edge decision scoring and blend profile classification
- `BPM Sensor`
  - maps to BPM descriptors / transition tempo context
- `Key Sensor`
  - maps to tonal descriptors / key compatibility context
- `Blend Profile Sensor`
  - maps to current blend profile decision output
- `Telemetry Screen`
  - maps to exported decision summaries and validation dashboards
- `Listen Screen`
  - maps to the external listen-board concept

### Partially Backed

- `Load Corpus`
  - concept exists, but host-facing input contract should be explicit
- `Filter`
  - valid as host-side utility once typed payloads are stabilized
- `Corpus` tab
  - reasonable future panel once corpus manifests are exposed cleanly

### Not Yet Formalized Enough

- `Blend Curve`
  - visually useful, but should not imply real DJ transition synthesis unless the engine exposes a formal curve / swap recommendation contract
- `Live Input`
  - desirable later, but outside the first usable host scope

## MVP Host Build Order

The package should drive implementation in this order.

### Phase A: Shell

- top bar
- left node library
- center graph canvas
- right inspector / info panel
- fixed engine node

### Phase B: Graph Basics

- zoom
- pan
- node drag
- selection
- typed ports
- compatible linking

### Phase C: First Runnable Chain

- `Upload Tracks`
- `Analyze Tracks`
- `Select Pair`
- `Edge Decision`
- `Telemetry Screen`

Optional second branch:

- `Edge Decision -> Listen Screen`

### Phase D: Sensor Layer

- `BPM Sensor`
- `Key Sensor`
- `Blend Profile Sensor`

Sensors should read existing outputs, not trigger new hidden engine behavior.

## Live Data Contract

The host should consume stable outputs, not scrape internal engine state.

Current preferred source:

- telemetry manifest such as `decision_summary.json`

Future preferred source:

- explicit host-facing sensor / telemetry contracts

The host should never depend on undocumented private paths if a manifest or exported contract exists.

## UX Rule

This system is not a report page with prettier panels.

It is a graph host for attaching tools to the engine.

That means the main mental model is:

1. engine exists
2. user attaches input
3. engine emits signals
4. user attaches sensors and screens
5. external tools display results

## Decision

Treat the July 8 design package as the visual and interaction contract for the node host, with the corrections above.

It is approved as the direction for the host layer.

It is not a mandate to move UI state, reports, or test tooling into the engine core.

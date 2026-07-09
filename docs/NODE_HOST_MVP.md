# Node Host MVP

## Goal

Build a node-based control surface around the engine.

The engine stays headless and computes signals.
The node host is a separate layer that lets the user plug screens, tools, and flows into those signals.

This should feel closer to Blender Geometry Nodes, Nuke, or a modular patch graph than to a report viewer.

## Core Rule

- The engine is the center.
- The engine exposes ports and signals.
- Nodes attach to the engine or to other nodes.
- Tracks are not the main UI object on startup.
- Tracks enter the system only when the user plugs in an input node like `Upload Tracks` or `Load Corpus`.
- Screens, previews, dashboards, and exports live outside the engine.

## Canvas Layout

## Center

- Infinite zoom and pan canvas.
- One fixed `Engine` node visible on startup.
- Optional minimap later.

## Left Sidebar

- Search.
- Node categories.
- Drag node onto canvas.

## Right Inspector

- Selected node details.
- Port list.
- Valid connections.
- Quick examples:
  - `Upload Tracks -> Analyze Tracks -> Telemetry Screen`
  - `Select Pair -> Edge Decision -> Listen Screen`
  - `Load Corpus -> Filter -> Sequence -> Export CSV`

## Top Bar

- Run graph.
- Stop graph.
- Save patch.
- Load patch.
- Live status.

## Engine Node

The `Engine` node is static in v1 and acts like the runtime core.

## Engine Inputs

- `tracks_in`
- `context_in`
- `pair_request_in`
- `sequence_request_in`

## Engine Outputs

- `analysis_out`
- `windows_out`
- `mixability_out`
- `edge_decision_out`
- `sequence_out`
- `telemetry_out`

## Port Types

Keep port typing simple and explicit.

- `track_files`
- `track_ids`
- `analysis_set`
- `track_analysis`
- `pair_selection`
- `mixability_result`
- `edge_decision`
- `edge_decision_set`
- `sequence_result`
- `telemetry_snapshot`
- `context_profile`
- `artifact_ref`

Connections should only work when types are compatible.

## Node Categories

## Input

- `Upload Tracks`
- `Load Corpus`
- `Select Track`
- `Select Pair`
- `Select Context`

## Engine Ops

- `Analyze Tracks`
- `Transition Windows`
- `Mixability`
- `Edge Decision`
- `Sequence`

These are wrappers around existing engine capabilities, not new engine logic.

## Sensors

- `BPM Sensor`
- `Key Sensor`
- `Energy Sensor`
- `Risk Sensor`
- `Blend Profile Sensor`
- `Window Sensor`

These nodes read engine outputs and isolate one measurement stream.

## Screens

- `Telemetry Screen`
- `Waveform Screen`
- `Listen Screen`
- `Pair Screen`
- `Warning Console`

These are view nodes only.
They do not compute engine decisions.

## Utility

- `Filter`
- `Sort`
- `Top N`
- `Threshold`
- `Compare`
- `Route`

## Output

- `Export CSV`
- `Export Rekordbox`
- `Save Snapshot`

## MVP v1 Scope

The first usable version should include only a small set of nodes.

## Required v1 Nodes

- `Engine`
- `Upload Tracks`
- `Analyze Tracks`
- `Select Pair`
- `Edge Decision`
- `Telemetry Screen`
- `Listen Screen`
- `Filter`

## First Runnable Graph

`Upload Tracks -> Analyze Tracks -> Select Pair -> Edge Decision -> Telemetry Screen`

Optional second branch:

`Edge Decision -> Listen Screen`

This gives one clean end-to-end path:

1. upload tracks
2. analyze them
3. choose a pair
4. get engine decision
5. view telemetry
6. optionally preview transition diagnostics

## Behavior Model

Nodes should not all auto-run at once in v1.

Use a simple execution model:

- each node shows `idle`, `running`, `done`, or `error`
- running a downstream node pulls from upstream dependencies
- outputs are cached in the node host session
- engine data stays read-only from the perspective of screen nodes

## Informational Helper

The right-side help panel should explain:

- what the selected node does
- what input types it accepts
- what output types it emits
- which nodes are recommended next

Example:

- `Edge Decision`
  - accepts: `pair_selection`
  - emits: `edge_decision`
  - works well with: `Telemetry Screen`, `Listen Screen`, `Blend Profile Sensor`

## Existing Assets To Reuse

Current diagnostic surfaces can later become screen nodes instead of standalone tools:

- `listen_board`
- `waveform board`
- `control center`

In other words:

- do not throw them away
- wrap them as node outputs later
- do not let them define the engine architecture

## Non-Goals For v1

- no full DAW
- no stem-routing graph
- no collaborative multi-user graph
- no plugin marketplace
- no visual scripting language inside nodes

## Implementation Order

1. define node graph schema
2. build static canvas with fixed `Engine` node
3. add left node library and right inspector
4. add drag-drop node creation
5. add typed ports and connections
6. implement first runnable graph
7. attach current telemetry screens as screen nodes

## Success Criteria

The MVP is successful when a user can:

- open the node host
- see the engine in the center
- drag `Upload Tracks` onto canvas
- connect it through analysis and decision nodes
- open a telemetry screen from the graph
- understand valid next connections without reading code

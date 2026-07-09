# Node Dictionary

## Purpose

This is the human-readable companion to the machine contract in
`src/dancelab/contracts/node_host.py`.

Use it to decide which nodes are real now, which ones are host-only helpers,
and which ones are approved placeholders waiting for a cleaner adapter.

## Status Legend

- `implemented`: backed by current engine code or a stable public endpoint
- `adapter_needed`: engine capability exists, but the node wrapper or route is not yet formalized
- `host_only`: belongs to the host shell, not the engine core
- `planned`: approved direction, not yet built

## System

- `Engine`
  - status: `implemented`
  - role: pinned graph anchor
  - boot rule: this is the only node that should exist on an empty canvas

## Input

- `Upload Tracks`
  - status: `host_only`
  - emits: `track_files`
  - role: explicit session start from user-selected audio files

- `Load Corpus`
  - status: `adapter_needed`
  - emits: `track_id_list`, optional `analysis_set`, `dataset_manifest`
  - role: bring analyzed corpus data into the host without auto-starting a session

- `Select Track`
  - status: `host_only`
  - emits: `track_id` or `analysis_result`
  - role: choose one track for single-track engine ops

- `Select Pair`
  - status: `host_only`
  - emits: `track_pair_selection`
  - role: choose an ordered A->B transition candidate

- `Select Context`
  - status: `host_only`
  - emits: `context_profile`
  - role: pick or inject a set context

## Engine Ops

- `Analyze Tracks`
  - status: `implemented`
  - backing: `analyze_track`, `POST /tracks/analyze`
  - emits: `analysis_set`

- `Extract Stems`
  - status: `adapter_needed`
  - backing: `analyze_track_with_stems`, `extract_stems`
  - emits: `analysis_set`, `stem_bundle`, `stem_window_feature_set`

- `Transition Windows`
  - status: `implemented`
  - backing: `detect_transition_windows`, `POST /tracks/{track_id}/transition-windows`
  - emits: `transition_window_set`

- `Mixability`
  - status: `implemented`
  - backing: `compute_mixability`, `POST /pairs/mixability`
  - emits: `mixability_result`

- `Edge Decision`
  - status: `implemented`
  - backing: `build_edge_decision`, `POST /pairs/edge-decision`
  - emits: `edge_decision`, `warning_stream`

- `Context Evaluate`
  - status: `implemented`
  - backing: `evaluate_context`, `POST /contexts/evaluate`
  - emits: `context_evaluation`

- `Set Function`
  - status: `implemented`
  - backing: `classify_set_function`, `POST /tracks/{track_id}/set-function`
  - emits: `set_function_output`

- `Recommend Next`
  - status: `implemented`
  - backing: `recommend_next`, `POST /sets/recommend-next`
  - emits: `next_track_recommendation`, `warning_stream`

- `Recommend Sequence`
  - status: `implemented`
  - backing: `recommend_sequence`, `POST /sets/recommend-sequence`
  - emits: `sequence_decision`, `warning_stream`

- `Build Set`
  - status: `adapter_needed`
  - backing: `build_set`
  - emits: `set_plan`

## Sensors

- `BPM Sensor`
  - status: `implemented`
  - reads: BPM, tempo deltas, effective BPM fields

- `Key Sensor`
  - status: `implemented`
  - reads: key estimates and harmonic relation data

- `Energy Sensor`
  - status: `implemented`
  - reads: energy-profile-like fields from analysis and sequencing outputs

- `Risk Sensor`
  - status: `implemented`
  - reads: risks, warnings, policy flags, guardrails

- `Blend Profile Sensor`
  - status: `implemented`
  - reads: `blend_profile_auto`

- `Window Sensor`
  - status: `implemented`
  - reads: transition timing and selected mix windows

- `Harmonic Sensor`
  - status: `implemented`
  - reads: harmonic relation and harmonic risk

- `Stem Window Sensor`
  - status: `adapter_needed`
  - reads: `stem_window_features`
  - role: later support for stems-aware transition heuristics and review

## Screens

- `Telemetry Screen`
  - status: `adapter_needed`
  - current source: existing validation dashboards and summaries

- `Waveform Screen`
  - status: `adapter_needed`
  - current source: waveform gallery tooling

- `Listen Screen`
  - status: `adapter_needed`
  - current source: external listen board

- `Pair Review Screen`
  - status: `adapter_needed`
  - current source: swipe review tooling

- `Control Center Screen`
  - status: `adapter_needed`
  - current source: control-center diagnostics page

- `Warning Console`
  - status: `planned`
  - role: compact risk and warning monitor

## Utility

- `Filter`
  - status: `planned`

- `Sort`
  - status: `planned`

- `Top N`
  - status: `planned`

- `Threshold`
  - status: `planned`

- `Compare`
  - status: `planned`

- `Route`
  - status: `planned`

These are host nodes only.
They must not push utility state back into the engine.

## Output

- `Decision Report`
  - status: `implemented`
  - backing: `build_decision_report`
  - emits: `telemetry_manifest`, `artifact_bundle`

- `Validation Pack`
  - status: `implemented`
  - backing: `build_validation_pack`
  - emits: `artifact_bundle`

- `Export Rekordbox`
  - status: `implemented`
  - backing: rekordbox XML export
  - emits: `rekordbox_xml`

- `Stem Export`
  - status: `adapter_needed`
  - backing: `export_stem_artifacts`
  - emits: `artifact_bundle`

- `Save Snapshot`
  - status: `planned`
  - role: persist host-side visual state outside the engine

## First Real Host Chains

- `Upload Tracks -> Analyze Tracks -> Select Pair -> Edge Decision -> Telemetry Screen`
- `Upload Tracks -> Analyze Tracks -> Select Pair -> Edge Decision -> Listen Screen`
- `Load Corpus -> Select Track -> Transition Windows -> Waveform Screen`
- `Load Corpus -> Decision Report -> Pair Review Screen`
- `Load Corpus -> Recommend Sequence -> Risk Sensor -> Control Center Screen`

## Non-Negotiable Boundary

Node screens, review boards, players, dashboards, swipe tools, and future host utilities stay outside the engine.

The engine computes.
The host connects.
The screens observe.

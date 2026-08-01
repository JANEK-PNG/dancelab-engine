# Production Plan

The order below protects the contract boundary before investing in a large UI
or real-time engine.

## Phase 0 — Freeze the baseline

Goal: make refactoring measurable.

Deliverables:

- golden fixtures for representative `EdgeDecision` outputs;
- golden preview timing/envelope fixtures;
- characterization tests for preview cache keys and atomic output;
- documented supported Rekordbox cue behavior;
- resolve or formally record the stale desktop-host documentation;
- no behavior change in scoring.

Exit gate:

- existing focused engine suite passes;
- baseline artifacts are committed and reproducible.

## Phase 1 — TransitionPlan foundation

Goal: establish the shared contract.

Deliverables:

- `transitions/models.py`;
- `PlaybackSet` and `PlaybackTrack` input contracts;
- deterministic identity/hash;
- `compiler.py` from current `EdgeDecision`;
- source-runway, rate and curve guardrails;
- JSON repository with atomic save;
- schema/model tests and migration policy;
- minimal `/v1/transitions/compile` and read route.

Exit gate:

- one real A→B pair compiles to stable JSON twice;
- an ordered two-track `PlaybackSet` round-trips without changing order;
- missing evidence produces explicit safety state;
- changed source checksum prevents silent execution.

## Phase 2 — Exact WHERE selection

Goal: choose the best executable seam, not merely the best tracks.

Deliverables:

- `decision/window_pairs.py`;
- explicit A.out × B.in cross-product;
- pair scoring with phrase, tempo, runway and stem-aware collision terms;
- separate measured pair from synthesized fallback;
- chosen pair provenance and alternatives;
- held-out/golden regression set.

Exit gate:

- compiler never rewards a synthesized fallback as measured evidence;
- selected windows are within source bounds;
- unreliable beatgrid paths do not fabricate beat duration.

## Phase 3 — HOW compiler

Goal: convert strategy intent into automation.

Deliverables:

- profile templates moved into `transitions/profiles.py`;
- duration and tempo policy;
- effect allow-list;
- safety/fallback compilation;
- automation validation;
- stable plan hash.

Exit gate:

- every supported strategy compiles or names its supported fallback;
- all curves have ordered knots and bounded values;
- rate/source-runway limits are enforced.

## Phase 4 — Plan-driven preview

Goal: prove the contract through existing DSP.

Deliverables:

- renderer consumes `TransitionPlan`;
- existing `transition_simulation.py` remains a compatibility facade;
- DSP, I/O and cache responsibilities separated;
- render manifest records plan hash and backend versions;
- UI-independent preview API job.

Exit gate:

- old and new path timing/envelopes match for equivalent input;
- atomic render survives interruption without presenting partial output;
- cache invalidates on execution-relevant plan revision.

## Phase 5 — Transition Lab review and revision

Goal: close the user feedback loop.

Deliverables:

- production `TransitionEdit`/revision model outside `validation/`;
- revision repository;
- preview/revise/accept/reject endpoints;
- Transition Lab UI with engine suggestion vs active revision;
- validation adapter consumes product events.

Exit gate:

- edit creates a child revision;
- original plan remains readable;
- reload restores latest accepted revision;
- rejected plan cannot be silently executed by AutoMix.

## Phase 6 — Rekordbox delivery

Goal: export what is representable and report what is not.

Deliverables:

- plan-aware transition cue mapping;
- written-file verification gate;
- DanceLab sidecar manifest;
- capability report;
- Delivery workspace inside DanceLab with error recovery.

Exit gate:

- corrupt/invalid cue XML fails verification;
- every claimed cue exists in the written XML;
- EQ/fader/effect automation is clearly marked sidecar-only.

## Phase 7 — PlaybackSession and embedded Player

Goal: establish one authoritative playback runtime and expose it inside
DanceLab before opening a second window.

Deliverables:

- device and decoder adapters;
- gapless single-deck playback;
- ordered `PlaybackSet` loading;
- queue/history/readiness;
- transport state machine;
- `PlaybackSession` and session service;
- FLX4-inspired `PlayerConsoleState` and control ownership contract;
- prefetch and error/fallback behavior;
- compact embedded Player workspace;
- **Open in Player** attach contract with a placeholder full view;
- M4 latency/underrun benchmark harness.

Exit gate:

- multi-hour local playback without unbounded memory growth;
- pause/seek/skip deterministic;
- device loss/recovery explicit;
- attaching a second view does not restart audio or reset the playhead;
- one session cannot acquire the audio device twice;
- no analysis work on the audio callback.

## Phase 8 — Linked standalone two-deck AutoMix

Goal: execute the ordered queue automatically and show the same live session
in the embedded and standalone Player views.

Deliverables:

- two deck lifecycle;
- sample/beat clock;
- block scheduler;
- shared mixing/automation kernel;
- real-time time-stretch adapter;
- pre-roll and upcoming-plan preparation;
- automatic execution of the fixed ordered queue;
- standalone full console attached by `session_id`;
- P0 FLX4 semantic surface: transport, cue, sync, EQ, faders, crossfader,
  meters, queue and AutoMix controls;
- automatic/manual/pickup control ownership;
- state/event synchronization across both windows;
- playlist/files/folder source adapters for standalone launch;
- visible analysis and transition readiness;
- manual takeover.

Exit gate:

- cue alignment and duration match plan tolerances;
- preview/live automation parity tests pass;
- imported playlist order is preserved;
- folder order is deterministic, visible and never silently optimized;
- commands from either window produce one authoritative event;
- closing one window does not stop or duplicate the active runtime;
- every moving console control is backed by actual runtime state;
- soft takeover prevents discontinuities when manual/hardware input takes over;
- plan failure selects declared fallback;
- manual takeover is immediate and leaves transport coherent;
- benchmark passes on the target MacBook Air M4.

## Phase 9 — Continuous mix renderer

Goal: Apple-like hands-off output from an accepted set plan.

Deliverables:

- timeline composition from track order and transition plans;
- loudness/headroom policy;
- WAV/AIFF output;
- chapter/cue sidecar;
- resumable long render job.

Exit gate:

- output duration and seam positions match manifest;
- no clipping beyond defined policy;
- interrupted job can restart safely.

## Phase 10 — Personalization

Goal: learn the DJ's preferences without corrupting model honesty.

Prerequisites:

- enough accepted/rejected/revised transitions;
- stable event schema;
- held-out evaluation;
- opt-in and reset controls.

Deliverables:

- cue and strategy priors;
- bounded personalization weights;
- explanation of personalized influence;
- rollback and “base engine” comparison.

## Suggested first tickets

1. Add `TransitionPlan` Pydantic contracts and round-trip tests.
2. Add `PlaybackSet` with strict ordered-adjacency invariants.
3. Add deterministic plan/revision identity.
4. Implement compiler for `plain_blend`, `bass_swap`, `tops_swap` and
   `contour_blend`.
5. Add source-runway and playback-rate guardrails.
6. Adapt preview renderer to accept a plan.
7. Persist plans atomically.
8. Add compile/read/render job API.
9. Build a minimal Transition Lab client against one real pair.
10. Record immutable revisions and verdicts.
11. Add preview/plan parity acceptance test.
12. Add `PlaybackSession` with one device owner and controller attachment.
13. Add FLX4-based `PlayerConsoleState` and P0 visual console.
14. Add control ownership, manual takeover and soft-pickup tests.

Do not start the large standalone Player UI before tickets 1–6 establish the
contracts. A compact embedded transport may begin once `PlaybackSet` and
session ownership are fixed.

Physical FLX4 MIDI support is a separate ticket after the virtual console and
ownership arbiter pass acceptance. It reuses the same control contract and
must not fork Player behavior.

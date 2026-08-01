# Product Scope

## Product statement

DanceLab is a local DJ-intelligence and automatic playback system. DanceLab
may decide and prepare a set; the Player executes an ordered set on two virtual
decks and exposes the behavior of a DJ console.

The hard product boundary is:

> DanceLab prepares repertoire decisions. DanceLab Player mixes the ordered
> queue it receives.

The Player does not contain the DanceLab brief. It does not need to know
whether its tracks came from a DanceLab project, a folder, an M3U playlist or
another supported source.

## One product, two Player surfaces

### Embedded Player

Lives inside DanceLab Pro after planning and review:

- shows the prepared playlist and its readiness;
- plays the accepted `SetPlan` and `TransitionPlan` revisions;
- exposes compact Deck A/B, mixer, meters and transport;
- opens the selected seam in Transition Lab;
- offers **Open in Player** without restarting playback.

### Standalone Player window

The full console view:

- the same active queue and `PlaybackSession`;
- full Deck A/B waveforms and status;
- low/mid/high EQ, channel faders, crossfader and meters;
- visible automatic control movement;
- AutoMix start/stop, skip/fade-now and manual takeover;
- transition details and readiness;
- local playlist/folder import when launched without DanceLab.

Embedded and standalone are two controllers over one runtime. Only one runtime
owns the audio device and sample clock.

## Preparation surfaces inside DanceLab

### Set Architect

- receives the brief and library evidence;
- selects and orders repertoire;
- creates `SetPlan`;
- owns energy arc, locks, pins, replacements and sequence reasoning.

### Transition Lab

- prepares or edits exact A→B transitions;
- chooses WHERE and HOW after WITH WHAT is known;
- renders previews;
- creates immutable `TransitionPlan` revisions;
- returns the accepted revision to the set.

Both are part of the DanceLab experience. They can be opened while the Player
is visible, but they are not duplicated inside the real-time audio engine.

### Delivery

Delivery is the final DanceLab workspace, not a separate product:

- continuous mix render;
- Rekordbox playlist/cue export;
- sidecar manifest;
- written-file and capability verification.

It consumes the same accepted set and transition plans used by the Player.

## Player input contract

The Player receives a `PlaybackSet`:

```text
PlaybackSet
  ordered_tracks[]
  transition_plans[]
  source_kind
  source_reference
  readiness
  revision
```

Input behavior:

| Source | Who establishes order? | Player behavior |
|---|---|---|
| DanceLab project | Set Architect | preserve order and accepted plans |
| M3U/Rekordbox playlist | playlist author | preserve imported order |
| selected files | user | preserve visible selection/drop order |
| folder | deterministic import order, then user | show order before playback; never silently optimize |

An explicit **Open in Set Architect** action may ask DanceLab to optimize a
standalone queue. That is a user-invoked handoff, not Player behavior.

## Playback behavior

The primary mode is **AutoMix Queue**:

1. load the current track on Deck A;
2. prepare the next ordered track on Deck B;
3. obtain or compile the adjacent `TransitionPlan`;
4. execute tempo, EQ, fader and crossfader automation;
5. promote B to current and preload the following track on the opposite deck;
6. continue until the queue is empty.

Controls modify execution, not repertoire intelligence:

- play/pause;
- skip next;
- fade now;
- AutoMix on/off;
- manual takeover;
- resume automatic execution;
- queue reorder by explicit user action.

There is no default mode in which the Player autonomously chooses a different
next track from the library.

## The three-level decision

### WHERE

Choose exact, feasible time regions:

- outgoing window on Track A;
- incoming window on Track B;
- phrase alignment;
- available source runway;
- beatgrid reliability;
- cue origin and confidence.

### WITH WHAT

Choose Track B and evaluate the pair:

- tempo feasibility;
- harmonic relation;
- energy and tension progression;
- groove/style/context fit;
- bass and vocal collision risk;
- history and repetition;
- hard blocks and review-only policies.

In a DanceLab-prepared set, Set Architect owns this decision. In a standalone
Player queue, the user-provided order supplies Track B; the Player must not
replace it silently.

### HOW

Compile an executable performance:

- transition strategy;
- duration in beats;
- master tempo and deck playback rates;
- channel fader curves;
- low/mid/high EQ curves;
- optional approved effects;
- fallback behavior;
- safety and review flags.

## Product boundaries

- No crowd-response prediction without a real crowd-response dataset.
- Candidate decisions are recommendations, not guaranteed live truth.
- Demucs is a **Stem Separation Worker**, not the DanceLab engine.
- Deep analysis is never performed on the real-time audio thread.
- AutoMix never silently overwrites source audio or Rekordbox tempo grids.
- User edits are append-only revisions; the original engine suggestion remains
  recoverable and comparable.
- Ordinary playback must remain possible without Deep analysis.
- The embedded and standalone views must never start two competing audio
  engines for one session.
- Opening or closing the standalone window must not reset the playhead.
- Analysis may run ahead in a worker, but audio playback has priority.
- No brief or automatic repertoire selection is required to use the Player.

## Competitive direction

The target combines:

- Apple-like invisible, context-sensitive transition execution;
- Spotify-like visible/editable transition controls;
- DanceLab-specific DJ intent, stem-aware risk, explainability, manual
  takeover and Rekordbox delivery.

This is a product direction, not a claim that commercial services use the same
models or internal architecture.

# Player Product Flow

Status: canonical product behavior for implementation

## Core rule

DanceLab Player is an automatic two-deck mixer for an **ordered queue**. It
does not care where the tracks came from and does not silently select a
different next track.

```text
Input owns WITH WHAT
Player prepares/receives WHERE + HOW
Playback runtime executes the plan
```

## Product workspace map

```mermaid
flowchart TB
    subgraph APP["DanceLab"]
        LIB["Library"]
        ARCH["Set Architect"]
        LAB["Transition Lab"]
        EMBED["Embedded Player"]
        DELIVERY["Delivery<br/>render + Rekordbox"]

        LIB --> ARCH
        ARCH --> LAB
        LAB --> EMBED
        ARCH --> EMBED
        ARCH --> DELIVERY
        LAB --> DELIVERY
    end

    EMBED -->|"Open in Player"| FULL["Standalone Player window"]
    EMBED <-->|"same PlaybackSession"| RUNTIME["Playback Session Service"]
    FULL <-->|"same PlaybackSession"| RUNTIME
```

Set Architect, Transition Lab, Embedded Player and Delivery are DanceLab
workspaces. The standalone Player is a full console window linked to the same
runtime, not a detached product copy.

## Two entry paths

```mermaid
flowchart TB
    subgraph DL["DanceLab preparation"]
        BRIEF["Brief and DJ intent"] --> ANALYZE["Quick / Deep analysis"]
        ANALYZE --> ARCH["Set Architect<br/>ordered SetPlan"]
        ARCH --> LAB["Transition Lab<br/>reviewed TransitionPlans"]
    end

    subgraph ST["Standalone preparation"]
        INPUT["Folder / files / playlist"] --> SCAN["Scan and visible queue"]
        SCAN --> ORDER["User confirms or reorders"]
        ORDER --> AHEAD["Analyze and compile adjacent transitions"]
    end

    LAB --> PACKAGE["PlaybackSet"]
    AHEAD --> PACKAGE
    PACKAGE --> SESSION["One PlaybackSession"]
    SESSION --> EMBED["Embedded Player"]
    SESSION --> FULL["Standalone Player window"]
```

The two paths converge before playback. Player execution is identical after a
valid `PlaybackSet` exists.

## Linked-window model

```mermaid
flowchart LR
    EMBED["Embedded Player<br/>inside DanceLab"] <-->|"commands + state events"| SERVICE["Playback Session Service"]
    FULL["Standalone Player<br/>full console"] <-->|"commands + state events"| SERVICE
    SERVICE --> RUNTIME["Single Playback Runtime"]
    RUNTIME --> DEVICE["One audio device"]
    RUNTIME --> CLOCK["One sample clock"]
    RUNTIME --> DECKS["Deck A + Deck B"]
    RUNTIME --> QUEUE["One ordered queue"]
```

Invariant: multiple views may exist, but exactly one runtime is authoritative
for audio, playhead, deck state and automation position.

## Open in Player sequence

```mermaid
sequenceDiagram
    participant U as User
    participant E as Embedded Player
    participant S as Playback Session Service
    participant R as Playback Runtime
    participant F as Standalone Player

    U->>E: Open in Player
    E->>S: attach_full_view(session_id)
    S->>F: launch with session_id
    F->>S: subscribe snapshot + events
    S-->>F: queue, deck state, playhead, plan revision
    F-->>U: show live full console
    Note over R: Audio never restarts
    U->>F: pause / skip / takeover
    F->>S: idempotent command
    S->>R: apply command
    R-->>S: authoritative event
    S-->>E: update embedded view
    S-->>F: update standalone view
```

Opening the standalone window attaches a controller. It does not clone the
session, reload the track or reacquire the device.

## Playback queue semantics

### DanceLab-prepared

The queue contains:

- ordered track references from `SetPlan`;
- accepted `TransitionPlan` revision for each adjacent pair;
- warnings and readiness;
- source/project identity.

The Player is an execution preview of what DanceLab designed.

### Standalone

The user supplies:

- an ordered playlist;
- selected files;
- or a folder that becomes a visible deterministic list.

The Player:

1. scans metadata and validates paths;
2. displays the queue immediately;
3. schedules analysis;
4. prepares transitions only between adjacent items;
5. begins once the first execution runway is ready;
6. continues analysis/prefetch ahead without blocking audio.

Folder import never implies smart set ordering. An explicit user reorder or
handoff to Set Architect is required to change repertoire order.

## Analysis readiness

```mermaid
stateDiagram-v2
    [*] --> Scanned
    Scanned --> QuickReady
    QuickReady --> DeepQueued
    DeepQueued --> DeepReady
    QuickReady --> PlaybackReady: safe transition compiled
    DeepReady --> PlaybackReady: stem-aware transition compiled
    Scanned --> Blocked: source invalid
    QuickReady --> Blocked: no safe execution plan
```

The runtime should normally maintain at least the current track, next track
and one following track in a prepared state. Exact lookahead is configurable
and benchmarked.

Deep/Demucs analysis:

- never runs on the audio callback;
- yields or pauses when it threatens playback stability;
- may finish before playback or continue ahead in a bounded worker;
- is not required for basic playback;
- improves transition evidence when ready in time.

## Automatic deck cycle

```mermaid
sequenceDiagram
    participant Q as Ordered Queue
    participant A as Deck A
    participant M as Mixer/Automation
    participant B as Deck B

    Q->>A: load Track 1
    Q->>B: preload Track 2
    A->>A: play
    B->>B: seek to incoming cue
    M->>A: outgoing automation
    M->>B: tempo + incoming automation
    Note over A,B: execute TransitionPlan 1->2
    B->>B: becomes current
    Q->>A: preload Track 3
    Note over A,B: deck roles alternate
```

## Console model

```text
┌────────────────────── DECK A ──────────────────────┐
│ title · BPM · rate · phase · cue · waveform        │
│ HIGH   MID   LOW               channel fader       │
└────────────────────────────────────────────────────┘

                  MASTER METERS
                   CROSSFADER
            AUTOMIX · FADE NOW · TAKEOVER

┌────────────────────── DECK B ──────────────────────┐
│ title · BPM · rate · phase · cue · waveform        │
│ HIGH   MID   LOW               channel fader       │
└────────────────────────────────────────────────────┘

PLAYLIST / AUTOMIX QUEUE
  playing
  loaded next
  analyzed and ready
  analysis pending
  blocked with reason
```

Controls should visibly follow the active `TransitionPlan`. The UI is a
faithful console representation of the runtime, not an animation that guesses
what the engine is doing.

The canonical console semantics and control-by-control mapping are defined in
[11_DDJ_FLX4_CONTROL_MAP.md](11_DDJ_FLX4_CONTROL_MAP.md). FLX4 is the
interaction reference; DanceLab is not required to copy its branding or exact
industrial design.

## Relationship to Mixxx

The local R&D source
`/Users/jantrybus/Desktop/AI/RnD-DanceLab-Pro/notes/mixxx-manual-2.5-en.pdf`
documents useful baseline behavior:

- an Auto DJ queue is a special ordered playlist;
- tracks may be loaded from a playlist, crate, library or files;
- the first tracks are loaded into opposing decks;
- Auto DJ continues until the queue is empty;
- intro/outro sections may align transition timing;
- Auto DJ controls the crossfader.

DanceLab keeps that source-agnostic queue/deck model but extends execution
with phrase evidence, tempo planning, low/mid/high automation, line faders,
stem-aware collision risk and explicit `TransitionPlan` provenance.

## Product actions

Embedded Player:

- Open in Player;
- open current seam in Transition Lab;
- open queue in Set Architect;
- start/stop AutoMix;
- basic transport and status.

Standalone Player:

- attach to an existing DanceLab session;
- start a new local session from files/playlist/folder;
- show the full console;
- explicit queue reorder;
- manual takeover and resume;
- return/open the session in DanceLab.

## Non-goals

- no brief inside the Player;
- no silent playlist optimization;
- no random library selection by default;
- no duplicate audio runtime when two windows are open;
- no Deep analysis on the audio callback;
- no UI-authored fake playhead or fader state.

# API and Frontend Handoff

## Client strategy

DanceLab and the standalone Player are two windows over one contract-driven
local application runtime. They may use a desktop web shell or native shell,
but product and playback state must not live only in view components.

Recommended frontend layers:

```text
app shell
  -> route/workspace controllers
    -> query + command client
      -> normalized client store
        -> presentational components
```

Waveforms, transport and automation controls subscribe to bounded state
slices. A global high-frequency rerender on every audio position update is
not acceptable.

## DanceLab workspaces

### Library

- folder/file import;
- Rekordbox source import when supported;
- Quick/Deep status;
- analysis and cache state;
- search, sort and filters;
- queue/add-to-set actions.

### Set

- DJ intent/context;
- ordered track terrain/timeline;
- candidate ranking with reasons and risk;
- pin, lock, move and replace;
- selected edge opens Transition Lab;
- completed set creates an ordered `PlaybackSet`.

### Transition Lab

- Track A/B waveforms and exact windows;
- strategy, duration and blend profile;
- fader/EQ automation;
- preview render and playback;
- engine suggestion vs current revision;
- accept, revise, reject and manual-listen verdicts.

### Embedded Player

- now playing and queue;
- compact two-deck and mixer state;
- current/upcoming transition;
- play, pause, seek, skip;
- AutoMix on/off;
- manual takeover and resume policy;
- clear fallback/error state;
- **Open in Player** attaches the full standalone window to the same session.

### Delivery

- continuous render;
- Rekordbox export;
- capability/verification report;
- output location and immutable manifest.

Delivery is inside DanceLab and consumes the same `PlaybackSet` and accepted
plans used by the Player.

## Standalone Player window

- full Deck A/B waveforms;
- BPM, playback rate, phase, cue and plan status;
- low/mid/high controls;
- channel faders, crossfader and master meters;
- visible ordered AutoMix queue;
- analysis/readiness status for upcoming items;
- fade now, skip, takeover and resume;
- open current transition in DanceLab Transition Lab;
- open current queue in Set Architect;
- when started alone: import playlist/files/folder and preserve user order.

The standalone window is not a separate playback engine. It is an additional
controller attached to `PlaybackSession`.

Its console control semantics follow
[11_DDJ_FLX4_CONTROL_MAP.md](11_DDJ_FLX4_CONTROL_MAP.md): two deck strips,
FLX4-familiar transport/loop/pad placement, central low/mid/high mixer,
channel faders, crossfader, meters and PFL. Beat FX and channel-filter controls
stay hidden until matching DSP exists in the runtime.

## API additions

Existing routes remain compatible. Add a versioned surface such as `/v1`.

### Transition planning

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/v1/transitions/compile` | compile EdgeDecision or track pair to a plan |
| `GET` | `/v1/transitions/{plan_id}` | latest or requested revision |
| `POST` | `/v1/transitions/{plan_id}/revisions` | apply immutable user edit |
| `POST` | `/v1/transitions/{plan_id}/review` | persist verdict |
| `POST` | `/v1/transitions/{plan_id}/render` | enqueue preview render |
| `GET` | `/v1/transitions/{plan_id}/artifact` | fetch render metadata/file handle |

### Jobs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/v1/jobs` | start analysis/render/export job |
| `GET` | `/v1/jobs/{job_id}` | snapshot |
| `POST` | `/v1/jobs/{job_id}/cancel` | cooperative cancellation |
| `GET` | `/v1/events` | SSE initially; job and durable product events |

Job state:

```text
queued -> running -> completed
                  -> failed
                  -> cancelling -> cancelled
```

Every progress event contains:

- `job_id`, `kind`, `state`;
- stage name from the real worker;
- completed/total units;
- current track or plan ID;
- warnings;
- recoverable error payload;
- timestamps.

### Playback

Commands:

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/v1/playback/sets` | create a `PlaybackSet` from prepared plans or explicit user order |
| `POST` | `/v1/playback/sessions` | create one authoritative runtime session |
| `POST` | `/v1/playback/{id}/attachment-token` | obtain a short-lived attach token for another local window |
| `POST` | `/v1/playback/{id}/attachments` | attach embedded or standalone controller |
| `POST` | `/v1/playback/{id}/queue` | replace/append/reorder queue |
| `POST` | `/v1/playback/{id}/commands` | play, pause, seek, skip, takeover |
| `PUT` | `/v1/playback/{id}/automix` | enable/disable automatic execution of the ordered queue |
| `GET` | `/v1/playback/{id}` | low-frequency state snapshot |
| `GET` | `/v1/playback/{id}/events` | transport/deck/plan event stream |
| `POST` | `/v1/playback/{id}/controls/{control_id}` | apply an idempotent UI/controller value |

For a local desktop app, these routes are a control contract. High-frequency
audio does not travel over HTTP.

`Open in Player` passes an opaque `session_id` or short-lived local attach
token. It never serializes a second independent copy of the live session.

### Source adapters

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/v1/playback/sources/dancelab` | adapt an accepted DanceLab set |
| `POST` | `/v1/playback/sources/playlist` | import ordered supported playlist |
| `POST` | `/v1/playback/sources/files` | preserve explicit file order |
| `POST` | `/v1/playback/sources/folder` | scan folder into visible deterministic order |

Source adapters never start playback automatically and never optimize track
order. They return a draft queue and readiness state for user confirmation.

### Controller adapters

Physical FLX4 support is local and optional:

- device discovery reports controller/audio capabilities;
- MIDI input becomes the same typed commands used by the UI;
- runtime state drives supported LEDs/meters;
- soft takeover prevents a physical knob from jumping an automated value;
- detaching hardware does not stop the software runtime;
- Master 1–2 and Headphones 3–4 are configurable output pairs;
- microphone capture is outside the initial contract.

High-rate MIDI/controller events should use a local adapter/event channel,
not individual HTTP requests. The HTTP route above defines semantics and is
useful for tests and remote UI controls.

## Command idempotency

Mutating requests carry `command_id`. Repeating a command after a client
timeout must not create a second revision, job or queue insertion.

The session service serializes commands from embedded and standalone
controllers. Every accepted command emits one authoritative state event back
to all attached views.

## Error contract

Use stable machine-readable codes:

```json
{
  "error": "transition_not_executable",
  "message": "Track B has insufficient source runway.",
  "details": {
    "plan_id": "tp_...",
    "available_beats": 24,
    "requested_beats": 64
  },
  "recoverable": true,
  "suggested_action": "shorten_transition"
}
```

Do not leak local paths unnecessarily. UI-facing messages are derived from
codes, not string matching.

## Frontend state ownership

Durable backend state:

- projects;
- analysis references;
- set plans;
- playback sets and their source/order provenance;
- transition revisions and verdicts;
- export manifests;
- relevant playback history.

Ephemeral client state:

- open panels;
- waveform zoom/pan;
- hover/selection;
- unsaved control drag before commit.

Runtime state owned by playback:

- device;
- sample clock;
- deck buffers;
- exact playhead;
- current automation position;
- underrun counters.

The UI mirrors runtime state; it does not authoritatively advance the clock.
Closing a view detaches a controller; it does not implicitly stop the runtime.
Explicit product policy controls whether closing the last view stops playback.

## UI honesty rules

- Show confidence and warnings near the recommendation they qualify.
- Label Demucs as `Stem Separation Worker (Demucs v4 / htdemucs)`.
- Show the actual backend from provenance, for example `Apple Silicon (MPS)`.
- Distinguish `Rendered`, `Accepted` and `Exported`.
- Display fallback mode when AutoMix cannot execute the requested plan.
- Manual takeover must be a primary control, not hidden in settings.
- Display queue order exactly as the runtime sees it.
- Do not show brief/context controls in the Player.
- Do not label background transition preparation as next-track selection.
- EQ/fader movement must reflect authoritative runtime automation.
- Automatic/manual ownership must be visible for touched controls.
- A physical-control pickup state must be visible without changing audio.
- Never present a sidecar-only automation as “exported to Rekordbox”.

## Security and local-file rules

- Backend validates allowed input/output roots.
- Browser/web views never receive arbitrary filesystem privileges.
- File selection is performed by a trusted desktop bridge or explicit
  server-side path policy.
- Output writes are atomic.
- API binds to loopback by default and uses an origin/session token for a
  packaged client.
- Logs and event payloads avoid unnecessary personal paths and metadata.

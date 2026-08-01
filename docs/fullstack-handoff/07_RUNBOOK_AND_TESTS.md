# Development Runbook and Test Gates

## Current engine setup

From the repository root:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e ".[dev,audio,stems]"
```

Run the API:

```bash
PYTHONPATH=src ./.venv/bin/uvicorn dancelab.api.main:app --reload
```

OpenAPI is available at `http://127.0.0.1:8000/docs`.

Do not use the older `dancelab-host` instructions on this branch until a host
package and matching extras are restored or replaced.

## Standard verification

```bash
PYTHONPATH=src ./.venv/bin/pytest
./.venv/bin/ruff check src tests
./.venv/bin/python -m compileall -q src tests
./.venv/bin/python -m pip check
git diff --check
```

During implementation, start with the smallest focused suite and finish the
milestone with the full suite.

## Test layers

### Contract tests

- Pydantic round trip;
- schema version is present;
- unknown/incompatible schema is rejected or migrated explicitly;
- deterministic IDs and hashes;
- nullability for unverified evidence;
- all enums serialize to stable strings.
- `PlaybackSet` preserves explicit queue order;
- exactly one transition revision maps to each adjacent pair;
- queue provenance distinguishes DanceLab order from explicit user order.

### Compiler tests

- each supported strategy/profile;
- exact automation knots;
- short source runway;
- unreliable/missing beatgrid;
- excessive tempo adjustment;
- hard-blocked standard blend;
- missing source or changed checksum;
- fallback selection and explanation;
- repeat input produces repeat output.

### Renderer tests

- plan timing equals rendered duration;
- cue offsets match source reads;
- PCM format/channel/rate;
- automation and normalization bounds;
- no partial artifact after failure;
- cache key changes after execution-relevant revision;
- cache key does not change for review note only.

### Repository tests

- atomic save;
- concurrent read during write;
- revision chain integrity;
- latest accepted revision query;
- corrupt record quarantine;
- backward migration fixture;
- user project data never evicted with preview cache.

### API tests

- success/error schemas;
- idempotent commands;
- job cancellation;
- reconnect to event stream;
- invalid local path policy;
- body/queue limits;
- client recovery after backend restart.
- attaching embedded and standalone controllers to one session;
- two create retries do not create two audio runtimes;
- stale attach tokens cannot control another session;
- folder/playlist adapters return visible order without optimization.

### Playback tests

- state machine transitions;
- gapless queue boundary;
- alternating Deck A/B lifecycle;
- prefetch miss and declared fallback;
- pause/seek/skip around a scheduled seam;
- device loss;
- underrun counting;
- no forbidden callback work;
- manual takeover and safe resume.
- embedded and standalone snapshots agree;
- a command from either view reaches both views as one event;
- attaching/detaching a view preserves playhead and automation position;
- only one component owns the audio device;
- Player never invokes next-track recommendation to replace a queue item.
- FLX4-mapped UI controls mutate the matching runtime field;
- automatic EQ/fader/crossfader values match active plan execution;
- runtime control ownership changes from plan to user/hardware explicitly;
- soft pickup suppresses discontinuous physical-knob jumps;
- effect kill resets the approved effect chain safely;
- PFL/headphone routing is independent from the master output;
- controller disconnect leaves software AutoMix running.

### Cross-path parity

For the same `TransitionPlan`:

- preview and live start at the same cues within tolerance;
- duration is the same within one audio block;
- automation reaches the same knot values at the same beat/sample positions;
- playback rates and tempo strategy match;
- plan/revision/hash are visible in both manifests.

## MacBook Air M4 benchmark gate

Test on battery and power:

- 44.1 kHz stereo;
- representative buffer sizes;
- two simultaneous decoded decks;
- time stretching on both decks at bounded rates;
- three-band processing and automation;
- UI event load;
- at least 60 minutes continuous playback.

Record:

- selected device/backend;
- callback buffer size;
- p50/p95/p99 callback time;
- underrun count;
- memory growth;
- thermal/power mode;
- fallback events.

Release target: zero underruns in the reference session under supported system
load. If this cannot be achieved in Python, move the real-time kernel/device
adapter behind the existing plan boundary.

## First vertical-slice acceptance scenario

1. Analyze two real local tracks.
2. Request their `EdgeDecision`.
3. Compile and persist a plan.
4. Render a preview.
5. Reload the plan from disk.
6. Move one cue or change one profile.
7. Create a child revision.
8. Render again with a different plan hash.
9. Accept the revision.
10. Create a `PlaybackSet` with explicit order.
11. Execute it in the embedded Player.
12. Open the standalone Player on the same session.
13. Verify that playback and deck state did not restart.
14. Issue a transport command from standalone and observe both views.
15. Export supported cues and a sidecar manifest.
16. Verify the written export.

Required assertions:

- no source audio modified;
- exact lineage from edge decision to export;
- original suggestion preserved;
- warnings remain visible end to end;
- live and preview timing agree;
- one active session and one audio-device owner;
- embedded and standalone views share the same playhead;
- queue order remains unchanged unless explicitly edited;
- visible FLX4-style controls equal authoritative runtime values;
- unsupported Rekordbox automation is not overclaimed.

## Definition of done for each milestone

- public contract documented;
- migrations or explicit incompatibility behavior included;
- focused and regression tests pass;
- errors are recoverable and visible;
- real backend/provenance shown;
- no validation module imported by production;
- no heavy work on the real-time path;
- relevant docs in this folder updated in the same change.

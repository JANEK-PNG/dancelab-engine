# Decisions, Open Questions and Risks

## Accepted decisions

| ID | Decision |
|---|---|
| D-01 | DanceLab Player is a first-class part of DanceLab and may also open as a standalone window. |
| D-02 | `TransitionPlan` is the single execution contract. |
| D-03 | Decision and execution are separate bounded contexts. |
| D-04 | Preview, live playback and full render share mixing/automation semantics. |
| D-05 | Demucs v4/HTDemucs is an optional preprocessing worker. |
| D-06 | Deep analysis and model loading never run on the audio callback. |
| D-07 | Local playback works when Deep analysis is unavailable. |
| D-08 | User edits create immutable revisions. |
| D-09 | Rekordbox export explicitly reports lossy/unsupported mappings. |
| D-10 | Validation data influences production only through a documented gate. |
| D-11 | AutoMix always has a declared safe fallback and manual takeover. |
| D-12 | Apple Silicon MPS provenance reports the actual selected backend. |
| D-13 | Embedded and standalone Player views attach to one `PlaybackSession`. |
| D-14 | Exactly one runtime owns the audio device and sample clock per session. |
| D-15 | Player consumes an ordered `PlaybackSet`; it does not contain the brief. |
| D-16 | Player never silently selects or reorders repertoire. |
| D-17 | DanceLab Set Architect owns WITH WHAT; standalone user order supplies WITH WHAT. |
| D-18 | Delivery is a DanceLab workspace consuming the same accepted plans as Player. |
| D-19 | DDJ-FLX4 is the semantic reference for the two-deck console, not a branded visual clone. |
| D-20 | Virtual console and optional physical FLX4 adapter use one typed control/state contract. |
| D-21 | Every moving control reflects runtime state; decorative fake automation is forbidden. |
| D-22 | Manual/hardware takeover uses explicit ownership and soft pickup. |

## Open product questions

These do not block Phase 1:

- May standalone AutoMix execute newly compiled, unreviewed transitions by
  default, or only in a conservative fallback policy?
- When the user takes over, does AutoMix stay suspended until explicitly
  resumed?
- Effects in v1: none. Beat FX and channel-filter UI remain hidden until matching
  DSP and safety tests exist.
- Is the initial client a desktop web shell, a restored PySide6 host, or
  another native framework?
- Which formats are promised for gapless playback in the first release?
- Is continuous mix export WAV-only first, or WAV and AIFF?
- Does closing the last attached window stop playback or leave a background
  session with a menu-bar status?
- Which P1 FLX4 functions follow P0: loops/beat jump, jog, effects or physical
  MIDI integration?

## Primary engineering risks

### Real-time Python risk

Python analysis is appropriate; Python audio callback reliability must be
measured. Mitigation: keep the plan and orchestration language-neutral, build
a benchmark early, move only the time-critical kernel if needed.

### Preview/live drift

Different backends can interpret time stretch, EQ and interpolation
differently. Mitigation: one automation/mix contract, parity fixtures and
bounded tolerances.

### Multi-window state split

Two windows can accidentally become two controllers with divergent local
state or two audio engines. Mitigation: authoritative session service, opaque
`session_id`, one command log/event stream and hard single-device ownership.

### Accidental repertoire intelligence in Player

Background analysis could be confused with track selection and silently alter
the queue. Mitigation: immutable visible order by default, explicit reorder
commands, source/order provenance and tests forbidding next-track replacement
inside playback.

### Physical/automatic control collision

An automated fader can differ from a connected physical fader. Applying the
hardware value immediately would create an audible jump. Mitigation: explicit
ownership, soft takeover/pickup, bounded return-to-auto ramps and one
authoritative control state.

### Console animation drift

A visual console can look convincing while not representing the audio path.
Mitigation: render UI only from runtime events, test plan/control parity and
never animate unused crossfader or EQ paths.

### Beatgrid/downbeat uncertainty

Phrase-perfect marketing can exceed evidence. Mitigation: safety flags,
nullable beat-derived fields, conservative fallback and manual-listen state.

### Source mutation

A plan can refer to a file that changed after analysis. Mitigation: source
checksum in anchor and pre-execution validation.

### Stale documentation

Older docs currently name a desktop host absent from the branch. Mitigation:
make client choice explicit, add CI checks for documented entry points later,
and avoid copying old module maps into implementation tickets.

### Long-running jobs

Analysis, Demucs and rendering do not fit synchronous request lifetimes.
Mitigation: durable job state, cooperative cancellation, resumable work and
event streams.

### Storage growth

Stems and previews can consume many gigabytes. Mitigation: visible cache
classes, size estimation, eviction only for derived artifacts, never user
exports or accepted plans.

### Rekordbox capability mismatch

XML can carry cues/order but not the full DanceLab performance. Mitigation:
written-file verification, capability report and sidecar manifest.

### Personalization feedback loops

Learning too early can reinforce model mistakes. Mitigation: immutable raw
events, base-engine comparison, held-out gate, bounded influence and reset.

## Non-goals for the first vertical slice

- cloud streaming catalog integration;
- social playlists;
- remote multi-user collaboration;
- autonomous repertoire selection inside Player;
- brief/context forms inside Player;
- silent folder-to-smart-set optimization;
- automatic mastering;
- generative stem reconstruction;
- crowd-response prediction;
- learned end-to-end transition DSP;
- plug-in hosting;
- Rekordbox database mutation beyond already verified, explicitly scoped
  pathways.

## Change protocol

Any change to an accepted decision should:

1. record the old decision and reason for replacement;
2. identify affected contracts and migrations;
3. add or update acceptance tests;
4. state whether existing plans remain executable;
5. update this folder in the same pull request.

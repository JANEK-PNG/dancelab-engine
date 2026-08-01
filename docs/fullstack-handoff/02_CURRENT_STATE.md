# Current Codebase State

This is a verified snapshot of the repository at the handoff baseline. It is
not a description of the complete target.

## Implemented now

| Capability | State | Main code |
|---|---|---|
| Track analysis | CURRENT | `core/pipeline.py`, `features/`, `descriptors/` |
| Beat/tempo/structure | CURRENT, with honesty warnings | `preprocessing/` |
| Stem-aware analysis | CURRENT, optional | `stems/`, `features/vocals.py` |
| Pair mixability | CURRENT candidate model | `decision/mixability.py` |
| Transition windows | CURRENT candidate model | `decision/transition_windows.py` |
| Unified pair decision | CURRENT candidate model | `decision/edge_decision.py` |
| Strategy and blend profile | CURRENT intent classification | `decision/transition_strategy.py`, `decision/blend_profile.py` |
| Next-track and sequence planning | CURRENT candidate model | `decision/next_track.py`, `decision/sequence.py`, `decision/set_builder.py` |
| Transition preview DSP | CURRENT | `preview/transition_simulation.py` |
| Rekordbox XML/cues | CURRENT, bounded feature set | `export/rekordbox.py`, cue modules |
| JSON/file storage | CURRENT | `storage/` |
| FastAPI gateway | CURRENT | `api/` |
| Folder → analysis → SetPlan → Rekordbox workflow | CURRENT | `workflows/smart_playlist.py` |
| Standalone playback runtime | NOT IMPLEMENTED | target `playback/` |
| Embedded Player / linked playback session | NOT IMPLEMENTED | target Player surfaces |
| Ordered `PlaybackSet` input contract | NOT IMPLEMENTED | target `playback/models.py` |
| FLX4-based virtual console state | NOT IMPLEMENTED | target console contract |
| Physical DDJ-FLX4 adapter | NOT IMPLEMENTED, optional | target `playback/controllers/flx4.py` |
| Canonical `TransitionPlan` | NOT IMPLEMENTED | target `transitions/` |
| Transition plan API/repository | NOT IMPLEMENTED | target modules |
| Continuous-set renderer | NOT IMPLEMENTED | target `export/continuous_mix.py` |

## Deep analysis and hardware

- Installed model family: **Demucs v4**.
- Default deep model: `htdemucs`.
- Exposed stems: drums, bass, other and vocals.
- Model audio rate: 44.1 kHz.
- On the target MacBook Air M4, the engine selects Apple Metal through
  PyTorch MPS when it is available.
- New Demucs provenance uses the resolved device label
  (`demucs.apply_model.mps` or the actual fallback), rather than a hard-coded
  CPU label.
- Existing artifacts keep their historical provenance. Re-analysis creates a
  new truthful record; old records must not be silently rewritten.

## Existing transition preview

`preview/transition_simulation.py` already supplies valuable production
building blocks:

- 32–256 beat transition durations;
- 8-beat control knots;
- linear, plain blend, bass swap, tops swap and contour blend profiles;
- source-runway guard;
- independent deck playback rates;
- librosa phase-vocoder time stretching;
- three-band low/mid/high processing;
- sample-accurate stereo PCM24 WAV output;
- cache key inputs and waveform summaries.

The problem is structural: the renderer currently receives many loose
arguments. It must consume a canonical `TransitionPlan`, and its reusable DSP
must be extracted for both offline and live use.

## Existing decision payload

`EdgeDecision` already contains most of the information needed to begin a
plan:

- selected Track A and Track B windows;
- compatibility score and confidence;
- recommended strategy and alternatives;
- blend profile;
- tempo and harmonic gates;
- BPM delta and tempo relation;
- bass/vocal/harmonic risks;
- hard block and recommendation policy;
- explanations, warnings and provenance.

It does not yet define executable timing, rate, duration, automation, revision
identity or render/playback lifecycle.

## Existing feedback

`validation/transition_edits.py` stores append-only CSV events for waveform
edits. That is useful evidence but it is currently owned by `validation/`.
Product editing must move to a production event/revision contract. The
validation module may consume those events, but the engine must not import
from `validation/`.

## API baseline

Current useful routes include:

- `GET /health`
- `POST /tracks/analyze`
- `POST /tracks/{track_id}/transition-windows`
- `POST /pairs/mixability`
- `POST /pairs/edge-decision`
- `POST /sets/recommend-next`
- `POST /sets/recommend-sequence`
- `POST /sets/build`
- `POST /sets/export-rekordbox`
- `POST /sets/smart-playlist`
- `POST /stems/export`

Heavy operations are still mainly synchronous. A production client needs a
job/event model rather than holding an HTTP request open for analysis,
separation or rendering.

There is currently no Player that sources tracks at runtime. The implemented
smart-playlist workflow accepts a folder, discovers audio, analyzes tracks,
builds a set and writes Rekordbox XML. The existing preview renderer handles
one transition artifact; it is not continuous two-deck playback.

## Documentation/runtime discrepancy

The current branch does **not** contain `src/dancelab/host/`, a desktop script
or `desktop` optional dependencies in `pyproject.toml`. Older documents and
the root `README.md` still describe that PySide6 host and its launcher.

Full-stack work must therefore choose and state its client shell explicitly.
Do not assume the older desktop launch command works on this branch. The
recommended separation is:

- Python package: engine, analysis, planning, render and playback services;
- DanceLab and standalone Player windows: linked controllers consuming stable
  contracts;
- local integration: HTTP plus a local event channel initially;
- native low-latency audio: in-process/native boundary when the live runtime
  is introduced.

## Technical debt relevant to this build

- `core/models.py` is already large; new transition contracts should live in
  `transitions/models.py`, not expand the core monolith.
- `preview/transition_simulation.py` mixes contracts, DSP, I/O and rendering.
- storage is JSON/file based; no SQL migration path exists yet.
- some older docs describe modules removed from the current branch.
- downbeat phase is not strong enough to be treated as verified truth.
- Rekordbox support must only claim what the written XML actually contains.

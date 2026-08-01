# Research and Reference Context

This note captures the starting references and the engineering conclusions
already made from them. It is not a substitute for model cards or validation.

## Demucs

References:

- [Open Laboratory — Demucs](https://openlaboratory.com/models/demucs/)
- [Audio WebUI](https://github.com/gitmylo/audio-webui)

Repository decision:

- use Demucs v4 with `htdemucs` for optional four-stem separation;
- treat it as a worker behind `stems/extractor.py`;
- cache and provenance must include model name, signature and actual device;
- Deep analysis may consume stem-derived features;
- live playback consumes prepared analysis/plans and never invokes Demucs on
  the audio thread;
- Audio WebUI is useful as a laboratory UX/reference, not a production
  dependency boundary.

## Vocos

References:

- [gemelo-ai/vocos](https://github.com/gemelo-ai/vocos)
- [Vocos paper](https://arxiv.org/abs/2306.00814)
- [Open Laboratory — Vocos](https://openlaboratory.com/models/vocos/)

Conclusion:

- Vocos is a neural vocoder, not a source separator;
- it does not replace Demucs;
- the available pretrained use cases are not a direct fit for transparent,
  full-band DJ playback;
- keep it in R&D for later neural audio generation/reconstruction experiments,
  outside the first AutoMix production path.

## Apple Music reference

Product reference:

- automatic transitions can be invisible and require little user setup;
- the system chooses transition behavior dynamically;
- playback continuity and safe fallback matter more than exposing every
  parameter.

DanceLab takeaway:

- automatic queue mixing should feel effortless after its policy is chosen;
- expensive analysis happens ahead of playback;
- transitions that cannot be executed safely degrade cleanly;
- do not infer or claim Apple's private implementation or use of stems.

## Spotify reference

Product reference:

- editable transitions can expose BPM/key/waveform context;
- users can start from automatic choices and refine them;
- saved/shareable mix decisions have value beyond one playback session.

DanceLab takeaway:

- Seam review should expose the compiled plan rather than a disconnected
  mockup;
- user edits must become durable revisions;
- preview, playback and export must refer to the same revision;
- do not infer or claim Spotify's private implementation or use of stems.

## Mixxx 2.5.6 manual reference

Local R&D source:
`/Users/jantrybus/Desktop/AI/RnD-DanceLab-Pro/notes/mixxx-manual-2.5-en.pdf`

Relevant manual sections:

- Library and Auto DJ overview: pages 41–42;
- mixer, EQ, line faders, PFL and crossfader: pages 20–23;
- Intro/Outro cues: pages 93–94;
- Auto DJ queue and mix modes: pages 95–98.

Verified product lessons:

- the Auto DJ queue is a visible ordered playlist;
- tracks can enter it from a playlist, crate, library or files;
- source selection is separate from deck execution;
- Auto DJ loads opposing decks and continues until the queue is empty;
- intro/outro sections can control alignment and transition duration;
- the crossfader is runtime state and Auto DJ visibly controls it.

DanceLab adopts the source-agnostic queue and two-deck execution model. It
extends it with phrase/tempo evidence, low/mid/high and line-fader automation,
stem-aware collision risk, immutable plan revisions and linked embedded/full
Player views.

Mixxx can add random tracks from crates or the full library. DanceLab Player
must not do this by default: repertoire changes require explicit user action
or Set Architect.

### Pioneer DDJ-FLX4 mapping

Official online reference:
[Mixxx 2.5 - Pioneer DDJ-FLX4](https://manual.mixxx.org/2.5/en/hardware/controllers/pioneer_ddj_flx4)

Verified reference facts:

- two decks with an integrated audio interface;
- class-compliant USB audio and MIDI on macOS;
- Master output on channels 1–2 and Headphones on 3–4;
- browser rotary and deck load controls;
- sync, tempo, cue, play, jog, loop and pad controls;
- trim, high/mid/low, filter, PFL, channel faders, meters and crossfader;
- routed Beat FX with wet/dry and a kill/reset action;
- soft takeover for a multiplexed effect knob;
- microphone input is not routed back to the computer in this setup.

DanceLab maps these semantics to one authoritative virtual console state.
Physical FLX4 support remains an adapter over that contract. See
`11_DDJ_FLX4_CONTROL_MAP.md`.

## DanceLab differentiation to protect

- context-aware next-track choice;
- explicit WHERE + WITH WHAT + HOW reasoning;
- stem-aware risk with truthful fallback provenance;
- personal DJ style learned from real edits only after validation;
- manual takeover;
- local-first library/player;
- same plan across audition, live execution, full render and Rekordbox
  delivery;
- one live session shared by embedded and standalone Player views;
- source-agnostic execution without silently changing queue order;
- explanations and evidence boundaries visible to the DJ.

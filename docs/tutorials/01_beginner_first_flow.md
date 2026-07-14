# Beginner Tutorial: Build Your First Set

## Goal

Create, review, save, and export a small DanceLab set through the guided
desktop workflow.

## What You Touch

- DanceLab Pro Simple Mode
- audio import and Initial Check
- set brief and generated sequence
- transition review
- project save and Rekordbox XML export

## Input

Use one or more folders containing at least five tracks you know well. Stable
4/4 tracks with clear intros and outros make the first review easier.

## Steps

### Exercise 1: Open DanceLab Pro

Run:

```bash
dancelab-host
```

Pass check:

- the DanceLab Pro window opens
- the left stepper starts at `Import Tracks`
- the project bar reports whether the project is saved

### Exercise 2: Import tracks

Choose one or more music folders. Review any warning for audio shorter than
2 minutes or longer than 10 minutes before accepting it.

Pass check:

- the import page lists the selected audio files
- non-audio files are ignored
- the next action is clear

### Exercise 3: Run Initial Check

Start Initial Check and wait for analysis to complete. You can stop between
tracks; completed analyses stay cached.

Pass check:

- every successful track appears in the analyzed library
- BPM, key, energy, and available style metadata are visible
- failures are reported instead of silently disappearing

### Exercise 4: Generate a set

Choose 5 tracks, select a starting brief, and adjust style, BPM, role, or
energy only when needed. Select `Generate Set`.

Pass check:

- an ordered sequence appears
- the energy timeline is visible
- the context panel explains the active constraints

### Exercise 5: Review transitions

Open `Review Transitions`, select each pair, and preview the proposed handoff.

Pass check:

- Deck A and Deck B show the correct track names
- cue positions and waveforms change with the selected pair
- the incoming deck uses preview-only beat sync and 8-beat quantization

### Exercise 6: Save and export

Save the project as a `.dlproj`, then export the set as Rekordbox XML.

Pass check:

- reopening the project restores the session
- the XML file exists and contains the playlist order and hot cues
- DanceLab does not overwrite Rekordbox BPM or beatgrid data

## Common Failure Signals

- No tracks found: the selected folder contains no supported audio files.
- Analysis failed: inspect the reported file instead of retrying the whole library.
- Generate Set disabled: Initial Check or the minimum candidate count is incomplete.
- Export disabled: a set has not been generated yet.

## What To Do Next

Move to [02_intermediate_corpus_set_workflows.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/02_intermediate_corpus_set_workflows.md).

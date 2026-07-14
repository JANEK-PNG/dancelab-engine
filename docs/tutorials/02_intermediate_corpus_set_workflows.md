# Intermediate Tutorial: Shape and Validate a Set

## Goal

Use the analyzed library and planner controls to build a set for a real event,
then validate its transitions before export.

## Before You Start

Complete the beginner tutorial and open a project with an analyzed library.

## Workflow A: Constrain the Library

1. Filter or sort the analyzed library by BPM, style, energy, or key.
2. Mark essential tracks as `Must Have`.
3. Mark unsuitable tracks as `Not Tonight`.
4. Confirm that enough eligible tracks remain for the requested set length.

Pass check:

- Must Have tracks survive regeneration
- Not Tonight tracks never enter the generated sequence
- constraints remain visible in the session brief

## Workflow B: Express DJ Intent

1. Choose a preset or start from Custom.
2. Set the target track count or duration.
3. Add a leading style and BPM range when the event requires them.
4. Choose set role, energy, planner preference, and energy arc.
5. Generate the sequence.

Pass check:

- the generated set respects hard BPM and exclusion constraints
- repeated artists are avoided when the library allows it
- the energy timeline reflects the selected role and arc

## Workflow C: Deep-Analyze the Shortlist

After the sequence exists, run Deep Analysis for its tracks when stem-aware
review is worth the additional time and storage.

Pass check:

- Deep Analysis is limited to the shortlisted set
- Demucs/stem status is explicit
- the quick Initial Check cache remains reusable

## Workflow D: Review and Rate Transitions

1. Review every adjacent pair.
2. Confirm the displayed names match the audio on both decks.
3. Check waveform timing, 8-beat cue quantization, key risk, and BPM behavior.
4. Record a rating and note when a recommendation is weak.

Pass check:

- no track ID resolves to the wrong audio file
- transition ratings are saved outside the engine
- preview beat sync never changes exported Rekordbox BPM values

## Workflow E: Export Rekordbox XML

1. Name the playlist.
2. Choose the XML output path.
3. Export and inspect the summary.
4. Import the XML through Rekordbox's Imported Library workflow.

Pass check:

- playlist order matches DanceLab
- hot cues exist on intended phrase/grid positions
- Rekordbox remains responsible for device BPM and beatgrid analysis

## What To Do Next

Move to [03_advanced_validation_review.md](/Users/jantrybus/Desktop/AI/dancelab-engine/docs/tutorials/03_advanced_validation_review.md).

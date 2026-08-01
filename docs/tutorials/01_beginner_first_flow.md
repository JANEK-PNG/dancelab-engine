# Beginner Tutorial: Build Your First Set

## Goal

Analyze a familiar music folder, create a five-track playlist, hear one proposed
transition, and export a Rekordbox XML without touching the Rekordbox database.

## Input

Use a folder containing at least five complete tracks you know well. A first
test is easiest with stable 4/4 material and clear phrases.

## 1. Check the installation

```bash
dancelab version
dancelab --help
```

Pass check: both commands finish normally and the help lists `batch`,
`smart-playlist`, `preview`, and `export-rekordbox`.

## 2. Analyze the folder

```bash
dancelab batch "/path/to/music" \
  --output-dir "/path/to/work/processed"
```

Analysis JSON is cached in the output directory. Running the command again
skips completed tracks unless `--recompute` is supplied.

Pass check:

- supported audio files produce analysis JSON,
- failures name the affected file,
- BPM, beatgrid, key, structure, and energy remain attached to the same track.

## 3. Build a small playlist

```bash
dancelab smart-playlist "/path/to/music" \
  --count 5 \
  --processed-dir "/path/to/work/processed" \
  --output "/path/to/work/first_set.xml" \
  --name "DanceLab First Set"
```

Pass check:

- the command reports an ordered five-track set,
- `first_set.xml` exists,
- each playlist entry points to the intended source file.

## 4. Hear one transition

Choose two adjacent source files from the generated sequence:

```bash
dancelab preview "/path/to/track_a.wav" "/path/to/track_b.wav" \
  --output "/path/to/work/a_to_b.wav" \
  --profile contour_blend \
  --beats 64
```

The preview is a separate WAV artifact. Beat sync and EQ automation exist only
inside this audition; they do not overwrite track BPM or Rekordbox beatgrids.

Pass check:

- the printed A and B cue times are plausible,
- the rendered file contains the intended two tracks,
- the handoff remains rhythmically aligned.

## 5. Import the XML in Rekordbox

Use Rekordbox's XML import workflow and inspect the playlist before using it in
a performance.

Pass check:

- order and track identity match the terminal result,
- source tracks remain unchanged,
- no native Rekordbox database write was required.

## Common Failure Signals

- `no such audio file`: the path is wrong or the drive is unavailable.
- No analysis output: the folder contains no supported complete tracks.
- No usable transition window: inspect another pair instead of forcing a cue.
- Wrong audio under a title: stop and treat it as an identity regression.

Continue with [Shape and inspect a real set](02_intermediate_corpus_set_workflows.md).

# DJ Mix Validation Add-on

DanceLab includes an offline validation port of the method from:

- Taejun Kim et al., *A Computational Analysis of Real-World DJ Mixes using
  Mix-To-Track Subsequence Alignment*, ISMIR 2020 (`DLASOT-13`);
- `mir-aidj/djmix-analysis`, audited at commit `a2ae903`.

This is a measurement tool, not a new production planner. It reads local audio
files and emits a separate JSON report. It never changes engine BPM, beatgrids,
rankings, source files, or Rekordbox export.

## Implemented method

1. Estimate a beatgrid for the mix and each original track.
2. Extract beat-synchronous CENS chroma and 12 MFCC coefficients.
3. Evaluate 12 circular chroma shifts when key invariance is enabled.
4. Run subsequence DTW to align the whole original track to the mix.
5. Compute the published diagonal-step match rate.
6. Return explicit 32-, 16-, and 8-beat cue-evidence tiers.

The default `source_global` normalization reproduces the public demonstration's
block-level standardization with finite/zero-variance guards. A safer
`per_dimension` mode is available for experiments, but is a DanceLab adaptation
and must be reported as such.

## Run on local audio

Install the existing DanceLab audio extra, then run:

```bash
cd /Users/jantrybus/Desktop/AI/dancelab-engine
PYTHONPATH=src ./.venv/bin/python -m dancelab.validation.djmix \
  --mix /absolute/path/to/dj_mix.wav \
  --track /absolute/path/to/original_track_a.wav \
  --track /absolute/path/to/original_track_b.wav \
  --output data/reports/djmix_validation/result.json
```

Add `--include-path` when the full warping path is needed for visualization.
Without it, the report stays compact and contains alignment metrics plus cue
candidates.

## Source Palms Trax fixture

The source repository includes `data/meta/tracklist.csv` for one Palms Trax mix
and 31 original tracks. Its old downloader is an acquisition helper, not part of
DanceLab. Once those files exist locally, pass them to this command exactly like
any other local files.

Do not point the production app at downloaded research audio. Keep it in a
separate local validation workspace and store only derived reports under
`data/reports/`.

## Reading the result

- `match_rate >= 0.4` reproduces the paper's experimental filtering threshold;
- `key_shift_semitones` is the best circular chroma shift, not a guaranteed
  musical key-transposition label;
- `normalized_cost` is useful for comparison within the same feature/config
  version;
- cue tiers indicate stable diagonal evidence, not DJ-approved hot cues;
- unreliable beatgrids remain visible in the report and must not be hidden.

## Validation boundary

The paper's large-corpus aggregate findings remain population priors. This tool
lets DanceLab reproduce the method on local lawful fixtures and compare its own
transition windows with performed mixes. It does not imply possession of the
private row-level 1001Tracklists corpus.

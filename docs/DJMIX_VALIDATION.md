# DJ Mix Validation Add-on

DanceLab includes an offline validation port of the method from:

- Taejun Kim et al., *A Computational Analysis of Real-World DJ Mixes using
  Mix-To-Track Subsequence Alignment*, ISMIR 2020 (`DLASOT-13`);
- `mir-aidj/djmix-analysis`, audited at commit `a2ae903`.

This is a measurement tool, not a new production planner. It reads local audio
files and emits a separate JSON report. It never changes engine BPM, beatgrids,
rankings, source files, or Rekordbox export.

The public repository does not contain an explicit license file at the audited
commit. DanceLab therefore does not vendor or copy that source. This package is
an independent implementation of the published method, with the repository
used only as a behavioral reference.

## Implemented method

1. Estimate a beatgrid for the mix and each original track.
2. Extract beat-synchronous CENS chroma and 12 MFCC coefficients.
3. Evaluate 12 circular chroma shifts when key invariance is enabled.
4. Run subsequence DTW to align the whole original track to the mix.
5. Compute the published diagonal-step match rate.
6. Return explicit 32-, 16-, and 8-beat cue-evidence tiers.
7. Bind every mix/original to a full SHA-256 file fingerprint.
8. Pair the previous track's cue-out with the next track's cue-in to describe a
   performed transition region and midpoint.

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

Track arguments are interpreted as the performed order. Adjacent tracks are
paired into `transitions`. Supplying the same audio bytes twice is a hard
identity error, even when the files have different names.

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

`track_id` and all transition links use `sha256:<full digest>`. Human-readable
filenames remain display metadata only. This prevents the title/index/audio
cross-linking failures that a positional ID can hide.

## Diagnostic confidence, not probability

Each cue boundary reports five visible components:

```text
cost_quality      = 1 / (1 + normalized_cost)
match_rate        = published diagonal-step ratio
run_quality       = min(diagonal_run_beats / 32, 1)
beatgrid_quality  = minimum quality of mix and original beatgrids
feature_coverage  = finite feature/path coverage
```

Version `m11-cue-confidence-equal-v1-untuned` gives each component weight
`0.2`. Missing beatgrid quality contributes zero rather than being silently
renormalized away. The final transition confidence is the lower of its two
boundary scores.

These values are deliberately **not calibrated probabilities** and have no
acceptance threshold. They are instrumentation for validation reports only.

## Published evaluation metrics

`evaluate_boundary_predictions()` reports absolute cue error, coverage,
failure rate and hit rates at the paper's `15`, `30` and `60` second
tolerances. It emits two denominators explicitly:

- `hit_rate_evaluated`: only cases with a prediction;
- `hit_rate_all`: all ground-truth cases, so missing predictions cannot inflate
  the result.

## Validation boundary

The paper's large-corpus aggregate findings remain population priors. This tool
lets DanceLab reproduce the method on local lawful fixtures and compare its own
transition windows with performed mixes. It does not imply possession of the
private row-level 1001Tracklists corpus.

The source match-rate threshold can produce false positives for some unrelated
same-length feature sequences. Normalized cost is therefore exposed but not
thresholded until a held-out negative corpus supports calibration. `matched`
means "passed the paper's path-shape screen", not "identity proven".

Before M11 can influence runtime decisions it still needs held-out,
style-stratified validation, wrong-track negatives, and comparison against
DanceLab windows plus DJ edits. M12/CAGE remains explicitly deferred.

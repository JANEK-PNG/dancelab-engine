# Tempo and beat-grid validation

## Scope

DanceLab validates tempo against an explicit Rekordbox XML export in a separate,
read-only validation package. Rekordbox is an operational DJ reference here,
not scientific ground truth. The validator neither opens the encrypted
Rekordbox database nor changes engine weights.

The implementation is based on the current `librosa.beat.beat_track` baseline,
which follows the onset-strength, tempo-estimation and dynamic-programming
approach described by Ellis (2007):

- <https://librosa.org/doc/latest/generated/librosa.beat.beat_track.html>
- <https://labrosa.ee.columbia.edu/projects/beattrack/>

Metric-level ambiguity remains a separate problem. Half/double-time and other
metrical-level errors are known beat-tracking failure modes; the benchmark
therefore reports 2:1, 3:2, 4:3 and 5:4 relations but does not turn them into
automatic correction factors:

- <https://arxiv.org/abs/2210.06817>

## Stable long-span refinement

Frame-based beat positions quantize single intervals. DanceLab now estimates a
more precise constant tempo only after the tracker has selected a metric level.
For beat times `t_i`, it measures 32-beat periods:

```text
p_i = (t_(i+32) - t_i) / 32
p_hat = median(p_i)
BPM_refined = 60 / p_hat
robust_CV = 1.4826 * median(|p_i - p_hat|) / p_hat
```

The candidate is accepted only when:

- at least eight 32-beat spans exist;
- `robust_CV <= 0.01`;
- the result stays within 5% of the tracker's current BPM.

The final condition prevents this precision stage from inventing half-time,
double-time or 3:2 corrections. It improves precision within the already chosen
metrical level; it does not decide which level is musically correct.

## Current benchmark

Run:

```bash
PYTHONPATH=src ./.venv/bin/python -m dancelab.validation.tempo \
  --analyses data/processed/smart_playlist \
  --rekordbox-xml "/path/to/rekordbox-export.xml" \
  --output data/reports/tempo_validation_rekordbox
```

Primary results use exact normalized file paths only. Name matching is reported
separately and never enters the primary score.

Current exact-path benchmark:

- 142 analyzed tracks matched;
- raw BPM median error: 0.386%;
- refined BPM median error: 0.013%;
- raw BPM p90 error: 1.204%;
- refined BPM p90 error: 0.051%;
- 12 metric-level errors above 2% remain visible;
- only 73/142 first tracked beats correspond to Rekordbox beat 1;
- only 11/142 tracks keep p90 grid-phase error within 0.05 beat.

The complete deterministic outputs are in
`data/reports/tempo_validation_rekordbox/`.

## Safety decisions

- Default Rekordbox export continues to omit `AverageBpm` and `TEMPO`.
- Beat sync remains a DanceLab review-player function.
- A baseline `BeatGrid` can be reliable for beat playback while its bar phase
  remains unverified.
- Unverified grids may snap an exported hot cue to the nearest detected beat,
  but may not claim an 8/16/32-beat phrase boundary.
- Diagnostic Rekordbox TEMPO export requires a verified downbeat phase.
- Automatic 3:2, 4:3 and 5:4 metric-level correction remains disabled until a
  separately validated multi-hypothesis tempo model exists.

## Remaining blocker

The current librosa baseline detects beats but not a trustworthy beat-one/bar
phase. `downbeats_sec` remains a visual proxy (`beat_times[::4]`) and carries
`downbeat_phase_unverified_proxy`. A future downbeat source must pass the same
large-library benchmark before phrase quantization or exported phrase claims
can rely on it.

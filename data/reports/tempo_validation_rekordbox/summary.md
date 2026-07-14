# Tempo and beat-grid operational benchmark

Rekordbox XML is used as a read-only operational reference, not scientific ground truth.
Only exact-path matches are included in the primary metrics.

## Coverage

- DanceLab analyses: 240
- Exact-path matches: 142
- Unique-name fallback matches (diagnostic only): 24

## BPM precision

- Raw median / p90 error: 0.386364% / 1.204398%
- 32-beat refined median / p90 error: 0.012686% / 0.050977%
- Gross metric-level errors above 2% remain: 12

## Grid phase

- Median per-track p90 phase error: 0.460027 beat
- Tracks with p90 phase error <= 0.05 beat: 11 / 142
- First tracked beat is a true downbeat: 73 / 142

## Decision gates

- Long-span BPM precision candidate: PASS
- Proxy downbeats for 8/16/32-beat phrase claims: FAIL
- Automatic 3:2 / 4:3 / 5:4 metric correction: NOT VALIDATED
- This report mutates engine weights or Rekordbox data: NO

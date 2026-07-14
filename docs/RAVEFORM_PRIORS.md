# Raveform Transition-Duration Priors

DanceLab can train an offline, source-backed population prior from the public
[Raveform dataset](https://mir-aidj.github.io/raveform/). This is a validation
artifact, not a production planner. It does not modify engine weights, track
analysis, BPM, beatgrids, transition windows, or Rekordbox export.

## Dataset boundary

The audited archive has SHA-256:

```text
10c97fa9213fe4ca032195e73b6a9d068c0d5ca8a8f603615bb1bdbabffb34de
```

The loader reproduces the existing strict audit:

- `4,911` mix tracklists;
- `78,344` raw alignment rows;
- `62,302` rows with `match_rate > 0.4` and track-beat data;
- `41,081` qualified adjacent pairs;
- `24,558` positive overlap observations in the `1..256` beat product range.

The extracted table has an explicit grain of one qualified positive-overlap
transition per `(mix_id, tracklist_position)`. The current artifact reports:

- `0` duplicate primary rows;
- `0` transitions with the same track on both sides;
- genre context for `24,556 / 24,558` observations (`99.9919%`);
- section-pair context for only `421 / 24,558` observations (`1.7143%`);
- `72` distinct mix-level genre labels and `28` distinct section pairs.

Target-distribution total variation is `0.01718` between train and validation
and `0.01836` between train and test. This is recorded to distinguish model
quality from accidental split drift.

Missing or failed entries are never skipped to manufacture a false A-to-B
pair. Raveform mix points are DTW estimates, not manually captured fader or EQ
movements.

## Model

Observed overlap is mapped to the nearest supported duration in:

```text
32, 64, 96, 128, 160, 192, 224, 256 beats
```

For bucket `k`, the global posterior mean uses a symmetric Dirichlet prior with
`alpha = 0.5`:

```text
p_global(k) = (n_k + 0.5) / (N + 0.5 K)
```

For context `c` (genre or outgoing/incoming section pair), DanceLab applies
hierarchical shrinkage toward that global distribution:

```text
p(k | c) = (n_c,k + tau p_global(k)) / (n_c + tau)
```

`tau` is selected only on validation mixes from the fixed candidate set
`1, 2, 5, 10, 20, 50, 100`. The implementation uses no track ID as a model
feature.

This is a transparent empirical-Bayes categorical model. The probability
contract follows the standard Dirichlet distribution described by
[SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.dirichlet.html),
but DanceLab implements the small closed-form posterior directly and does not
depend on SciPy at runtime.

## Leakage and selection

Whole `mix_id` groups are deterministically split `70/15/15`; mix overlap is
zero. A fully track-disjoint split is not statistically usable: `94.5%` of
mixes form one connected component through repeated tracks. The report keeps
track-ID overlap visible, and the model cannot memorize track IDs because they
are excluded from its inputs.

The held-out split contains `5,490` distinct tracks. It shares `1,140` with
training, or `20.77%` of the smaller track set. This is a limitation of the
collection rather than silent leakage across mix groups; no row from a held-out
mix is used for fitting or model selection.

Context is enabled only when the paired validation log-loss improvement is
statistically stable:

```text
delta_i = NLL_context,i - NLL_global,i
upper_95 = mean(delta) + 1.64485 * SE(delta)
enable context only if upper_95 < 0
```

The untouched test split is then used once for the final report. Metrics include
negative log-likelihood, multiclass Brier score, top-1 accuracy and expected
calibration error. These metrics follow the separation between discrimination
and calibration described in the
[scikit-learn calibration guide](https://scikit-learn.org/stable/modules/calibration.html).

## Current held-out result

The generated `v1` artifact selected `tau = 50` for genre and section contexts.

| Test model | NLL | Brier | Top-1 |
|---|---:|---:|---:|
| Global | 1.70125 | 0.77563 | 0.36148 |
| Genre | 1.66449 | 0.76050 | 0.36148 |
| Hybrid after validation gates | 1.66449 | 0.76050 | 0.36148 |

Genre passed the validation gate (`upper_95 = -0.04499`). Section pairs did
not (`upper_95 = +0.01624`) and are disabled in the default hybrid. On the
structured held-out subset, section conditioning also performed worse than its
global baseline (`NLL 1.74183` versus `1.71628`). Its tables remain in the
artifact for diagnosis, not runtime use.

The result supports a soft genre-conditioned **duration prior**. It does not
support automatic cue placement, pair acceptance, EQ automation, or claims of
DJ preference probability. `eligible_for_engine_influence` remains `false`.

## Reproduce

```bash
cd /Users/jantrybus/Desktop/AI/dancelab-engine
PYTHONPATH=src ./.venv/bin/python -m dancelab.validation.raveform \
  --archive /tmp/raveform.zip \
  --output data/reports/raveform_prior_v1/raveform_duration_prior.json
```

The command reads the local archive and writes a separate JSON artifact. It
does not download audio and does not write to the engine cache.

# Raveform Duration Prior v1

Status: **validated offline; not connected to engine decisions**.

- Source archive: `10c97fa9213fe4ca032195e73b6a9d068c0d5ca8a8f603615bb1bdbabffb34de`
- Observations: `24,558` positive adjacent overlaps from `4,911` mixes.
- Split: `3,213 / 689 / 689` train/validation/test mixes; zero mix-ID overlap.
- Model: Dirichlet-smoothed categorical duration prior over `32..256` beats.
- Selected prior strength: genre `50`, section pair `50`.
- Genre context: enabled by paired validation gate.
- Section-pair context: disabled by paired validation gate.

Data-quality checks:

- Grain: one positive qualified transition per `(mix_id, tracklist_position)`;
  `0` duplicate primary rows and `0` same-track transitions.
- Context coverage: genre `99.9919%`; section pair `1.7143%`.
- Split target drift is small: total variation `0.01718` train/validation and
  `0.01836` train/test.
- Mix-ID overlap is `0`. Track overlap remains visible because the public
  collection is highly connected: train/test share `1,140` tracks (`20.77%`
  of the smaller track set). Track IDs are not model inputs.

Held-out result:

| Model | NLL | Brier | Top-1 |
|---|---:|---:|---:|
| Global | 1.70125 | 0.77563 | 0.36148 |
| Genre | 1.66449 | 0.76050 | 0.36148 |
| Default hybrid | 1.66449 | 0.76050 | 0.36148 |

The genre prior improves probabilistic fit but does not change the most common
class. It is a population prior for future controlled experiments, not a reason
to alter the current planner automatically.

Full model, distributions, selection trials, leakage audit and limitations are
in `raveform_duration_prior.json`.

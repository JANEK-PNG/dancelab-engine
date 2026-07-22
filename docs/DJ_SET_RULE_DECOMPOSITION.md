# DJ Set Rule Decomposition

Status: offline measurement protocol, not a production ranking term.

This module formalizes the 2026-07-19 DanceLab workshop result about separating
what can be reconstructed from DJ sets into:

- `C_rule`: contribution of interpretable audio rules such as tempo, key,
  energy and timbre;
- `C_sim`: contribution of learned audio similarity embeddings;
- `I`: regularized DJ-specific effect;
- `N`: residual resistance to reconstruction.

The workshop result is a research hypothesis implemented for validation. It is
not itself an external publication, calibrated probability or proof of DJ
intent.

## The closed formula

For five held-out negative log-likelihoods evaluated on identical test sets,
available pools `U` and transition risk sets `R_t`:

```text
L0    random baseline
LH    handcrafted audio features
LE    audio embeddings
LHE   handcrafted + embedding features
LHEI  handcrafted + embedding + regularized DJ effect
```

the two-block Shapley decomposition is:

```text
C_rule = ((L0 - LH) + (LE - LHE)) / (2 * L0)
C_sim  = ((L0 - LE) + (LH - LHE)) / (2 * L0)
I      = (LHE - LHEI) / L0
N      = LHEI / L0
```

The four values sum to exactly one. Negative values are retained: they indicate
that a layer failed to generalize on held-out data.

Every loss carries the same mandatory `evaluation_hash`. The hash must cover
the test set IDs, observed pools `U`, per-transition risk sets `R_t`, weights
and split version. `decompose_losses()` refuses to compare mismatched hashes.

## Selection and ordering are separate

The protocol reports:

1. `order-given-crate`: how the already selected crate was ordered;
2. `joint-selection-and-ordering`: selection loss plus ordering loss.

The joint report is valid only when both components use the same evaluation
universe.

Selection uses an additive fixed-size subset model. For item log-scores `s_i`
and selected subset size `m`, its partition function is:

```text
Z(U, m) = [z^m] product_i (1 + z * exp(s_i))
```

`log_fixed_size_partition()` calculates it exactly in `O(|U| * m)` with a
log-domain dynamic program. No importance-sampling approximation is hidden in
the implementation.

Scope limitation: this additive selection model measures the attractiveness of
individual tracks relative to the observed pool. Emergent crate coherence and
track-to-track interactions are not represented and remain in `N_selection`.
If the true available pool `U` is unknown, selection is non-identifiable and
only the ordering report is valid.

## DJ identity versus a different crate

`assess_crate_overlap()` computes an audio-space qualification for every DJ:

```text
epsilon_d = alpha * median within-crate nearest-neighbour distance
O_dd'     = fraction of tracks in d with a neighbour in d' below epsilon_d
q_d       = max_d' min(O_dd', O_d'd)
```

Low `q_d` means a positive `I` cannot be cleanly attributed to DJ identity; it
may simply describe a different crate. The aggregate `weighted_q` is weighted
by the number of sets per DJ.

Collapsed embedding geometry and crates with fewer than two tracks are
reported as non-identifiable rather than assigned invented overlap values.

## Uncertainty

Transitions inside one set are dependent because the risk set shrinks with
history. Bootstrap units must therefore be whole sets. The helper
`block_bootstrap_set_ids()` creates deterministic set-level samples.

Valid full uncertainty intervals require refitting all five models, including
regularization selection, in every bootstrap replicate. Reusing one fitted
model measures only test-sample uncertainty and must be labeled as such.

## Runtime boundary

Implementation:

- `src/dancelab/validation/djmix/decomposition.py`
- `tests/test_djmix_decomposition.py`

Nothing in this module is imported by `decision/`, the desktop host, Rekordbox
export or the production planner. Corpus training and any engine influence
remain separate future gates requiring leakage-free, style-stratified held-out
validation.

The executable dataset, feature provenance and five-model protocol are
documented in `docs/CORPUS_ORDERING_DATASET_V1.md`.

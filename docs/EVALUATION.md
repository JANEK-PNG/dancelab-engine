# Evaluation

How DanceLab's decision layer is measured, what it scores against a baseline, and which of its ideas failed. This is the short version for a reader who has two minutes. Every number here names the script that produced it.

---

## The question

> Given what a DJ has already played, does the engine rank the track they actually played next above the alternatives they had available?

Not "is this transition good" — that requires an opinion. This question has a recorded answer.

---

## Data

| Source | Scale |
|---|---|
| Aligned public DJ mixes | 5,040 mixes, ~100k tracklist positions |
| Mix alignments used for priors | 801 mixes → 23,644 candidate transitions → 10,233 valid → **6,144 joined with analysis** |
| Track analysis catalogue (BPM, Camelot key, energy) | 2,881 tracks |
| Audio embeddings (LAION-CLAP) | 12,668 vectors |
| Ordering observations (history + candidates + the DJ's actual pick) | **1,604** |

Corpus audio is never redistributed and is deleted after feature extraction — see [CORPUS_ETHICS.md](CORPUS_ETHICS.md). What survives is features, alignments and statistics.

---

## The contrast class: chance, not human negatives

Published DJ sets are a survivorship-biased sample — they are all "good". Comparing good transitions against human-rated bad ones would model the annotator, not the practice. So the contrast class is **random pairs drawn from the same mixes' track pools**: what would a transition look like if the DJ had not chosen?

Consequence: no labelling effort, no annotator bias, and the gap between the two distributions *is* the preference signal.

One human-rated dataset does exist in the project — 35 blind ratings by the author. It was **removed from the tuning loop**: the transitions had been rendered on a beat grid later found to be wrong, so the ratings punished pairs for an analysis bug, and n = 1 is not a population.

---

## Metric

Rank of the DJ's actual next track among the candidates available at that moment, scored from the last track in history.

The first version of this evaluation reported top-1 accuracy over 333 observations — those with ≥5 candidates. That filter was an artifact: the average observation has ~3.5 candidates, so the metric had silently selected the easy half of the data and discarded set openers. **Version 2 uses a candidate-count-independent rank-percentile over all 1,604 observations** (0.5 = random). The headline got less impressive and the result got true.

---

## Result 1 — Corpus-measured weights beat hand-set weights

`scripts/priors_validation.py` → `data/reports/corpus_priors/validation_v1.json`

| Scorer | Rank percentile (lower = better) | Top-1, n≥5 subset |
|---|---|---|
| **Measured** (likelihood ratios from the corpus) | **0.427** | **24.3%** |
| Hand (the engine's original weights) | 0.442 | 20.7% |
| Random | 0.490 | 18% |

Both beat random decisively. Measured beats hand consistently in direction across every metric, and the paired bootstrap gives **p = 0.12** — *not* significant at α = 0.05. It is reported that way here and everywhere else in the project.

The secondary finding is the more useful one: hand-set weights sat barely above random.

---

## Result 2 — Tempo prior strong, harmonic prior weak

`scripts/corpus_priors.py` → `data/reports/corpus_priors/priors_v1.json`

- Real transitions stay within 0–2% octave-folded ΔBPM **62.9%** of the time vs **51.6%** by chance; jumps >10% are avoided at **2×** chance.
- **63% of real DJ transitions are "risky"** under the engine's own Camelot vocabulary, a lift of only ~1.3× over chance.

The engine was over-weighting harmony relative to observed practice. Caveat kept with the number: key detection on rips is noisy, so part of that gap may be measurement rather than practice.

---

## Result 3 (negative) — Sound similarity is real in the population and harmful in the ranking

`scripts/corpus_priors_clap.py` → `data/reports/corpus_priors/priors_clap_v1.json`

DJs do prefer similar-sounding tracks: **1.52× lift** at CLAP cosine ≥ 0.90, tracks below 0.60 avoided at 2×, median 0.833 vs 0.815 chance.

Adding that lift to pair scoring **reduced top-1 from 24.3% to 20.1%**.

Diagnosis: the candidates in an observation come from a crate the DJ already curated for sound, so the signal is nearly constant *inside* the choice set. Sound similarity governs **pool construction**, not **next-item ranking**. The feature was moved, not shipped — a measured negative result blocking a plausible weight.

---

## Result 4 (negative) — Energy prior is flat

Energy quintiles against chance produced lifts of **0.94–1.04**. The rule "do not wire it unless it beats chance" was declared before the measurement and held: it is not wired. Energy belongs to the set-level arc the engine already models, not to the pair — within-mix pools are energy-homogeneous.

---

## Result 5 (negative) — Blind seam detection fails its own gate

Detecting transitions in a mix *without* the tracklist, on a real 52-minute set with 18 known transitions:

- Best of 16 operating points: precision **25%**, recall **28%**, **F1 0.263** (5 found, 15 false alarms).
- Negative control (10 single tracks, zero seams): **0.21 detections/min** against a pre-declared gate of **<0.20** — failed.

Two assumptions died with it, including "a fixed bar grid is valid across a 52-minute set": real local tempo ranged 89–141 BPM and a global fit drifted 28 bars. Work was redirected to subsequence-DTW alignment of known source tracks (Kim et al., ISMIR 2020), which the engine already implements as M11.

The honest measuring harness (`evaluate.py`, 1:1 matching, tolerance in bars, mandatory negative control) survived and has since stopped two premature success claims.

---

## Numbers we withdrew from our own work

Kept here because they are the reason to trust the rest.

- **Median transition length of 94 beats** was wired into production scoring one morning and removed the same day. A field audit showed 14.3% of the underlying values were *negative*, 28.7% longer than four minutes, and only 42.4% physically possible. The alignment pipeline cuts out the overlap region, so its "transition length" is the distance between track boundaries, not the seam. Scoring reverted to structural phrase multiples (8/16/32).
- **"Bass cut by hand in 86% of transitions"** became **62%** once a guard distinguished *a bass that was removed* from *a track that never had bass in its intro*.
- **A usable-seam count of ~6,500** became **49** after deduplication (29% duplicates) and a requirement that both tracks actually overlap for ≥4 s.

---

## What these numbers do not show

- Top-1 accuracy treats every unplayed candidate as wrong. Several would have worked. This measures **agreement with one realised human path**, not quality.
- The corpus is published sets by professional DJs. It says nothing about listeners, and nothing about how a room responded. The engine is forbidden from predicting crowd response.
- Key detection on rips is noisy; the harmonic result carries that caveat.
- No result here has been peer-reviewed.

---

## Reproducing

**The headline numbers cannot be reproduced from a clone, by design.** The corpus alignments live on an external volume and are never redistributed (see [CORPUS_ETHICS.md](CORPUS_ETHICS.md)), and `data/reports/` is gitignored. What is in the repository is the code that produced every number, plus the JSON schemas of the outputs.

With the corpus mounted and the analysis catalogue built:

```bash
PYTHONPATH=src python3 scripts/corpus_priors.py        # → data/reports/corpus_priors/priors_v1.json
PYTHONPATH=src python3 scripts/priors_validation.py    # → validation_v1.json  (Result 1)
PYTHONPATH=src python3 scripts/corpus_priors_clap.py   # → priors_clap_v1.json (Result 3)
```

Required inputs, all regenerable by other scripts in `scripts/`:
`data/reports/corpus_ordering/` — `dataset.json`, `analysis_index.json`, `h_analysis/`, `embeddings.json`; and corpus alignments at the path configured at the top of each script.

The engine's own decision layer is covered by the test suite, which *does* run from a clone:

```bash
.venv/bin/python -m pytest
```

---

## Provenance rules these results follow

- Formulas are tagged `candidate` or `hypothesis`; an unimplemented computation **raises an error rather than returning a plausible default**.
- Unknown values leave the system as `None` with a warning, never as an imputed default. A measurement below the noise floor is reported as unmeasurable.
- Every decision output carries an explanation, a confidence and a provenance record naming what the result may not be used to claim.
- Predicting crowd response is prohibited outright.

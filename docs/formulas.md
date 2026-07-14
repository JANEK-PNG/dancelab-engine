# Formula → module mapping (Engine Computation Specification)

| Spec § | Formula | Module | Status | Implemented |
|---|---|---|---|---|
| 1.1 | RMS(t) = √(1/N Σ x²) | `features/rms.py` | stable | ✅ |
| 1.2 | SF(t) = Σₖ max(0, Xₜ−Xₜ₋₁) | `features/spectral_flux.py` | stable | ✅ |
| 1.3 | LFER(t) = ΣP(low)/ΣP(all), band 20–150 Hz | `features/spectral_flux.py` | stable | ✅ |
| 2.1 | D_onset = N_onset/Δ | `features/onset_density.py` | stable | ✅ (librosa onsets; sliding-window count) |
| 2.2 | C_pulse = A_beat/(ΣAᵢ+ε) | `features/pulse.py` | candidate | ✅ (beat-aligned novelty autocorrelation ratio proxy) |
| 2.3 | S_sync = Σ wᵢ·max(0, aᵢᵒᶠᶠ−aᵢᵒⁿ) | `features/microtiming.py` | candidate | ✅ (beat-vs-offbeat onset distance proxy) |
| 2.4 | G_audio = w₁C_pulse+w₂S_sync+w₃D_onset+w₄B_sal+w₅M_micro | `descriptors/groove.py` | candidate | ✅ (candidate weighted groove curve from implemented proxies) |
| 3.1 | B_energy = Σ P(bass band) | `features/bass.py` | stable | ✅ |
| 3.2 | B_sal = α₁B̃+α₂A_kick+α₃C_rhythm−α₄C_mask | `descriptors/bass_salience.py` | candidate | ✅ (candidate bass readability / masking proxy) |
| 4 | M_micro = Var(δ) or MAD(δ), δᵢ = tᵢ−t̂ᵢ | `features/microtiming.py` | candidate | ✅ (matched onset-beat MAD + per-window profile) |
| Vocal | vocal_density_proxy: demucs vocals-stem energy ratio (silence-gated), HPSS fallback | `features/vocals.py` | candidate | ✅ (demucs; feeds TW R_vocal + mixability S_vocal) |
| 5.1 | T_audio = Σ βᵢZᵢ | `descriptors/tension.py` | candidate | ✅ (candidate cue fusion from rise/delay/spectral/instability/expectation proxies) |
| 5.2 | R(t) = max(0, T_eff(t⁻)−T_eff(t⁺)) | `descriptors/release.py` | candidate | ✅ (candidate release map from local tension drop after peaks) |
| 5.x | breakdown / drop candidate detectors | `descriptors/breakdown_drop.py` | candidate | ✅ (candidate likelihood curves from energy/bass/onset/tension/release; used to refine non-edge segment labels) |
| 6 | PE(t) = d(E_obs, E_pred) — v0 proxies | — | deferred | ❌ (no runtime placeholder) |
| 7 → **TW v0.1** | W = γ₁S_struct+γ₂S_rhythm+γ₃S_energy+γ₄S_phrase+γ₅S_bass−γ₆S_vocal−γ₇S_tension; TopK(localmax) + NMS | `decision/transition_windows.py` | candidate | ✅ (Sprint 2; components from available inputs, missing → neutral+warning) |
| 8 → **Mix v0.1** | M_ix = ΣλᵢSᵢ (tempo,phrase,energy,bass,vocal,tension,style,context); M_pair = M_ix+Wₐ+W_b−R_conflict | `decision/mixability.py` | candidate | ✅ (phrase-aware windows + tension/release coverage now feed pair scoring when analyses carry Phase 2 descriptors) |
| SF v0.1 | F_set = argmax_r S_r(x,c); S_r = w_r·φ(x)+b_r−R_r; conf=softmax | `decision/set_function.py` | candidate | ✅ (Sprint 2 Final; rule-based priors, φ from energy shape/LFER/windows) |
| 9 | U_DJ = F(G_eff, T_eff, R, M_ix, W_trans, C_fit) | `decision/next_track.py` | candidate | ✅ (v0.1 heuristic ranker from mixability + context fit + role fit + energy-step suitability + groove continuity) |
| Core Eq. | X_eff(t\|s,c) = X_audio(t\|s)·C_fit(t\|c) | `context/conditioning.py` | candidate | ✅ (role-conditioned heuristic `C_fit` over energy/bass/vocal curves) |

**Phase 1 pair layer additions:** transition windows now infer `compatible_contexts`
heuristically and carry candidate strategy hints; unified pair decisions are
available through `decision/edge_decision.py` and the `/pairs/edge-decision`
API route. Transition strategy remains a candidate heuristic, not a validated
live-mixing prescription.

**Phase 2 descriptor additions:** `analyze` now persists candidate descriptor
curves for groove, bass salience, tension, release, and explicit
`breakdown_likelihood` / `drop_likelihood`; non-edge segment labels are refined
with those detectors after the baseline segmentation pass.

**Beatgrid** (`preprocessing/beatgrid.py`, candidate): librosa DP beat tracker → BPM +
beat times + an unverified 4/4 downbeat proxy; feeds phrase alignment. Octave-folds
half/double-time candidates into [90,180) and applies a 32-beat tempo refinement.
Beat timing has operational benchmark coverage; downbeat phase is not ground truth
and is not exported as a Rekordbox tempo grid.
**Phrase awareness** (`core/phrasing.py`, candidate): phrase anchors now combine
beatgrid regularity with snapped segment boundaries, so transition/mixability
logic is less rigid than a plain 32-beat grid.
**Normalization** (`core/normalization.py`, Normalization Protocol v0.1): min-max +
robust percentile (P5–P95, outlier-safe) to [0,1]/[0,100]; constant → 0.5.
**Validation metrics** (`validation/dj_decision_metrics.py`): IoU, top-k hit, Spearman ρ,
Kendall τ, Cohen κ (S039/S041/S042) — for EXP014/015 once DJ labels exist. **Segmentation**
(`preprocessing/segmentation.py`, candidate): agglomerative over MFCC+chroma+RMS →
boundaries (reliable) + heuristic type labels (unvalidated); feeds structural score.

Weights: `configs/descriptor_weights.yaml` (versioned; initial values are untuned priors).

**ADR-005 discipline:** implemented candidate modules carry explicit status and
provenance. Deferred ideas are documented here rather than exposed as importable
functions that can only raise `NotImplementedFeature`.

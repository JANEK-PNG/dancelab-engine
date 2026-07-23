# Pre-registered predictions — corpus transition analysis

Registered 2026-07-15, BEFORE measuring the aligned corpus
(`/Volumes/MY_PC/DanceLabCorpus/alignments/`). Discipline: predictions are
written down first, then measured, then compared. No post-hoc "I knew it".

## P1 — octave-cross transitions are near-zero (Janek, domain expert)

Claim: real DJs almost never transition between tracks whose true tempos
relate by ~2× (e.g. house 90 ↔ jungle 180), even though beat-sync math
allows it. "Mathematically it can work, but it sounds awful. No one wants
to hear jungle with house."

Measure: fraction of valid corpus transitions where adjacent tracks' engine
BPMs (octave-folded to true musical tempo) differ by a factor in
[1.8, 2.2]. Prediction: **< 2% of transitions.**

Engine consequence if confirmed: `nearest_bpm_variant` / `bpm_score` treat
octave-equivalence as free compatibility today. A confirmed near-zero rate
means octave-variant matches need a calibrated penalty (size = measured
rate), or a genre/style gate.

## P2 — D&B/jungle tempo cluster stays high (Janek)

Claim: jungle/D&B lives at ~170-200 BPM perceived (artists deliberately
write in double-time to squeeze more BPM into CDJ ranges). The corpus BPM
histogram for D&B-tagged mixes should cluster ~170-185, NOT fold down to
85-95.

Measure: per-genre BPM histogram of matched tracks. Prediction: D&B modal
bin 170-180; if we instead see a twin peak at 85-92, that is the engine's
octave fold failing on real data (bug evidence, not DJ behavior).

## P3 — transition lengths ordered by genre (Claude)

My skin in the game: median transition length in beats is ordered
**D&B < house/techno < trance**. D&B culture favors quick chops and double
drops (16-32 beats); trance favors long blends (64+). Paper (DLASOT-13,
house/trance-heavy) found peaks at multiples of 32 overall.

Measure: per-genre median + IQR of `transition_length_beats` on valid
transitions.

## P4 — tempo-change replication holds overall (both)

The corpus-wide tempo-change distribution should replicate DLASOT-13
(≈86% < 5%, ≈95% < 10%). Large deviation = OUR pipeline is broken, not a
discovery. This is the trust gate, not a discovery claim.

## Scoring

After measurement each prediction gets: CONFIRMED / REFUTED / INCONCLUSIVE
(+ the actual number with bootstrap CI). Refuted predictions are as valuable
as confirmed ones — they calibrate the predictor, per the mentor protocol.

## P5 — rho after octave fix (Janek, registered 2026-07-16 pre-reveal)

Prediction: re-scoring the same 35 blind ratings against the current engine
(evidence-gated octave fold) lifts Spearman rho from 0.30 to **0.65**.
Reasoning given: "BPM is fixed now."

### P5 verdict — REFUTED (measured 2026-07-16)

rho_old = 0.304 → rho_new = 0.272 (tau 0.251 → 0.244). Prediction was 0.65.
Only 2/36 tracks changed BPM at all (both ~1 BPM, cosmetic). The evidence
gate refused to double the four half-time suspects on REAL audio (e.g.
TOM LECHEF - HEAD COUNT stays 90.67, no double-time evidence found), while
it fires fine on synthetic clicks and on some tracks (Hush: folded to 140,
coverage=0.90). Finding: the gate's thresholds are tuned too strict for
real bass-music texture — sensitivity/specificity trade-off to calibrate
against ear-verified ground truth. Second finding: even a perfect BPM fix
could not lift rho to 0.65 — ratings partly scored the broken player, and
the missing signals (texture/mood/genre) are not in the engine yet.

## Werdykty na PEŁNYM korpusie (801 mixów, 23 644 przejścia, 2026-07-17)

- **P1 (Janek, octave-cross <2%): CONFIRMED.** 0.9% (CI 0.6–1.1%), n=6142 par.
  Cały CI poniżej 2%. Pilot dawał 3% (szeroki CI) — na masie usiadło. DJ-e
  praktycznie nie przechodzą przez oktawę. Wiedza domenowa Janka potwierdzona.
- **P2 (Janek, jungle wysoko, bez zapadu half-time): CONFIRMED.** bass median
  156.9 BPM (najszybszy gatunek; house 124.9, techno 127, trance 130), tylko
  1% w paśmie 82-96 → zero zapadu oktawowego na korpusie. Mediana <170-185 bo
  tag "bass" łapie bass house ~125, ale modalna górka ~172. Kluczowa
  falsyfikowalna część (brak twin-peak) potwierdzona.
- **P3 (Claude, D&B najkrótsze przejścia): REFUTED.** Zmierzone: house 110 <
  bass 132 < techno 163 < trance 174 beatów. D&B w środku stawki, nie
  najkrótszy. Model "jungle = szybkie cięcia" obalony. Trance najdłużej (to
  jedno trafione). Uwaga: długości nadal noisy (IQR szeroki, śmieci przeciekają).
- **P4 (replikacja tempo-change): DEFERRED** — wymaga persystencji ścieżki DTW,
  której nie zapisujemy. Do zrobienia przy Transition Reverse-Engineering.

Bilans korpusu: Janek 2/2 (domena), Claude 0/1 (inżynierska zgadywanka).
Wniosek nadrzędny: zapad oktawy = problem OTAGOWANEJ biblioteki Janka
(Rekordbox), NIE korpusu. Ripy YouTube (bez tagów) składają się poprawnie.

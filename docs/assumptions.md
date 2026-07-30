# Assumptions (deliverable 9)

1. **Server-visible paths in v0 API.** `POST /tracks/analyze` takes `source_path`
   instead of multipart upload. Upload + object storage is Sprint 1+. Keeps v0
   testable and honest about scope.
2. **Mono 44.1 kHz analysis.** Config default `mono: true`. Stereo-specific cues
   (width, panning) are not v0 descriptors. Revisit if DJ Domain Expert flags
   stereo-dependent decisions.
3. **Track identity = sha1(source_path)[:16].** Deterministic and simple; NOT
   content-based. Re-encoded duplicates get different ids. Content hashing
   (audio fingerprint) is a later decision.
4. **Weights are untuned priors.** `descriptor_weights.yaml` v0.1.0 values are
   placeholders for pipeline construction; tuning requires the annotated dataset
   (validation.md). No claim of correctness.
5. **Normalization strategy unresolved.** Composite descriptors (groove, tension)
   sum differently-scaled inputs; z-score vs min-max vs style-relative normalization
   is an open Sprint 1 decision. Blocking for descriptor implementation.
6. **`X_eff = X_audio · C_fit` multiplicative form is itself a candidate model**
   (Core Equations status: candidate). Engine treats it as pluggable.
7. **Optional integrations and heavy deps.** librosa/scipy/pandas live behind
   `[audio]`; direct Rekordbox cue writing lives behind `[rekordbox]`. The core
   installs without either profile, while CI exercises both supported paths.
8. **SQLite before PostgreSQL.** Postgres only via docker-compose; no ORM decision
   yet (sqlite3 vs SQLAlchemy is Sprint 1).
9. **Batch-first over API-first** for validation work (Sprint Zero open decision —
   resolved: batch CLI is the primary research loop; API serves integration).
10. **Example JSON contains illustrative values**, clearly derived from no real
    audio; its role is schema documentation, enforced by test.
11. **Fourth router (`routes_sets.py`)** added beyond blueprint's three route files —
    contract draft's `/sets/recommend-next` deserved its own module.
12. **Polish vault, English code.** Code, docstrings, API in English; vault terms
    (groove, tension, set function) kept as domain vocabulary.

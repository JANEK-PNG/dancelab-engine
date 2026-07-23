# NAINA Presents catalogue pipeline

## Purpose

This offline validation add-on maps the public NAINA Presents series as:

`published performer billing -> Apple Music DJ mix -> ordered mixed-song IDs`

The output is suitable for catalogue QA, identity adjudication and descriptive
ordering analysis. It is not imported by the production planner and does not
change DanceLab rankings.

## Trust boundary

- The raw Apple Music snapshot is immutable evidence.
- `apple_music:album:<id>` identifies the published mix.
- `apple_music:song:<id>` identifies a segment on that mixed album.
- A mixed-song ID is not treated as an ISRC, an original master ID or a local
  DanceLab audio fingerprint.
- Published adjacency means only that B follows A in the official tracklist. It
  does not reveal the transition boundary, EQ movement or rejected crate tracks.
- Explicit `b2b` billings are source-backed. Multiple creators without `b2b`
  remain in manual review rather than being guessed as solo, duo or collective.
- Missing row-level artist credits use the album creator only as a visibly
  provisional fallback and create a review item.

## Layers

1. `apple_music_raw.json`: unchanged collection snapshot and source provenance.
2. `naina_catalog.json`: deterministic normalized exchange format.
3. `naina_catalog.sqlite3`: foreign-keyed analysis database.
4. `DanceLab_NAINA_Catalog_Review.xlsx`: separately generated, human-readable
   QA and adjudication layer.

The spreadsheet is not a second source of truth. Review decisions should be
imported explicitly and fingerprinted before they are allowed into a model gate.

## Build

```bash
PYTHONPATH=src python scripts/build_naina_catalog.py \
  data/reports/naina_catalog/apple_music_raw.json \
  data/reports/naina_catalog
```

The builder fails closed when volumes are missing, positions are not contiguous,
or the independent DOM and JSON-LD representations disagree.

# Warehouse Project Apple Music catalogue

## Purpose

This validation add-on turns the official Apple Music Warehouse Project curator
catalogue into a reviewable relationship graph:

`published performer billing -> DJ mix -> ordered Apple mixed-song segments`

It is deliberately separate from the DanceLab recommendation engine. Building or
reviewing this dataset does not tune ranking weights, change transition rules, or
modify the supported terminal workflow.

## Source contract

The source of truth is the public Apple Music curator page and the linked album
pages. Screenshots are useful for visual coverage checks only; no catalogue row is
created from OCR.

For every accepted album, the importer compares two independent representations
published on the same Apple page:

- serialized page data used by the Apple Music interface;
- `MusicAlbum` JSON-LD used for structured metadata.

Album ID, title, creator credits, track count, track order, segment ID and segment
title must agree. A disagreement stops the build instead of being silently repaired.

## Inclusion and roles

- A release is accepted only when its published title ends with `(DJ Mix)`.
- Releases, singles and EPs without that explicit suffix remain in the rejected-items
  table with their source URL and rejection reason.
- `b2b` is assigned only when the published title explicitly contains `b2b`.
- `with`, `w/`, `Featuring`, and multi-artist billing without `b2b` remain separate
  role suggestions and enter manual review where needed.
- A mix may belong to more than one Apple Music program shelf; this is represented
  as a many-to-many relation, not duplicated mixes.

## Identity boundary

An Apple mixed-song ID identifies the segment published inside a DJ-mix album. It
must not be treated as proof of the underlying source master, ISRC, local file, or
DanceLab audio fingerprint. Missing artist IDs stay null. Placeholder titles such as
`ID` or `ID1` stay unresolved and are placed in the review queue.

Published neighbouring rows provide observed ordering evidence only. They do not
reveal a transition boundary, EQ movement, cue point, rejected crate candidates, or
the DJ's causal intent.

## Reproducible build

```bash
PYTHONPATH=src ./.venv/bin/python scripts/fetch_warehouse_catalog.py \
  data/reports/warehouse_catalog

PYTHONPATH=src ./.venv/bin/python scripts/build_warehouse_catalog.py \
  data/reports/warehouse_catalog/apple_music_raw.json \
  data/reports/warehouse_catalog
```

The fetcher is resumable. Valid cached pages are reused; invalid cached pages are
fetched again. It accepts only HTTPS URLs on `music.apple.com`, limits redirects,
response size, concurrency, timeout and retry count, and writes the raw snapshot
only after every accepted DJ mix passes validation.

The normalized JSON has a deterministic fingerprint. SQLite is written atomically,
uses foreign keys, and must pass `PRAGMA foreign_key_check` before replacing the
previous database.

## Outputs

- `apple_music_raw.json`: immutable source snapshot and page hashes;
- `warehouse_catalog.json`: normalized, deterministic review dataset;
- `warehouse_catalog.sqlite3`: relational analysis database;
- `DanceLab_Warehouse_Project_Catalog_Review.xlsx`: human review workbook generated
  from the normalized JSON, never used as the source of truth.

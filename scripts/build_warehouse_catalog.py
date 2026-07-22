#!/usr/bin/env python3
"""Build Warehouse Project JSON and SQLite from an immutable raw snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dancelab.validation.djmix.warehouse_catalog import (
    load_warehouse_raw_snapshot,
    normalize_warehouse_catalog,
    write_warehouse_catalog_json,
    write_warehouse_catalog_sqlite,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_snapshot", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    raw = load_warehouse_raw_snapshot(args.raw_snapshot)
    catalog = normalize_warehouse_catalog(raw)
    output = args.output_directory
    write_warehouse_catalog_json(catalog, output / "warehouse_catalog.json")
    write_warehouse_catalog_sqlite(catalog, output / "warehouse_catalog.sqlite3")
    print(json.dumps(catalog["analysis"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

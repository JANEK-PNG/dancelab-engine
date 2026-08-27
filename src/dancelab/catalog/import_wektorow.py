"""Load CLAP embeddings into pgvector.

The "sounds like X" anchor is a nearest-neighbour search over 512-dimensional
CLAP vectors. Until now that meant loading a 143 MB JSON into memory on every
run. Stored in pgvector with an HNSW index it becomes a query, which is the
single concrete reason this catalog runs on PostgreSQL rather than SQLite.

Embedding spaces are kept apart by the ``przestrzen`` column: the corpus keys
are YouTube video IDs, the library keys are file paths, and comparing across
the two without an explicit mapping would be meaningless.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dancelab.catalog.db import EMBEDDING_DIM

# space name -> (file, origin). Origin drives the 11.08 restriction: only
# corpus rows may back a measurement or an argument.
SPACES: dict[str, tuple[Path, str]] = {
    "korpus_pelny": (Path("data/reports/corpus_embeddings_full.json"), "korpus"),
    "korpus_kolejnosc": (Path("data/reports/corpus_ordering/embeddings.json"), "korpus"),
    "biblioteka": (Path("data/reports/library_embeddings.json"), "biblioteka_lokalna"),
    # Apple 30-second previews, but each record carries a Rekordbox
    # content_id, so these describe the DJ's own library and are filed on the
    # restricted side.
    "apple_preview": (
        Path("data/reports/apple_preview_embeddings.json"),
        "biblioteka_lokalna",
    ),
}


def _load(path: Path) -> tuple[dict[str, tuple[list[float], dict[str, Any]]], str | None]:
    """Read one embedding file, normalising the two shapes in use.

    Most files map a key straight to a vector. The Apple preview file maps a
    key to a record whose ``vector`` field holds the numbers and whose other
    fields (notably ``content_id``) are worth keeping.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = payload.get("model")
    if isinstance(model, dict):
        model = model.get("name")

    out: dict[str, tuple[list[float], dict[str, Any]]] = {}
    for key, value in (payload.get("tracks") or {}).items():
        if isinstance(value, list):
            out[key] = (value, {})
        elif isinstance(value, dict) and isinstance(value.get("vector"), list):
            meta = {k: v for k, v in value.items() if k != "vector"}
            out[key] = (value["vector"], meta)
    return out, model


def run(
    conn: Any,
    *,
    spaces: dict[str, tuple[Path, str]] | None = None,
    build_index: bool = True,
) -> dict[str, int]:
    """Rebuild the ``wektor`` table. Returns rows written per space."""
    selected = spaces or SPACES
    written: dict[str, int] = {}

    with conn.cursor() as cur:
        cur.execute("TRUNCATE wektor RESTART IDENTITY")
        # The index is dropped first: building HNSW once at the end is far
        # cheaper than maintaining it across ~16k inserts.
        cur.execute("DROP INDEX IF EXISTS wektor_hnsw_idx")

        for space, (path, origin) in selected.items():
            if not path.exists():
                written[f"_brak_{space}"] = 0
                continue
            tracks, model = _load(path)
            rows = 0
            zle_wymiary = 0
            with cur.copy(
                "COPY wektor (klucz, przestrzen, model, embedding, zrodlo, meta)"
                " FROM STDIN"
            ) as copy:
                for key, (vector, meta) in tracks.items():
                    if len(vector) != EMBEDDING_DIM:
                        zle_wymiary += 1
                        continue
                    # pgvector's text input format is the literal list form.
                    copy.write_row(
                        (
                            key,
                            space,
                            model,
                            "[" + ",".join(map(repr, vector)) + "]",
                            origin,
                            json.dumps(meta, ensure_ascii=False) if meta else None,
                        )
                    )
                    rows += 1
            written[space] = rows
            if zle_wymiary:
                written[f"_zly_wymiar_{space}"] = zle_wymiary

        if build_index:
            # Cosine distance: CLAP vectors are compared by direction, and the
            # rest of the engine already scores affinity that way.
            cur.execute(
                "CREATE INDEX wektor_hnsw_idx ON wektor"
                " USING hnsw (embedding vector_cosine_ops)"
            )
    conn.commit()
    return written


def podobne(
    conn: Any,
    klucz: str,
    *,
    przestrzen: str = "korpus_pelny",
    limit: int = 10,
    tylko_korpus: bool = True,
) -> list[tuple[str, float]]:
    """Nearest neighbours by cosine distance, as (key, distance).

    ``tylko_korpus`` defaults to True so a casual call cannot quietly produce
    an argument built on the personal library.
    """
    sql = (
        "SELECT w.klucz, w.embedding <=> (SELECT embedding FROM wektor"
        "        WHERE przestrzen = %s AND klucz = %s) AS dystans"
        " FROM wektor w"
        " WHERE w.przestrzen = %s AND w.klucz <> %s"
        + (" AND w.zrodlo = 'korpus'" if tylko_korpus else "")
        + " ORDER BY dystans LIMIT %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (przestrzen, klucz, przestrzen, klucz, limit))
        return [(row[0], float(row[1])) for row in cur.fetchall()]

"""Connection handling for the identity catalog.

The database URL comes from ``DANCELAB_DB_URL``. The default points at the
``db`` service in ``docker-compose.yml`` bound to loopback, so a developer who
ran ``docker compose up -d db`` needs no configuration at all.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

DEFAULT_URL = "postgresql://dancelab:dancelab@127.0.0.1:5432/dancelab"

# CLAP htsat-unfused produces 512 floats. Declared here rather than in the DDL
# so importers can assert against it before writing anything.
EMBEDDING_DIM = 512


class CatalogUnavailable(RuntimeError):
    """Raised when psycopg is missing or the server cannot be reached."""


def database_url() -> str:
    """Return the configured database URL."""
    return os.environ.get("DANCELAB_DB_URL", DEFAULT_URL).strip() or DEFAULT_URL


def _psycopg() -> Any:
    try:
        import psycopg
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise CatalogUnavailable(
            'psycopg is not installed. Run: uv pip install -e ".[catalog]"'
        ) from exc
    return psycopg


@contextmanager
def connect(url: str | None = None, *, autocommit: bool = False) -> Iterator[Any]:
    """Open a connection, registering the pgvector adapters.

    Without ``register_vector`` psycopg sends Python lists as arrays and the
    server rejects them, so registration happens here rather than at each call
    site where it is easy to forget.
    """
    psycopg = _psycopg()
    target = url or database_url()
    try:
        conn = psycopg.connect(target, autocommit=autocommit)
    except psycopg.OperationalError as exc:
        raise CatalogUnavailable(
            f"cannot reach PostgreSQL at {_redact(target)}: {exc}\n"
            "Is the container up?  docker compose up -d db"
        ) from exc
    try:
        try:
            from pgvector.psycopg import register_vector

            register_vector(conn)
        except (ModuleNotFoundError, psycopg.ProgrammingError):
            # The extension is created by schema.apply(); on a virgin database
            # registration fails and that is fine until the schema exists.
            conn.rollback()
        yield conn
    finally:
        conn.close()


def _redact(url: str) -> str:
    """Strip the password so connection errors are safe to print or log."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def scalar(conn: Any, sql: str, params: Sequence[Any] | None = None) -> Any:
    """Run a query expected to yield a single value."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return None if row is None else row[0]


def table_counts(conn: Any) -> dict[str, int]:
    """Row count per catalog table, for the verification reports."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' ORDER BY tablename"
        )
        names = [r[0] for r in cur.fetchall()]
        counts: dict[str, int] = {}
        for name in names:
            # Identifier is read back from the catalog, never user input.
            cur.execute(f'SELECT count(*) FROM "{name}"')  # noqa: S608
            counts[name] = cur.fetchone()[0]
    return counts

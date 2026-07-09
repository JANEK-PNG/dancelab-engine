"""Database access. v0: SQLite; PostgreSQL via docker-compose (Runtime Strategy).

STATUS: planned — Sprint 1 decision: plain sqlite3 vs SQLAlchemy.
Schema follows Data Model and Schemas entities: Track, Segment, FeatureFrame,
DecisionOutput, ContextProfile.
"""

from __future__ import annotations

from dancelab.core.errors import NotImplementedFeature


def get_connection(db_url: str = "sqlite:///data/dancelab.db"):
    raise NotImplementedFeature("database connection", status="planned")

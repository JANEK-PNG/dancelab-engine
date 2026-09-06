"""Catalog table names are identifiers even when their names contain SQL punctuation."""

from types import SimpleNamespace

import pytest

from dancelab.catalog import db


def test_table_count_quotes_identifier_without_changing_query_structure(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    name = 'example"; DROP TABLE tracks; --'
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query):
            executed.append(query)

        def fetchall(self):
            return [(name,)]

        def fetchone(self):
            return (7,)

    monkeypatch.setattr(db, "_psycopg", lambda: psycopg)
    assert db.table_counts(SimpleNamespace(cursor=Cursor)) == {name: 7}
    assert executed[1].as_string() == 'SELECT count(*) FROM "example""; DROP TABLE tracks; --"'

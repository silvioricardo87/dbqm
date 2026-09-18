"""DDL extraction on a real SQLite file, and the engine dispatch it exposed."""
from unittest.mock import patch

import pytest

from dbqm.core.ddl_extractor import ExtractionResult, extract_ddl
from dbqm.core.ddl_sqlite import extract_sqlite_ddl
from dbqm.models.connection import Connection


@pytest.fixture
def catalog(tmp_path):
    """A table with an index and a trigger, plus a view. Closed after use:
    with filterwarnings = error an unclosed handle fails some other test."""
    import sqlite3
    path = tmp_path / "ddl.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
        CREATE INDEX ix_nome ON clientes(nome);
        CREATE TRIGGER tg_up AFTER UPDATE ON clientes BEGIN SELECT 1; END;
        CREATE VIEW v_todos AS SELECT id, nome FROM clientes;
    """)
    db.commit()
    yield db, str(path)
    db.close()


def _result(name):
    return ExtractionResult(object_name=name, object_type="UNKNOWN", owner="", connection_name="l")


class TestExtractSqliteDdl:
    def test_a_table_brings_its_index_and_trigger(self, catalog):
        db, _ = catalog
        r = _result("clientes")
        extract_sqlite_ddl(db, "clientes", r)
        assert r.object_type == "TABLE"
        assert r.errors == []
        assert [(o.obj_type, o.name) for o in r.objects] == [
            ("TABLE", "clientes"), ("INDEX", "ix_nome"), ("TRIGGER", "tg_up"),
        ]
        assert r.objects[0].ddl.startswith("CREATE TABLE clientes")
        assert r.objects[0].ddl.endswith(";")

    def test_a_view_is_its_create_statement(self, catalog):
        db, _ = catalog
        r = _result("v_todos")
        extract_sqlite_ddl(db, "v_todos", r)
        assert r.object_type == "VIEW"
        assert r.objects[0].ddl == "CREATE VIEW v_todos AS SELECT id, nome FROM clientes;"

    def test_a_missing_object_is_the_same_message_as_the_other_engines(self, catalog):
        db, _ = catalog
        r = _result("nada")
        extract_sqlite_ddl(db, "nada", r)
        assert r.objects == []
        assert r.errors == ["Object 'nada' not found."]
        assert r.not_found is True

    def test_progress_counts_the_table_and_its_children(self, catalog):
        db, _ = catalog
        visto = []
        extract_sqlite_ddl(db, "clientes", _result("clientes"),
                           on_progress=lambda i, n, t, nome: visto.append((i, n, t)))
        assert visto == [(1, 3, "TABLE"), (2, 3, "INDEX"), (3, 3, "TRIGGER")]


class TestExtractDdlDispatch:
    """`extract_ddl` is the function `dbqm ddl` calls. Until 2.9.0 it had no
    `db_type` at all: every engine was asked Oracle's catalogue questions."""

    def test_sqlite_goes_end_to_end_through_extract_ddl(self, catalog):
        _, path = catalog
        conn = Connection(name="l", db_type="sqlite", user="", password="", database=path)
        r = extract_ddl(conn, "clientes")
        assert r.errors == []
        assert [o.name for o in r.objects] == ["clientes", "ix_nome", "tg_up"]

    def test_postgresql_reaches_its_own_extractor_not_oracle_sql(self):
        """The bug the review found: a PostgreSQL connection used to be sent
        `SELECT ... FROM all_objects`."""
        conn = Connection(name="p", db_type="postgresql", user="u", password="", host="h")
        with patch("dbqm.core.ddl_extractor.get_connection") as mock_get, \
             patch("dbqm.core.ddl_pg.extract_pg_ddl") as mock_pg:
            extract_ddl(conn, "clientes")
        mock_pg.assert_called_once()
        mock_get.return_value.close.assert_called_once()

    def test_an_engine_with_no_extractor_is_told_so(self):
        conn = Connection(name="s", db_type="sqlserver", user="u", password="", host="h")
        with patch("dbqm.core.ddl_extractor.get_connection") as mock_get:
            r = extract_ddl(conn, "x")
        assert r.errors == ["Extracao de DDL nao suportada para sqlserver."]
        mock_get.assert_not_called()

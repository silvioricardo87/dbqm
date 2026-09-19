"""Tests for table browser — identifier validation and SQLite integration."""
import sqlite3
import pytest
from dbqm.core.table_browser import _validate_identifier


class TestValidateIdentifier:
    def test_valid_simple(self):
        assert _validate_identifier("employees") == "employees"

    def test_valid_with_underscore(self):
        assert _validate_identifier("my_table") == "my_table"

    def test_valid_with_dot(self):
        assert _validate_identifier("schema.table") == "schema.table"

    def test_valid_with_hash(self):
        assert _validate_identifier("#temp") == "#temp"

    def test_invalid_space(self):
        with pytest.raises(ValueError):
            _validate_identifier("my table")

    def test_invalid_semicolon(self):
        with pytest.raises(ValueError):
            _validate_identifier("table; DROP TABLE x")

    def test_invalid_dash(self):
        with pytest.raises(ValueError):
            _validate_identifier("my-table")

    def test_empty(self):
        with pytest.raises(ValueError):
            _validate_identifier("")

@pytest.fixture
def sqlite_catalog(tmp_path):
    """A real file with a PK, an FK, a unique index and a view.

    A fixture, not a helper, so the handle is closed after the test: with
    `filterwarnings = error`, an unclosed sqlite3 connection raises its
    ResourceWarning at garbage collection -- inside whichever test happens
    to be running then, which is how it surfaced as flaky failures in files
    that had nothing to do with SQLite."""
    import sqlite3
    path = tmp_path / "cat.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, status TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY,
                              customer_id INTEGER REFERENCES customers(id), value REAL);
        CREATE UNIQUE INDEX ix_customers_name ON customers(name);
        CREATE VIEW v_active AS SELECT id, name FROM customers WHERE status = 'A';
        INSERT INTO customers VALUES (1, 'Ana', 'A'), (2, 'Bia', 'I'), (3, 'Caio', 'A');
        INSERT INTO orders VALUES (10, 1, 9.5), (11, 3, 20.0);
    """)
    db.commit()
    yield db
    db.close()


class TestSqliteBrowsing:
    """list_tables, foreign keys, label detection and paging on a real file."""

    def test_list_tables(self, sqlite_catalog):
        from dbqm.core.table_browser import list_tables
        db = sqlite_catalog
        assert list_tables(db, "sqlite") == ["customers", "orders"]

    def test_foreign_keys_from_pragma(self, sqlite_catalog):
        from dbqm.core.table_browser import get_foreign_keys
        db = sqlite_catalog
        fks = get_foreign_keys(db, "sqlite", "orders")
        assert [(f.column, f.ref_table, f.ref_column) for f in fks] == [
            ("customer_id", "customers", "id"),
        ]

    def test_label_column_is_the_first_text_column_that_is_not_the_key(self, sqlite_catalog):
        from dbqm.core.table_browser import detect_label_column
        db = sqlite_catalog
        assert detect_label_column(db, "sqlite", "customers", "id") == "name"

    def test_browse_pages_with_limit_and_offset(self, sqlite_catalog):
        from dbqm.core.table_browser import browse_table
        db = sqlite_catalog
        page = browse_table(db, "sqlite", "customers", "local", limit=2, offset=1)
        assert page.total_count == 3
        assert [r[0] for r in page.rows] == [2, 3]
        assert page.columns == ["id", "name", "status"]

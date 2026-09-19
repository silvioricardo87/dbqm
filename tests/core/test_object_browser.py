"""Tests for object browser — pure logic functions."""
import pytest
import re
from unittest.mock import MagicMock, patch
from dbqm.core.object_browser import (
    _is_numeric_type, _parse_params, _parse_spec_routines,
    RoutineInfo, RoutineParam, UnsupportedEngine, get_standalone_routine_info,
    list_objects,
)


class TestIsNumericType:
    @pytest.mark.parametrize("dtype,expected", [
        ("NUMBER", True),
        ("INTEGER", True),
        ("VARCHAR2", False),
        ("DATE", False),
        ("FLOAT", True),
        ("NUMBER(10,2)", True),
        ("DECIMAL", True),
        ("TEXT", False),
    ])
    def test_types(self, dtype, expected):
        assert _is_numeric_type(dtype) is expected


class TestParseParams:
    def test_simple_in(self):
        params = _parse_params("p_id IN NUMBER")
        assert len(params) == 1
        assert params[0].name == "p_id"
        assert params[0].direction == "IN"
        assert params[0].data_type == "NUMBER"

    def test_out_param(self):
        params = _parse_params("p_result OUT VARCHAR2")
        assert params[0].direction == "OUT"
        assert params[0].data_type == "VARCHAR2"

    def test_in_out(self):
        params = _parse_params("p_val IN OUT NUMBER")
        assert params[0].direction == "IN OUT"

    def test_default_value(self):
        params = _parse_params("p_flag IN BOOLEAN DEFAULT TRUE")
        assert params[0].default == "TRUE"

    def test_multiple_params(self):
        params = _parse_params("p_id IN NUMBER, p_name IN VARCHAR2, p_out OUT NUMBER")
        assert len(params) == 3
        assert params[2].direction == "OUT"

    def test_empty(self):
        assert _parse_params("") == []
        assert _parse_params("   ") == []

    def test_complex_type(self):
        params = _parse_params("p_val IN NUMBER(10,2)")
        assert params[0].data_type == "NUMBER(10,2)"

    def test_implicit_in(self):
        params = _parse_params("p_id NUMBER")
        assert params[0].direction == "IN"
        assert params[0].data_type == "NUMBER"


class TestParseSpecRoutines:
    def test_procedure_no_params(self):
        spec = "PROCEDURE do_stuff;"
        routines = _parse_spec_routines(spec)
        assert len(routines) == 1
        assert routines[0].name == "do_stuff"
        assert routines[0].routine_type == "PROCEDURE"

    def test_function_with_return(self):
        spec = "FUNCTION get_value RETURN NUMBER;"
        routines = _parse_spec_routines(spec)
        assert routines[0].routine_type == "FUNCTION"
        assert routines[0].return_type == "NUMBER"

    def test_procedure_with_params(self):
        spec = "PROCEDURE update_rec(p_id IN NUMBER, p_name IN VARCHAR2);"
        routines = _parse_spec_routines(spec)
        assert len(routines[0].params) == 2

    def test_multiple(self):
        spec = """
        PROCEDURE proc1;
        FUNCTION func1 RETURN VARCHAR2;
        PROCEDURE proc2(p_id NUMBER);
        """
        routines = _parse_spec_routines(spec)
        assert len(routines) == 3


class TestRoutineInfoSignature:
    def test_procedure_signature(self):
        r = RoutineInfo(name="test", routine_type="PROCEDURE",
                        params=[RoutineParam("p_id", "NUMBER", "IN")])
        assert "p_id IN NUMBER" in r.signature

    def test_function_signature(self):
        r = RoutineInfo(name="test", routine_type="FUNCTION",
                        params=[RoutineParam("p_id", "NUMBER", "IN")],
                        return_type="VARCHAR2")
        assert "RETURN VARCHAR2" in r.signature


class TestListObjectsProcedureFunction:
    """Test list_objects support for PROCEDURE and FUNCTION types."""

    def test_oracle_procedure(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("MY_PROC",), ("OTHER_PROC",)]
        mock_db.cursor.return_value = mock_cursor

        result = list_objects(mock_db, "oracle", "PROCEDURE")
        assert result == ["MY_PROC", "OTHER_PROC"]
        sql = mock_cursor.execute.call_args[0][0]
        assert "user_objects" in sql
        assert mock_cursor.execute.call_args[0][1]["t"] == "PROCEDURE"

    def test_oracle_function(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("FN_CALC",)]
        mock_db.cursor.return_value = mock_cursor

        result = list_objects(mock_db, "oracle", "FUNCTION")
        assert result == ["FN_CALC"]
        assert mock_cursor.execute.call_args[0][1]["t"] == "FUNCTION"

    @pytest.mark.parametrize("db_type", ["sqlserver", "postgresql", "mysql"])
    def test_package_refuses_every_engine_but_oracle(self, db_type):
        """An empty list would read as "there are none here"; packages are
        a concept that does not exist off Oracle at all, so the caller must
        get the same refusal `list_package_routines`/`get_package_source`
        already give for the same question."""
        mock_db = MagicMock()
        with pytest.raises(UnsupportedEngine, match=db_type):
            list_objects(mock_db, db_type, "PACKAGE")
        # No cursor should have opened: the refusal happens before any query.
        mock_db.cursor.assert_not_called()

    def test_an_unrecognized_type_still_returns_empty(self):
        """The guard is keyed on PACKAGE alone. A type dbqm does not know is
        not a lie of omission the way PACKAGE was — it is an unknown key, and
        an empty list is the honest answer."""
        mock_db = MagicMock()
        mock_db.cursor.return_value.fetchall.return_value = []

        assert list_objects(mock_db, "sqlserver", "SEQUENCE") == []
        assert list_objects(mock_db, "oracle", "SEQUENCE") == []
        # The `else: return []` guards are what make that true. Without them
        # control reaches the trailing `return [row[0] for row in
        # cursor.fetchall()]` with no statement ever executed -- which a
        # MagicMock answers with `[]` just the same, hiding the bug that a
        # real driver would raise on. Asserting nothing was executed is what
        # tells the two apart.
        mock_db.cursor.return_value.execute.assert_not_called()

    def test_package_still_works_on_oracle(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PKG_ORDERS",)]
        mock_db.cursor.return_value = mock_cursor

        result = list_objects(mock_db, "oracle", "PACKAGE")
        assert result == ["PKG_ORDERS"]

    def test_sqlserver_routine_reaches_the_cursor(self):
        """Falsified: with the `ROUTINE` branch removed from the `sqlserver`
        block, this test fails with
        `assert [] == ['MY_PROC', 'FN_CALC']` — `list_objects` falls through
        to the trailing `else: return []` instead of querying
        `information_schema.routines`. Restoring the branch makes it pass
        again, which is what proves this test can tell right code from
        wrong."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("MY_PROC",), ("FN_CALC",)]
        mock_db.cursor.return_value = mock_cursor

        result = list_objects(mock_db, "sqlserver", "ROUTINE")
        assert result == ["MY_PROC", "FN_CALC"]
        sql = mock_cursor.execute.call_args[0][0]
        assert "information_schema.routines" in sql

    def test_oracle_routine_returns_procedures_and_functions(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("FN_CALC",), ("MY_PROC",)]
        mock_db.cursor.return_value = mock_cursor

        result = list_objects(mock_db, "oracle", "ROUTINE")
        assert result == ["FN_CALC", "MY_PROC"]
        sql = mock_cursor.execute.call_args[0][0]
        assert "user_objects" in sql
        assert "PROCEDURE" in sql
        assert "FUNCTION" in sql
        assert "ORDER BY object_name" in sql


class TestGetStandaloneRoutineInfo:
    """Test get_standalone_routine_info.

    Two queries now: `all_objects` resolves the owner and the real type,
    then `all_arguments` is asked about that owner. `_cursor` wires both,
    so a test says which routine the database knows about instead of
    handing back a `MagicMock` for the first one.
    """

    @staticmethod
    def _cursor(arguments, object_=("APP", "PROCEDURE")):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = object_
        mock_cursor.fetchall.return_value = arguments
        mock_db.cursor.return_value = mock_cursor
        return mock_db, mock_cursor

    def test_procedure_with_params(self):
        mock_db, mock_cursor = self._cursor([
            ("P_ID", "NUMBER", "IN", None, 1),
            ("P_NAME", "VARCHAR2", "IN", None, 2),
            ("P_RESULT", "NUMBER", "OUT", None, 3),
        ])

        info = get_standalone_routine_info(mock_db, "MY_PROC", "PROCEDURE")
        assert info.name == "MY_PROC"
        assert info.routine_type == "PROCEDURE"
        assert len(info.params) == 3
        assert info.params[0].name == "P_ID"
        assert info.params[0].direction == "IN"
        assert info.params[2].direction == "OUT"
        assert info.return_type == ""

    def test_function_with_return(self):
        mock_db, mock_cursor = self._cursor([
            (None, "NUMBER", "OUT", None, 0),  # return type
            ("P_INPUT", "VARCHAR2", "IN", None, 1),
        ], object_=("APP", "FUNCTION"))

        info = get_standalone_routine_info(mock_db, "FN_CALC", "FUNCTION")
        assert info.return_type == "NUMBER"
        assert len(info.params) == 1
        assert info.params[0].name == "P_INPUT"

    def test_procedure_no_params(self):
        mock_db, mock_cursor = self._cursor([])

        info = get_standalone_routine_info(mock_db, "SIMPLE_PROC")
        assert info.params == []
        assert info.routine_type == "PROCEDURE"

    def test_the_owner_comes_from_all_objects_not_from_USER(self):
        """`all_arguments` was filtered by `owner = USER`, so a routine the
        caller can execute but does not own came back with no arguments --
        indistinguishable from a real zero-argument procedure, and the block
        was built without its parameters."""
        mock_db, mock_cursor = self._cursor([
            ("P_ID", "NUMBER", "IN", None, 1),
        ], object_=("OUTRO_SCHEMA", "PROCEDURE"))

        info = get_standalone_routine_info(mock_db, "MY_PROC")

        resolution, arguments = mock_cursor.execute.call_args_list
        assert "all_objects" in resolution[0][0]
        assert resolution[0][1] == {"name": "MY_PROC"}
        assert "owner = USER" not in arguments[0][0]
        assert arguments[0][1]["owner"] == "OUTRO_SCHEMA"
        assert [p.name for p in info.params] == ["P_ID"]

    def test_all_objects_wins_over_the_type_the_caller_guessed(self):
        """A command line has no list to pick a type from, so the CLI asks
        for PROCEDURE and re-tags afterwards. The dictionary is looking at
        the routine; it answers."""
        mock_db, _ = self._cursor([
            (None, "NUMBER", "OUT", None, 0),
        ], object_=("APP", "FUNCTION"))

        info = get_standalone_routine_info(mock_db, "FN_CALC", "PROCEDURE")

        assert info.routine_type == "FUNCTION"
        assert info.return_type == "NUMBER"

    def test_a_name_all_objects_does_not_know_falls_back_to_the_caller(self):
        """No row means the caller cannot see the name at all. The lookup
        does not invent a refusal: an empty `params` reaches the caller and
        the statement reaches Oracle, which answers PLS-00201."""
        mock_db, mock_cursor = self._cursor([], object_=None)

        info = get_standalone_routine_info(mock_db, "NAO_EXISTE", "FUNCTION")

        assert info.routine_type == "FUNCTION"
        assert info.params == []
        arguments = mock_cursor.execute.call_args_list[1]
        assert arguments[0][1]["owner"] is None

    def test_in_out_direction_mapping(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_VAL", "NUMBER", "IN/OUT", None, 1),
        ]
        mock_db.cursor.return_value = mock_cursor

        info = get_standalone_routine_info(mock_db, "MY_PROC")
        assert info.params[0].direction == "IN OUT"


class TestUnsupportedEngine:
    """Packages and routine introspection are Oracle-only in fact: these four
    functions take a db_type and never branch on it, going straight to
    all_source with Oracle bind syntax. The guard turns a driver traceback
    into a message a user can act on."""

    def test_list_package_routines_refuses_sqlserver(self):
        from unittest.mock import MagicMock

        import pytest

        from dbqm.core.object_browser import UnsupportedEngine, list_package_routines

        db = MagicMock()
        with pytest.raises(UnsupportedEngine, match="Oracle"):
            list_package_routines(db, "sqlserver", "MEU_PACOTE")
        db.cursor.assert_not_called()

    def test_get_package_source_refuses_postgresql(self):
        from unittest.mock import MagicMock

        import pytest

        from dbqm.core.object_browser import UnsupportedEngine, get_package_source

        db = MagicMock()
        with pytest.raises(UnsupportedEngine, match="Oracle"):
            get_package_source(db, "postgresql", "MEU_PACOTE")
        db.cursor.assert_not_called()

    def test_get_package_source_respects_its_default_source_type(self):
        """The signature is (db, db_type, package, source_type="PACKAGE");
        the guard must fire whether or not the fourth argument is given."""
        from unittest.mock import MagicMock

        import pytest

        from dbqm.core.object_browser import UnsupportedEngine, get_package_source

        with pytest.raises(UnsupportedEngine):
            get_package_source(MagicMock(), "mysql", "PKG", "BODY")

    def test_the_message_names_the_engine_that_was_asked(self):
        """A message saying only "Oracle only" leaves the user guessing what
        dbqm thought the connection was."""
        from unittest.mock import MagicMock

        import pytest

        from dbqm.core.object_browser import UnsupportedEngine, list_package_routines

        with pytest.raises(UnsupportedEngine, match="sqlserver"):
            list_package_routines(MagicMock(), "sqlserver", "X")

    def test_oracle_is_not_refused(self):
        """The guard must not become a wall. Oracle reaches the cursor."""
        from unittest.mock import MagicMock

        from dbqm.core.object_browser import list_package_routines

        db = MagicMock()
        db.cursor.return_value.fetchall.return_value = []
        list_package_routines(db, "oracle", "MEU_PACOTE")
        db.cursor.assert_called()


def _db_with_columns(lines):
    """A db whose cursor returns `linhas` for the columns query.

    Row shape, per `get_table_structure`:
    (name, data_type, data_length, data_precision, data_scale, nullable_raw)
    """
    from unittest.mock import MagicMock

    db = MagicMock()
    db.cursor.return_value.fetchall.return_value = list(lines)
    return db


class TestGetTableStructure:
    """`describe` rests on this and it had no tests."""

    def test_oracle_columns_carry_type_and_nullability(self):
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_with_columns([
            ("ID", "NUMBER", 22, 10, 0, "N"),
            ("VALUE", "NUMBER", 22, 12, 2, "Y"),
        ])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            structure = get_table_structure(db, "oracle", "ORDERS")

        assert structure.table == "ORDERS"
        assert [c.name for c in structure.columns] == ["ID", "VALUE"]
        assert structure.columns[0].data_type == "NUMBER"
        assert structure.columns[0].nullable is False, "Oracle spells it N"
        assert structure.columns[1].nullable is True, "Oracle spells it Y"

    def test_the_other_engines_spell_nullability_differently(self):
        """Oracle compares against "Y"; everyone else against "YES". A test
        that only covers Oracle would miss a whole branch reading it wrong."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_with_columns([
            ("ID", "int", 4, 10, 0, "NO"),
            ("VALUE", "decimal", 9, 12, 2, "YES"),
        ])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            structure = get_table_structure(db, "sqlserver", "ORDERS")

        assert structure.columns[0].nullable is False
        # The load-bearing half. "NO" is False against both "Y" and "YES", so
        # a NOT NULL column alone cannot tell the right comparison from the
        # wrong one; only a nullable column can.
        assert structure.columns[1].nullable is True

    def test_a_primary_key_column_is_marked(self):
        """`is_pk` is how `describe` shows the key without a second call."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_with_columns([
            ("ID", "NUMBER", 22, 10, 0, "N"),
            ("VALUE", "NUMBER", 22, 12, 2, "Y"),
        ])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value={"ID"}), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            structure = get_table_structure(db, "oracle", "ORDERS")

        assert [c.name for c in structure.columns if c.is_pk] == ["ID"]

    def test_a_lowercase_column_still_matches_its_key(self):
        """The lookup upper-cases the column name before checking. PostgreSQL
        returns lower-case names, so without that this silently marks nothing."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_with_columns([("id", "integer", 4, 32, 0, "NO")])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value={"ID"}), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            structure = get_table_structure(db, "postgresql", "orders")

        assert structure.columns[0].is_pk is True

    def test_a_foreign_key_column_carries_its_reference(self):
        """`fk_ref` is why `describe` needs no separate FK query."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_with_columns([("CLIENTE_ID", "NUMBER", 22, 10, 0, "N")])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map",
                   return_value={"CLIENTE_ID": "CUSTOMERS.ID"}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            structure = get_table_structure(db, "oracle", "ORDERS")

        assert structure.columns[0].fk_ref == "CUSTOMERS.ID"

    def test_indexes_come_back(self):
        from unittest.mock import patch

        from dbqm.core.object_browser import IndexInfo, get_table_structure

        db = _db_with_columns([("ID", "NUMBER", 22, 10, 0, "N")])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes",
                   return_value=[IndexInfo("PK_PEDIDOS", ["ID"], True)]):
            structure = get_table_structure(db, "oracle", "ORDERS")

        assert [i.name for i in structure.indexes] == ["PK_PEDIDOS"]
        assert structure.indexes[0].is_unique is True

    def test_a_table_with_no_columns_returns_empty_not_an_error(self):
        """A name that matches nothing is a normal answer, not an exception —
        the CLI turns an empty structure into `not_found`, and it cannot do
        that if this raises first."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_with_columns([])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            structure = get_table_structure(db, "oracle", "NAO_EXISTE")

        assert structure.columns == []


class TestGetViewDefinition:
    """The other function `describe` rests on, also untested until now."""

    def test_it_returns_the_sql(self):
        from dbqm.core.object_browser import get_view_definition

        db = _db_with_columns([])
        # For db_type "oracle", get_view_definition first calls _detect_owner,
        # which also reads via cursor.fetchone() on the SAME mocked cursor.
        # A 1-tuple works there (it only reads row[0]) but then blows up with
        # an IndexError on the real query, which reads row[0] and row[1].
        # A 2-tuple (owner, text) satisfies both call sites for real.
        db.cursor.return_value.fetchone.return_value = ("SCOTT", "SELECT id FROM orders")
        view = get_view_definition(db, "oracle", "V_PEDIDOS")

        assert view.name == "V_PEDIDOS"
        assert "SELECT" in view.sql_definition.upper()

    def test_a_missing_view_gives_an_empty_definition(self):
        """`describe` uses an empty definition plus zero columns to decide the
        object does not exist, so this must not raise."""
        from dbqm.core.object_browser import get_view_definition

        db = _db_with_columns([])
        db.cursor.return_value.fetchone.return_value = None
        view = get_view_definition(db, "oracle", "NAO_EXISTE")

        assert view.sql_definition == ""

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


class TestSqliteCatalog:
    """The fifth engine's catalogue: sqlite_master and PRAGMA, against a
    real file. No mocks -- a mocked PRAGMA would only prove the mock."""

    def test_tables_and_views_come_from_sqlite_master(self, sqlite_catalog):
        db = sqlite_catalog
        assert list_objects(db, "sqlite", "TABLE") == ["customers", "orders"]
        assert list_objects(db, "sqlite", "VIEW") == ["v_active"]

    def test_routines_and_packages_are_refused_not_empty(self, sqlite_catalog):
        """An empty list would read as "none here" instead of "does not apply"."""
        db = sqlite_catalog
        for kind in ("PACKAGE", "ROUTINE", "PROCEDURE", "FUNCTION"):
            with pytest.raises(UnsupportedEngine):
                list_objects(db, "sqlite", kind)

    def test_structure_reports_pk_nullability_and_the_unique_index(self, sqlite_catalog):
        from dbqm.core.object_browser import get_table_structure
        db = sqlite_catalog
        est = get_table_structure(db, "sqlite", "customers")
        by_name = {c.name: c for c in est.columns}
        assert by_name["id"].is_pk is True
        assert by_name["name"].nullable is False
        assert by_name["status"].nullable is True
        assert by_name["name"].data_type == "TEXT"
        idx = {i.name: i for i in est.indexes}
        assert idx["ix_customers_name"].columns == ["name"]
        assert idx["ix_customers_name"].is_unique is True

    def test_structure_reports_the_foreign_key(self, sqlite_catalog):
        from dbqm.core.object_browser import get_table_structure
        db = sqlite_catalog
        est = get_table_structure(db, "sqlite", "orders")
        by_name = {c.name: c for c in est.columns}
        assert by_name["customer_id"].fk_ref == "customers.id"
        assert by_name["id"].fk_ref == ""

    def test_view_definition_is_the_create_statement(self, sqlite_catalog):
        from dbqm.core.object_browser import get_view_definition
        db = sqlite_catalog
        info = get_view_definition(db, "sqlite", "v_active")
        assert "SELECT id, name FROM customers" in info.sql_definition
        assert info.owner == ""

    def test_a_table_name_that_is_not_an_identifier_is_refused(self, sqlite_catalog):
        """PRAGMA takes no bind parameters, so the name reaches SQL as text.
        It must never be interpolated unchecked."""
        from dbqm.core.object_browser import get_table_structure
        db = sqlite_catalog
        with pytest.raises(ValueError):
            get_table_structure(db, "sqlite", 'x"); DROP TABLE customers; --')


class TestSqliteHasNoRoutines:
    """`get_standalone_routine_info` and `execute_routine` take an open
    handle, not a Connection, so until 2.9.0 nothing stopped them from
    sending Oracle SQL to any engine. They refuse now, before touching it."""

    def test_standalone_lookup_refuses_sqlite_before_querying(self):
        db = MagicMock()
        with pytest.raises(UnsupportedEngine):
            get_standalone_routine_info(db, "P", db_type="sqlite")
        db.cursor.assert_not_called()

    def test_execute_routine_refuses_a_sqlite_connection_before_touching_it(self):
        from dbqm.core.object_browser import execute_routine
        from dbqm.models.connection import Connection
        db = MagicMock()
        conn = Connection(name="l", db_type="sqlite", user="", password="", database=":memory:")
        routine_info = RoutineInfo(name="P", routine_type="PROCEDURE", params=[])
        with pytest.raises(UnsupportedEngine):
            execute_routine(db, "", routine_info, {}, conn=conn)
        db.cursor.assert_not_called()


class TestExecuteRoutineHandsValuesBack:
    """OUT values and a function's return travel back marked.

    They used to arrive as bare `NAME=value` lines mixed into whatever the
    routine printed: a caller could not tell one from the other, and a
    routine printing its own `RETURN=...` shadowed the real return value.
    """

    MARKER = re.compile(r"##dbqm[0-9a-f]{8}##")

    def _run(self, extra_lines=(), routine=None):
        from dbqm.core.object_browser import (
            RoutineInfo, RoutineParam, execute_routine,
        )
        from dbqm.models.connection import Connection

        routine_info = routine or RoutineInfo(
            name="SOMA", routine_type="FUNCTION", return_type="NUMBER",
            params=[
                RoutineParam(name="A", data_type="NUMBER", direction="IN"),
                RoutineParam(name="R", data_type="NUMBER", direction="OUT"),
            ],
        )
        conn = Connection(name="ora", db_type="oracle", user="u", password="p")
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        executed: list[str] = []
        cursor.execute.side_effect = lambda sql, binds=None: executed.append(sql)

        def lines(_cursor):
            marker = self.MARKER.search("\n".join(executed)).group(0)
            return [
                f"{marker}R=5",
                *extra_lines,
                f"{marker}RETURN=12",
            ]

        with patch("dbqm.core.query_engine._read_dbms_output", lines):
            result = execute_routine(db, "PKG", routine_info, {"A": "7"}, conn=conn)
        return result, executed

    def test_out_values_are_their_own_field(self):
        result, _ = self._run()
        assert result.success is True
        assert result.out_values == {"R": "5"}
        assert result.return_value == "12"
        assert result.output_lines == []

    def test_a_routine_printing_RETURN_no_longer_shadows_the_real_one(self):
        """The line the routine printed stays in `output_lines`, verbatim,
        and the return value is still the one the block handed back."""
        result, _ = self._run(extra_lines=["RETURN=I am not the return value"])
        assert result.return_value == "12"
        assert result.output_lines == ["RETURN=I am not the return value"]

    def test_a_line_the_routine_printed_is_not_read_as_an_out_value(self):
        result, _ = self._run(extra_lines=["R=99", "processando..."])
        assert result.out_values == {"R": "5"}
        assert result.output_lines == ["R=99", "processando..."]

    def test_the_marker_is_generated_per_execution(self):
        """A constant could appear in a routine's own source; a marker that
        did not exist when the routine was compiled cannot."""
        _, first = self._run()
        _, second = self._run()
        um = self.MARKER.search("\n".join(first)).group(0)
        other = self.MARKER.search("\n".join(second)).group(0)
        assert um != other

    def test_to_dict_carries_the_out_values(self):
        result, _ = self._run()
        assert result.to_dict()["out_values"] == {"R": "5"}

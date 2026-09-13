"""Tests for object browser — pure logic functions."""
import pytest
from unittest.mock import MagicMock
from dbqm.core.object_browser import (
    _is_numeric_type, _parse_params, _parse_spec_routines,
    RoutineInfo, RoutineParam, get_standalone_routine_info,
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

    def test_sqlserver_no_packages(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor

        result = list_objects(mock_db, "sqlserver", "PACKAGE")
        assert result == []

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
    """Test get_standalone_routine_info."""

    def test_procedure_with_params(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "NUMBER", "IN", None, 1),
            ("P_NAME", "VARCHAR2", "IN", None, 2),
            ("P_RESULT", "NUMBER", "OUT", None, 3),
        ]
        mock_db.cursor.return_value = mock_cursor

        info = get_standalone_routine_info(mock_db, "MY_PROC", "PROCEDURE")
        assert info.name == "MY_PROC"
        assert info.routine_type == "PROCEDURE"
        assert len(info.params) == 3
        assert info.params[0].name == "P_ID"
        assert info.params[0].direction == "IN"
        assert info.params[2].direction == "OUT"
        assert info.return_type == ""

    def test_function_with_return(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (None, "NUMBER", "OUT", None, 0),  # return type
            ("P_INPUT", "VARCHAR2", "IN", None, 1),
        ]
        mock_db.cursor.return_value = mock_cursor

        info = get_standalone_routine_info(mock_db, "FN_CALC", "FUNCTION")
        assert info.return_type == "NUMBER"
        assert len(info.params) == 1
        assert info.params[0].name == "P_INPUT"

    def test_procedure_no_params(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor

        info = get_standalone_routine_info(mock_db, "SIMPLE_PROC")
        assert info.params == []
        assert info.routine_type == "PROCEDURE"

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


def _db_com_colunas(linhas):
    """A db whose cursor returns `linhas` for the columns query.

    Row shape, per `get_table_structure`:
    (name, data_type, data_length, data_precision, data_scale, nullable_raw)
    """
    from unittest.mock import MagicMock

    db = MagicMock()
    db.cursor.return_value.fetchall.return_value = list(linhas)
    return db


class TestGetTableStructure:
    """`describe` rests on this and it had no tests."""

    def test_oracle_columns_carry_type_and_nullability(self):
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_com_colunas([
            ("ID", "NUMBER", 22, 10, 0, "N"),
            ("VALOR", "NUMBER", 22, 12, 2, "Y"),
        ])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            estrutura = get_table_structure(db, "oracle", "PEDIDOS")

        assert estrutura.table == "PEDIDOS"
        assert [c.name for c in estrutura.columns] == ["ID", "VALOR"]
        assert estrutura.columns[0].data_type == "NUMBER"
        assert estrutura.columns[0].nullable is False, "Oracle spells it N"
        assert estrutura.columns[1].nullable is True, "Oracle spells it Y"

    def test_the_other_engines_spell_nullability_differently(self):
        """Oracle compares against "Y"; everyone else against "YES". A test
        that only covers Oracle would miss a whole branch reading it wrong."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_com_colunas([
            ("ID", "int", 4, 10, 0, "NO"),
            ("VALOR", "decimal", 9, 12, 2, "YES"),
        ])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            estrutura = get_table_structure(db, "sqlserver", "PEDIDOS")

        assert estrutura.columns[0].nullable is False
        # The load-bearing half. "NO" is False against both "Y" and "YES", so
        # a NOT NULL column alone cannot tell the right comparison from the
        # wrong one; only a nullable column can.
        assert estrutura.columns[1].nullable is True

    def test_a_primary_key_column_is_marked(self):
        """`is_pk` is how `describe` shows the key without a second call."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_com_colunas([
            ("ID", "NUMBER", 22, 10, 0, "N"),
            ("VALOR", "NUMBER", 22, 12, 2, "Y"),
        ])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value={"ID"}), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            estrutura = get_table_structure(db, "oracle", "PEDIDOS")

        assert [c.name for c in estrutura.columns if c.is_pk] == ["ID"]

    def test_a_lowercase_column_still_matches_its_key(self):
        """The lookup upper-cases the column name before checking. PostgreSQL
        returns lower-case names, so without that this silently marks nothing."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_com_colunas([("id", "integer", 4, 32, 0, "NO")])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value={"ID"}), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            estrutura = get_table_structure(db, "postgresql", "pedidos")

        assert estrutura.columns[0].is_pk is True

    def test_a_foreign_key_column_carries_its_reference(self):
        """`fk_ref` is why `describe` needs no separate FK query."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_com_colunas([("CLIENTE_ID", "NUMBER", 22, 10, 0, "N")])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map",
                   return_value={"CLIENTE_ID": "CLIENTES.ID"}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            estrutura = get_table_structure(db, "oracle", "PEDIDOS")

        assert estrutura.columns[0].fk_ref == "CLIENTES.ID"

    def test_indexes_come_back(self):
        from unittest.mock import patch

        from dbqm.core.object_browser import IndexInfo, get_table_structure

        db = _db_com_colunas([("ID", "NUMBER", 22, 10, 0, "N")])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes",
                   return_value=[IndexInfo("PK_PEDIDOS", ["ID"], True)]):
            estrutura = get_table_structure(db, "oracle", "PEDIDOS")

        assert [i.name for i in estrutura.indexes] == ["PK_PEDIDOS"]
        assert estrutura.indexes[0].is_unique is True

    def test_a_table_with_no_columns_returns_empty_not_an_error(self):
        """A name that matches nothing is a normal answer, not an exception —
        the CLI turns an empty structure into `not_found`, and it cannot do
        that if this raises first."""
        from unittest.mock import patch

        from dbqm.core.object_browser import get_table_structure

        db = _db_com_colunas([])
        with patch("dbqm.core.object_browser._get_pk_columns", return_value=set()), \
             patch("dbqm.core.object_browser._get_fk_map", return_value={}), \
             patch("dbqm.core.object_browser._get_indexes", return_value=[]):
            estrutura = get_table_structure(db, "oracle", "NAO_EXISTE")

        assert estrutura.columns == []


class TestGetViewDefinition:
    """The other function `describe` rests on, also untested until now."""

    def test_it_returns_the_sql(self):
        from dbqm.core.object_browser import get_view_definition

        db = _db_com_colunas([])
        # For db_type "oracle", get_view_definition first calls _detect_owner,
        # which also reads via cursor.fetchone() on the SAME mocked cursor.
        # A 1-tuple works there (it only reads row[0]) but then blows up with
        # an IndexError on the real query, which reads row[0] and row[1].
        # A 2-tuple (owner, text) satisfies both call sites for real.
        db.cursor.return_value.fetchone.return_value = ("SCOTT", "SELECT id FROM pedidos")
        view = get_view_definition(db, "oracle", "V_PEDIDOS")

        assert view.name == "V_PEDIDOS"
        assert "SELECT" in view.sql_definition.upper()

    def test_a_missing_view_gives_an_empty_definition(self):
        """`describe` uses an empty definition plus zero columns to decide the
        object does not exist, so this must not raise."""
        from dbqm.core.object_browser import get_view_definition

        db = _db_com_colunas([])
        db.cursor.return_value.fetchone.return_value = None
        view = get_view_definition(db, "oracle", "NAO_EXISTE")

        assert view.sql_definition == ""

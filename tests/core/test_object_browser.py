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

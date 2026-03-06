"""Tests for object browser — pure logic functions."""
import pytest
from dbqm.core.object_browser import (
    _is_numeric_type, _parse_params, _parse_spec_routines,
    RoutineInfo, RoutineParam,
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

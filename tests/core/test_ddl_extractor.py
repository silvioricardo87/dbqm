"""Tests for DDL extractor — PL/SQL parsing and helpers."""
import pytest
from dbqm.core.ddl_extractor import (
    _parse_routines, _find_routine_end, _find_internal_calls,
    _format_column_type, _safe_name, _collect_routine_deps,
    ExtractionResult, save_extraction,
)


class TestFormatColumnType:
    @pytest.mark.parametrize("dtype,dlen,dprec,dscale,expected", [
        ("VARCHAR2", 100, None, None, "VARCHAR2(100)"),
        ("NUMBER", 0, 10, 2, "NUMBER(10,2)"),
        ("NUMBER", 0, 10, 0, "NUMBER(10)"),
        ("NUMBER", 0, None, None, "NUMBER"),
        ("DATE", 0, None, None, "DATE"),
        ("CHAR", 1, None, None, "CHAR(1)"),
        ("RAW", 16, None, None, "RAW(16)"),
    ])
    def test_format(self, dtype, dlen, dprec, dscale, expected):
        assert _format_column_type(dtype, dlen, dprec, dscale) == expected


class TestSafeName:
    def test_basic(self):
        assert _safe_name("MY_TABLE") == "MY_TABLE"

    def test_special_chars(self):
        assert _safe_name("my table!@#") == "my_table___"

    def test_truncation(self):
        assert len(_safe_name("x" * 100)) == 60
        assert len(_safe_name("x" * 100, max_len=20)) == 20


class TestParseRoutines:
    def test_simple_procedure(self):
        source = """
PROCEDURE do_stuff IS
BEGIN
    NULL;
END do_stuff;
"""
        routines = _parse_routines(source)
        assert "DO_STUFF" in routines
        assert routines["DO_STUFF"]["type"] == "PROCEDURE"

    def test_function_with_return(self):
        source = """
FUNCTION get_value RETURN NUMBER IS
BEGIN
    RETURN 42;
END get_value;
"""
        routines = _parse_routines(source)
        assert "GET_VALUE" in routines
        assert routines["GET_VALUE"]["type"] == "FUNCTION"

    def test_forward_declaration(self):
        source = """
PROCEDURE helper;

PROCEDURE main IS
BEGIN
    helper;
END main;
"""
        routines = _parse_routines(source)
        assert "HELPER" in routines
        assert "MAIN" in routines

    def test_nested_begin_end(self):
        source = """
PROCEDURE complex IS
BEGIN
    BEGIN
        NULL;
    END;
    BEGIN
        NULL;
    END;
END complex;
"""
        routines = _parse_routines(source)
        assert "COMPLEX" in routines
        assert "END complex" in routines["COMPLEX"]["source"]

    def test_multiple_routines(self):
        source = """
PROCEDURE a IS
BEGIN
    NULL;
END a;

PROCEDURE b IS
BEGIN
    NULL;
END b;
"""
        routines = _parse_routines(source)
        assert len(routines) == 2


class TestFindInternalCalls:
    def test_finds_call(self):
        source = "BEGIN helper; END;"
        names = {"HELPER", "MAIN"}
        result = _find_internal_calls(source, names, "MAIN")
        assert "HELPER" in result

    def test_ignores_self(self):
        source = "BEGIN main; END;"
        result = _find_internal_calls(source, {"MAIN"}, "MAIN")
        assert "MAIN" not in result

    def test_ignores_strings(self):
        source = "BEGIN x := 'HELPER'; END;"
        result = _find_internal_calls(source, {"HELPER", "MAIN"}, "MAIN")
        assert "HELPER" not in result


class TestCollectRoutineDeps:
    def test_simple(self):
        routines = {
            "MAIN": {"name": "main", "type": "PROCEDURE", "source": "BEGIN helper; END;"},
            "HELPER": {"name": "helper", "type": "PROCEDURE", "source": "BEGIN NULL; END;"},
        }
        collected = _collect_routine_deps("MAIN", routines)
        assert "MAIN" in collected
        assert "HELPER" in collected

    def test_no_deps(self):
        routines = {
            "MAIN": {"name": "main", "type": "PROCEDURE", "source": "BEGIN NULL; END;"},
        }
        collected = _collect_routine_deps("MAIN", routines)
        assert collected == {"MAIN": routines["MAIN"]}


class TestSaveExtraction:
    def test_save_creates_files(self, tmp_config_dir):
        from dbqm.core.ddl_extractor import ExtractedObject
        result = ExtractionResult(
            object_name="MY_TABLE", object_type="TABLE",
            owner="SCOTT", connection_name="test_conn",
            objects=[ExtractedObject("MY_TABLE", "TABLE", "CREATE TABLE MY_TABLE (id NUMBER);")],
        )
        dir_path, next_num = save_extraction(result)
        assert len(result.saved_files) == 1
        assert next_num == 2

"""Tests for Oracle package editor."""
from unittest.mock import MagicMock

from dbqm.core.package_editor import (
    check_package_exists,
    fetch_package_source,
    compile_package,
    fetch_compilation_errors,
    generate_blank_template,
    generate_wizard_template,
)


class TestCheckPackageExists:
    def test_exists(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchone.return_value = (1,)
        assert check_package_exists(db, "my_pkg") is True

    def test_not_exists(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchone.return_value = (0,)
        assert check_package_exists(db, "my_pkg") is False

    def test_none_result(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchone.return_value = None
        assert check_package_exists(db, "my_pkg") is False


class TestFetchPackageSource:
    def test_fetches_spec_and_body(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor

        call_count = [0]

        def execute_side(sql, params):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                cursor.fetchall.return_value = [("PACKAGE MY_PKG AS\n",), ("END MY_PKG;\n",)]
            else:
                cursor.fetchall.return_value = [("PACKAGE BODY MY_PKG AS\n",), ("END MY_PKG;\n",)]

        cursor.execute.side_effect = execute_side

        spec, body = fetch_package_source(db, "my_pkg")
        assert "CREATE OR REPLACE" in spec
        assert "CREATE OR REPLACE" in body

    def test_empty_source(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        spec, body = fetch_package_source(db, "missing_pkg")
        assert spec == ""
        assert body == ""


class TestCompilePackage:
    def test_success(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        success, error = compile_package(db, "CREATE OR REPLACE PACKAGE ...")
        assert success is True
        assert error == ""

    def test_failure(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.execute.side_effect = Exception("PLS-00103: syntax error")
        success, error = compile_package(db, "INVALID SQL")
        assert success is False
        assert "PLS-00103" in error


class TestFetchCompilationErrors:
    def test_returns_errors(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            (10, 5, "PLS-00103: unexpected symbol"),
            (15, 1, "PLS-00103: missing semicolon"),
        ]
        errors = fetch_compilation_errors(db, "my_pkg", "PACKAGE")
        assert len(errors) == 2
        assert errors[0]["line"] == 10
        assert errors[0]["col"] == 5

    def test_no_errors(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        errors = fetch_compilation_errors(db, "my_pkg", "PACKAGE")
        assert errors == []


class TestGenerateBlankTemplate:
    def test_structure(self):
        spec, body = generate_blank_template("my_pkg")
        assert "MY_PKG" in spec
        assert "MY_PKG" in body
        assert "CREATE OR REPLACE PACKAGE MY_PKG" in spec
        assert "CREATE OR REPLACE PACKAGE BODY MY_PKG" in body

    def test_uppercases_name(self):
        spec, body = generate_blank_template("lower_case")
        assert "LOWER_CASE" in spec


class TestGenerateWizardTemplate:
    def test_procedure(self):
        routines = [{"name": "do_stuff", "type": "PROCEDURE", "params": "p_id IN NUMBER", "return_type": None}]
        spec, body = generate_wizard_template("my_pkg", routines)
        assert "PROCEDURE do_stuff" in spec
        assert "NULL; -- TODO" in body

    def test_function(self):
        routines = [{"name": "get_val", "type": "FUNCTION", "params": "", "return_type": "NUMBER"}]
        spec, body = generate_wizard_template("my_pkg", routines)
        assert "FUNCTION get_val" in spec
        assert "RETURN NUMBER" in spec
        assert "RETURN NULL; -- TODO" in body

    def test_multiple_routines(self):
        routines = [
            {"name": "proc1", "type": "PROCEDURE", "params": "", "return_type": None},
            {"name": "func1", "type": "FUNCTION", "params": "p_id NUMBER", "return_type": "VARCHAR2"},
        ]
        spec, body = generate_wizard_template("pkg", routines)
        assert "proc1" in spec
        assert "func1" in spec

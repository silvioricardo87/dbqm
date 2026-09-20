"""Ad-hoc statements through ops/, measured against `dbqm sql -f json`."""
from __future__ import annotations

from dataclasses import replace

import pytest

from dbqm.ops import catalogue
from dbqm.ops import sql as ops_sql
from dbqm.ops.errors import OperationError
from tests.ops.conftest import envelope


def test_a_select_matches_the_cli(local_db, capsys):
    _, body = envelope(["sql", "SELECT id, name FROM customers ORDER BY id", "local", "-f", "json"], capsys)
    result = ops_sql.run_sql(catalogue.connection("local"),
                             "SELECT id, name FROM customers ORDER BY id", {}, commit=False).to_dict()
    # `elapsed` is a real wall-clock measurement of its own query; the CLI's
    # run and this one each measure their own, so only the rest need match
    # (same idiom as `tests/ops/test_schema.py`).
    result.pop("elapsed")
    expected = {k: v for k, v in body["data"].items() if k != "elapsed"}
    assert result == expected


def test_a_bound_parameter_is_accepted(local_db):
    result = ops_sql.run_sql(catalogue.connection("local"),
                             "SELECT name FROM customers WHERE id = :id", {"id": "2"}, commit=False)
    assert result.rows == [["Bia"]]


def test_an_undeclared_parameter_is_validation(local_db):
    with pytest.raises(OperationError) as e:
        ops_sql.run_sql(catalogue.connection("local"), "SELECT 1", {"x": "1"}, commit=False)
    assert e.value.code == "validation"


def test_dml_without_commit_is_usage(local_db):
    with pytest.raises(OperationError) as e:
        ops_sql.run_sql(catalogue.connection("local"), "DELETE FROM orders", {}, commit=False)
    assert e.value.code == "usage"


def test_dml_with_commit_writes(local_db):
    conn = catalogue.connection("local")
    result = ops_sql.run_sql(conn, "DELETE FROM orders WHERE id = 13", {}, commit=True)
    assert result.rows_affected == 1
    assert ops_sql.run_sql(conn, "SELECT COUNT(*) FROM orders", {}, commit=False).rows == [[3]]


def test_a_read_only_connection_refuses_dml_before_anything_else(read_only_db):
    with pytest.raises(OperationError) as e:
        ops_sql.run_sql(catalogue.connection("ro"), "DELETE FROM orders", {}, commit=False)
    assert e.value.code == "read_only"


def test_a_transient_read_only_copy_is_honoured(local_db):
    """The seam the MCP policy uses: `replace(conn, read_only=True)` and
    nothing else, and the guard refuses."""
    conn = replace(catalogue.connection("local"), read_only=True)
    with pytest.raises(OperationError) as e:
        ops_sql.run_sql(conn, "DELETE FROM orders", {}, commit=True)
    assert e.value.code == "read_only"


def test_a_statement_the_engine_rejects_is_sql_error(local_db):
    with pytest.raises(OperationError) as e:
        ops_sql.run_sql(catalogue.connection("local"), "SELECT * FROM no_such_table", {}, commit=False)
    assert e.value.code == "sql_error"


def test_a_dead_database_is_connection_failed(broken_db):
    with pytest.raises(OperationError) as e:
        ops_sql.run_sql(catalogue.connection("broken"), "SELECT 1", {}, commit=False)
    assert e.value.code == "connection_failed"


def test_classify_and_guard_returns_the_type(local_db):
    assert ops_sql.classify_and_guard(catalogue.connection("local"), "SELECT 1", {}) == "SELECT"


def test_explain_matches_the_cli(local_db, capsys):
    _, body = envelope(["sql", "SELECT * FROM customers", "local", "--explain", "-f", "json"], capsys)
    result = ops_sql.explain(catalogue.connection("local"), "SELECT * FROM customers", {})
    assert [row[0] if row else "" for row in result.rows] == body["data"]["plan"]

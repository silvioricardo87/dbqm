"""Tests for query engine — SQL parsing, classification, parameter binding."""
import pytest
from dbqm.core.query_engine import (
    classify_sql, parse_sql, detect_params, replace_literals_with_params,
    generate_sql_text, _is_select_only, _bind_params_oracle, _bind_params_pyformat,
    _extract_alias, parse_dml_literals, execute_query, execute_adhoc, QueryResult,
)
from dbqm.models.query import Query
from dbqm.models.connection import Connection
from unittest.mock import patch, MagicMock
import sqlite3


class TestClassifySql:
    @pytest.mark.parametrize("sql,expected", [
        ("SELECT * FROM t", "SELECT"),
        ("select id from t where x=1", "SELECT"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET x=1", "UPDATE"),
        ("DELETE FROM t WHERE id=1", "DELETE"),
        ("CREATE TABLE t (id INT)", "DDL"),
        ("", "UNKNOWN"),
        ("DROP TABLE t", "DDL"),
    ])
    def test_classify(self, sql, expected):
        assert classify_sql(sql) == expected


class TestIsSelectOnly:
    def test_select(self):
        assert _is_select_only("SELECT * FROM t") is True

    def test_insert(self):
        assert _is_select_only("INSERT INTO t VALUES (1)") is False

    def test_update(self):
        assert _is_select_only("UPDATE t SET x=1") is False


class TestParseSql:
    def test_simple_select(self):
        r = parse_sql("SELECT id, name FROM employees WHERE status = 'active' ORDER BY name")
        assert r["table"] == "employees"
        assert "id" in r["columns"]
        assert "name" in r["columns"]
        assert r["where_values"].get("status") == "active"
        assert "name" in r["order_by"]

    def test_no_where(self):
        r = parse_sql("SELECT * FROM t")
        assert r["table"] == "t"
        assert r["where_values"] == {}

    def test_alias_extraction(self):
        r = parse_sql("SELECT a.id AS user_id, b.name FROM t a JOIN u b ON a.id=b.id")
        assert "user_id" in r["columns"]


class TestDetectParams:
    def test_simple(self):
        params = detect_params("SELECT * FROM t WHERE id = :id AND name = :name")
        assert set(params) == {"id", "name"}

    def test_no_params(self):
        assert detect_params("SELECT 1") == []

    def test_duplicate_params(self):
        params = detect_params("SELECT * FROM t WHERE a = :x OR b = :x")
        assert params == ["x"]


class TestBindParams:
    def test_oracle_passthrough(self):
        sql, params = _bind_params_oracle("SELECT * FROM t WHERE id = :id", {"id": 1})
        assert ":id" in sql
        assert params == {"id": 1}

    def test_pyformat_conversion(self):
        sql, params = _bind_params_pyformat("SELECT * FROM t WHERE id = :id AND name = :name", {"id": 1, "name": "x"})
        assert "%(id)s" in sql
        assert "%(name)s" in sql
        assert ":id" not in sql
        assert ":name" not in sql

    def test_pyformat_no_partial_replace(self):
        sql, _ = _bind_params_pyformat("SELECT * FROM t WHERE id = :id AND id_name = :id_name", {"id": 1, "id_name": "x"})
        assert "%(id)s" in sql
        assert "%(id_name)s" in sql


class TestReplaceLiterals:
    def test_replace(self):
        sql = "SELECT * FROM t WHERE status = 'active'"
        result = replace_literals_with_params(sql, {"status": "active"})
        assert ":status" in result
        assert "'active'" not in result


class TestGenerateSqlText:
    def test_numeric(self):
        result = generate_sql_text("SELECT * FROM t WHERE id = :id", {"id": "42"})
        assert "42" in result
        assert ":id" not in result

    def test_string(self):
        result = generate_sql_text("SELECT * FROM t WHERE name = :name", {"name": "Alice"})
        assert "'Alice'" in result


class TestExtractAlias:
    @pytest.mark.parametrize("expr,expected", [
        ("col", "col"),
        ("t.col", "t.col"),
        ("col AS alias", "alias"),
        ("CASE WHEN x THEN 1 END status", "status"),
    ])
    def test_alias(self, expr, expected):
        assert _extract_alias(expr) == expected


class TestParseDmlLiterals:
    def test_insert(self):
        r = parse_dml_literals("INSERT INTO t (name, age) VALUES ('Alice', 30)")
        assert r["name"] == "Alice"
        assert r["age"] == "30"

    def test_update(self):
        r = parse_dml_literals("UPDATE t SET name = 'Bob' WHERE id = '1'")
        assert r["name"] == "Bob"
        assert r["id"] == "1"

    def test_delete(self):
        r = parse_dml_literals("DELETE FROM t WHERE status = 'old'")
        assert r["status"] == "old"


class TestExecuteWithSqlite:
    """Integration tests using SQLite as a proxy database."""

    def _make_conn(self):
        return Connection(name="test", db_type="sqlite", user="", password="")

    def _make_query(self, sql):
        return Query(name="q", connection="test", sql=sql)

    def test_execute_query_select(self, sqlite_db):
        q = self._make_query("SELECT id, name FROM employees WHERE department = :dept")
        conn = self._make_conn()

        with patch("dbqm.core.query_engine.get_connection", return_value=sqlite_db):
            # SQLite uses :param natively like Oracle
            with patch.object(conn, "db_type", "oracle"):
                result = execute_query(q, conn, {"dept": "Engineering"})

        assert result.success
        assert result.row_count == 2
        assert "id" in result.columns

    def test_execute_query_rejects_insert(self, sqlite_db):
        q = self._make_query("INSERT INTO employees VALUES (4, 'Dave', 'HR', 50000)")
        conn = self._make_conn()

        with patch("dbqm.core.query_engine.get_connection", return_value=sqlite_db):
            result = execute_query(q, conn, {})

        assert not result.success
        assert "SELECT" in result.error

    def test_execute_adhoc_select(self, sqlite_db):
        conn = self._make_conn()
        with patch("dbqm.core.query_engine.get_connection", return_value=sqlite_db):
            with patch.object(conn, "db_type", "oracle"):
                result = execute_adhoc("SELECT COUNT(*) FROM employees", conn, {})

        assert result.success
        assert result.row_count == 1

    def test_execute_adhoc_dml_autocommit(self, sqlite_db):
        conn = self._make_conn()
        with patch("dbqm.core.query_engine.get_connection", return_value=sqlite_db):
            with patch.object(conn, "db_type", "oracle"):
                result = execute_adhoc(
                    "UPDATE employees SET salary = 100000 WHERE id = 1",
                    conn, {}, auto_commit=True
                )

        assert result.success
        assert result.rows_affected == 1
        assert result.committed is True

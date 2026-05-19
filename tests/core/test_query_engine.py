"""Tests for query engine — SQL parsing, classification, parameter binding."""
import pytest
from dbqm.core.query_engine import (
    classify_sql, parse_sql, detect_params, replace_literals_with_params,
    generate_sql_text, _is_select_only, _bind_params_oracle, _bind_params_pyformat,
    _extract_alias, parse_dml_literals, execute_query, execute_adhoc,
    execute_explain, QueryResult,
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
        ("ALTER TABLE t ADD col INT", "DDL"),
        ("TRUNCATE TABLE t", "DDL"),
        ("GRANT SELECT ON t TO u", "DDL"),
        ("REVOKE SELECT ON t FROM u", "DDL"),
        ("CREATE OR REPLACE PACKAGE pkg AS END;", "DDL"),
        ("CREATE OR REPLACE PROCEDURE p AS BEGIN NULL; END;", "DDL"),
        ("CREATE OR REPLACE VIEW v AS SELECT 1 FROM dual", "DDL"),
        ("COMMENT ON TABLE t IS 'desc'", "DDL"),
        ("RENAME old_t TO new_t", "DDL"),
        ("PURGE RECYCLEBIN", "DDL"),
        ("ANALYZE TABLE t COMPUTE STATISTICS", "DDL"),
        ("BEGIN NULL; END;", "PLSQL"),
        ("DECLARE v NUMBER; BEGIN v := 1; END;", "PLSQL"),
        ("declare v number; begin null; end;", "PLSQL"),
        ("EXEC pkg.proc('x')", "PLSQL"),
        ("EXECUTE pkg.proc", "PLSQL"),
        ("CALL pkg.proc(1)", "PLSQL"),
        # CTE (WITH ... SELECT) — sqlparse classifies as SELECT
        ("WITH x AS (SELECT 1 AS n FROM dual) SELECT n FROM x", "SELECT"),
        ("with x as (select 1 from dual) select * from x", "SELECT"),
        ("WITH a AS (SELECT 1 FROM dual), b AS (SELECT 2 FROM dual) SELECT * FROM a, b", "SELECT"),
        # EXPLAIN PLAN
        ("EXPLAIN PLAN FOR SELECT 1 FROM dual", "EXPLAIN"),
        ("explain plan for select * from t", "EXPLAIN"),
        ("EXPLAIN PLAN SET STATEMENT_ID = 'x' FOR SELECT 1 FROM dual", "EXPLAIN"),
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

    def test_execute_adhoc_ddl_create_table(self, sqlite_db):
        """DDL CREATE TABLE should execute and return success."""
        conn = self._make_conn()
        with patch("dbqm.core.query_engine.get_connection", return_value=sqlite_db):
            with patch.object(conn, "db_type", "sqlite"):
                result = execute_adhoc(
                    "CREATE TABLE test_ddl (id INTEGER, name TEXT)",
                    conn, {},
                )

        assert result.success
        assert result.sql_type == "DDL"
        assert result.committed is True

    def test_execute_adhoc_ddl_alter_table(self, sqlite_db):
        """DDL ALTER TABLE should execute and return success."""
        conn = self._make_conn()
        with patch("dbqm.core.query_engine.get_connection", return_value=sqlite_db):
            with patch.object(conn, "db_type", "sqlite"):
                result = execute_adhoc(
                    "ALTER TABLE employees ADD COLUMN bonus REAL",
                    conn, {},
                )

        assert result.success
        assert result.sql_type == "DDL"

    def test_execute_adhoc_ddl_error(self):
        """DDL on non-existent table should return error."""
        conn = self._make_conn()
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("ORA-00942: table or view does not exist")
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db
            with patch.object(conn, "db_type", "oracle"):
                result = execute_adhoc("DROP TABLE nonexistent_xyz", conn, {})

        assert not result.success
        assert "ORA-00942" in result.error
        assert result.sql_type == "DDL"

    def test_execute_adhoc_unknown_rejected(self):
        """UNKNOWN SQL type should be rejected."""
        conn = self._make_conn()
        result = execute_adhoc("MERGE INTO t USING s ON (t.id=s.id)", conn, {})
        assert not result.success
        assert "nao suportado" in result.error


class TestDdlTrailingSemicolonPreservation:
    """Trailing `;` must be preserved for DDL (esp. PL/SQL bodies).

    Regression test for the bug where CREATE OR REPLACE PACKAGE BODY ending in
    `END pkg;` had its final `;` stripped before being sent to Oracle, causing
    PLS-00103 and leaving the object INVALID.
    """

    def _make_conn(self):
        return Connection(name="test", db_type="oracle", user="", password="")

    def _capture_executed_sql(self, sql: str, sql_type_for_classify: str = "DDL"):
        """Run execute_adhoc with mocks and return the SQL actually sent to the driver."""
        conn = self._make_conn()
        captured = {}

        with patch("dbqm.core.query_engine.get_connection") as mock_get, \
             patch("dbqm.core.query_engine._fetch_ddl_errors", return_value=""):
            mock_db = MagicMock()
            mock_cursor = MagicMock()

            def _capture(executed_sql, *args, **kwargs):
                captured["sql"] = executed_sql

            mock_cursor.execute.side_effect = _capture
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            execute_adhoc(sql, conn, {})

        return captured.get("sql")

    def test_ddl_package_body_preserves_trailing_semicolon(self):
        sql = (
            "CREATE OR REPLACE PACKAGE BODY ASDADM.MEU_PACKAGE IS\n"
            "  PROCEDURE P IS BEGIN NULL; END P;\n"
            "END MEU_PACKAGE;"
        )
        sent = self._capture_executed_sql(sql)
        assert sent.endswith("END MEU_PACKAGE;"), \
            f"Expected DDL to end with `END MEU_PACKAGE;`, got: {sent[-40:]!r}"

    def test_ddl_create_trigger_preserves_semicolon(self):
        sql = (
            "CREATE OR REPLACE TRIGGER trg_audit\n"
            "  BEFORE INSERT ON t\n"
            "  FOR EACH ROW\n"
            "BEGIN NULL; END;"
        )
        sent = self._capture_executed_sql(sql)
        assert sent.endswith("END;")

    def test_ddl_simple_alter_preserves_semicolon(self):
        sql = "ALTER TABLE t ADD col NUMBER;"
        sent = self._capture_executed_sql(sql)
        assert sent.endswith("ADD col NUMBER;")

    def test_select_still_strips_trailing_semicolon(self):
        """SELECT must continue to have trailing `;` stripped (Oracle rejects it)."""
        conn = self._make_conn()
        captured = {}
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.description = [("ID",)]
            mock_cursor.fetchmany.return_value = [(1,)]

            def _capture(executed_sql, *args, **kwargs):
                captured["sql"] = executed_sql

            mock_cursor.execute.side_effect = _capture
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            execute_adhoc("SELECT 1 FROM dual;", conn, {})

        assert not captured["sql"].endswith(";"), \
            f"SELECT should have trailing `;` stripped, got: {captured['sql']!r}"

    def test_dml_update_strips_trailing_semicolon(self):
        conn = self._make_conn()
        captured = {}
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1

            def _capture(executed_sql, *args, **kwargs):
                captured["sql"] = executed_sql

            mock_cursor.execute.side_effect = _capture
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            execute_adhoc("UPDATE t SET x = 1 WHERE id = 2;", conn, {}, auto_commit=True)

        assert not captured["sql"].endswith(";")


class TestNormalizePlsql:
    """_normalize_plsql expands EXEC/CALL shortcuts and strips SQL*Plus `/`."""

    def test_strips_trailing_slash_terminator(self):
        from dbqm.core.query_engine import _normalize_plsql
        sql = "BEGIN NULL; END;\n/"
        assert _normalize_plsql(sql) == "BEGIN NULL; END;"

    def test_strips_trailing_slash_with_whitespace(self):
        from dbqm.core.query_engine import _normalize_plsql
        sql = "BEGIN NULL; END;\n  /  "
        assert _normalize_plsql(sql) == "BEGIN NULL; END;"

    def test_exec_shortcut_wrapped(self):
        from dbqm.core.query_engine import _normalize_plsql
        assert _normalize_plsql("EXEC pkg.proc('x')") == "BEGIN pkg.proc('x'); END;"

    def test_execute_shortcut_wrapped(self):
        from dbqm.core.query_engine import _normalize_plsql
        assert _normalize_plsql("EXECUTE pkg.proc") == "BEGIN pkg.proc; END;"

    def test_call_shortcut_wrapped(self):
        from dbqm.core.query_engine import _normalize_plsql
        assert _normalize_plsql("CALL pkg.proc(1)") == "BEGIN pkg.proc(1); END;"

    def test_exec_with_trailing_semicolon_normalized(self):
        from dbqm.core.query_engine import _normalize_plsql
        assert _normalize_plsql("EXEC pkg.proc;") == "BEGIN pkg.proc; END;"

    def test_declare_block_unchanged(self):
        from dbqm.core.query_engine import _normalize_plsql
        sql = "DECLARE v NUMBER; BEGIN v := 1; END;"
        assert _normalize_plsql(sql) == sql

    def test_begin_block_unchanged(self):
        from dbqm.core.query_engine import _normalize_plsql
        sql = "BEGIN DBMS_OUTPUT.PUT_LINE('hi'); END;"
        assert _normalize_plsql(sql) == sql


class TestPlsqlExecution:
    """End-to-end PL/SQL execution via execute_adhoc with mocks."""

    def _make_conn(self):
        return Connection(name="test", db_type="oracle", user="", password="")

    def _capture_executed_sql(self, sql: str):
        conn = self._make_conn()
        captured = {}

        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()

            def _capture(executed_sql, *args, **kwargs):
                captured["sql"] = executed_sql

            mock_cursor.execute.side_effect = _capture
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            result = execute_adhoc(sql, conn, {})

        return captured.get("sql"), result

    def test_anonymous_block_no_longer_rejected(self):
        sent, result = self._capture_executed_sql("BEGIN NULL; END;")
        assert result.success
        assert result.sql_type == "PLSQL"
        assert sent == "BEGIN NULL; END;"

    def test_declare_block_executes(self):
        sql = "DECLARE v NUMBER; BEGIN v := 1; END;"
        sent, result = self._capture_executed_sql(sql)
        assert result.success
        assert sent == sql

    def test_exec_shortcut_expanded_before_send(self):
        sent, result = self._capture_executed_sql("EXEC MEU_PKG.MINHA_PROC('p1')")
        assert result.success
        assert sent == "BEGIN MEU_PKG.MINHA_PROC('p1'); END;"

    def test_sqlplus_slash_terminator_stripped(self):
        sent, result = self._capture_executed_sql("BEGIN NULL; END;\n/")
        assert result.success
        assert sent == "BEGIN NULL; END;"
        assert "/" not in sent

    def test_plsql_returns_committed(self):
        _, result = self._capture_executed_sql("BEGIN NULL; END;")
        assert result.committed is True

    def test_plsql_error_propagates(self):
        conn = self._make_conn()
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception(
                "ORA-06550: line 1, column 7: PLS-00201: identifier 'X' must be declared"
            )
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db
            result = execute_adhoc("BEGIN x := 1; END;", conn, {})
        assert not result.success
        assert "ORA-06550" in result.error
        assert result.sql_type == "PLSQL"


class TestFetchDdlErrors:
    """Tests for _fetch_ddl_errors helper."""

    def test_non_oracle_returns_empty(self):
        from dbqm.core.query_engine import _fetch_ddl_errors
        assert _fetch_ddl_errors(None, "CREATE TABLE t (id INT)", "sqlite") == ""

    def test_non_create_alter_returns_empty(self):
        from dbqm.core.query_engine import _fetch_ddl_errors
        assert _fetch_ddl_errors(None, "DROP TABLE t", "oracle") == ""

    def test_no_matching_object_returns_empty(self):
        from dbqm.core.query_engine import _fetch_ddl_errors
        assert _fetch_ddl_errors(None, "CREATE TABLE t (id INT)", "oracle") == ""

    def test_fetches_errors_for_package(self):
        from dbqm.core.query_engine import _fetch_ddl_errors
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (5, 10, "PLS-00103: Encountered the symbol 'END'"),
        ]
        mock_db.cursor.return_value = mock_cursor

        result = _fetch_ddl_errors(mock_db, "CREATE OR REPLACE PACKAGE pkg_test AS END;", "oracle")
        assert "Linha 5" in result
        assert "PLS-00103" in result

    def test_fetches_errors_with_owner(self):
        from dbqm.core.query_engine import _fetch_ddl_errors
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor

        result = _fetch_ddl_errors(mock_db, "CREATE OR REPLACE PROCEDURE MYSCHEMA.MY_PROC AS BEGIN NULL; END;", "oracle")
        assert result == ""
        # Verify it used all_errors (with owner) not user_errors
        call_args = mock_cursor.execute.call_args
        sql_arg = call_args[0][0]
        params_arg = call_args[0][1]
        assert "all_errors" in sql_arg
        assert params_arg["o"] == "MYSCHEMA"
        assert params_arg["n"] == "MY_PROC"

    def test_no_errors_returns_empty(self):
        from dbqm.core.query_engine import _fetch_ddl_errors
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor

        result = _fetch_ddl_errors(mock_db, "CREATE OR REPLACE FUNCTION fn_test RETURN NUMBER AS BEGIN RETURN 1; END;", "oracle")
        assert result == ""


class TestExecuteExplain:
    """Tests for execute_explain — wraps user query in EXPLAIN PLAN + DBMS_XPLAN.DISPLAY."""

    def _make_conn(self, db_type="oracle"):
        return Connection(name="test", db_type=db_type, user="", password="")

    def test_oracle_runs_explain_and_returns_plan_lines(self):
        conn = self._make_conn("oracle")
        executed = []
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = lambda sql, *a, **kw: executed.append(sql)
            mock_cursor.fetchmany.return_value = [
                ("Plan hash value: 123",),
                ("--------------------",),
                ("| Id | Operation     |",),
            ]
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            result = execute_explain("SELECT 1 FROM dual", conn, {})

        assert result.success
        assert result.sql_type == "EXPLAIN"
        assert result.columns == ["plan"]
        assert result.row_count == 3
        assert result.rows[0] == ["Plan hash value: 123"]
        # First execute is EXPLAIN PLAN FOR, second is DBMS_XPLAN.DISPLAY
        assert len(executed) == 2
        assert executed[0].startswith("EXPLAIN PLAN SET STATEMENT_ID = 'dbqm_")
        assert executed[0].endswith("FOR SELECT 1 FROM dual")
        assert "DBMS_XPLAN.DISPLAY" in executed[1]
        # Statement ID is consistent between the two calls
        import re as _re
        m = _re.search(r"dbqm_\d+", executed[0])
        assert m and m.group(0) in executed[1]

    def test_oracle_strips_trailing_semicolon_before_wrapping(self):
        conn = self._make_conn("oracle")
        executed = []
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = lambda sql, *a, **kw: executed.append(sql)
            mock_cursor.fetchmany.return_value = []
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            execute_explain("SELECT 1 FROM dual;", conn, {})

        # Wrapped query must not have the trailing ; (otherwise ORA-00911)
        assert executed[0].endswith("FOR SELECT 1 FROM dual")

    def test_oracle_passes_param_values_to_explain_plan(self):
        conn = self._make_conn("oracle")
        captured = []
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()

            def _capture(sql, params=None, *a, **kw):
                captured.append((sql, params))

            mock_cursor.execute.side_effect = _capture
            mock_cursor.fetchmany.return_value = []
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            execute_explain("SELECT * FROM t WHERE id = :id", conn, {"id": 42})

        # First call is the EXPLAIN PLAN and must carry the binds.
        assert captured[0][1] == {"id": 42}

    def test_already_explain_query_is_rejected(self):
        conn = self._make_conn("oracle")
        result = execute_explain("EXPLAIN PLAN FOR SELECT 1 FROM dual", conn, {})
        assert not result.success
        assert "EXPLAIN PLAN FOR" in result.error

    def test_oracle_propagates_driver_errors(self):
        conn = self._make_conn("oracle")
        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("ORA-00942: table or view does not exist")
            mock_db.cursor.return_value = mock_cursor
            mock_get.return_value = mock_db

            result = execute_explain("SELECT * FROM bogus_table", conn, {})

        assert not result.success
        assert "ORA-00942" in result.error

    def test_postgresql_delegates_to_execute_adhoc_with_explain_prefix(self):
        conn = self._make_conn("postgresql")
        with patch("dbqm.core.query_engine.execute_adhoc") as mock_adhoc:
            mock_adhoc.return_value = "delegated"
            result = execute_explain("SELECT 1", conn, {"x": 1})

        assert result == "delegated"
        called_sql = mock_adhoc.call_args[0][0]
        assert called_sql == "EXPLAIN SELECT 1"
        assert mock_adhoc.call_args[0][2] == {"x": 1}

    def test_unsupported_db_returns_clear_error(self):
        conn = self._make_conn("sqlserver")
        result = execute_explain("SELECT 1", conn, {})
        assert not result.success
        assert "sqlserver" in result.error

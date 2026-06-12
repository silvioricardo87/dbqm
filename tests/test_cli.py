"""Tests for the CLI module — argument parsing and command execution."""
from __future__ import annotations

import json

import pytest
from unittest.mock import patch, MagicMock

from dbqm.cli import build_parser, run_cli, _parse_params, COMMAND_MAP
from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult, ComparisonResult, ComparisonRow
from dbqm.models.connection import Connection
from dbqm.models.query import Query, QueryParam
from dbqm.models.group import Group


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connection(name="test_conn"):
    return Connection(name=name, db_type="oracle", user="usr", password="enc_pw")


def _make_query(name="test_query", connection="test_conn", sql="SELECT 1 FROM dual",
                params=None):
    return Query(
        name=name, connection=connection, sql=sql,
        params=params or [],
    )


def _make_query_result(success=True, rows=None, columns=None):
    return QueryResult(
        query_name="test_query",
        connection_name="test_conn",
        columns=columns or ["id", "name"],
        rows=rows if rows is not None else [[1, "Alice"], [2, "Bob"]],
        row_count=len(rows) if rows is not None else 2,
        elapsed=0.05,
        success=success,
        error="" if success else "some error",
    )


def _make_group():
    return Group(
        name="test_group", description="desc",
        queries=["q1", "q2"], join_key="id",
        compare_columns=["status"],
    )


def _make_group_result():
    qr1 = QueryResult(
        query_name="q1", connection_name="c1",
        columns=["id", "status"], rows=[[1, "ok"]], row_count=1, elapsed=0.1,
    )
    qr2 = QueryResult(
        query_name="q2", connection_name="c2",
        columns=["id", "status"], rows=[[1, "ok"]], row_count=1, elapsed=0.1,
    )
    return GroupResult(
        group_name="test_group",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[
            ComparisonResult(
                column="status",
                rows=[ComparisonRow(key_value=1, values={"q1": "ok", "q2": "ok"}, status="OK")],
                total_keys=1, equal_count=1, diff_count=0, absent_count=0, normalized_count=0,
            )
        ],
        all_match=True,
        summary_lines=["Coluna: status", "  Iguais: 1"],
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_parser_creates_all_subcommands(self):
        parser = build_parser()
        # Verify parser was built (no exception)
        assert parser.prog == "dbqm"

    def test_all_commands_have_handlers(self):
        expected = {"run", "run-group", "sql", "test", "list", "ddl",
                    "export-config", "import-config", "history"}
        assert set(COMMAND_MAP.keys()) == expected


class TestParseParams:
    def test_empty(self):
        assert _parse_params(None) == {}
        assert _parse_params([]) == {}

    def test_single_param(self):
        assert _parse_params(["key=value"]) == {"key": "value"}

    def test_multiple_params(self):
        result = _parse_params(["a=1", "b=2"])
        assert result == {"a": "1", "b": "2"}

    def test_value_with_equals(self):
        result = _parse_params(["expr=a=b"])
        assert result == {"expr": "a=b"}

    def test_invalid_param_exits(self):
        with pytest.raises(SystemExit):
            _parse_params(["no_equals_sign"])


class TestRunCliRouting:
    def test_no_command_returns_false(self):
        assert run_cli([]) is False

    def test_help_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            run_cli(["--help"])
        assert exc_info.value.code == 0

    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            run_cli(["nonexistent"])


# ---------------------------------------------------------------------------
# run subcommand
# ---------------------------------------------------------------------------

class TestCmdRun:
    def test_run_query_not_found(self):
        with patch("dbqm.cli.find_query", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run", "missing_query"])

    def test_run_connection_not_found(self):
        query = _make_query()
        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_missing_params(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="")])
        conn = _make_connection()
        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_uses_param_defaults(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="42")])
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_query", return_value=result) as mock_exec, \
             patch("dbqm.cli.record_query_execution"), \
             patch("dbqm.cli.log_execution"), \
             patch("dbqm.cli._print_query_result"):
            run_cli(["run", "test_query"])
            # Should have used default value
            call_params = mock_exec.call_args[0][2]
            assert call_params["id"] == "42"

    def test_run_explicit_params_override_defaults(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="42")])
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_query", return_value=result) as mock_exec, \
             patch("dbqm.cli.record_query_execution"), \
             patch("dbqm.cli.log_execution"), \
             patch("dbqm.cli._print_query_result"):
            run_cli(["run", "test_query", "-p", "id=99"])
            call_params = mock_exec.call_args[0][2]
            assert call_params["id"] == "99"

    def test_run_with_connection_override(self):
        query = _make_query()
        conn = _make_connection("other_conn")
        result = _make_query_result()

        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn) as mock_find_conn, \
             patch("dbqm.cli.execute_query", return_value=result), \
             patch("dbqm.cli.record_query_execution"), \
             patch("dbqm.cli.log_execution"), \
             patch("dbqm.cli._print_query_result"):
            run_cli(["run", "test_query", "-c", "other_conn"])
            mock_find_conn.assert_called_with("other_conn")

    def test_run_failed_query_exits(self):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result(success=False)

        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_query", return_value=result), \
             patch("dbqm.cli.record_query_execution"), \
             patch("dbqm.cli.log_execution"):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_export_csv(self, tmp_config_dir):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_query", return_value=result), \
             patch("dbqm.cli.record_query_execution"), \
             patch("dbqm.cli.log_execution"), \
             patch("dbqm.cli.export_query_csv", return_value="/tmp/out.csv") as mock_exp:
            run_cli(["run", "test_query", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_run_format_json(self, capsys):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.find_query", return_value=query), \
             patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_query", return_value=result), \
             patch("dbqm.cli.record_query_execution"), \
             patch("dbqm.cli.log_execution"):
            run_cli(["run", "test_query", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert data["row_count"] == 2
            assert data["columns"] == ["id", "name"]


# ---------------------------------------------------------------------------
# run-group subcommand
# ---------------------------------------------------------------------------

class TestCmdRunGroup:
    def test_group_not_found(self):
        with patch("dbqm.cli.find_group", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run-group", "missing"])

    def test_group_query_not_found(self):
        group = _make_group()
        with patch("dbqm.cli.find_group", return_value=group), \
             patch("dbqm.cli.find_query", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run-group", "test_group"])

    def test_group_success(self):
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.find_group", return_value=group), \
             patch("dbqm.cli.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.build_group_result", return_value=gr), \
             patch("dbqm.cli.record_group_execution"):
            run_cli(["run-group", "test_group"])

    def test_group_json_output(self, capsys):
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.find_group", return_value=group), \
             patch("dbqm.cli.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.build_group_result", return_value=gr), \
             patch("dbqm.cli.record_group_execution"):
            run_cli(["run-group", "test_group", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert data["all_match"] is True

    def test_group_export(self):
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.find_group", return_value=group), \
             patch("dbqm.cli.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.build_group_result", return_value=gr), \
             patch("dbqm.cli.record_group_execution"), \
             patch("dbqm.cli.export_group_csv", return_value="/tmp/g.csv") as mock_exp:
            run_cli(["run-group", "test_group", "-e", "csv"])
            mock_exp.assert_called_once()


# ---------------------------------------------------------------------------
# sql subcommand
# ---------------------------------------------------------------------------

class TestCmdSql:
    def test_sql_connection_not_found(self):
        with patch("dbqm.cli.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["sql", "SELECT 1", "missing_conn"])

    def test_sql_select(self, capsys):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "SELECT 1 FROM dual", "test_conn", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert data["row_count"] == 1

    def test_sql_dml_autocommit(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UPDATE", connection_name="test_conn",
            rows_affected=3, elapsed=0.01, committed=True,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "UPDATE t SET x=1", "test_conn", "--commit"])

    def test_sql_dml_without_commit_exits(self):
        conn = _make_connection()
        with patch("dbqm.cli.find_connection", return_value=conn):
            with pytest.raises(SystemExit):
                run_cli(["sql", "UPDATE t SET x=1", "test_conn"])

    def test_sql_dml_failed_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UPDATE", connection_name="test_conn",
            rows_affected=0, elapsed=0.01, success=False, error="constraint violation",
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=adhoc):
            with pytest.raises(SystemExit):
                run_cli(["sql", "UPDATE t SET x=1", "test_conn", "--commit"])

    def test_sql_failed_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            success=False, error="syntax error",
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=adhoc):
            with pytest.raises(SystemExit):
                run_cli(["sql", "INVALID SQL", "test_conn"])

    def test_sql_reads_file(self, tmp_path):
        sql_file = tmp_path / "query.sql"
        sql_file.write_text("SELECT * FROM employees", encoding="utf-8")
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["id"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=adhoc) as mock_exec:
            run_cli(["sql", str(sql_file), "test_conn", "-f", "json"])
            called_sql = mock_exec.call_args[0][0]
            assert "SELECT * FROM employees" in called_sql

    def test_sql_export(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=adhoc), \
             patch("dbqm.cli.export_query_csv", return_value="/tmp/out.csv") as mock_exp:
            run_cli(["sql", "SELECT 1", "test_conn", "-e", "csv"])
            mock_exp.assert_called_once()


# ---------------------------------------------------------------------------
# test subcommand
# ---------------------------------------------------------------------------

class TestCmdTest:
    def test_connection_not_found(self):
        with patch("dbqm.cli.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["test", "missing"])

    def test_connection_ok(self):
        conn = _make_connection()
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.test_connection", return_value=(True, 'OK (0.01s)\n  Versao: v1')):
            run_cli(["test", "test_conn"])

    def test_connection_fail(self):
        conn = _make_connection()
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.test_connection", return_value=(False, "Erro ao conectar")):
            with pytest.raises(SystemExit):
                run_cli(["test", "test_conn"])

    def test_all_connections(self):
        conns = [_make_connection("c1"), _make_connection("c2")]
        with patch("dbqm.cli.load_connections", return_value=conns), \
             patch("dbqm.cli.test_connection", return_value=(True, "OK")):
            run_cli(["test"])

    def test_no_connections(self):
        with patch("dbqm.cli.load_connections", return_value=[]):
            run_cli(["test"])


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------

class TestCmdList:
    def test_list_connections(self):
        conns = [_make_connection()]
        with patch("dbqm.cli.load_connections", return_value=conns):
            run_cli(["list", "connections"])

    def test_list_connections_json(self, capsys):
        conns = [_make_connection()]
        with patch("dbqm.cli.load_connections", return_value=conns):
            run_cli(["list", "connections", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert len(data) == 1
            assert data[0]["name"] == "test_conn"

    def test_list_queries(self):
        queries = [_make_query()]
        with patch("dbqm.cli.load_queries", return_value=queries):
            run_cli(["list", "queries"])

    def test_list_queries_json(self, capsys):
        queries = [_make_query()]
        with patch("dbqm.cli.load_queries", return_value=queries):
            run_cli(["list", "queries", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert len(data) == 1

    def test_list_groups(self):
        groups = [_make_group()]
        with patch("dbqm.cli.load_groups", return_value=groups):
            run_cli(["list", "groups"])

    def test_list_groups_json(self, capsys):
        groups = [_make_group()]
        with patch("dbqm.cli.load_groups", return_value=groups):
            run_cli(["list", "groups", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert data[0]["join_key"] == "id"

    def test_list_empty_connections(self):
        with patch("dbqm.cli.load_connections", return_value=[]):
            run_cli(["list", "connections"])

    def test_list_empty_queries(self):
        with patch("dbqm.cli.load_queries", return_value=[]):
            run_cli(["list", "queries"])

    def test_list_empty_groups(self):
        with patch("dbqm.cli.load_groups", return_value=[]):
            run_cli(["list", "groups"])


# ---------------------------------------------------------------------------
# ddl subcommand
# ---------------------------------------------------------------------------

class TestCmdDdl:
    def test_ddl_connection_not_found(self):
        with patch("dbqm.cli.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["ddl", "MY_TABLE", "missing"])

    def test_ddl_save(self):
        conn = _make_connection()
        from dbqm.core.ddl_extractor import ExtractionResult, ExtractedObject
        result = ExtractionResult(
            object_name="MY_TABLE", object_type="TABLE",
            owner="OWNER", connection_name="test_conn",
            objects=[ExtractedObject("MY_TABLE", "TABLE", "CREATE TABLE ...")],
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.extract_ddl", return_value=result), \
             patch("dbqm.cli.save_extraction", return_value=("/tmp/ddl", 2)) as mock_save:
            run_cli(["ddl", "MY_TABLE", "test_conn"])
            mock_save.assert_called_once()

    def test_ddl_stdout(self, capsys):
        conn = _make_connection()
        from dbqm.core.ddl_extractor import ExtractionResult, ExtractedObject
        result = ExtractionResult(
            object_name="MY_TABLE", object_type="TABLE",
            owner="OWNER", connection_name="test_conn",
            objects=[ExtractedObject("MY_TABLE", "TABLE", "CREATE TABLE MY_TABLE (id NUMBER);")],
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.extract_ddl", return_value=result):
            run_cli(["ddl", "MY_TABLE", "test_conn", "--stdout"])
            out = capsys.readouterr().out
            assert "CREATE TABLE" in out

    def test_ddl_errors_no_objects_exits(self):
        conn = _make_connection()
        from dbqm.core.ddl_extractor import ExtractionResult
        result = ExtractionResult(
            object_name="MISSING", object_type="UNKNOWN",
            owner="", connection_name="test_conn",
            errors=["Objeto 'MISSING' nao encontrado."],
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.extract_ddl", return_value=result):
            with pytest.raises(SystemExit):
                run_cli(["ddl", "MISSING", "test_conn"])


# ---------------------------------------------------------------------------
# history subcommand
# ---------------------------------------------------------------------------

class TestCmdHistory:
    def test_history_empty(self):
        with patch("dbqm.cli.load_history", return_value=[]):
            run_cli(["history"])

    def test_history_with_entries(self):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id="1", timestamp="2026-01-01T00:00:00", entry_type="query",
                         name="q1", connection="c1", row_count=10, elapsed=0.5),
        ]
        with patch("dbqm.cli.load_history", return_value=entries):
            run_cli(["history", "-n", "5"])

    def test_history_json(self, capsys):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id="1", timestamp="2026-01-01", entry_type="query",
                         name="q1", connection="c1"),
        ]
        with patch("dbqm.cli.load_history", return_value=entries):
            run_cli(["history", "-f", "json"])
            out = capsys.readouterr().out
            data = json.loads(out)
            assert len(data) == 1
            assert data[0]["name"] == "q1"

    def test_history_clear(self):
        with patch("dbqm.cli.clear_history") as mock_clear:
            run_cli(["history", "--clear"])
            mock_clear.assert_called_once()

    def test_history_limit(self):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id=str(i), timestamp="t", entry_type="query",
                         name=f"q{i}", connection="c")
            for i in range(50)
        ]
        with patch("dbqm.cli.load_history", return_value=entries):
            # Default limit is 20, but custom limit of 5
            run_cli(["history", "-n", "5"])


# ---------------------------------------------------------------------------
# export-config / import-config subcommands
# ---------------------------------------------------------------------------

class TestCmdExportConfig:
    def test_export_with_password(self):
        with patch("dbqm.cli.export_configs", return_value="/tmp/cfg.dbqm") as mock_exp:
            run_cli(["export-config", "--password", "s3cret"])
            mock_exp.assert_called_once_with(
                "s3cret",
                include_connections=True,
                include_queries=True,
                include_groups=True,
            )

    def test_export_no_connections(self):
        with patch("dbqm.cli.export_configs", return_value="/tmp/cfg.dbqm") as mock_exp:
            run_cli(["export-config", "--password", "pw", "--no-connections"])
            mock_exp.assert_called_once_with(
                "pw",
                include_connections=False,
                include_queries=True,
                include_groups=True,
            )

    def test_export_prompts_password(self):
        with patch("dbqm.cli.export_configs", return_value="/tmp/cfg.dbqm"), \
             patch("dbqm.cli.getpass.getpass", return_value="prompted_pw") as mock_gp:
            run_cli(["export-config"])
            mock_gp.assert_called_once()


class TestCmdImportConfig:
    def test_import_success(self):
        summary = {"connections": 2, "queries": 3, "groups": 1, "skipped": 0}
        with patch("dbqm.cli.import_configs", return_value=summary):
            run_cli(["import-config", "file.dbqm", "--password", "pw"])

    def test_import_error(self):
        with patch("dbqm.cli.import_configs", side_effect=ValueError("bad password")):
            with pytest.raises(SystemExit):
                run_cli(["import-config", "file.dbqm", "--password", "wrong"])


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

class TestPrintQueryResult:
    def test_json_format(self, capsys):
        from dbqm.cli import _print_query_result
        result = _make_query_result()
        _print_query_result(result, "json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["row_count"] == 2
        assert len(data["rows"]) == 2

    def test_csv_format(self, capsys):
        from dbqm.cli import _print_query_result
        result = _make_query_result()
        _print_query_result(result, "csv")
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        assert "id" in lines[0]
        assert len(lines) == 3  # header + 2 rows

    def test_table_format(self):
        from dbqm.cli import _print_query_result
        result = _make_query_result()
        # Should not raise
        _print_query_result(result, "table")

    def test_failed_result_exits(self):
        from dbqm.cli import _print_query_result
        result = _make_query_result(success=False)
        with pytest.raises(SystemExit):
            _print_query_result(result, "table")

    def test_raw_format_single_column_no_decoration(self, capsys):
        """`--format raw` with one column prints bare values, one per row."""
        from dbqm.cli import _print_query_result
        result = _make_query_result(
            columns=["text"],
            rows=[["line one"], ["line two"], ["line three"]],
        )
        _print_query_result(result, "raw")
        out = capsys.readouterr().out
        assert out == "line one\nline two\nline three\n"
        assert "text" not in out  # no header
        assert "registros em" not in out  # no footer

    def test_raw_format_multi_column_tab_separated(self, capsys):
        from dbqm.cli import _print_query_result
        result = _make_query_result(
            columns=["id", "name"],
            rows=[[1, "Alice"], [2, "Bob"]],
        )
        _print_query_result(result, "raw")
        out = capsys.readouterr().out
        assert out == "1\tAlice\n2\tBob\n"

    def test_raw_format_materializes_clob_like_objects(self, capsys):
        """Objects exposing .read() (CLOB/LONG) are materialized to text."""
        from dbqm.cli import _print_query_result

        class FakeClob:
            def __init__(self, text):
                self._text = text

            def read(self):
                return self._text

        result = _make_query_result(
            columns=["body"],
            rows=[[FakeClob("CREATE OR REPLACE VIEW v AS SELECT 1 FROM dual")]],
        )
        _print_query_result(result, "raw")
        out = capsys.readouterr().out
        assert "CREATE OR REPLACE VIEW" in out
        assert "FakeClob" not in out

    def test_raw_format_handles_none(self, capsys):
        from dbqm.cli import _print_query_result
        result = _make_query_result(
            columns=["v"],
            rows=[[None], ["x"]],
        )
        _print_query_result(result, "raw")
        out = capsys.readouterr().out
        assert out == "\nx\n"


class TestRawFormatChoiceAccepted:
    """argparse must accept `raw` for both `run` and `sql` subcommands."""

    def test_run_accepts_raw(self):
        parser = build_parser()
        args = parser.parse_args(["run", "myq", "-f", "raw"])
        assert args.format == "raw"

    def test_sql_accepts_raw(self):
        parser = build_parser()
        args = parser.parse_args(["sql", "SELECT 1", "myconn", "-f", "raw"])
        assert args.format == "raw"


class TestSqlSubcommandHelpMentionsPlsql:
    """The `sql` subcommand help must advertise PL/SQL/EXEC support so users
    discover it without reading the changelog."""

    def test_sql_help_mentions_plsql(self, capsys):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["sql", "--help"])
        out = capsys.readouterr().out
        assert "PL/SQL" in out
        assert "EXEC" in out

    def test_sql_help_mentions_explain_and_cte(self, capsys):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["sql", "--help"])
        out = capsys.readouterr().out
        assert "--explain" in out
        assert "CTE" in out
        assert "EXPLAIN PLAN" in out


class TestCmdSqlExplain:
    """--explain dispatches to execute_explain and prints the plan."""

    def test_explain_prints_plan_lines_and_skips_execute_adhoc(self, capsys):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        plan = AdhocResult(
            sql_type="EXPLAIN", connection_name="test_conn",
            columns=["plan"],
            rows=[["Plan hash value: 999"], ["FULL TABLE SCAN T"]],
            row_count=2, elapsed=0.01,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_explain", return_value=plan) as mock_explain, \
             patch("dbqm.cli.execute_adhoc") as mock_adhoc:
            run_cli(["sql", "SELECT * FROM t", "test_conn", "--explain"])

        assert mock_explain.called
        assert not mock_adhoc.called
        out = capsys.readouterr().out
        assert "Plan hash value: 999" in out
        assert "FULL TABLE SCAN T" in out

    def test_explain_failure_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        plan = AdhocResult(
            sql_type="EXPLAIN", connection_name="test_conn",
            success=False, error="ORA-00942: table or view does not exist",
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_explain", return_value=plan):
            with pytest.raises(SystemExit):
                run_cli(["sql", "SELECT * FROM bogus", "test_conn", "--explain"])

    def test_explain_passes_param_values(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        plan = AdhocResult(
            sql_type="EXPLAIN", connection_name="test_conn",
            columns=["plan"], rows=[], row_count=0, elapsed=0.0,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_explain", return_value=plan) as mock_explain:
            run_cli(["sql", "SELECT * FROM t WHERE id = :id", "test_conn",
                     "--explain", "-p", "id=42"])
        # call signature: execute_explain(sql, conn, param_values)
        assert mock_explain.call_args[0][2] == {"id": "42"}


class TestCmdSqlPlsqlOutput:
    """PL/SQL via CLI prints captured DBMS_OUTPUT lines."""

    def test_prints_dbms_output_lines(self, capsys):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        res = AdhocResult(
            sql_type="PLSQL", connection_name="test_conn",
            elapsed=0.01, committed=True,
            output_lines=["processando 1", "processando 2"],
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=res):
            run_cli(["sql", "BEGIN NULL; END;", "test_conn"])
        out = capsys.readouterr().out
        assert "processando 1" in out
        assert "processando 2" in out
        assert "Bloco PL/SQL executado" in out

    def test_no_output_lines_prints_only_status(self, capsys):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        res = AdhocResult(
            sql_type="PLSQL", connection_name="test_conn",
            elapsed=0.01, committed=True,
        )
        with patch("dbqm.cli.find_connection", return_value=conn), \
             patch("dbqm.cli.execute_adhoc", return_value=res):
            run_cli(["sql", "BEGIN NULL; END;", "test_conn"])
        out = capsys.readouterr().out
        assert "Bloco PL/SQL executado" in out


# ---------------------------------------------------------------------------
# main.py integration
# ---------------------------------------------------------------------------

class TestMainEntryPoint:
    def test_main_with_args_routes_to_cli(self):
        """main.py routes to CLI when args are provided."""
        from dbqm.main import main as dbqm_main
        with patch("sys.argv", ["dbqm", "list", "connections"]), \
             patch("dbqm.cli.run_cli", return_value=True) as mock_cli:
            dbqm_main()
            mock_cli.assert_called_once()

    def test_main_no_args_routes_to_tui(self):
        """main.py routes to Textual TUI when no args are provided."""
        from dbqm.main import main as dbqm_main
        with patch("sys.argv", ["dbqm"]), \
             patch("dbqm.core.paths.ensure_dirs"), \
             patch("dbqm.ui.app.DBQMApp.run") as mock_run:
            dbqm_main()
            mock_run.assert_called_once()

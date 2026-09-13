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
                    "export-config", "import-config", "history", "connection"}
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
        with patch("dbqm.cli.deps.find_query", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run", "missing_query"])

    def test_run_connection_not_found(self):
        query = _make_query()
        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_missing_params(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="")])
        conn = _make_connection()
        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_uses_param_defaults(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="42")])
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result) as mock_exec, \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"), \
             patch("dbqm.cli.render._print_query_result") as mock_print:
            run_cli(["run", "test_query"])
            # Should have used default value
            call_params = mock_exec.call_args[0][2]
            assert call_params["id"] == "42"
            mock_print.assert_called_once()

    def test_run_explicit_params_override_defaults(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="42")])
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result) as mock_exec, \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"), \
             patch("dbqm.cli.render._print_query_result") as mock_print:
            run_cli(["run", "test_query", "-p", "id=99"])
            call_params = mock_exec.call_args[0][2]
            assert call_params["id"] == "99"
            mock_print.assert_called_once()

    def test_run_with_connection_override(self):
        query = _make_query()
        conn = _make_connection("other_conn")
        result = _make_query_result()

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn) as mock_find_conn, \
             patch("dbqm.cli.deps.execute_query", return_value=result), \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"), \
             patch("dbqm.cli.render._print_query_result") as mock_print:
            run_cli(["run", "test_query", "-c", "other_conn"])
            mock_find_conn.assert_called_with("other_conn")
            mock_print.assert_called_once()

    def test_run_failed_query_exits(self):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result(success=False)

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result), \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_export_csv(self, tmp_config_dir):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result), \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"), \
             patch("dbqm.cli.deps.export_query_csv", return_value="/tmp/out.csv") as mock_exp:
            run_cli(["run", "test_query", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_run_format_json(self, capsys):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result), \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"):
            run_cli(["run", "test_query", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "run"
            assert corpo["data"]["row_count"] == 2
            assert corpo["data"]["columns"] == ["id", "name"]

    def test_run_export_json_format_emits_envelope(self, capsys):
        """CRITICAL fix: `-e` used to print bare prose and return under
        `-f json`, exiting 0 with no envelope on stdout at all."""
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result), \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"), \
             patch("dbqm.cli.deps.export_query_csv", return_value="/tmp/out.csv"):
            run_cli(["run", "test_query", "-e", "csv", "-f", "json"])
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["ok"] is True
            assert corpo["command"] == "run"
            assert corpo["data"] == {"exported": "/tmp/out.csv", "format": "csv"}

    def test_run_failed_query_table_format_exits_via_fail_or_print(self):
        """IMPORTANT fix: `table`/`csv`/`raw` used to fall through to
        `render._print_query_result`'s own bare `exit(1)` instead of
        `_fail_or_print`'s mapped exit code."""
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result(success=False)

        with patch("dbqm.cli.deps.find_query", return_value=query), \
             patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_query", return_value=result), \
             patch("dbqm.cli.deps.record_query_execution"), \
             patch("dbqm.cli.deps.log_execution"):
            with pytest.raises(SystemExit) as exc:
                run_cli(["run", "test_query"])
            assert exc.value.code == 4


# ---------------------------------------------------------------------------
# run-group subcommand
# ---------------------------------------------------------------------------

class TestCmdRunGroup:
    def test_group_not_found(self):
        with patch("dbqm.cli.deps.find_group", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run-group", "missing"])

    def test_group_query_not_found(self):
        group = _make_group()
        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", return_value=None):
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

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"):
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

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"):
            run_cli(["run-group", "test_group", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "run-group"
            assert corpo["data"]["all_match"] is True

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

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"), \
             patch("dbqm.cli.deps.export_group_csv", return_value="/tmp/g.csv") as mock_exp:
            run_cli(["run-group", "test_group", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_group_export_json_format_emits_envelope(self, capsys):
        """CRITICAL fix: `-e` used to print bare prose and return under
        `-f json`."""
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()  # all_match True

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"), \
             patch("dbqm.cli.deps.export_group_csv", return_value="/tmp/g.csv"):
            run_cli(["run-group", "test_group", "-e", "csv", "-f", "json"])
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["ok"] is True
            assert corpo["command"] == "run-group"
            assert corpo["data"] == {"exported": "/tmp/g.csv", "format": "csv"}

    def test_export_json_with_divergence_exits_five_after_the_envelope(self, capsys):
        """CRITICAL fix, json side: the export envelope still prints, but
        the process exits 5 — `--export` doesn't opt json out either."""
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()
        gr.all_match = False

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"), \
             patch("dbqm.cli.deps.export_group_csv", return_value="/tmp/g.csv"):
            with pytest.raises(SystemExit) as exc:
                run_cli(["run-group", "test_group", "-e", "csv", "-f", "json"])
            assert exc.value.code == 5
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["data"] == {"exported": "/tmp/g.csv", "format": "csv"}

    def test_export_with_divergence_still_exits_five(self):
        """CRITICAL fix: `--export` must not opt run-group out of the
        divergence exit (it did, silently, before this fix)."""
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()
        gr.all_match = False

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"), \
             patch("dbqm.cli.deps.export_group_csv", return_value="/tmp/g.csv") as mock_exp:
            with pytest.raises(SystemExit) as exc:
                run_cli(["run-group", "test_group", "-e", "csv"])
            assert exc.value.code == 5
            mock_exp.assert_called_once()

    def test_matching_group_exits_zero_under_table(self):
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()  # all_match True

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"):
            run_cli(["run-group", "test_group"])  # must not raise

    def test_divergent_group_exits_five_under_table(self):
        group = _make_group()
        q1 = _make_query("q1", "c1")
        q2 = _make_query("q2", "c2")
        c1 = _make_connection("c1")
        c2 = _make_connection("c2")
        gr = _make_group_result()
        gr.all_match = False

        def find_query_side(name):
            return {"q1": q1, "q2": q2}.get(name)

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        with patch("dbqm.cli.deps.find_group", return_value=group), \
             patch("dbqm.cli.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.cli.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.cli.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.cli.deps.build_group_result", return_value=gr), \
             patch("dbqm.cli.deps.record_group_execution"):
            with pytest.raises(SystemExit) as exc:
                run_cli(["run-group", "test_group"])
            assert exc.value.code == 5


# ---------------------------------------------------------------------------
# sql subcommand
# ---------------------------------------------------------------------------

class TestCmdSql:
    def test_sql_connection_not_found(self):
        with patch("dbqm.cli.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["sql", "SELECT 1", "missing_conn"])

    def test_sql_select(self, capsys):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "SELECT 1 FROM dual", "test_conn", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "sql"
            assert corpo["data"]["row_count"] == 1

    def test_sql_dml_autocommit(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UPDATE", connection_name="test_conn",
            rows_affected=3, elapsed=0.01, committed=True,
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "UPDATE t SET x=1", "test_conn", "--commit"])

    def test_sql_dml_without_commit_exits(self):
        conn = _make_connection()
        with patch("dbqm.cli.deps.find_connection", return_value=conn):
            with pytest.raises(SystemExit):
                run_cli(["sql", "UPDATE t SET x=1", "test_conn"])

    def test_sql_dml_failed_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UPDATE", connection_name="test_conn",
            rows_affected=0, elapsed=0.01, success=False, error="constraint violation",
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc):
            with pytest.raises(SystemExit):
                run_cli(["sql", "UPDATE t SET x=1", "test_conn", "--commit"])

    def test_sql_failed_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            success=False, error="syntax error",
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc):
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc) as mock_exec:
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc), \
             patch("dbqm.cli.deps.export_query_csv", return_value="/tmp/out.csv") as mock_exp:
            run_cli(["sql", "SELECT 1", "test_conn", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_sql_export_json_format_emits_envelope(self, capsys):
        """CRITICAL fix: `-e` used to print bare prose and return under
        `-f json`."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc), \
             patch("dbqm.cli.deps.export_query_csv", return_value="/tmp/out.csv"):
            run_cli(["sql", "SELECT 1", "test_conn", "-e", "csv", "-f", "json"])
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["ok"] is True
            assert corpo["command"] == "sql"
            assert corpo["data"] == {"exported": "/tmp/out.csv", "format": "csv"}

    def test_sql_unclassified_type_gets_envelope_under_json(self, capsys):
        """CRITICAL fix: a statement `execute_adhoc` runs but doesn't
        special-case (sql_type not SELECT/INSERT/UPDATE/DELETE/DDL/PLSQL)
        used to fall past every json branch to a bare `print`."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="MERGE", connection_name="test_conn",
            rows_affected=2, elapsed=0.02, committed=True,
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.classify_sql", return_value="MERGE"), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "MERGE INTO t ...", "test_conn", "-f", "json"])
            saida = capsys.readouterr()
            corpo = json.loads(saida.out)
            assert corpo["ok"] is True
            assert corpo["command"] == "sql"
            assert corpo["data"]["sql_type"] == "MERGE"
            assert corpo["data"]["rows_affected"] == 2

    def test_sql_unsupported_type_is_usage_not_sql_error(self, capsys):
        """MINOR fix: `core/`'s "Tipo de SQL nao suportado" is bad input,
        not the driver rejecting a statement it actually received."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UNKNOWN", connection_name="test_conn",
            success=False,
            error="Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE, "
                  "DELETE, DDL (CREATE/ALTER/DROP...) ou EXPLAIN PLAN.",
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.classify_sql", return_value="UNKNOWN"), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=adhoc):
            with pytest.raises(SystemExit) as exc:
                run_cli(["sql", "??? nonsense ???", "test_conn", "-f", "json"])
            assert exc.value.code == 2
            saida = capsys.readouterr()
            assert saida.out == ""
            assert json.loads(saida.err)["error"]["code"] == "usage"


# ---------------------------------------------------------------------------
# test subcommand
# ---------------------------------------------------------------------------

class TestCmdTest:
    def test_connection_not_found(self):
        with patch("dbqm.cli.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["test", "missing"])

    def test_connection_ok(self):
        conn = _make_connection()
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.test_connection", return_value=(True, 'OK (0.01s)\n  Versao: v1')):
            run_cli(["test", "test_conn"])

    def test_connection_fail(self):
        conn = _make_connection()
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.test_connection", return_value=(False, "Erro ao conectar")):
            with pytest.raises(SystemExit):
                run_cli(["test", "test_conn"])

    def test_all_connections(self):
        conns = [_make_connection("c1"), _make_connection("c2")]
        with patch("dbqm.cli.deps.load_connections", return_value=conns), \
             patch("dbqm.cli.deps.test_connection", return_value=(True, "OK")):
            run_cli(["test"])

    def test_no_connections(self):
        with patch("dbqm.cli.deps.load_connections", return_value=[]):
            run_cli(["test"])


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------

class TestCmdList:
    def test_list_connections(self):
        conns = [_make_connection()]
        with patch("dbqm.cli.deps.load_connections", return_value=conns):
            run_cli(["list", "connections"])

    def test_list_connections_json(self, capsys):
        conns = [_make_connection()]
        with patch("dbqm.cli.deps.load_connections", return_value=conns):
            run_cli(["list", "connections", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "list.connections"
            assert len(corpo["data"]) == 1
            assert corpo["data"][0]["name"] == "test_conn"

    def test_list_queries(self):
        queries = [_make_query()]
        with patch("dbqm.cli.deps.load_queries", return_value=queries):
            run_cli(["list", "queries"])

    def test_list_queries_json(self, capsys):
        queries = [_make_query()]
        with patch("dbqm.cli.deps.load_queries", return_value=queries):
            run_cli(["list", "queries", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "list.queries"
            assert len(corpo["data"]) == 1

    def test_list_groups(self):
        groups = [_make_group()]
        with patch("dbqm.cli.deps.load_groups", return_value=groups):
            run_cli(["list", "groups"])

    def test_list_groups_json(self, capsys):
        groups = [_make_group()]
        with patch("dbqm.cli.deps.load_groups", return_value=groups):
            run_cli(["list", "groups", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "list.groups"
            assert corpo["data"][0]["join_key"] == "id"

    def test_list_empty_connections(self):
        with patch("dbqm.cli.deps.load_connections", return_value=[]):
            run_cli(["list", "connections"])

    def test_list_empty_queries(self):
        with patch("dbqm.cli.deps.load_queries", return_value=[]):
            run_cli(["list", "queries"])

    def test_list_empty_groups(self):
        with patch("dbqm.cli.deps.load_groups", return_value=[]):
            run_cli(["list", "groups"])


# ---------------------------------------------------------------------------
# ddl subcommand
# ---------------------------------------------------------------------------

class TestCmdDdl:
    def test_ddl_connection_not_found(self):
        with patch("dbqm.cli.deps.find_connection", return_value=None):
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.extract_ddl", return_value=result), \
             patch("dbqm.cli.deps.save_extraction", return_value=("/tmp/ddl", 2)) as mock_save:
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.extract_ddl", return_value=result):
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.extract_ddl", return_value=result):
            with pytest.raises(SystemExit) as exc:
                run_cli(["ddl", "MISSING", "test_conn"])
            assert exc.value.code == 4

    def test_ddl_json_envelope(self, capsys):
        conn = _make_connection()
        from dbqm.core.ddl_extractor import ExtractionResult, ExtractedObject
        result = ExtractionResult(
            object_name="MY_TABLE", object_type="TABLE",
            owner="OWNER", connection_name="test_conn",
            objects=[ExtractedObject("MY_TABLE", "TABLE", "CREATE TABLE MY_TABLE (id NUMBER);")],
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.extract_ddl", return_value=result), \
             patch("dbqm.cli.deps.save_extraction", return_value=("/tmp/ddl", 1)):
            run_cli(["ddl", "MY_TABLE", "test_conn", "-f", "json"])
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["ok"] is True
            assert corpo["command"] == "ddl"
            assert corpo["data"]["path"] == "/tmp/ddl"
            assert corpo["data"]["objects"][0]["name"] == "MY_TABLE"
            assert corpo["data"]["objects"][0]["ddl"] == "CREATE TABLE MY_TABLE (id NUMBER);"

    def test_ddl_json_failure_leaves_stdout_clean(self, capsys):
        with patch("dbqm.cli.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit) as exc:
                run_cli(["ddl", "MY_TABLE", "missing", "-f", "json"])
            assert exc.value.code == 2
            saida = capsys.readouterr()
            assert saida.out == ""
            assert json.loads(saida.err)["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# history subcommand
# ---------------------------------------------------------------------------

class TestCmdHistory:
    def test_history_empty(self):
        with patch("dbqm.cli.deps.load_history", return_value=[]):
            run_cli(["history"])

    def test_history_with_entries(self):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id="1", timestamp="2026-01-01T00:00:00", entry_type="query",
                         name="q1", connection="c1", row_count=10, elapsed=0.5),
        ]
        with patch("dbqm.cli.deps.load_history", return_value=entries):
            run_cli(["history", "-n", "5"])

    def test_history_json(self, capsys):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id="1", timestamp="2026-01-01", entry_type="query",
                         name="q1", connection="c1"),
        ]
        with patch("dbqm.cli.deps.load_history", return_value=entries):
            run_cli(["history", "-f", "json"])
            out = capsys.readouterr().out
            corpo = json.loads(out)
            assert corpo["command"] == "history"
            assert len(corpo["data"]) == 1
            assert corpo["data"][0]["name"] == "q1"

    def test_history_clear(self):
        with patch("dbqm.cli.deps.clear_history") as mock_clear:
            run_cli(["history", "--clear"])
            mock_clear.assert_called_once()

    def test_history_limit(self):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id=str(i), timestamp="t", entry_type="query",
                         name=f"q{i}", connection="c")
            for i in range(50)
        ]
        with patch("dbqm.cli.deps.load_history", return_value=entries):
            # Default limit is 20, but custom limit of 5
            run_cli(["history", "-n", "5"])


# ---------------------------------------------------------------------------
# export-config / import-config subcommands
# ---------------------------------------------------------------------------

class TestCmdExportConfig:
    def test_export_with_password(self):
        with patch("dbqm.cli.deps.export_configs", return_value="/tmp/cfg.dbqm") as mock_exp:
            run_cli(["export-config", "--password", "s3cret"])
            mock_exp.assert_called_once_with(
                "s3cret",
                include_connections=True,
                include_queries=True,
                include_groups=True,
            )

    def test_export_no_connections(self):
        with patch("dbqm.cli.deps.export_configs", return_value="/tmp/cfg.dbqm") as mock_exp:
            run_cli(["export-config", "--password", "pw", "--no-connections"])
            mock_exp.assert_called_once_with(
                "pw",
                include_connections=False,
                include_queries=True,
                include_groups=True,
            )

    def test_export_prompts_password(self):
        with patch("dbqm.cli.deps.export_configs", return_value="/tmp/cfg.dbqm"), \
             patch("sys.stdin.isatty", return_value=True), \
             patch("dbqm.cli.params.getpass.getpass", return_value="prompted_pw") as mock_gp:
            run_cli(["export-config"])
            mock_gp.assert_called_once()

    def test_export_config_json_envelope(self, capsys):
        with patch("dbqm.cli.deps.export_configs", return_value="/tmp/cfg.dbqm"):
            run_cli(["export-config", "--password", "s3cret", "-f", "json"])
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["ok"] is True
            assert corpo["command"] == "export-config"
            assert corpo["data"] == {"path": "/tmp/cfg.dbqm"}

    def test_export_config_json_failure_leaves_stdout_clean(self, monkeypatch, capsys):
        """No password source and no tty — `resolve_password`'s own failure,
        now threaded through the envelope too."""
        monkeypatch.delenv("DBQM_BUNDLE_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        with pytest.raises(SystemExit) as exc:
            run_cli(["export-config", "-f", "json"])
        assert exc.value.code == 2
        saida = capsys.readouterr()
        assert saida.out == ""
        assert json.loads(saida.err)["error"]["code"] == "usage"


class TestCmdImportConfig:
    def test_import_success(self):
        summary = {"connections": 2, "queries": 3, "groups": 1, "skipped": 0}
        with patch("dbqm.cli.deps.import_configs", return_value=summary):
            run_cli(["import-config", "file.dbqm", "--password", "pw"])

    def test_import_error(self):
        with patch("dbqm.cli.deps.import_configs", side_effect=ValueError("bad password")):
            with pytest.raises(SystemExit) as exc:
                run_cli(["import-config", "file.dbqm", "--password", "wrong"])
            assert exc.value.code == 2

    def test_import_config_json_envelope(self, capsys):
        summary = {"connections": 2, "queries": 3, "groups": 1, "skipped": 0}
        with patch("dbqm.cli.deps.import_configs", return_value=summary):
            run_cli(["import-config", "file.dbqm", "--password", "pw", "-f", "json"])
            corpo = json.loads(capsys.readouterr().out)
            assert corpo["ok"] is True
            assert corpo["command"] == "import-config"
            assert corpo["data"] == summary

    def test_import_config_json_failure_leaves_stdout_clean(self, capsys):
        with patch("dbqm.cli.deps.import_configs", side_effect=ValueError("bad password")):
            with pytest.raises(SystemExit) as exc:
                run_cli(["import-config", "file.dbqm", "--password", "wrong", "-f", "json"])
            assert exc.value.code == 2
            saida = capsys.readouterr()
            assert saida.out == ""
            assert json.loads(saida.err)["error"]["code"] == "validation"


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

class TestPrintQueryResult:
    """`_print_query_result` no longer has a `json` branch: every caller now
    builds the envelope itself (`ok()`) before ever reaching this function,
    so a bare unwrapped dict on stdout under `-f json` can't reappear here
    for the next caller to trip over."""

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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_explain", return_value=plan) as mock_explain, \
             patch("dbqm.cli.deps.execute_adhoc") as mock_adhoc:
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_explain", return_value=plan):
            with pytest.raises(SystemExit):
                run_cli(["sql", "SELECT * FROM bogus", "test_conn", "--explain"])

    def test_explain_passes_param_values(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        plan = AdhocResult(
            sql_type="EXPLAIN", connection_name="test_conn",
            columns=["plan"], rows=[], row_count=0, elapsed=0.0,
        )
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_explain", return_value=plan) as mock_explain:
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=res):
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
        with patch("dbqm.cli.deps.find_connection", return_value=conn), \
             patch("dbqm.cli.deps.execute_adhoc", return_value=res):
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


class TestResolvePassword:
    """Non-interactive password sources — an agent has no TTY."""

    def _args(self, **kwargs):
        from argparse import Namespace
        base = {"password_stdin": False, "password": None}
        base.update(kwargs)
        return Namespace(**base)

    def test_stdin_wins(self, monkeypatch):
        import io
        from dbqm.cli import resolve_password

        monkeypatch.setattr("sys.stdin", io.StringIO("from-stdin\n"))
        monkeypatch.setenv("DBQM_PASSWORD", "from-env")
        args = self._args(password_stdin=True)
        assert resolve_password(args, "DBQM_PASSWORD", "p: ", required=True) == "from-stdin"

    def test_stdin_keeps_inner_spaces_and_drops_only_the_newline(self, monkeypatch):
        import io
        from dbqm.cli import resolve_password

        monkeypatch.setattr("sys.stdin", io.StringIO(" a b \r\n"))
        args = self._args(password_stdin=True)
        assert resolve_password(args, "DBQM_PASSWORD", "p: ", required=True) == " a b "

    def test_flag_beats_env(self, monkeypatch):
        from dbqm.cli import resolve_password

        monkeypatch.setenv("DBQM_PASSWORD", "from-env")
        args = self._args(password="from-flag")
        assert resolve_password(args, "DBQM_PASSWORD", "p: ", required=True) == "from-flag"

    def test_env_is_used_when_nothing_else_is_given(self, monkeypatch):
        from dbqm.cli import resolve_password

        monkeypatch.setenv("DBQM_PASSWORD", "from-env")
        assert resolve_password(self._args(), "DBQM_PASSWORD", "p: ", required=True) == "from-env"

    def test_stdin_and_flag_together_is_an_error(self, monkeypatch):
        from dbqm.cli import resolve_password

        args = self._args(password_stdin=True, password="x")
        with pytest.raises(SystemExit) as exc:
            resolve_password(args, "DBQM_PASSWORD", "p: ", required=True)
        assert exc.value.code == 2

    def test_required_without_a_source_and_without_a_tty_exits_2(self, monkeypatch):
        from dbqm.cli import resolve_password

        monkeypatch.delenv("DBQM_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        with pytest.raises(SystemExit) as exc:
            resolve_password(self._args(), "DBQM_PASSWORD", "p: ", required=True)
        assert exc.value.code == 2

    def test_required_prompts_on_a_tty(self, monkeypatch):
        from dbqm.cli import resolve_password

        monkeypatch.delenv("DBQM_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("getpass.getpass", lambda prompt="": "typed")
        assert resolve_password(self._args(), "DBQM_PASSWORD", "p: ", required=True) == "typed"

    def test_optional_without_a_source_returns_none_and_never_prompts(self, monkeypatch):
        from dbqm.cli import resolve_password

        monkeypatch.delenv("DBQM_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def _explode(prompt=""):
            raise AssertionError("an optional password must not prompt")

        monkeypatch.setattr("getpass.getpass", _explode)
        assert resolve_password(self._args(), "DBQM_PASSWORD", "p: ", required=False) is None


class TestConfigBundlePassword:
    def test_export_config_reads_the_bundle_password_from_stdin(self, monkeypatch, tmp_config_dir):
        import io
        from dbqm.cli import cmd_export_config
        from argparse import Namespace

        monkeypatch.setattr("sys.stdin", io.StringIO("bundle-pw\n"))
        captured = {}

        def _fake_export(password, **kwargs):
            captured["password"] = password
            return "C:/tmp/bundle.dbqm"

        monkeypatch.setattr("dbqm.cli.deps.export_configs", _fake_export)
        cmd_export_config(Namespace(
            password=None, password_stdin=True,
            no_connections=False, no_queries=False, no_groups=False,
            format="table",
        ))
        assert captured["password"] == "bundle-pw"

    def test_export_config_uses_the_bundle_env_var(self, monkeypatch, tmp_config_dir):
        from dbqm.cli import cmd_export_config
        from argparse import Namespace

        monkeypatch.setenv("DBQM_BUNDLE_PASSWORD", "env-pw")
        captured = {}

        def _fake_export(password, **kwargs):
            captured["password"] = password
            return "C:/tmp/bundle.dbqm"

        monkeypatch.setattr("dbqm.cli.deps.export_configs", _fake_export)
        cmd_export_config(Namespace(
            password=None, password_stdin=False,
            no_connections=False, no_queries=False, no_groups=False,
            format="table",
        ))
        assert captured["password"] == "env-pw"

    def test_export_config_without_a_tty_and_without_a_source_aborts_before_writing(self, monkeypatch, tmp_config_dir):
        from dbqm.cli import run_cli

        monkeypatch.delenv("DBQM_BUNDLE_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        spy = MagicMock()
        monkeypatch.setattr("dbqm.cli.deps.export_configs", spy)

        with pytest.raises(SystemExit) as exc:
            run_cli(["export-config"])
        assert exc.value.code == 2
        spy.assert_not_called()

    def test_import_config_without_a_tty_and_without_a_source_aborts_before_reading(self, monkeypatch, tmp_config_dir):
        from dbqm.cli import run_cli

        monkeypatch.delenv("DBQM_BUNDLE_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        spy = MagicMock()
        monkeypatch.setattr("dbqm.cli.deps.import_configs", spy)

        with pytest.raises(SystemExit) as exc:
            run_cli(["import-config", "file.dbqm"])
        assert exc.value.code == 2
        spy.assert_not_called()


class TestConnectionAdd:
    def _run(self, argv, monkeypatch, stdin_text=None):
        import io
        from dbqm.cli import run_cli

        if stdin_text is not None:
            monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
        return run_cli(argv)

    def test_creates_a_mysql_connection(self, tmp_config_dir, monkeypatch):
        from dbqm.core.crypto import decrypt
        from dbqm.models.connection import find_connection

        self._run([
            "connection", "add", "local", "--type", "mysql",
            "--host", "127.0.0.1", "--user", "root", "--password-stdin",
        ], monkeypatch, stdin_text="pw\n")

        conn = find_connection("local")
        assert conn is not None
        assert conn.db_type == "mysql"
        assert conn.host == "127.0.0.1"
        assert conn.port == 3306, "the engine default port must be applied"
        assert decrypt(conn.password) == "pw"

    def test_creates_an_oracle_tns_connection(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import find_connection

        self._run([
            "connection", "add", "tnsconn", "--type", "oracle", "--mode", "tns",
            "--tns-path", "C:/tns", "--tns-name", "ORCL",
            "--user", "sys", "--password-stdin",
        ], monkeypatch, stdin_text="pw\n")

        conn = find_connection("tnsconn")
        assert conn.tns_name == "ORCL"
        assert conn.host is None, "TNS mode must not persist a host"

    def test_no_password_creates_without_one(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import find_connection

        self._run([
            "connection", "add", "sem", "--type", "mysql", "--no-password",
        ], monkeypatch)
        assert find_connection("sem").password == ""

    def test_password_from_the_environment(self, tmp_config_dir, monkeypatch):
        from dbqm.core.crypto import decrypt
        from dbqm.models.connection import find_connection

        monkeypatch.setenv("DBQM_PASSWORD", "env-pw")
        self._run(["connection", "add", "env", "--type", "mysql"], monkeypatch)
        assert decrypt(find_connection("env").password) == "env-pw"

    def test_duplicate_name_exits_2_and_changes_nothing(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import find_connection

        self._run([
            "connection", "add", "dup", "--type", "mysql", "--host", "a",
            "--no-password",
        ], monkeypatch)
        with pytest.raises(SystemExit) as exc:
            self._run([
                "connection", "add", "dup", "--type", "oracle", "--no-password",
            ], monkeypatch)
        assert exc.value.code == 2
        assert find_connection("dup").db_type == "mysql"

    def test_invalid_db_type_exits_2_with_the_dbqm_message(self, tmp_config_dir,
                                                           monkeypatch, capsys):
        with pytest.raises(SystemExit) as exc:
            self._run([
                "connection", "add", "x", "--type", "sqlite", "--no-password",
            ], monkeypatch)
        assert exc.value.code == 2
        assert "Tipo de banco invalido" in capsys.readouterr().out

    def test_missing_db_type_exits_2(self, tmp_config_dir, monkeypatch):
        with pytest.raises(SystemExit) as exc:
            self._run(["connection", "add", "x", "--no-password"], monkeypatch)
        assert exc.value.code == 2

    def test_no_password_source_without_a_tty_exits_2(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import load_connections

        monkeypatch.delenv("DBQM_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        with pytest.raises(SystemExit) as exc:
            self._run(["connection", "add", "x", "--type", "mysql"], monkeypatch)
        assert exc.value.code == 2
        assert load_connections() == []

    def test_failing_test_flag_exits_3_and_saves_nothing(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import load_connections

        monkeypatch.setattr("dbqm.cli.deps.test_connection",
                            lambda conn: (False, "ORA-12154: TNS nao resolvido"))
        with pytest.raises(SystemExit) as exc:
            self._run([
                "connection", "add", "x", "--type", "mysql", "--no-password",
                "--test",
            ], monkeypatch)
        assert exc.value.code == 3
        assert load_connections() == [], "a connection that fails --test must not be saved"

    def test_passing_test_flag_saves(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import find_connection

        monkeypatch.setattr("dbqm.cli.deps.test_connection", lambda conn: (True, "OK"))
        self._run([
            "connection", "add", "x", "--type", "mysql", "--no-password", "--test",
        ], monkeypatch)
        assert find_connection("x") is not None

    def test_json_format_reports_the_outcome(self, tmp_config_dir, monkeypatch, capsys):
        self._run([
            "connection", "add", "j", "--type", "mysql", "--no-password",
            "-f", "json",
        ], monkeypatch)
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["command"] == "connection.add"
        assert corpo["data"] == {"name": "j", "created": True}

    def test_bare_connection_command_exits_2(self, tmp_config_dir, monkeypatch):
        with pytest.raises(SystemExit) as exc:
            self._run(["connection"], monkeypatch)
        assert exc.value.code == 2

    def test_bare_connection_command_prints_the_group_help(self, tmp_config_dir,
                                                            monkeypatch, capsys):
        """A bare `dbqm connection` must print the group's own help (Minor 4),
        not a one-line usage reminder."""
        with pytest.raises(SystemExit) as exc:
            self._run(["connection"], monkeypatch)
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "usage:" in out.lower(), "expected argparse's own help, not a one-line reminder"
        assert "Criar uma conexao" in out, \
            "expected each subcommand's own help text, e.g. add's, to be listed"

    def test_empty_password_stdin_exits_2_and_saves_nothing(self, tmp_config_dir, monkeypatch):
        """A closed/empty --password-stdin pipe must be an error, not a
        passwordless connection (Important 2)."""
        from dbqm.models.connection import load_connections

        with pytest.raises(SystemExit) as exc:
            self._run([
                "connection", "add", "p", "--type", "mysql", "--password-stdin",
            ], monkeypatch, stdin_text="")
        assert exc.value.code == 2
        assert load_connections() == [], \
            "an empty stdin read must not create a passwordless connection"

    def test_invalid_type_does_not_prompt_for_a_password(self, tmp_config_dir, monkeypatch):
        """Validation must run before the password is resolved (Minor 6): a
        terminal user must learn about a bad --type before being asked to
        type a secret that turns out not to matter."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def _explode(prompt=""):
            raise AssertionError("must not prompt for a password before validation")

        monkeypatch.setattr("getpass.getpass", _explode)
        with pytest.raises(SystemExit) as exc:
            self._run(["connection", "add", "x", "--type", "bogus"], monkeypatch)
        assert exc.value.code == 2


class TestConnectionUpdate:
    def _seed(self, monkeypatch):
        import io
        from dbqm.cli import run_cli

        monkeypatch.setattr("sys.stdin", io.StringIO("pw\n"))
        run_cli([
            "connection", "add", "alvo", "--type", "oracle", "--mode", "direct",
            "--host", "velho.example.com", "--port", "1521",
            "--service", "VELHO", "--user", "admin", "--password-stdin",
            "--description", "nota original",
        ])

    def test_only_the_given_flag_changes(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        run_cli(["connection", "update", "alvo", "--host", "novo.example.com"])

        conn = find_connection("alvo")
        assert conn.host == "novo.example.com"
        assert conn.service_name == "VELHO", "an unmentioned field must not change"
        assert conn.user == "admin"
        assert conn.description == "nota original"

    def test_the_stored_password_survives(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.core.crypto import decrypt
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        run_cli(["connection", "update", "alvo", "--host", "novo.example.com"])
        assert decrypt(find_connection("alvo").password) == "pw"

    def test_created_at_survives(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        before = find_connection("alvo").created_at
        run_cli(["connection", "update", "alvo", "--host", "novo.example.com"])
        assert find_connection("alvo").created_at == before

    def test_a_new_password_replaces_the_stored_one(self, tmp_config_dir, monkeypatch):
        import io
        from dbqm.cli import run_cli
        from dbqm.core.crypto import decrypt
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("sys.stdin", io.StringIO("nova-pw\n"))
        run_cli(["connection", "update", "alvo", "--password-stdin"])
        assert decrypt(find_connection("alvo").password) == "nova-pw"

    def test_no_password_clears_the_stored_one(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        run_cli(["connection", "update", "alvo", "--no-password"])
        assert find_connection("alvo").password == ""

    def test_update_ignores_the_dbqm_password_env_var(self, tmp_config_dir, monkeypatch):
        """An ambient DBQM_PASSWORD must not silently replace the stored
        password on `update` (Important 1) — only --password-stdin or
        --no-password, said on this command line, may change it."""
        from dbqm.cli import run_cli
        from dbqm.core.crypto import decrypt
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setenv("DBQM_PASSWORD", "leftover-from-an-earlier-add")
        run_cli(["connection", "update", "alvo", "--description", "owner: infra"])

        conn = find_connection("alvo")
        assert decrypt(conn.password) == "pw", \
            "an ambient DBQM_PASSWORD must not overwrite the stored password on update"
        assert conn.description == "owner: infra"

    def test_empty_password_stdin_exits_2_and_keeps_the_stored_password(
        self, tmp_config_dir, monkeypatch
    ):
        """A closed/empty --password-stdin pipe must error, not silently
        clear the stored password (Important 2)."""
        import io
        from dbqm.cli import run_cli
        from dbqm.core.crypto import decrypt
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "update", "alvo", "--password-stdin"])
        assert exc.value.code == 2
        assert decrypt(find_connection("alvo").password) == "pw", \
            "an empty stdin read must not silently clear the stored password"

    def test_switching_to_tns_clears_the_direct_fields(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        run_cli([
            "connection", "update", "alvo", "--mode", "tns",
            "--tns-path", "C:/tns", "--tns-name", "ORCL",
        ])
        conn = find_connection("alvo")
        assert conn.tns_name == "ORCL"
        assert conn.host is None and conn.service_name is None

    def test_unknown_name_exits_2(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "update", "inexistente", "--host", "h"])
        assert exc.value.code == 2

    def test_failing_test_flag_exits_3_and_keeps_the_stored_version(
        self, tmp_config_dir, monkeypatch
    ):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("dbqm.cli.deps.test_connection", lambda conn: (False, "falhou"))
        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "update", "alvo", "--host", "novo", "--test"])
        assert exc.value.code == 3
        assert find_connection("alvo").host == "velho.example.com"

    def test_json_format_reports_the_outcome(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        self._seed(monkeypatch)
        capsys.readouterr()
        run_cli(["connection", "update", "alvo", "--host", "h", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["command"] == "connection.update"
        assert corpo["data"] == {"name": "alvo", "updated": True}


class TestConnectionRemoveAndList:
    def _seed(self, monkeypatch, name="alvo"):
        from dbqm.cli import run_cli

        run_cli(["connection", "add", name, "--type", "mysql", "--host", "h",
                 "--no-password"])

    def test_rm_with_yes_removes(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        run_cli(["connection", "rm", "alvo", "--yes"])
        assert find_connection("alvo") is None

    def test_rm_without_yes_and_without_a_tty_exits_2(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "rm", "alvo"])
        assert exc.value.code == 2
        assert find_connection("alvo") is not None, "a refusal must not remove"

    def test_rm_on_a_tty_asks_and_honours_a_no(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        run_cli(["connection", "rm", "alvo"])
        assert find_connection("alvo") is not None

    def test_rm_on_a_tty_honours_a_yes(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "s")
        run_cli(["connection", "rm", "alvo"])
        assert find_connection("alvo") is None

    def test_rm_unknown_name_exits_2(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "rm", "inexistente", "--yes"])
        assert exc.value.code == 2

    def test_rm_cancel_under_json_format_prints_json(self, tmp_config_dir, monkeypatch, capsys):
        """Cancelling under -f json must still emit valid JSON on stdout
        (Minor 5), since this path exists for scripted/agent use."""
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        capsys.readouterr()
        run_cli(["connection", "rm", "alvo", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["command"] == "connection.rm"
        assert corpo["data"] == {"name": "alvo", "removed": False}
        assert find_connection("alvo") is not None

    def test_rm_json_format_reports_the_outcome(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        self._seed(monkeypatch)
        capsys.readouterr()
        run_cli(["connection", "rm", "alvo", "--yes", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["command"] == "connection.rm"
        assert corpo["data"] == {"name": "alvo", "removed": True}

    def test_list_matches_list_connections(self, tmp_config_dir, monkeypatch, capsys):
        """`connection list` and `list connections` both speak the envelope
        now (Task 6 migrated the latter), so their arrays match directly."""
        from dbqm.cli import run_cli

        self._seed(monkeypatch, "a")
        self._seed(monkeypatch, "b")

        capsys.readouterr()
        run_cli(["connection", "list", "-f", "json"])
        via_group = json.loads(capsys.readouterr().out)
        assert via_group["ok"] is True
        assert via_group["command"] == "connection.list"

        run_cli(["list", "connections", "-f", "json"])
        via_list = json.loads(capsys.readouterr().out)
        assert via_list["command"] == "list.connections"

        assert via_group["data"] == via_list["data"]
        assert [item["name"] for item in via_group["data"]] == ["a", "b"]


class TestConnectionShow:
    def test_show_redacts_the_password(self, tmp_config_dir, monkeypatch, capsys):
        import io
        from dbqm.cli import run_cli

        monkeypatch.setattr("sys.stdin", io.StringIO("s3cret\n"))
        run_cli(["connection", "add", "alvo", "--type", "mysql", "--host", "h",
                 "--user", "u", "--password-stdin"])

        capsys.readouterr()
        run_cli(["connection", "show", "alvo", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        data = corpo["data"]

        assert data["password"] == "***"
        assert "s3cret" not in json.dumps(corpo)
        assert data["host"] == "h"

    def test_show_reports_an_empty_password_as_empty(self, tmp_config_dir,
                                                     monkeypatch, capsys):
        from dbqm.cli import run_cli

        run_cli(["connection", "add", "sem", "--type", "mysql", "--no-password"])
        capsys.readouterr()
        run_cli(["connection", "show", "sem", "-f", "json"])
        assert json.loads(capsys.readouterr().out)["data"]["password"] == ""

    def test_show_unknown_name_exits_2(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "show", "inexistente"])
        assert exc.value.code == 2


class TestConnectionMarkupSafety:
    """User-supplied values must never be interpreted as Rich markup
    (Minor 3) — a bad value must exit 2 cleanly and stay visible in the
    error message, not crash with a MarkupError or get erased."""

    def test_invalid_type_with_markup_characters_exits_cleanly(self, tmp_config_dir,
                                                                monkeypatch, capsys):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "add", "x", "--type", "[/x]", "--no-password"])
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "[/x]" in out, "the offending value must still be shown, not swallowed by markup"

    def test_show_unknown_name_with_markup_characters_exits_cleanly(self, tmp_config_dir,
                                                                     monkeypatch):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "show", "[/x]"])
        assert exc.value.code == 2

    def test_connection_name_with_markup_characters_round_trips(self, tmp_config_dir,
                                                                 monkeypatch, capsys):
        """add -> outcome message -> table show -> table list, none of which
        may raise a rich.errors.MarkupError for a name like `[/x]`."""
        from dbqm.cli import run_cli

        run_cli(["connection", "add", "[/x]", "--type", "mysql", "--no-password"])
        run_cli(["connection", "show", "[/x]"])
        run_cli(["connection", "list"])


class TestEmptyStdinHint:
    """P4 — the hint must name a flag the command actually has."""

    def _args(self, **kw):
        from argparse import Namespace

        base = {"password_stdin": True, "password": None}
        base.update(kw)
        return Namespace(**base)

    def test_connection_commands_are_pointed_at_no_password(self, monkeypatch, capsys):
        import io

        from dbqm.cli import resolve_password

        monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
        with pytest.raises(SystemExit):
            resolve_password(
                self._args(no_password=False), "DBQM_PASSWORD", "p: ", required=True
            )
        assert "--no-password" in capsys.readouterr().out

    def test_bundle_commands_are_not_pointed_at_a_flag_they_lack(
        self, monkeypatch, capsys
    ):
        """export-config and import-config have no --no-password."""
        import io

        from dbqm.cli import resolve_password

        monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
        with pytest.raises(SystemExit):
            resolve_password(
                self._args(), "DBQM_BUNDLE_PASSWORD", "p: ", required=True
            )
        saida = capsys.readouterr().out
        assert "Senha vazia" in saida
        assert "--no-password" not in saida

    def test_the_real_parsers_agree_with_that_split(self):
        """Derived from the parser, not from a list kept by hand."""
        from dbqm.cli import build_parser

        parser = build_parser()
        args_conn = parser.parse_args(["connection", "add", "x", "--no-password"])
        assert getattr(args_conn, "no_password", None) is not None
        args_bundle = parser.parse_args(["export-config"])
        assert getattr(args_bundle, "no_password", None) is None


class TestConnectionEnvelope:
    """The contract, proved on the group that already spoke JSON."""

    def _seed(self):
        from dbqm.cli import run_cli

        run_cli(["connection", "add", "alvo", "--type", "mysql",
                 "--host", "h", "--no-password"])

    def test_show_wraps_the_connection_in_data(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        self._seed()
        capsys.readouterr()
        run_cli(["connection", "show", "alvo", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)

        assert corpo["ok"] is True
        assert corpo["command"] == "connection.show"
        assert corpo["data"]["name"] == "alvo"
        assert corpo["data"]["password"] == "", "redaction survives the envelope"

    def test_list_wraps_the_array_in_data(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        self._seed()
        capsys.readouterr()
        run_cli(["connection", "list", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["ok"] is True
        assert [c["name"] for c in corpo["data"]] == ["alvo"]

    def test_a_missing_name_leaves_stdout_parseable(self, tmp_config_dir, capsys):
        """The defect this whole sub-project exists for."""
        import json

        import pytest

        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "show", "inexistente", "-f", "json"])
        assert exc.value.code == 2

        saida = capsys.readouterr()
        assert saida.out == "", "stdout must be empty, not prose"
        erro = json.loads(saida.err)
        assert erro["ok"] is False
        assert erro["error"]["code"] == "not_found"

    def test_add_reports_the_outcome_in_the_envelope(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "novo", "--type", "mysql",
                 "--no-password", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["ok"] is True
        assert corpo["command"] == "connection.add"
        assert corpo["data"] == {"name": "novo", "created": True}

    def test_a_failing_test_flag_reports_connection_failed(self, tmp_config_dir, capsys, monkeypatch):
        import json

        import pytest

        from dbqm.cli import run_cli

        monkeypatch.setattr("dbqm.cli.deps.test_connection",
                            lambda conn: (False, "ORA-12154"))
        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "add", "x", "--type", "mysql",
                     "--no-password", "--test", "-f", "json"])
        assert exc.value.code == 3
        erro = json.loads(capsys.readouterr().err)
        assert erro["error"]["code"] == "connection_failed"

    def test_table_format_gets_no_envelope(self, tmp_config_dir, capsys):
        """`table` is for a human; the envelope belongs to `json` alone."""
        from dbqm.cli import run_cli

        self._seed()
        capsys.readouterr()
        run_cli(["connection", "show", "alvo"])
        saida = capsys.readouterr().out
        assert '"ok"' not in saida
        assert "alvo" in saida


class TestEveryCommandSpeaksTheEnvelope:
    """One test per command: success is an envelope, failure leaves stdout clean.

    The second assertion is the one that did not exist anywhere before this
    sub-project, and it is the regression that matters — an error on stdout is
    what breaks a consumer.
    """

    def test_test_command_reports_each_connection(self, tmp_config_dir, capsys, monkeypatch):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "c1", "--type", "mysql", "--no-password"])
        monkeypatch.setattr("dbqm.cli.deps.test_connection", lambda conn: (True, "OK"))
        capsys.readouterr()
        run_cli(["test", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["ok"] is True
        assert corpo["command"] == "test"
        assert corpo["data"][0]["name"] == "c1"
        assert corpo["data"][0]["ok"] is True

    def test_list_wraps_its_array(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "c1", "--type", "mysql", "--no-password"])
        capsys.readouterr()
        run_cli(["list", "connections", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["command"] == "list.connections"
        assert [c["name"] for c in corpo["data"]] == ["c1"]

    def test_history_wraps_its_array(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        capsys.readouterr()
        run_cli(["history", "-f", "json"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["ok"] is True
        assert corpo["command"] == "history"
        assert isinstance(corpo["data"], list)

    def test_run_on_a_missing_query_is_not_found(self, tmp_config_dir, capsys):
        import json

        import pytest

        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["run", "nao-existe", "-f", "json"])
        assert exc.value.code == 2
        saida = capsys.readouterr()
        assert saida.out == ""
        assert json.loads(saida.err)["error"]["code"] == "not_found"

    def test_sql_failure_is_a_sql_error(self, tmp_config_dir, capsys, monkeypatch):
        import json

        import pytest

        from dbqm.cli import run_cli
        from dbqm.core.query_engine import AdhocResult

        run_cli(["connection", "add", "c1", "--type", "mysql", "--no-password"])
        monkeypatch.setattr(
            "dbqm.cli.deps.execute_adhoc",
            lambda *a, **k: AdhocResult(sql_type="SELECT", connection_name="c1",
                                        success=False, error="ORA-00942"),
        )
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["sql", "SELECT 1", "c1", "-f", "json"])
        assert exc.value.code == 4
        saida = capsys.readouterr()
        assert saida.out == ""
        erro = json.loads(saida.err)
        assert erro["error"]["code"] == "sql_error"
        assert "ORA-00942" in erro["error"]["message"]

    def test_run_group_missing_group_leaves_stdout_clean(self, tmp_config_dir, capsys):
        import json

        import pytest

        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["run-group", "nao-existe", "-f", "json"])
        assert exc.value.code == 2
        saida = capsys.readouterr()
        assert saida.out == ""
        assert json.loads(saida.err)["error"]["code"] == "not_found"

    def test_a_divergent_group_exits_five(self, tmp_config_dir, capsys, sample_group_result, monkeypatch):
        """RULING: divergence is `ok`, not `fail` — the command did its job
        and the comparison counts are exactly what an agent runs it for, so
        they ride in `data` on stdout; the exit code alone (still 5, still
        under `table` too — see TestCmdRunGroup) is what lets a shell branch
        without parsing. Behaviour change either way: run-group exited 0
        before this task whether it matched or not."""
        import json

        import pytest

        from dbqm.cli import run_cli

        # sample_group_result has all_match False (see tests/conftest.py)
        monkeypatch.setattr("dbqm.cli.deps.build_group_result",
                            lambda *a, **k: sample_group_result)
        monkeypatch.setattr("dbqm.cli.deps.find_group", lambda n: _make_group())
        monkeypatch.setattr("dbqm.cli.deps.find_query", lambda n: _make_query())
        monkeypatch.setattr("dbqm.cli.deps.find_connection", lambda n: _make_connection())
        monkeypatch.setattr("dbqm.cli.deps.execute_query",
                            lambda *a, **k: _make_query_result())
        monkeypatch.setattr("dbqm.cli.deps.record_group_execution", lambda *a, **k: None)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["run-group", "test_group", "-f", "json"])
        assert exc.value.code == 5
        saida = capsys.readouterr()
        assert saida.err == "", "divergence is ok(), not fail() — nothing on stderr"
        corpo = json.loads(saida.out)
        assert corpo["ok"] is True
        assert corpo["command"] == "run-group"
        assert corpo["data"]["all_match"] is False
        assert corpo["data"]["comparisons"][0]["column"] == "status"

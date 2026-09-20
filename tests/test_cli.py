"""Tests for the CLI module — argument parsing and command execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock

from dbqm.cli import build_parser, run_cli, _parse_params, COMMAND_MAP
from dbqm.core.query_engine import AdhocResult, QueryResult
from dbqm.core.group_engine import GroupResult, ComparisonResult, ComparisonRow
from dbqm.core.ddl_extractor import ExtractionResult, ExtractedObject
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


def _make_query_result(success=True, rows=None, columns=None, error="", error_kind=""):
    return QueryResult(
        query_name="test_query",
        connection_name="test_conn",
        columns=columns or ["id", "name"],
        rows=rows if rows is not None else [[1, "Alice"], [2, "Bob"]],
        row_count=len(rows) if rows is not None else 2,
        elapsed=0.05,
        success=success,
        error=error or ("" if success else "some error"),
        error_kind=error_kind,
    )


def _make_adhoc_result(success=True, error="", error_kind=""):
    return AdhocResult(
        sql_type="DELETE",
        connection_name="test_conn",
        sql="DELETE FROM t",
        rows_affected=1,
        success=success,
        error=error,
        error_kind=error_kind,
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


def _make_extraction():
    """Create a real ExtractionResult with the actual dataclass structure."""
    return ExtractionResult(
        object_name="MY_TABLE",
        object_type="TABLE",
        owner="TEST_OWNER",
        connection_name="test_conn",
        objects=[
            ExtractedObject(
                name="MY_TABLE",
                obj_type="TABLE",
                ddl="CREATE TABLE TEST_OWNER.MY_TABLE (id NUMBER PRIMARY KEY);",
            ),
        ],
        dependencies=[],
        errors=[],
        saved_files=[],
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_parser_creates_all_subcommands(self):
        parser = build_parser()
        # Verify parser was built (no exception)
        assert parser.prog == "dbqm"

    def test_every_parser_command_has_a_handler(self):
        """The parser is the source, not a list typed into this file.

        The typed set this replaces was edited four times in one
        sub-project and proved nothing the parser could not answer for
        itself: a name in `COMMAND_MAP` with no subparser is a command
        nobody can reach, and a subparser with no handler is a command that
        parses and then does nothing. `TestCmdDescribeCli` proves the same
        equality through the described output; this one asks the parser
        directly, without running a command.
        """
        parser = build_parser()
        actions = [
            a for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
        ]
        assert len(actions) == 1, "the parser grew a second subparser group"
        assert set(actions[0].choices) == set(COMMAND_MAP)


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
        with patch("dbqm.ops.deps.find_query", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run", "missing_query"])

    def test_run_connection_not_found(self):
        query = _make_query()
        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_missing_params(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="")])
        conn = _make_connection()
        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_uses_param_defaults(self):
        query = _make_query(params=[QueryParam(name="id", description="", default="42")])
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result) as mock_exec, \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"), \
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

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result) as mock_exec, \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"), \
             patch("dbqm.cli.render._print_query_result") as mock_print:
            run_cli(["run", "test_query", "-p", "id=99"])
            call_params = mock_exec.call_args[0][2]
            assert call_params["id"] == "99"
            mock_print.assert_called_once()

    def test_run_with_connection_override(self):
        query = _make_query()
        conn = _make_connection("other_conn")
        result = _make_query_result()

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn) as mock_find_conn, \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"), \
             patch("dbqm.cli.render._print_query_result") as mock_print:
            run_cli(["run", "test_query", "-c", "other_conn"])
            mock_find_conn.assert_called_with("other_conn")
            mock_print.assert_called_once()

    def test_run_failed_query_exits(self):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result(success=False)

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"):
            with pytest.raises(SystemExit):
                run_cli(["run", "test_query"])

    def test_run_export_csv(self, tmp_config_dir):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"), \
             patch("dbqm.ops.deps.export_query_csv", return_value="/tmp/out.csv") as mock_exp:
            run_cli(["run", "test_query", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_run_export_html(self, tmp_config_dir):
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"), \
             patch("dbqm.ops.deps.export_query_html", return_value="/tmp/out.html") as mock_exp:
            run_cli(["run", "test_query", "-e", "html"])
            mock_exp.assert_called_once()

    def test_run_format_json(self, capsys):
        """`data` is `QueryResult.to_dict()` verbatim: `rows` are parallel
        arrays (a list per row, indexed by `columns`), not a dict per row —
        a dict per row silently drops a repeated column name."""
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"):
            run_cli(["run", "test_query", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "run"
            assert body["data"]["row_count"] == 2
            assert body["data"]["columns"] == ["id", "name"]
            assert body["data"]["rows"] == [[1, "Alice"], [2, "Bob"]]
            assert body["data"]["query_name"] == "test_query"
            assert body["data"]["connection_name"] == "test_conn"

    def test_run_format_json_keeps_a_repeated_column(self, capsys):
        """The bug the parallel-array shape fixes: `SELECT a.id, b.id FROM
        a JOIN b` repeats a column name. `dict(zip(columns, row))` silently
        drops one of the two `id` values; parallel arrays keep both."""
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result(columns=["id", "id"], rows=[[1, 99]])

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"):
            run_cli(["run", "test_query", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["data"]["columns"] == ["id", "id"]
            assert body["data"]["rows"] == [[1, 99]]

    def test_run_export_json_format_emits_envelope(self, capsys):
        """CRITICAL fix: `-e` used to print bare prose and return under
        `-f json`, exiting 0 with no envelope on stdout at all."""
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result()

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"), \
             patch("dbqm.ops.deps.export_query_csv", return_value="/tmp/out.csv"):
            run_cli(["run", "test_query", "-e", "csv", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "run"
            assert body["data"] == {"exported": "/tmp/out.csv", "format": "csv"}

    def test_run_failed_query_table_format_exits_via_fail_or_print(self):
        """IMPORTANT fix: `table`/`csv`/`raw` used to fall through to
        `render._print_query_result`'s own bare `exit(1)` instead of
        `_fail_or_print`'s mapped exit code."""
        query = _make_query()
        conn = _make_connection()
        result = _make_query_result(success=False)

        with patch("dbqm.ops.deps.find_query", return_value=query), \
             patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_query", return_value=result), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"):
            with pytest.raises(SystemExit) as exc:
                run_cli(["run", "test_query"])
            assert exc.value.code == 4


# ---------------------------------------------------------------------------
# run-group subcommand
# ---------------------------------------------------------------------------

class TestCmdRunGroup:
    """Every test here isolates the config paths, whether or not it thinks
    it needs to.

    The class relies entirely on per-test `patch("dbqm.ops.deps.X")`. During
    the html-export sub-project a deliberate mutation left
    `record_group_execution` unpatched and the test wrote a junk entry into
    the developer's real `~/.dbqm/config/history/history.json`. Nothing is
    known broken today; the exposure is structural, so the fix belongs to
    the class rather than to whoever remembers to ask for the fixture.
    """

    @pytest.fixture(autouse=True)
    def _isolate_config(self, tmp_config_dir):
        return tmp_config_dir

    def test_group_not_found(self):
        with patch("dbqm.ops.deps.find_group", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["run-group", "missing"])

    def test_group_query_not_found(self):
        group = _make_group()
        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", return_value=None):
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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"):
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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"):
            run_cli(["run-group", "test_group", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "run-group"
            assert body["data"]["all_match"] is True

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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"), \
             patch("dbqm.ops.deps.export_group_csv", return_value="/tmp/g.csv") as mock_exp:
            run_cli(["run-group", "test_group", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_group_export_html(self):
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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"), \
             patch("dbqm.ops.deps.export_group_html", return_value="/tmp/g.html") as mock_exp:
            run_cli(["run-group", "test_group", "-e", "html"])
            mock_exp.assert_called_once()

    def test_group_flat_html_is_refused_table_format(self, capsys):
        """The trap: `--flat` is a CSV-shaped denormalisation with no HTML
        equivalent. Silently ignoring the flag would hand back a different
        shape (the non-flat report) with no signal that `--flat` was
        dropped. Checked under `table` too, not just `json`: a refusal that
        only fires under one renderer is the bug class 2.3.0 existed to
        fix.

        The refusal fires before the group is even resolved (a bad argument
        combination costs no work), so `find_group` is mocked but must never
        be called -- that is also what proves this test is pinned to *this*
        refusal and not to the flat arm's generic bare-`else` fallback,
        which would also exit 2 with no export call but only after
        resolving the group and running every query in it.
        """
        with patch("dbqm.ops.deps.find_group") as mock_find_group, \
             patch("dbqm.ops.deps.export_group_flat_csv") as mock_flat_csv, \
             patch("dbqm.ops.deps.export_group_flat_json") as mock_flat_json, \
             patch("dbqm.ops.deps.export_group_flat_txt") as mock_flat_txt:
            with pytest.raises(SystemExit) as excinfo:
                run_cli(["run-group", "test_group", "--flat", "-e", "html"])
            assert excinfo.value.code == 2
            output = capsys.readouterr().out
            assert "--flat" in output, "must name the refused flag, not just exit 2"
            assert "Exportado:" not in output, "no export must have happened"
            mock_find_group.assert_not_called()
            mock_flat_csv.assert_not_called()
            mock_flat_json.assert_not_called()
            mock_flat_txt.assert_not_called()

    def test_group_flat_html_is_refused_json_format(self, capsys):
        """Same refusal, `-f json` side: the contract is that stdout stays
        empty and the failure carries the usage token on stderr. Also fires
        before the group is resolved -- see the table-format sibling above
        for why `find_group` must stay uncalled."""
        with patch("dbqm.ops.deps.find_group") as mock_find_group, \
             patch("dbqm.ops.deps.export_group_flat_csv") as mock_flat_csv, \
             patch("dbqm.ops.deps.export_group_flat_json") as mock_flat_json, \
             patch("dbqm.ops.deps.export_group_flat_txt") as mock_flat_txt:
            with pytest.raises(SystemExit) as excinfo:
                run_cli(["run-group", "test_group", "--flat", "-e", "html", "-f", "json"])
            assert excinfo.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "usage"
            assert "--flat" in body["error"]["message"]
            assert "html" in body["error"]["message"]
            mock_find_group.assert_not_called()
            mock_flat_csv.assert_not_called()
            mock_flat_json.assert_not_called()
            mock_flat_txt.assert_not_called()

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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"), \
             patch("dbqm.ops.deps.export_group_csv", return_value="/tmp/g.csv"):
            run_cli(["run-group", "test_group", "-e", "csv", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "run-group"
            assert body["data"] == {"exported": "/tmp/g.csv", "format": "csv"}

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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"), \
             patch("dbqm.ops.deps.export_group_csv", return_value="/tmp/g.csv"):
            with pytest.raises(SystemExit) as exc:
                run_cli(["run-group", "test_group", "-e", "csv", "-f", "json"])
            assert exc.value.code == 5
            body = json.loads(capsys.readouterr().out)
            assert body["data"] == {"exported": "/tmp/g.csv", "format": "csv"}

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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"), \
             patch("dbqm.ops.deps.export_group_csv", return_value="/tmp/g.csv") as mock_exp:
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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"):
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

        with patch("dbqm.ops.deps.find_group", return_value=group), \
             patch("dbqm.ops.deps.find_query", side_effect=find_query_side), \
             patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_query", return_value=_make_query_result()), \
             patch("dbqm.ops.deps.build_group_result", return_value=gr), \
             patch("dbqm.ops.deps.record_group_execution"):
            with pytest.raises(SystemExit) as exc:
                run_cli(["run-group", "test_group"])
            assert exc.value.code == 5

    def test_multi_and_run_group_export_through_the_same_helper(self):
        """Two commands, one export path. A second implementation is how two
        commands start disagreeing about what --flat means.

        This test is deliberately structural: it does not exercise any
        behaviour (the export tests above already do that). It asserts that
        `cmd_run_group` delegates to `_export_group` instead of naming the
        exporters itself, and that `cmd_multi` shares the same helper rather
        than growing a second copy of the branch.
        """
        from dbqm.cli.commands import query as q
        import inspect

        # `cmd_run_group` runs both shapes -- saved queries and ad-hoc --
        # through `dbqm.ops.compare.run_group`, and reports the single
        # `Comparison` it gets back through `_report_group_result`, which is
        # where the export lives. Two hops, still one path.
        tail = inspect.getsource(q.cmd_run_group)
        assert "_report_group_result(" in tail
        assert "export_group_flat_csv" not in tail
        source = inspect.getsource(q._report_group_result)
        assert "_export_group(" in source
        assert "export_group_flat_csv" not in source

        # `cmd_multi` reports its own `Comparison` from
        # `dbqm.ops.compare.multi` through the same `_export_group` helper,
        # not a copy of the branch.
        multi_source = inspect.getsource(q.cmd_multi)
        assert "_export_group(" in multi_source
        assert "export_group_flat_csv" not in multi_source


# ---------------------------------------------------------------------------
# multi subcommand
# ---------------------------------------------------------------------------

def _make_multi_result(name, columns=None, rows=None, success=True, error="", error_kind=""):
    return AdhocResult(
        sql_type="SELECT",
        connection_name=name,
        columns=columns if columns is not None else ["ID", "NAME"],
        rows=rows if rows is not None else [[1, "Alice"]],
        row_count=1 if rows is None else len(rows),
        success=success,
        error=error,
        error_kind=error_kind,
    )


class TestCmdMulti:
    def test_two_connections_that_agree_exit_zero(self, tmp_config_dir):
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1"),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side) as mock_find, \
             patch("dbqm.ops.deps.execute_across", return_value=results) as mock_exec:
            run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2"])  # must not raise
            mock_exec.assert_called_once()
            assert mock_find.call_count == 2

    def test_two_connections_that_differ_exit_five(self, tmp_config_dir):
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", rows=[[1, "Alice"]]),
            "c2": _make_multi_result("c2", rows=[[1, "Bob"]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2"])
            assert exc.value.code == 5

    def test_one_connection_is_a_usage_error(self, tmp_config_dir, capsys):
        """Comparing one result against nothing is not a comparison."""
        with patch("dbqm.ops.deps.find_connection") as mock_find, \
             patch("dbqm.ops.deps.execute_across") as mock_exec:
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-f", "json"])
            assert exc.value.code == 2
            mock_find.assert_not_called()
            mock_exec.assert_not_called()
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "usage"

    def test_an_unknown_connection_is_not_found(self, tmp_config_dir, capsys):
        c1 = _make_connection("c1")

        def find_conn_side(name):
            return {"c1": c1}.get(name)

        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across") as mock_exec:
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "ghost"])
            assert exc.value.code == 2
            mock_exec.assert_not_called()
            output = capsys.readouterr().out
            assert "ghost" in output

    def test_a_dead_connection_stops_the_command(self, tmp_config_dir, capsys):
        """error_kind 'connection' maps to 3, and the message must name which
        connection failed -- one 'Could not connect' across three databases costs a
        human a second run to interpret."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result(
                "c1", success=False, error="ORA-12541: TNS:no listener",
                error_kind="connection",
            ),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2"])
            assert exc.value.code == 3
            output = capsys.readouterr().out
            assert "c1" in output

    def test_a_rejected_statement_exits_four(self, tmp_config_dir, capsys):
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result(
                "c1", success=False, error="ORA-00904: invalid identifier",
                error_kind="statement",
            ),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2"])
            assert exc.value.code == 4
            output = capsys.readouterr().out
            assert "c1" in output

    def test_a_read_only_refusal_exits_two_not_three(self, tmp_config_dir, capsys):
        """`execute_across` tags a `ReadOnlyViolation` `error_kind="read_only"`
        (core/group_engine.py). `cmd_sql` reports the identical condition as
        `read_only`/exit 2 -- the two commands must not disagree about what
        the same event is, so this must not fall through to
        `connection_failed` (3) just because the guard raised before any
        driver call."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result(
                "c1", success=False,
                error="Connection 'c1' is read-only. Use --force-write to send it anyway.",
                error_kind="read_only",
            ),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "read_only"
            assert "c1" in body["error"]["message"]

    def test_nothing_is_exported_when_a_connection_failed(self, tmp_config_dir):
        """-e given, a connection down: no exporter is called."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result(
                "c1", success=False, error="host unreachable", error_kind="connection",
            ),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results), \
             patch("dbqm.ops.deps.export_group_csv") as mock_csv, \
             patch("dbqm.ops.deps.export_group_json") as mock_json, \
             patch("dbqm.ops.deps.export_group_txt") as mock_txt, \
             patch("dbqm.ops.deps.export_group_html") as mock_html:
            with pytest.raises(SystemExit):
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-e", "csv"])
            mock_csv.assert_not_called()
            mock_json.assert_not_called()
            mock_txt.assert_not_called()
            mock_html.assert_not_called()

    def test_no_common_columns_is_a_validation_error(self, tmp_config_dir, capsys):
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["A"], rows=[[1]]),
            "c2": _make_multi_result("c2", columns=["B"], rows=[[1]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"

    def test_key_not_a_common_column_is_a_validation_error(self, tmp_config_dir, capsys):
        """`--key FOO` where FOO is not one of the columns common to every
        result is the same class of silent wrong answer as comparing zero
        columns: `run_comparison` would index FOO to `None` in every result,
        every key set would come back empty, and `all([])` is `True` over
        rows that were never actually looked at."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
            "c2": _make_multi_result("c2", columns=["ID", "NAME"], rows=[[2, "Bob"]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "--key", "FOO", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"
            assert "FOO" in body["error"]["message"]

    def test_only_a_key_and_nothing_to_compare_is_a_validation_error_without_key(
        self, tmp_config_dir, capsys,
    ):
        """Reachable without `--key`: when the only column common to every
        result is the derived join key, `derive_comparison_columns` returns
        `(key, [])` on purpose (core allows this) -- but `cmd_multi` running
        a comparison of zero columns over genuinely divergent rows would
        still say CONSISTENT. `cmd_multi` refuses it instead of core."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["ID"], rows=[[1]]),
            "c2": _make_multi_result("c2", columns=["ID"], rows=[[2]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"

    def test_only_a_key_and_nothing_to_compare_is_a_validation_error_with_key(
        self, tmp_config_dir, capsys,
    ):
        """Same trap, reached via `--key` naming the only common column."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
            "c2": _make_multi_result("c2", columns=["ID"], rows=[[2]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "--key", "ID", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"

    def test_the_join_key_is_reported(self, tmp_config_dir, capsys):
        """A derived key the caller cannot see is a number produced by a rule
        they are guessing at."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
            "c2": _make_multi_result("c2", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["data"]["join_key"] == "ID"

    def test_key_overrides_the_derived_join_key(self, tmp_config_dir, capsys):
        """Not just that the reported key changes: passing `--key` must not
        drop the comparison. `join_key=args.key or ""` with no
        `compare_columns` makes `build_adhoc_group_result` default to an
        empty compare list, so genuinely divergent rows (same NAME, different
        ID) would compare zero columns and report CONSISTENT/exit 0 -- a
        silent wrong answer. Keying by NAME must still compare ID and catch
        the divergence."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
            "c2": _make_multi_result("c2", columns=["ID", "NAME"], rows=[[2, "Alice"]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "--key", "NAME", "-f", "json"])
            assert exc.value.code == 5
            body = json.loads(capsys.readouterr().out)
            assert body["data"]["join_key"] == "NAME"
            assert body["data"]["comparisons"], "the ID column must actually have been compared"
            assert body["data"]["all_match"] is False

    def test_export_reaches_the_exporter_and_prints_the_result(self, tmp_config_dir, capsys):
        """`test_nothing_is_exported_when_a_connection_failed` only proves the
        failure path skips the exporter; this proves the success path
        actually reaches `_export_group` and reports what it did."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1"),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results), \
             patch("dbqm.ops.deps.export_group_csv", return_value="/tmp/multi.csv") as mock_csv:
            run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-e", "csv"])
            mock_csv.assert_called_once()
            output = capsys.readouterr().out
            assert "Exported:" in output
            assert "/tmp/multi.csv" in output

    def test_export_json_format_emits_envelope(self, tmp_config_dir, capsys):
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1"),
            "c2": _make_multi_result("c2"),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results), \
             patch("dbqm.ops.deps.export_group_csv", return_value="/tmp/multi.csv") as mock_csv:
            run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-e", "csv", "-f", "json"])
            mock_csv.assert_called_once()
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["data"]["exported"] == "/tmp/multi.csv"

    def test_the_table_header_shows_the_join_key(self, tmp_config_dir, capsys):
        """Half of the join-key requirement -- `-f json`'s `data["join_key"]`
        -- is covered by `test_the_join_key_is_reported`. The other half is
        the same fact in the renderer a human actually reads."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        results = {
            "c1": _make_multi_result("c1", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
            "c2": _make_multi_result("c2", columns=["ID", "NAME"], rows=[[1, "Alice"]]),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2"])
            output = capsys.readouterr().out
            assert "key: ID" in output

    def test_multiple_failures_report_every_connection_deterministically(self, tmp_config_dir, capsys):
        """The exit code must not depend on which failing connection happens
        to be listed (or run) first: a connection failure outranks a
        statement failure regardless of order, and every failing connection
        is named, not just one.

        Runs the *same* failing state twice, with the two failures in
        opposite positions of `results`' iteration order. Checking only one
        order kills a `return codes[-1]` mutant (the connection failure
        happens to be last there) but lets it slip past the other order,
        where the connection failure is first and the statement failure is
        last -- a `codes[-1]`-shaped bug would report `sql_error`/4 there.
        Both orders must report `connection_failed`/3 and name both
        connections, which is the claim `compare.multi_failure_code`'s
        docstring actually makes.
        """
        c1, c2, c3 = _make_connection("c1"), _make_connection("c2"), _make_connection("c3")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2, "c3": c3}.get(name)

        statement_failure = _make_multi_result(
            "c1", success=False, error="ORA-00904: invalid identifier",
            error_kind="statement",
        )
        connection_failure = _make_multi_result(
            "c2", success=False, error="host unreachable", error_kind="connection",
        )
        success = _make_multi_result("c3")

        orderings = [
            {"c1": statement_failure, "c2": connection_failure, "c3": success},
            {"c2": connection_failure, "c1": statement_failure, "c3": success},
        ]
        for results in orderings:
            with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
                 patch("dbqm.ops.deps.execute_across", return_value=results):
                with pytest.raises(SystemExit) as exc:
                    run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2", "-c", "c3"])
                assert exc.value.code == 3, f"order {list(results)} must still exit 3"
                output = capsys.readouterr().out
                assert "c1" in output
                assert "c2" in output

    def test_a_statement_never_sent_is_a_usage_error_not_sql_error(self, tmp_config_dir, capsys):
        """`_sql_error_code` remaps the known 'never reached the driver'
        messages to `usage`. The hand-rolled connection/sql_error dichotomy
        this used to have mislabels this as `sql_error` (exit 4) -- claiming
        the driver rejected a statement that was never sent to it."""
        c1, c2 = _make_connection("c1"), _make_connection("c2")

        def find_conn_side(name):
            return {"c1": c1, "c2": c2}.get(name)

        from dbqm.i18n import t

        message = t("sql.unsupported_type")
        results = {
            "c1": _make_multi_result("c1", success=False, error=message, error_kind=""),
            "c2": _make_multi_result("c2", success=False, error=message, error_kind=""),
        }
        with patch("dbqm.ops.deps.find_connection", side_effect=find_conn_side), \
             patch("dbqm.ops.deps.execute_across", return_value=results):
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "NOT REALLY SQL", "-c", "c1", "-c", "c2", "-f", "json"])
            assert exc.value.code == 2
            body = json.loads(capsys.readouterr().err)
            assert body["error"]["code"] == "usage"

    def test_flat_with_html_is_refused_before_any_connection_opens(self, tmp_config_dir, capsys):
        """exit 2, and execute_across never called."""
        with patch("dbqm.ops.deps.find_connection") as mock_find, \
             patch("dbqm.ops.deps.execute_across") as mock_exec:
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "c1", "-c", "c2",
                         "--flat", "-e", "html", "-f", "json"])
            assert exc.value.code == 2
            mock_find.assert_not_called()
            mock_exec.assert_not_called()
        # Without the token this is indistinguishable from argparse
        # rejecting an argument, which also exits 2.
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert "--flat" in body["error"]["message"]

    @pytest.mark.parametrize("sql", [
        "DELETE FROM t",
        "DROP TABLE t",
        "BEGIN NULL; END;",
    ])
    def test_non_query_sql_is_refused_before_any_connection_opens(self, tmp_config_dir, capsys, sql):
        """A comparison has no result set to compare when the statement
        never returns one. `multi` has no `--commit` gate the way `cmd_sql`
        does -- there is no sense in which comparing DML/DDL/PL/SQL output
        could ever be meaningful, so it refuses outright, before a single
        connection is even resolved (never mind opened)."""
        with patch("dbqm.ops.deps.find_connection") as mock_find, \
             patch("dbqm.ops.deps.execute_across") as mock_exec:
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", sql, "-c", "c1", "-c", "c2", "-f", "json"])
            assert exc.value.code == 2
            mock_find.assert_not_called()
            mock_exec.assert_not_called()
        # Exit 2 is also argparse's own code for a bad argument, so the code
        # alone cannot tell this refusal from one we never wrote.
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "usage"

    def test_duplicate_connection_is_a_usage_error(self, tmp_config_dir, capsys):
        """`-c prod -c prod` passes the `len(names) >= 2` check but collapses
        to one entry once `execute_across` keys its result dict by
        connection name -- a comparison over a single result can only ever
        report OK. Refused before either connection is resolved."""
        with patch("dbqm.ops.deps.find_connection") as mock_find, \
             patch("dbqm.ops.deps.execute_across") as mock_exec:
            with pytest.raises(SystemExit) as exc:
                run_cli(["multi", "SELECT 1", "-c", "prod", "-c", "prod", "-f", "json"])
            assert exc.value.code == 2
            mock_find.assert_not_called()
            mock_exec.assert_not_called()
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "usage"
            assert "prod" in body["error"]["message"]


# ---------------------------------------------------------------------------
# sql subcommand
# ---------------------------------------------------------------------------

class TestCmdSql:
    def test_sql_connection_not_found(self):
        with patch("dbqm.ops.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["sql", "SELECT 1", "missing_conn"])

    def test_sql_select(self, capsys):
        """`data` is `AdhocResult.to_dict()` verbatim: `rows` are parallel
        arrays, and the executed text travels under the unambiguous `sql`
        key — not a `"query"` key that also means the saved-query *name*
        elsewhere in this same file."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            sql="SELECT 1 FROM dual",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "SELECT 1 FROM dual", "test_conn", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "sql"
            assert body["data"]["row_count"] == 1
            assert body["data"]["rows"] == [[1]]
            assert body["data"]["sql"] == "SELECT 1 FROM dual"
            assert body["data"]["connection_name"] == "test_conn"

    def test_sql_select_keeps_a_repeated_column(self, capsys):
        """The same fix as `run`'s: `SELECT a.id, b.id FROM a JOIN b` is
        ordinary ad-hoc usage, and `dict(zip(columns, row))` used to drop
        one of the two `id` values silently."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["id", "id"], rows=[[1, 99]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "SELECT a.id, b.id FROM a JOIN b", "test_conn", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["data"]["columns"] == ["id", "id"]
            assert body["data"]["rows"] == [[1, 99]]

    def test_sql_dml_autocommit(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UPDATE", connection_name="test_conn",
            rows_affected=3, elapsed=0.01, committed=True,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "UPDATE t SET x=1", "test_conn", "--commit"])

    def test_sql_dml_without_commit_exits(self):
        conn = _make_connection()
        with patch("dbqm.ops.deps.find_connection", return_value=conn):
            with pytest.raises(SystemExit):
                run_cli(["sql", "UPDATE t SET x=1", "test_conn"])

    def test_sql_dml_failed_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UPDATE", connection_name="test_conn",
            rows_affected=0, elapsed=0.01, success=False, error="constraint violation",
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
            with pytest.raises(SystemExit):
                run_cli(["sql", "UPDATE t SET x=1", "test_conn", "--commit"])

    def test_sql_failed_exits(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            success=False, error="syntax error",
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc) as mock_exec:
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc), \
             patch("dbqm.ops.deps.export_query_csv", return_value="/tmp/out.csv") as mock_exp:
            run_cli(["sql", "SELECT 1", "test_conn", "-e", "csv"])
            mock_exp.assert_called_once()

    def test_sql_export_html_does_not_fall_through_to_txt(self):
        """The trap: `sql`'s export branch used to end in a bare `else` that
        wrote TXT, so a new format would have written the wrong file and
        reported success."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc), \
             patch("dbqm.ops.deps.export_query_html", return_value="/tmp/o.html") as mock_html, \
             patch("dbqm.ops.deps.export_query_txt") as mock_txt:
            run_cli(["sql", "SELECT 1", "test_conn", "-e", "html"])
            mock_html.assert_called_once()
            mock_txt.assert_not_called()

    def test_sql_export_json_format_emits_envelope(self, capsys):
        """CRITICAL fix: `-e` used to print bare prose and return under
        `-f json`."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="SELECT", connection_name="test_conn",
            columns=["x"], rows=[[1]], row_count=1, elapsed=0.01,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc), \
             patch("dbqm.ops.deps.export_query_csv", return_value="/tmp/out.csv"):
            run_cli(["sql", "SELECT 1", "test_conn", "-e", "csv", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "sql"
            assert body["data"] == {"exported": "/tmp/out.csv", "format": "csv"}

    def test_sql_unclassified_type_gets_envelope_under_json(self, capsys):
        """CRITICAL fix: a statement `execute_adhoc` runs but doesn't
        special-case (sql_type not SELECT/INSERT/UPDATE/DELETE/DDL/PLSQL)
        used to fall past every json branch to a bare `print`. `data` is
        `AdhocResult.to_dict()`: the connection travels under
        `connection_name`, not a bare `"connection"` key."""
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="MERGE", connection_name="test_conn",
            rows_affected=2, elapsed=0.02, committed=True,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.classify_sql", return_value="MERGE"), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
            run_cli(["sql", "MERGE INTO t ...", "test_conn", "-f", "json"])
            output = capsys.readouterr()
            body = json.loads(output.out)
            assert body["ok"] is True
            assert body["command"] == "sql"
            assert body["data"]["sql_type"] == "MERGE"
            assert body["data"]["rows_affected"] == 2
            assert body["data"]["connection_name"] == "test_conn"

    def test_sql_unsupported_type_is_usage_not_sql_error(self, capsys):
        """MINOR fix: `core/`'s "unsupported SQL type" is bad input, not the driver
        rejecting a statement it actually received.
        """
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        adhoc = AdhocResult(
            sql_type="UNKNOWN", connection_name="test_conn",
            success=False,
            error="Unsupported SQL type. Use SELECT, INSERT, UPDATE, "
                  "DELETE, DDL (CREATE/ALTER/DROP...) or EXPLAIN PLAN.",
            error_kind="usage",
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.classify_sql", return_value="UNKNOWN"), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=adhoc):
            with pytest.raises(SystemExit) as exc:
                run_cli(["sql", "??? nonsense ???", "test_conn", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            assert json.loads(output.err)["error"]["code"] == "usage"


# ---------------------------------------------------------------------------
# call subcommand
# ---------------------------------------------------------------------------

class TestCmdCall:
    def test_a_non_oracle_connection_is_refused_before_anything_opens(self, tmp_config_dir, capsys):
        """`execute_routine` builds an anonymous PL/SQL block; the other three
        engines have no such thing. `db_type` is known from configuration, so
        the refusal costs no connection."""
        conn = Connection(name="c1", db_type="postgresql", user="usr", password="enc_pw")
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection") as mock_open:
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "c1", "-f", "json"])
            assert exited.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "usage"
            assert "postgresql" in body["error"]["message"]
            mock_open.assert_not_called()

    def test_a_package_routine_resolves_through_list_package_routines(self, tmp_config_dir):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg) as mock_pkg, \
             patch("dbqm.ops.deps.get_standalone_routine_info") as mock_standalone, \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
            mock_pkg.assert_called_once()
            mock_standalone.assert_not_called()

    def test_a_bare_name_resolves_through_get_standalone_routine_info(self, tmp_config_dir):
        from dbqm.core.object_browser import RoutineExecutionResult, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_ID", data_type="NUMBER", direction="IN", default="0")],
        )
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_standalone_routine_info", return_value=routine) as mock_standalone, \
             patch("dbqm.ops.deps.list_package_routines") as mock_pkg, \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "ROUTINE", "test_conn"])
            mock_standalone.assert_called_once()
            mock_pkg.assert_not_called()

    def test_a_standalone_function_is_re_tagged_before_execute_routine(self, tmp_config_dir):
        """`get_standalone_routine_info` always defaults `routine_type` to
        PROCEDURE, whatever it actually found. A non-empty `return_type` is
        the only tell that it is really a FUNCTION, and `execute_routine`
        (core/object_browser.py) only emits a return-variable assignment
        when `routine_type == "FUNCTION"` -- otherwise it emits the call as
        a bare statement, which Oracle rejects with PLS-00221."""
        from dbqm.core.object_browser import RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="FN_CALC", routine_type="PROCEDURE", params=[], return_type="NUMBER")
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value="42", elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_standalone_routine_info", return_value=routine), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result) as mock_exec:
            run_cli(["call", "FN_CALC", "test_conn"])
            called_routine = mock_exec.call_args[0][2]
            assert called_routine.routine_type == "FUNCTION"

    def test_a_zero_argument_standalone_procedure_still_runs(self, tmp_config_dir):
        """The regression this guards: a real procedure declared with no
        arguments (`PROCEDURE P IS BEGIN ... END;`) has zero rows in
        ALL_ARGUMENTS too, exactly like a name that does not exist at all --
        it must not be refused as `not_found`."""
        from dbqm.core.object_browser import RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="PROC_SEM_ARGUMENTOS", routine_type="PROCEDURE", params=[])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_standalone_routine_info", return_value=routine), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result) as mock_exec:
            run_cli(["call", "PROC_SEM_ARGUMENTOS", "test_conn"])
            mock_exec.assert_called_once()

    def test_a_bare_name_that_does_not_exist_exits_four(self, tmp_config_dir, capsys):
        """`get_standalone_routine_info` cannot tell "does not exist" apart
        from "exists with no arguments", so existence is not guessed
        CLI-side: the call is let through to `execute_routine`, and a name
        Oracle does not recognise comes back as a failed result
        (PLS-00201), reported the same as any other rejected statement."""
        from dbqm.core.object_browser import RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="NAO_EXISTE", routine_type="PROCEDURE", params=[])
        exec_result = RoutineExecutionResult(
            success=False, error="PLS-00201: identifier 'NAO_EXISTE' must be declared",
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_standalone_routine_info", return_value=routine), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "NAO_EXISTE", "test_conn", "-f", "json"])
            assert exited.value.code == 4
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "sql_error"
            assert "PLS-00201" in body["error"]["message"]

    def test_a_routine_that_does_not_exist_is_not_found(self, tmp_config_dir, capsys):
        from dbqm.core.object_browser import PackageInfo

        conn = _make_connection()
        pkg = PackageInfo(name="PKG", owner="APP", routines=[])
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "not_found"
            assert "PKG.ROUTINE" in body["error"]["message"]

    def test_a_missing_required_parameter_is_a_validation_error(self, tmp_config_dir, capsys):
        """A parameter with no default that the caller did not supply."""
        from dbqm.core.object_browser import PackageInfo, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_ID", data_type="NUMBER", direction="IN", default="")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine") as mock_exec:
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"
            assert "P_ID" in body["error"]["message"]
            mock_exec.assert_not_called()

    def test_a_parameter_with_a_default_may_be_omitted(self, tmp_config_dir):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_FLAG", data_type="NUMBER", direction="IN", default="0")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result) as mock_exec:
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
            mock_exec.assert_called_once()

    def test_a_parameter_name_is_matched_case_insensitively(self, tmp_config_dir):
        """Oracle declares `P_ID` upper case; `-p p_id=7` is not a typo and
        must not be refused. The value must also reach `execute_routine`
        keyed the way it looks values up -- exact `p.name` -- or it would
        silently run with the parameter's default instead of the value the
        caller gave, rather than failing loudly."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_ID", data_type="NUMBER", direction="IN", default="")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result) as mock_exec:
            run_cli(["call", "PKG.ROUTINE", "test_conn", "-p", "p_id=7"])
            called_params = mock_exec.call_args[0][3]
            assert called_params == {"P_ID": "7"}

    def test_an_in_out_parameter_without_a_default_is_required(self, tmp_config_dir, capsys):
        from dbqm.core.object_browser import PackageInfo, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_VAL", data_type="NUMBER", direction="IN OUT", default="")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine") as mock_exec:
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"
            assert "P_VAL" in body["error"]["message"]
            mock_exec.assert_not_called()

    def test_an_in_out_parameter_with_a_default_may_be_omitted(self, tmp_config_dir):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_VAL", data_type="NUMBER", direction="IN OUT", default="0")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result) as mock_exec:
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
            mock_exec.assert_called_once()

    def test_an_unknown_bare_name_with_a_param_says_the_routine_may_not_exist(
        self, tmp_config_dir, capsys
    ):
        """A standalone routine with no params and no return type is
        indistinguishable from one that does not exist -- both give zero
        ALL_ARGUMENTS rows. Blaming the parameter would send the reader to
        fix the wrong thing."""
        from dbqm.core.object_browser import RoutineInfo

        conn = _make_connection()
        empty = RoutineInfo(name="NAOEXISTE", routine_type="PROCEDURE", params=[])
        with patch("dbqm.ops.deps.find_connection", return_value=conn),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.get_standalone_routine_info", return_value=empty),              patch("dbqm.ops.deps.execute_routine") as mock_exec:
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "NAOEXISTE", "test_conn", "-p", "id=7", "-f", "json"])
            assert exited.value.code == 2
            mock_exec.assert_not_called()
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert "does not exist" in body["error"]["message"]
        assert "NAOEXISTE" in body["error"]["message"]

    def test_an_undeclared_parameter_is_a_validation_error(self, tmp_config_dir, capsys):
        """Almost always a typo. Ignoring it would run the routine with a
        default the caller did not intend."""
        from dbqm.core.object_browser import PackageInfo, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_FLAG", data_type="NUMBER", direction="IN", default="0")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine") as mock_exec:
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-p", "naoexiste=1", "-f", "json"])
            assert exited.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "validation"
            assert "naoexiste" in body["error"]["message"]
            mock_exec.assert_not_called()

    def test_an_out_parameter_is_not_required_from_the_caller(self, tmp_config_dir):
        """An OUT parameter is written by the routine, not supplied to it."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo, RoutineParam

        conn = _make_connection()
        routine = RoutineInfo(
            name="ROUTINE", routine_type="PROCEDURE",
            params=[RoutineParam(name="P_OUT", data_type="NUMBER", direction="OUT")],
        )
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=["P_OUT=5"], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result) as mock_exec:
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
            mock_exec.assert_called_once()

    def test_a_read_only_connection_is_refused(self, tmp_config_dir, capsys):
        """`execute_routine` raises ReadOnlyViolation: a routine can write
        regardless of the text that calls it."""
        from dbqm.core.object_browser import PackageInfo, RoutineInfo
        from dbqm.core.read_only import ReadOnlyViolation

        conn = Connection(name="test_conn", db_type="oracle", user="usr",
                          password="enc_pw", read_only=True)
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine",
                   side_effect=ReadOnlyViolation("Connection 'test_conn' is read-only")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            assert json.loads(output.err)["error"]["code"] == "read_only"

    def test_a_database_that_never_answered_exits_three(self, tmp_config_dir, capsys):
        """`open_connection` is a `@contextmanager`: the real one dials out
        (and can fail) inside `__enter__`, not when it is merely called. A
        fake that raises on the call itself would pass this test even
        without the nesting that keeps a connection failure (3) apart from
        a statement failure (4), so the fake here fails the same way the
        real one does -- at `__enter__`."""
        conn = _make_connection()
        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("ORA-12541: TNS:no listener")
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection", return_value=cm):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 3
            output = capsys.readouterr()
            assert output.out == ""
            assert json.loads(output.err)["error"]["code"] == "connection_failed"

    def test_a_routine_that_raised_exits_four(self, tmp_config_dir, capsys):
        """RoutineExecutionResult(success=False) -- the database answered."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=False, error="ORA-06502: numeric or value error")
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 4
            output = capsys.readouterr()
            assert output.out == ""
            body = json.loads(output.err)
            assert body["error"]["code"] == "sql_error"
            assert "ORA-06502" in body["error"]["message"]

    def test_a_value_error_from_execute_routine_is_sql_error_not_validation(self, tmp_config_dir, capsys):
        """The `ValueError` -> `validation` mapping exists for
        `_validate_call_params`'s own parameter checks. A `ValueError`
        surfacing from `execute_routine` itself is a statement failure, not
        a caller mistake, and must not be caught by that same handler."""
        from dbqm.core.object_browser import PackageInfo, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine",
                   side_effect=ValueError("invalid literal for int()")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 4
            output = capsys.readouterr()
            assert output.out == ""
            assert json.loads(output.err)["error"]["code"] == "sql_error"

    def test_json_carries_the_result_shape(self, tmp_config_dir, capsys):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="FUNCTION", params=[], return_type="NUMBER")
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(
            success=True, output_lines=["linha 1", "linha 2"],
            return_value="42", elapsed=0.03,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "call"
            assert body["data"] == {**exec_result.to_dict(), "committed": False}
            assert body["warnings"] == ["linha 1", "linha 2"]

    def test_table_shows_the_return_value_and_the_output_lines(self, tmp_config_dir, capsys):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="FUNCTION", params=[], return_type="NUMBER")
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(
            success=True, output_lines=["processando linha"],
            return_value="42", elapsed=0.03,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
            out = capsys.readouterr().out
            assert "42" in out
            assert "processando linha" in out

    def test_table_format_return_value_with_markup_characters_does_not_raise(self, tmp_config_dir, capsys):
        """`output_lines` already prints with `markup=False`; the return
        value must be just as safe -- a value containing `[algo]` must not
        be swallowed as Rich markup or raise `MarkupError`."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="FUNCTION", params=[], return_type="VARCHAR2")
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(
            success=True, output_lines=[], return_value="[x]", elapsed=0.01,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
            assert "[x]" in capsys.readouterr().out

    def test_without_commit_the_transaction_is_rolled_back(self, tmp_config_dir):
        """Assert the rollback actually happened -- a test that only checked
        the wording would pass over the very bug this exists for."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        db_handle = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db_handle
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection", return_value=cm), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn"])
        db_handle.rollback.assert_called_once()
        db_handle.commit.assert_not_called()

    def test_with_commit_the_transaction_is_committed(self, tmp_config_dir):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        db_handle = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db_handle
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection", return_value=cm), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn", "--commit"])
        db_handle.commit.assert_called_once()
        db_handle.rollback.assert_not_called()

    def test_the_table_output_says_which_happened(self, tmp_config_dir, capsys,
                                                  monkeypatch):
        """In every language, and the two outcomes never read the same.

        `--commit` is the difference between work that survives and work
        the driver throws away, so this is the one line here that cannot
        afford a translation reusing the other outcome's word.
        """
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo
        from dbqm.i18n import available_languages, t

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        for language in available_languages():
            monkeypatch.setenv("DBQM_LANG", language)
            with patch("dbqm.ops.deps.find_connection", return_value=conn), \
                 patch("dbqm.ops.deps.open_connection"), \
                 patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
                 patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
                run_cli(["call", "PKG.ROUTINE", "test_conn"])
                sem_commit = capsys.readouterr().out

                run_cli(["call", "PKG.ROUTINE", "test_conn", "--commit"])
                com_commit = capsys.readouterr().out

            # Only up to the em dash: this console encodes in cp1252 and the
            # dash comes back as a replacement character.
            undone = t("exec_routine.rolled_back").split("\u2014")[0].strip()
            confirmed = t("exec_routine.committed").split("\u2014")[0].strip()
            assert undone != confirmed, language
            assert undone in sem_commit, language
            assert confirmed in com_commit, language
            assert confirmed not in sem_commit, language

    def test_the_json_envelope_carries_the_commit_state(self, tmp_config_dir, capsys):
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True, output_lines=[], return_value=None, elapsed=0.01)
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            sem_commit = json.loads(capsys.readouterr().out)
            assert sem_commit["data"]["committed"] is False

            run_cli(["call", "PKG.ROUTINE", "test_conn", "--commit", "-f", "json"])
            com_commit = json.loads(capsys.readouterr().out)
            assert com_commit["data"]["committed"] is True

    def test_a_failed_routine_is_rolled_back_even_with_commit(self, tmp_config_dir):
        """--commit is not a promise to keep a failure."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=False, error="ORA-06502: numeric or value error")
        db_handle = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db_handle
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection", return_value=cm), \
             patch("dbqm.ops.deps.list_package_routines", return_value=pkg), \
             patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "--commit"])
            assert exited.value.code == 4
        db_handle.rollback.assert_called_once()
        db_handle.commit.assert_not_called()

    def test_a_routine_that_raised_is_rolled_back_too(self, tmp_config_dir):
        """A raise, not a `success=False` result: the block may have run in
        part before it blew up. Undoing it must not be left to the driver's
        close-time behaviour -- that is what --commit exists to stop anyone
        from having to trust."""
        from dbqm.core.object_browser import PackageInfo, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        db_handle = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db_handle
        with patch("dbqm.ops.deps.find_connection", return_value=conn),              patch("dbqm.ops.deps.open_connection", return_value=cm),              patch("dbqm.ops.deps.list_package_routines", return_value=pkg),              patch("dbqm.ops.deps.execute_routine", side_effect=RuntimeError("ORA-03113")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "--commit"])
            assert exited.value.code == 4
        db_handle.rollback.assert_called_once()
        db_handle.commit.assert_not_called()

    def test_a_rollback_that_fails_is_not_called_a_connection_failure(
        self, tmp_config_dir, capsys
    ):
        """Symmetric with the commit arm: nothing was kept either way, but
        letting it reach the outer handler would report a successful routine
        as a connection failure."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True)
        db_handle = MagicMock()
        db_handle.rollback.side_effect = RuntimeError("ORA-03113")
        cm = MagicMock()
        cm.__enter__.return_value = db_handle
        with patch("dbqm.ops.deps.find_connection", return_value=conn),              patch("dbqm.ops.deps.open_connection", return_value=cm),              patch("dbqm.ops.deps.list_package_routines", return_value=pkg),              patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "-f", "json"])
            assert exited.value.code == 4
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "sql_error"
        assert "nothing was written" in body["error"]["message"]

    def test_a_commit_that_fails_says_nothing_was_written(self, tmp_config_dir, capsys):
        """The one outcome a caller must not have to guess at: the routine
        ran and nothing was kept."""
        from dbqm.core.object_browser import PackageInfo, RoutineExecutionResult, RoutineInfo

        conn = _make_connection()
        routine = RoutineInfo(name="ROUTINE", routine_type="PROCEDURE", params=[])
        pkg = PackageInfo(name="PKG", owner="APP", routines=[routine])
        exec_result = RoutineExecutionResult(success=True)
        db_handle = MagicMock()
        db_handle.commit.side_effect = RuntimeError("ORA-01536: space quota exceeded")
        cm = MagicMock()
        cm.__enter__.return_value = db_handle
        with patch("dbqm.ops.deps.find_connection", return_value=conn),              patch("dbqm.ops.deps.open_connection", return_value=cm),              patch("dbqm.ops.deps.list_package_routines", return_value=pkg),              patch("dbqm.ops.deps.execute_routine", return_value=exec_result):
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "test_conn", "--commit", "-f", "json"])
            assert exited.value.code == 4
        db_handle.rollback.assert_called_once()
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "sql_error"
        assert "nothing was written" in body["error"]["message"]


# ---------------------------------------------------------------------------
# test subcommand
# ---------------------------------------------------------------------------

class TestCmdTest:
    def test_connection_not_found(self):
        with patch("dbqm.ops.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit):
                run_cli(["test", "missing"])

    def test_connection_ok(self):
        conn = _make_connection()
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.test_connection", return_value=(True, 'OK (0.01s)\n  Versao: v1')):
            run_cli(["test", "test_conn"])

    def test_connection_fail(self):
        conn = _make_connection()
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.test_connection", return_value=(False, "Erro ao conectar")):
            with pytest.raises(SystemExit):
                run_cli(["test", "test_conn"])

    def test_all_connections(self):
        conns = [_make_connection("c1"), _make_connection("c2")]
        with patch("dbqm.ops.deps.load_connections", return_value=conns), \
             patch("dbqm.ops.deps.test_connection", return_value=(True, "OK")):
            run_cli(["test"])

    def test_no_connections(self):
        with patch("dbqm.ops.deps.load_connections", return_value=[]):
            run_cli(["test"])


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------

class TestCmdList:
    def test_list_connections(self):
        conns = [_make_connection()]
        with patch("dbqm.ops.deps.load_connections", return_value=conns):
            run_cli(["list", "connections"])

    def test_list_connections_json(self, capsys):
        conns = [_make_connection()]
        with patch("dbqm.ops.deps.load_connections", return_value=conns):
            run_cli(["list", "connections", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "list.connections"
            assert len(body["data"]) == 1
            assert body["data"][0]["name"] == "test_conn"

    def test_list_queries(self):
        queries = [_make_query()]
        with patch("dbqm.ops.deps.load_queries", return_value=queries):
            run_cli(["list", "queries"])

    def test_list_queries_json(self, capsys):
        queries = [_make_query()]
        with patch("dbqm.ops.deps.load_queries", return_value=queries):
            run_cli(["list", "queries", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "list.queries"
            assert len(body["data"]) == 1

    def test_list_groups(self):
        groups = [_make_group()]
        with patch("dbqm.ops.deps.load_groups", return_value=groups):
            run_cli(["list", "groups"])

    def test_list_groups_json(self, capsys):
        groups = [_make_group()]
        with patch("dbqm.ops.deps.load_groups", return_value=groups):
            run_cli(["list", "groups", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "list.groups"
            assert body["data"][0]["join_key"] == "id"

    def test_list_empty_connections(self):
        with patch("dbqm.ops.deps.load_connections", return_value=[]):
            run_cli(["list", "connections"])

    def test_list_empty_queries(self):
        with patch("dbqm.ops.deps.load_queries", return_value=[]):
            run_cli(["list", "queries"])

    def test_list_empty_groups(self):
        with patch("dbqm.ops.deps.load_groups", return_value=[]):
            run_cli(["list", "groups"])


# ---------------------------------------------------------------------------
# ddl subcommand
# ---------------------------------------------------------------------------

class TestCmdDdl:
    def test_ddl_connection_not_found(self):
        with patch("dbqm.ops.deps.find_connection", return_value=None):
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.extract_ddl", return_value=result), \
             patch("dbqm.ops.deps.save_extraction", return_value=("/tmp/ddl", 2)) as mock_save:
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.extract_ddl", return_value=result):
            run_cli(["ddl", "MY_TABLE", "test_conn", "--stdout"])
            out = capsys.readouterr().out
            assert "CREATE TABLE" in out

    def test_ddl_errors_no_objects_exits(self):
        conn = _make_connection()
        from dbqm.core.ddl_extractor import ExtractionResult
        result = ExtractionResult(
            object_name="MISSING", object_type="UNKNOWN",
            owner="", connection_name="test_conn",
            errors=["Objeto 'MISSING' not found."],
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.extract_ddl", return_value=result):
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.extract_ddl", return_value=result), \
             patch("dbqm.ops.deps.save_extraction", return_value=("/tmp/ddl", 1)):
            run_cli(["ddl", "MY_TABLE", "test_conn", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "ddl"
            assert body["data"]["path"] == "/tmp/ddl"
            assert body["data"]["objects"][0]["name"] == "MY_TABLE"
            assert body["data"]["objects"][0]["ddl"] == "CREATE TABLE MY_TABLE (id NUMBER);"

    def test_ddl_json_failure_leaves_stdout_clean(self, capsys):
        with patch("dbqm.ops.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit) as exc:
                run_cli(["ddl", "MY_TABLE", "missing", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            assert json.loads(output.err)["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# config subcommand
# ---------------------------------------------------------------------------

class TestCmdConfig:
    def test_list_returns_every_setting(self, tmp_config_dir, capsys):
        run_cli(["config", "list", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "config.list"
        assert set(body["data"].keys()) == {
            "audit_log_enabled", "theme", "language", "default_export_dir",
            "export_dir_prompted", "create_export_subdirs", "oracle_client_dir",
        }

    def test_get_returns_the_real_type_not_a_string(self, tmp_config_dir, capsys):
        """A caller branching on audit_log_enabled must get true, not "true"."""
        run_cli(["config", "get", "audit_log_enabled", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "config.get"
        assert body["data"]["value"] is False

    def test_an_unknown_key_is_not_found_and_lists_the_valid_ones(self, tmp_config_dir, capsys):
        with pytest.raises(SystemExit) as exc:
            run_cli(["config", "get", "bogus_key", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"
        assert "theme" in body["error"]["message"]

    def test_set_parses_a_boolean(self, tmp_config_dir):
        from dbqm.models.settings import load_settings

        run_cli(["config", "set", "audit_log_enabled", "true"])
        assert load_settings().audit_log_enabled is True

    def test_a_bad_boolean_is_refused_not_coerced(self, tmp_config_dir, capsys):
        """`set audit_log_enabled talvez` must not quietly become False.

        The stored value is driven to True first, on purpose. `False` is the
        field's own default, so asserting it stayed False would be satisfied
        just as well by an implementation that coerced the bad input and
        wrote it -- the two states are indistinguishable from the outside.
        """
        from dbqm.models.settings import load_settings

        run_cli(["config", "set", "audit_log_enabled", "true", "-f", "json"])
        capsys.readouterr()
        assert load_settings().audit_log_enabled is True

        with pytest.raises(SystemExit) as exc:
            run_cli(["config", "set", "audit_log_enabled", "talvez", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert load_settings().audit_log_enabled is True

    def test_an_unknown_theme_is_refused_and_names_what_exists(self, tmp_config_dir, capsys):
        with pytest.raises(SystemExit) as exc:
            run_cli(["config", "set", "theme", "does-not-exist", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert "plano-escuro" in body["error"]["message"]

    def test_a_directory_that_does_not_exist_is_refused(self, tmp_config_dir, capsys):
        """oracle_client_dir exists to override auto-detection; a typo there
        becomes a confusing connection failure much later."""
        with pytest.raises(SystemExit) as exc:
            run_cli(["config", "set", "oracle_client_dir",
                     str(tmp_config_dir / "no-such-dir"), "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"

    def test_an_empty_directory_value_is_accepted(self, tmp_config_dir):
        """Empty means "auto-detect" and must stay settable."""
        from dbqm.models.settings import load_settings

        run_cli(["config", "set", "oracle_client_dir", ""])
        assert load_settings().oracle_client_dir == ""


# ---------------------------------------------------------------------------
# history subcommand
# ---------------------------------------------------------------------------

class TestCmdHistory:
    def test_history_empty(self):
        with patch("dbqm.ops.deps.load_history", return_value=[]):
            run_cli(["history"])

    def test_history_with_entries(self):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id="1", timestamp="2026-01-01T00:00:00", entry_type="query",
                         name="q1", connection="c1", row_count=10, elapsed=0.5),
        ]
        with patch("dbqm.ops.deps.load_history", return_value=entries):
            run_cli(["history", "-n", "5"])

    def test_history_json(self, capsys):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id="1", timestamp="2026-01-01", entry_type="query",
                         name="q1", connection="c1"),
        ]
        with patch("dbqm.ops.deps.load_history", return_value=entries):
            run_cli(["history", "-f", "json"])
            out = capsys.readouterr().out
            body = json.loads(out)
            assert body["command"] == "history"
            assert len(body["data"]) == 1
            assert body["data"][0]["name"] == "q1"

    def test_history_clear(self):
        with patch("dbqm.ops.deps.clear_history") as mock_clear:
            run_cli(["history", "--clear"])
            mock_clear.assert_called_once()

    def test_history_limit(self):
        from dbqm.core.history import HistoryEntry
        entries = [
            HistoryEntry(id=str(i), timestamp="t", entry_type="query",
                         name=f"q{i}", connection="c")
            for i in range(50)
        ]
        with patch("dbqm.ops.deps.load_history", return_value=entries):
            # Default limit is 20, but custom limit of 5
            run_cli(["history", "-n", "5"])


# ---------------------------------------------------------------------------
# export-config / import-config subcommands
# ---------------------------------------------------------------------------

class TestCmdExportConfig:
    def test_export_with_password(self):
        with patch("dbqm.ops.deps.export_configs", return_value="/tmp/cfg.dbqm") as mock_exp:
            run_cli(["export-config", "--password", "s3cret"])
            mock_exp.assert_called_once_with(
                "s3cret",
                include_connections=True,
                include_queries=True,
                include_groups=True,
            )

    def test_export_no_connections(self):
        with patch("dbqm.ops.deps.export_configs", return_value="/tmp/cfg.dbqm") as mock_exp:
            run_cli(["export-config", "--password", "pw", "--no-connections"])
            mock_exp.assert_called_once_with(
                "pw",
                include_connections=False,
                include_queries=True,
                include_groups=True,
            )

    def test_export_prompts_password(self):
        with patch("dbqm.ops.deps.export_configs", return_value="/tmp/cfg.dbqm"), \
             patch("sys.stdin.isatty", return_value=True), \
             patch("dbqm.cli.params.getpass.getpass", return_value="prompted_pw") as mock_gp:
            run_cli(["export-config"])
            mock_gp.assert_called_once()

    def test_export_config_json_envelope(self, capsys):
        with patch("dbqm.ops.deps.export_configs", return_value="/tmp/cfg.dbqm"):
            run_cli(["export-config", "--password", "s3cret", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "export-config"
            assert body["data"] == {"path": "/tmp/cfg.dbqm"}

    def test_export_config_json_failure_leaves_stdout_clean(self, monkeypatch, capsys):
        """No password source and no tty — `resolve_password`'s own failure,
        now threaded through the envelope too."""
        monkeypatch.delenv("DBQM_BUNDLE_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        with pytest.raises(SystemExit) as exc:
            run_cli(["export-config", "-f", "json"])
        assert exc.value.code == 2
        output = capsys.readouterr()
        assert output.out == ""
        assert json.loads(output.err)["error"]["code"] == "usage"


class TestCmdImportConfig:
    """The bundle path must exist before anything else is looked at, so
    these tests hand the command a real (empty) file and mock only what
    reads it."""

    @pytest.fixture
    def bundle(self, tmp_path):
        file = tmp_path / "file.dbqm"
        file.write_text("{}", encoding="utf-8")
        return str(file)

    def test_import_success(self, bundle):
        summary = {"connections": 2, "queries": 3, "groups": 1, "skipped": 0}
        with patch("dbqm.ops.deps.import_configs", return_value=summary):
            run_cli(["import-config", bundle, "--password", "pw"])

    def test_import_error(self, bundle):
        with patch("dbqm.ops.deps.import_configs", side_effect=ValueError("bad password")):
            with pytest.raises(SystemExit) as exc:
                run_cli(["import-config", bundle, "--password", "wrong"])
            assert exc.value.code == 2

    def test_import_config_json_envelope(self, bundle, capsys):
        summary = {"connections": 2, "queries": 3, "groups": 1, "skipped": 0}
        with patch("dbqm.ops.deps.import_configs", return_value=summary):
            run_cli(["import-config", bundle, "--password", "pw", "-f", "json"])
            body = json.loads(capsys.readouterr().out)
            assert body["ok"] is True
            assert body["command"] == "import-config"
            assert body["data"] == summary

    def test_import_config_json_failure_leaves_stdout_clean(self, bundle, capsys):
        with patch("dbqm.ops.deps.import_configs", side_effect=ValueError("bad password")):
            with pytest.raises(SystemExit) as exc:
                run_cli(["import-config", bundle, "--password", "wrong", "-f", "json"])
            assert exc.value.code == 2
            output = capsys.readouterr()
            assert output.out == ""
            assert json.loads(output.err)["error"]["code"] == "validation"

    def test_a_missing_bundle_is_not_found_before_the_password_is_asked(self, tmp_path, monkeypatch, capsys):
        """No password source at all: if the path check did not come first,
        this would fail as `usage` from `resolve_password` -- or worse, as
        the OS's localised "file not found" text under `validation`."""
        monkeypatch.delenv("DBQM_BUNDLE_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        spy = MagicMock()
        monkeypatch.setattr("dbqm.ops.deps.import_configs", spy)
        path = str(tmp_path / "missing.dbqm")
        with pytest.raises(SystemExit) as exc:
            run_cli(["import-config", path, "-f", "json"])
        assert exc.value.code == 2
        output = capsys.readouterr()
        assert output.out == ""
        error = json.loads(output.err)["error"]
        assert error["code"] == "not_found"
        assert error["message"] == f'File "{path}" not found.'
        spy.assert_not_called()


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

    def test_a_failed_result_is_not_the_renderers_decision(self):
        """The renderer renders; the caller decides the exit. It used to exit 1
        itself, which contradicts the published table where 1 means dbqm has a
        bug. Every caller now checks `success` first and exits through
        `_fail_or_print` with a mapped code -- see
        `test_run_failed_query_table_format_exits_via_fail_or_print`."""
        from dbqm.cli import _print_query_result
        result = _make_query_result(success=False)

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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_explain", return_value=plan) as mock_explain, \
             patch("dbqm.ops.deps.execute_adhoc") as mock_adhoc:
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_explain", return_value=plan):
            with pytest.raises(SystemExit):
                run_cli(["sql", "SELECT * FROM bogus", "test_conn", "--explain"])

    def test_explain_passes_param_values(self):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        plan = AdhocResult(
            sql_type="EXPLAIN", connection_name="test_conn",
            columns=["plan"], rows=[], row_count=0, elapsed=0.0,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_explain", return_value=plan) as mock_explain:
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
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=res):
            run_cli(["sql", "BEGIN NULL; END;", "test_conn"])
        out = capsys.readouterr().out
        assert "processando 1" in out
        assert "processando 2" in out
        assert "PL/SQL block ran" in out

    def test_no_output_lines_prints_only_status(self, capsys):
        conn = _make_connection()
        from dbqm.core.query_engine import AdhocResult
        res = AdhocResult(
            sql_type="PLSQL", connection_name="test_conn",
            elapsed=0.01, committed=True,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=res):
            run_cli(["sql", "BEGIN NULL; END;", "test_conn"])
        out = capsys.readouterr().out
        assert "PL/SQL block ran" in out


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

        monkeypatch.setattr("dbqm.ops.deps.export_configs", _fake_export)
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

        monkeypatch.setattr("dbqm.ops.deps.export_configs", _fake_export)
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
        monkeypatch.setattr("dbqm.ops.deps.export_configs", spy)

        with pytest.raises(SystemExit) as exc:
            run_cli(["export-config"])
        assert exc.value.code == 2
        spy.assert_not_called()

    def test_import_config_without_a_tty_and_without_a_source_aborts_before_reading(self, monkeypatch, tmp_config_dir):
        from dbqm.cli import run_cli

        monkeypatch.delenv("DBQM_BUNDLE_PASSWORD", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        spy = MagicMock()
        monkeypatch.setattr("dbqm.ops.deps.import_configs", spy)

        file = tmp_config_dir / "file.dbqm"
        file.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            run_cli(["import-config", str(file)])
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

    # "sqlite" was the invalid example until 2.9.0 made it an engine.
    def test_invalid_db_type_exits_2_with_the_dbqm_message(self, tmp_config_dir,
                                                           monkeypatch, capsys):
        with pytest.raises(SystemExit) as exc:
            self._run([
                "connection", "add", "x", "--type", "h2", "--no-password",
            ], monkeypatch)
        assert exc.value.code == 2
        assert "Invalid database type" in capsys.readouterr().out

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

        monkeypatch.setattr("dbqm.ops.deps.test_connection",
                            lambda conn: (False, "ORA-12154: TNS could not resolve"))
        with pytest.raises(SystemExit) as exc:
            self._run([
                "connection", "add", "x", "--type", "mysql", "--no-password",
                "--test",
            ], monkeypatch)
        assert exc.value.code == 3
        assert load_connections() == [], "a connection that fails --test must not be saved"

    def test_passing_test_flag_saves(self, tmp_config_dir, monkeypatch):
        from dbqm.models.connection import find_connection

        monkeypatch.setattr("dbqm.ops.deps.test_connection", lambda conn: (True, "OK"))
        self._run([
            "connection", "add", "x", "--type", "mysql", "--no-password", "--test",
        ], monkeypatch)
        assert find_connection("x") is not None

    def test_json_format_reports_the_outcome(self, tmp_config_dir, monkeypatch, capsys):
        self._run([
            "connection", "add", "j", "--type", "mysql", "--no-password",
            "-f", "json",
        ], monkeypatch)
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "connection.add"
        assert body["data"] == {"name": "j", "created": True}

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
        assert "Create a connection" in out, \
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
        monkeypatch.setattr("dbqm.ops.deps.test_connection", lambda conn: (False, "falhou"))
        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "update", "alvo", "--host", "novo", "--test"])
        assert exc.value.code == 3
        assert find_connection("alvo").host == "velho.example.com"

    def test_json_format_reports_the_outcome(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        self._seed(monkeypatch)
        capsys.readouterr()
        run_cli(["connection", "update", "alvo", "--host", "h", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "connection.update"
        assert body["data"] == {"name": "alvo", "updated": True}


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
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")
        run_cli(["connection", "rm", "alvo"])
        assert find_connection("alvo") is None

    def test_the_affirmative_is_the_one_of_the_language_in_use(self, tmp_config_dir, monkeypatch):
        """"s" confirms in Portuguese and "y" in English. A confirmation that
        only ever accepted one language would ignore the answer half its
        users give it."""
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.setenv("DBQM_LANG", "pt")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "s")
        run_cli(["connection", "rm", "alvo"])
        assert find_connection("alvo") is None

    def test_the_other_language_affirmative_is_not_taken_as_yes(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.connection import find_connection

        self._seed(monkeypatch)
        monkeypatch.delenv("DBQM_LANG", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "s")
        run_cli(["connection", "rm", "alvo"])
        assert find_connection("alvo") is not None

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
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "connection.rm"
        assert body["data"] == {"name": "alvo", "removed": False}
        assert find_connection("alvo") is not None

    def test_rm_json_format_reports_the_outcome(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        self._seed(monkeypatch)
        capsys.readouterr()
        run_cli(["connection", "rm", "alvo", "--yes", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "connection.rm"
        assert body["data"] == {"name": "alvo", "removed": True}

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
        body = json.loads(capsys.readouterr().out)
        data = body["data"]

        assert data["password"] == "***"
        assert "s3cret" not in json.dumps(body)
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


class TestCmdQuery:
    """`dbqm query add|update|show|rm|list`, mirroring TestConnection*.

    No command here opens a database: there is no `connection_failed` and no
    `sql_error` in this class, only `usage`/`not_found`/`validation`. Every
    failure asserts the machine token from the `-f json` envelope, not just
    the exit code — exit 2 is also argparse's own code for a bad argument.
    """

    def _add_connection(self, monkeypatch, name="db1"):
        from dbqm.cli import run_cli

        run_cli(["connection", "add", name, "--type", "mysql", "--host", "h",
                 "--no-password"])

    def test_add_creates(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli([
            "query", "add", "minha", "--connection", "db1",
            "--sql", "SELECT id, name FROM t", "--description", "nota",
        ])

        q = find_query("minha")
        assert q is not None
        assert q.connection == "db1"
        assert q.sql == "SELECT id, name FROM t"
        assert q.description == "nota"
        assert q.table == "t", "table must be derived from the SQL"

    def test_add_on_an_existing_name_is_a_validation_error(self, tmp_config_dir,
                                                            monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli(["query", "add", "dup", "--connection", "db1", "--sql", "SELECT 1"])
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "query", "add", "dup", "--connection", "db1", "--sql", "SELECT 2",
                "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert find_query("dup").sql == "SELECT 1", "a rejected add must change nothing"

    def test_update_on_a_missing_name_is_not_found(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "query", "update", "inexistente", "--description", "x", "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_update_preserves_column_maps_and_is_favorite(self, tmp_config_dir, monkeypatch):
        """The trap: an update must overlay only the flags actually given.
        `column_maps` has no CLI flag at all, so this also proves `build`
        (never `upsert`) is being called with a sparse dict, not a fully
        populated one that would wipe it back to empty."""
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query, load_queries, save_queries

        self._add_connection(monkeypatch)
        run_cli([
            "query", "add", "alvo", "--connection", "db1",
            "--sql", "SELECT id, name FROM t", "--favorite", "--folder", "pasta1",
        ])

        queries = load_queries()
        queries[0].column_maps = {"name": {"1": "um"}}
        # `parse_sql("SELECT id, name FROM t")` can only ever produce "t" --
        # so a plain "table survives" assertion against that value would
        # pass whether or not `table` was actually left alone. A value
        # `parse_sql` could never derive from this SQL is what tells the two
        # cases apart: it survives only if `build` never re-runs `parse_sql`
        # at all, which is the whole point of passing it the sparse
        # `values` dict instead of `merged`.
        queries[0].table = "tabela_editada"
        save_queries(queries)

        run_cli(["query", "update", "alvo", "--description", "description only"])

        q = find_query("alvo")
        assert q.description == "description only"
        assert q.column_maps == {"name": {"1": "um"}}, "column_maps must survive"
        assert q.is_favorite is True, "is_favorite must survive"
        assert q.folder == "pasta1", "folder must survive"
        assert q.sql == "SELECT id, name FROM t", "sql must survive"
        assert q.table == "tabela_editada", \
            "a manually edited table must survive an unrelated update, not be re-derived"

    def test_update_empty_description_clears_it_without_touching_other_fields(
        self, tmp_config_dir, monkeypatch
    ):
        """`--description ""` is a deliberate empty value, not "not given" --
        argparse hands the two cases different Python values (`""` vs
        `None`), and `_query_values` must keep them apart. If `_query_values`
        and its "effective state" merge in `_query_update` were ever
        collapsed into one dict, this would still pass by accident for most
        fields; the description assertion is what actually distinguishes
        "cleared" from "unmentioned"."""
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli([
            "query", "add", "alvo", "--connection", "db1",
            "--sql", "SELECT 1", "--description", "nota original",
            "--folder", "pasta1", "--favorite",
        ])

        run_cli(["query", "update", "alvo", "--description", ""])

        q = find_query("alvo")
        assert q.description == "", "an explicit empty value must clear the field"
        assert q.folder == "pasta1", "an unmentioned field must not change"
        assert q.is_favorite is True, "an unmentioned field must not change"

    def test_update_with_sql_re_derives_table_columns_and_order_by(
        self, tmp_config_dir, monkeypatch
    ):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli([
            "query", "add", "alvo", "--connection", "db1",
            "--sql", "SELECT id FROM velha",
        ])

        run_cli([
            "query", "update", "alvo",
            "--sql", "SELECT id, name FROM nova ORDER BY name",
        ])

        q = find_query("alvo")
        assert q.sql == "SELECT id, name FROM nova ORDER BY name"
        assert q.table == "nova", "an explicit --sql must re-derive table"
        assert q.columns == ["id", "name"], "an explicit --sql must re-derive columns"
        assert q.order_by, "an explicit --sql must re-derive order_by"

    def test_show_unknown_name_is_not_found(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["query", "show", "inexistente", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_rm_unknown_name_is_not_found(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["query", "rm", "inexistente", "--yes", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_sql_and_sql_file_are_mutually_exclusive(self, tmp_config_dir, monkeypatch,
                                                     tmp_path, capsys):
        """argparse rejects this one before the command runs, so there is no
        envelope and no token to assert -- the exit code alone would also be
        satisfied by any other bad argument, so pin argparse's own wording."""
        from dbqm.cli import run_cli

        self._add_connection(monkeypatch)
        sql_path = tmp_path / "query.sql"
        sql_path.write_text("SELECT 1", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "query", "add", "alvo", "--connection", "db1",
                "--sql", "SELECT 1", "--sql-file", str(sql_path),
            ])
        assert exc.value.code == 2
        assert "not allowed with argument" in capsys.readouterr().err

    def test_sql_file_pointing_at_a_directory_is_usage(self, tmp_config_dir, monkeypatch,
                                                        tmp_path, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "query", "add", "arq", "--connection", "db1",
                "--sql-file", str(tmp_path), "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_query("arq") is None

    def test_show_returns_to_dict(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli(["query", "add", "alvo", "--connection", "db1", "--sql", "SELECT 1"])
        capsys.readouterr()
        run_cli(["query", "show", "alvo", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "query.show"
        assert body["data"] == find_query("alvo").to_dict()

    def test_rm_with_yes_removes(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli(["query", "add", "alvo", "--connection", "db1", "--sql", "SELECT 1"])
        run_cli(["query", "rm", "alvo", "--yes"])
        assert find_query("alvo") is None

    def test_rm_without_yes_and_without_a_tty_is_usage(self, tmp_config_dir,
                                                        monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        run_cli(["query", "add", "alvo", "--connection", "db1", "--sql", "SELECT 1"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["query", "rm", "alvo", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_query("alvo") is not None, "a refusal must not remove"

    def test_list_filtered_by_connection(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        self._add_connection(monkeypatch, "db1")
        self._add_connection(monkeypatch, "db2")
        run_cli(["query", "add", "q1", "--connection", "db1", "--sql", "SELECT 1"])
        run_cli(["query", "add", "q2", "--connection", "db2", "--sql", "SELECT 2"])

        capsys.readouterr()
        run_cli(["query", "list", "--connection", "db1", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "query.list"
        assert [item["name"] for item in body["data"]] == ["q1"]

    def test_sql_file_reads_the_file(self, tmp_config_dir, monkeypatch, tmp_path):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        sql_path = tmp_path / "query.sql"
        sql_path.write_text("SELECT * FROM t WHERE 1=1", encoding="utf-8")
        run_cli([
            "query", "add", "arq", "--connection", "db1",
            "--sql-file", str(sql_path),
        ])
        assert find_query("arq").sql == "SELECT * FROM t WHERE 1=1"

    def test_unreadable_sql_file_is_usage(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.query import find_query

        self._add_connection(monkeypatch)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "query", "add", "arq", "--connection", "db1",
                "--sql-file", "path/that/does/not/exist.sql", "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_query("arq") is None, "a failed read must not create the query"


class TestCmdGroup:
    """`dbqm group add|update|show|rm|list`, mirroring `TestCmdQuery`.

    No command here opens a database: there is no `connection_failed` and no
    `sql_error` in this class, only `usage`/`not_found`/`validation`. Every
    failure asserts the machine token from the `-f json` envelope, not just
    the exit code -- exit 2 is also argparse's own code for a bad argument.
    """

    def _add_connection(self, monkeypatch, name="db1"):
        from dbqm.cli import run_cli

        run_cli(["connection", "add", name, "--type", "mysql", "--host", "h",
                 "--no-password"])

    def _add_query(self, monkeypatch, name, connection="db1"):
        from dbqm.cli import run_cli

        run_cli(["query", "add", name, "--connection", connection,
                 "--sql", f"SELECT id FROM {name}"])

    def test_add_creates(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli([
            "group", "add", "meugrupo", "--query", "q1", "--query", "q2",
            "--join-key", "id", "--description", "nota", "--folder", "pasta1",
            "--compare-column", "name",
        ])

        g = find_group("meugrupo")
        assert g is not None
        assert g.queries == ["q1", "q2"]
        assert g.join_key == "id"
        assert g.description == "nota"
        assert g.folder == "pasta1"
        assert g.compare_columns == ["name"]

    def test_add_on_an_existing_name_is_a_validation_error(self, tmp_config_dir,
                                                            monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "dup", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "group", "add", "dup", "--query", "q1", "--query", "q2",
                "--join-key", "outra", "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert find_group("dup").join_key == "id", "a rejected add must change nothing"

    def test_add_with_fewer_than_two_queries_is_validation(self, tmp_config_dir,
                                                            monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "group", "add", "sozinho", "--query", "q1", "--join-key", "id",
                "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert find_group("sozinho") is None

    def test_add_with_unknown_query_is_validation(self, tmp_config_dir,
                                                   monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "group", "add", "comfantasma", "--query", "q1",
                "--query", "naoexiste", "--join-key", "id", "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert find_group("comfantasma") is None

    def test_update_on_a_missing_name_is_not_found(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "group", "update", "inexistente", "--description", "x", "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_update_preserves_fields_not_mentioned(self, tmp_config_dir, monkeypatch):
        """The trap: an update must overlay only the flags actually given.
        None of these ten fields has a CLI flag, so this also proves `build`
        (never `upsert`) is called with a sparse dict, not the
        validation-only merged one. Each is set to a non-default value
        before the update -- `adhoc_sql=""`/`connections=[]` would still
        "survive" even if `build` dropped the field entirely, since those
        are also the field's own defaults (Task 3 shipped exactly that
        inert assertion and had to fix it), so every value used here is one
        the field would not otherwise hold.

        `folder` carries the one value-level discriminator this module has:
        leading/trailing whitespace. `_carry` (in `group_builder.build`) is
        asymmetric on purpose -- "key not in values" returns
        `getattr(existing, key)` untouched, "key in values" runs the value
        through `_text`, which strips. That is `build`'s actual contract
        (overlay only the keys `values` sets; normalise what the caller
        supplied, leave everything else byte-identical), not a defect, and
        every other field round-trips to an `==`-equal value whichever dict
        `build` receives -- `_carry_list`/`_carry_dict`/`template_fields`'s
        shallow copy all produce equal results either way, and `created_at`
        ignores `values` entirely. So the `folder` assertion below is the
        only one that can fail on its own from a sparse-vs-merged swap; the
        white-box guard in
        `test_update_calls_build_with_only_the_given_flags` (below) is what
        catches a regression that reuses `existing`'s exact values, since
        that swap alone is invisible to every other assertion here.
        """
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group, load_groups, save_groups

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli([
            "group", "add", "alvo", "--query", "q1", "--query", "q2",
            "--join-key", "id",
        ])

        groups = load_groups()
        groups[0].column_mapping = {"col": {"q1": "c1"}}
        groups[0].folder = "  folder with spaces  "
        groups[0].normalize = {"col": {"1": "um"}}
        groups[0].template = "tpl1"
        groups[0].template_fields = {"title": "literal:Test"}
        groups[0].validation_rule = "custom_rule"
        groups[0].created_at = "2020-01-01T00:00:00"
        groups[0].adhoc_sql = "SELECT 1"
        groups[0].connections = ["c1", "c2"]
        # Since 2.12.0 `validate` checks an ad-hoc group's connections
        # exist, the way it has always checked a saved query exists, so
        # the two names the file carries have to be real ones.
        self._add_connection(monkeypatch, "c1")
        self._add_connection(monkeypatch, "c2")
        groups[0].shared_params = {"param1": {"description": "d", "default": "x"}}
        save_groups(groups)

        run_cli(["group", "update", "alvo", "--description", "new description"])

        g = find_group("alvo")
        assert g.description == "new description"
        assert g.column_mapping == {"col": {"q1": "c1"}}, "column_mapping must survive"
        assert g.folder == "  folder with spaces  ", \
            "an unmentioned field must survive byte for byte, not be re-stripped"
        assert g.normalize == {"col": {"1": "um"}}, "normalize must survive"
        assert g.template == "tpl1", "template must survive"
        assert g.template_fields == {"title": "literal:Test"}, \
            "template_fields must survive"
        assert g.validation_rule == "custom_rule", "validation_rule must survive"
        assert g.created_at == "2020-01-01T00:00:00", "created_at must survive"
        assert g.adhoc_sql == "SELECT 1", \
            "adhoc_sql must survive an update it was not mentioned in"
        assert g.connections == ["c1", "c2"], \
            "connections must survive an update it was not mentioned in"
        assert g.shared_params == {"param1": {"description": "d", "default": "x"}}, \
            "shared_params must survive"
        assert g.queries == ["q1", "q2"], "queries must survive"
        assert g.join_key == "id", "join_key must survive"

    def test_update_calls_build_with_only_the_given_flags(self, tmp_config_dir, monkeypatch):
        """A white-box guard beside the `folder` whitespace check above.

        The reviewer traced all fourteen `Group` fields for a black-box
        discriminator and found only one: `folder`'s whitespace stripping,
        which lives in `_carry` and disappears if a future refactor
        normalises both of `_carry`'s branches the same way. This test
        asserts the rule itself instead of that one side effect of it, by
        spying on `group_builder.build` and checking the exact key set
        `_group_update` hands it -- so it stays a guard even if `_carry`
        changes.
        """
        from dbqm.cli import run_cli
        import dbqm.core.group_builder as group_builder

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "alvo", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])

        with patch("dbqm.core.group_builder.build", wraps=group_builder.build) as spy:
            run_cli(["group", "update", "alvo", "--description", "new description"])

        received = spy.call_args[0][0]
        assert set(received.keys()) == {"name", "description"}, \
            "build must receive only the flags actually given on this command line"

    def test_update_empty_description_clears_it_without_touching_other_fields(
        self, tmp_config_dir, monkeypatch
    ):
        """`--description ""` is a deliberate empty value, not "not given" --
        argparse hands the two cases different Python values (`""` vs
        `None`), and `_group_values` must keep them apart."""
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli([
            "group", "add", "alvo", "--query", "q1", "--query", "q2",
            "--join-key", "id", "--description", "nota original",
            "--folder", "pasta1",
        ])

        run_cli(["group", "update", "alvo", "--description", ""])

        g = find_group("alvo")
        assert g.description == "", "an explicit empty value must clear the field"
        assert g.folder == "pasta1", "an unmentioned field must not change"
        assert g.queries == ["q1", "q2"], "an unmentioned field must not change"

    def test_update_with_query_replaces_the_list(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        self._add_query(monkeypatch, "q3")
        run_cli([
            "group", "add", "alvo", "--query", "q1", "--query", "q2",
            "--join-key", "id",
        ])

        run_cli(["group", "update", "alvo", "--query", "q1", "--query", "q3"])

        g = find_group("alvo")
        assert g.queries == ["q1", "q3"], "an explicit --query must replace the list"

    def test_show_unknown_name_is_not_found(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["group", "show", "inexistente", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_show_returns_to_dict(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "alvo", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])
        capsys.readouterr()
        run_cli(["group", "show", "alvo", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "group.show"
        assert body["data"] == find_group("alvo").to_dict()

    def test_rm_unknown_name_is_not_found(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["group", "rm", "inexistente", "--yes", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_rm_with_yes_removes(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "alvo", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])
        run_cli(["group", "rm", "alvo", "--yes"])
        assert find_group("alvo") is None

    def test_rm_without_yes_and_without_a_tty_is_usage(self, tmp_config_dir,
                                                        monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "alvo", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["group", "rm", "alvo", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_group("alvo") is not None, "a refusal must not remove"

    def test_list_returns_groups(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "alvo", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])

        capsys.readouterr()
        run_cli(["group", "list", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "group.list"
        assert [item["name"] for item in body["data"]] == ["alvo"]

    def test_rm_on_a_tty_honours_a_no(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.group import find_group

        self._add_connection(monkeypatch)
        self._add_query(monkeypatch, "q1")
        self._add_query(monkeypatch, "q2")
        run_cli(["group", "add", "alvo", "--query", "q1", "--query", "q2",
                 "--join-key", "id"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        run_cli(["group", "rm", "alvo"])
        assert find_group("alvo") is not None, "a cancelled removal must not remove"

    def test_bare_group_command_exits_2(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["group"])
        assert exc.value.code == 2

    def test_bare_group_command_prints_the_group_help(self, tmp_config_dir,
                                                       monkeypatch, capsys):
        """A bare `dbqm group` must print the group's own help, not a
        one-line usage reminder -- mirrors `TestConnection`'s own
        bare-command test."""
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["group"])
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "usage:" in out.lower(), "expected argparse's own help, not a one-line reminder"
        assert "Create a group" in out, \
            "expected each subcommand's own help text, e.g. add's, to be listed"


class TestCmdTemplate:
    """`dbqm template add|update|show|rm|list`, mirroring `TestCmdQuery`.

    `Template` has no `connection`/`folder`/`is_favorite` to worry about --
    only `name`, `description` and `content` -- so there is no
    `connection_failed` and no `sql_error` here either, only
    `usage`/`not_found`/`validation`. Every failure asserts the machine
    token from the `-f json` envelope, not just the exit code -- exit 2 is
    also argparse's own code for a bad argument.
    """

    def test_add_creates(self, tmp_config_dir):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli([
            "template", "add", "report", "--content", "Ola {{name}}",
            "--description", "nota",
        ])

        t = find_template("report")
        assert t is not None
        assert t.content == "Ola {{name}}"
        assert t.description == "nota"

    def test_add_on_an_existing_name_is_a_validation_error(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "dup", "--content", "v1"])
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["template", "add", "dup", "--content", "v2", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert find_template("dup").content == "v1", "a rejected add must change nothing"

    def test_add_without_content_is_validation(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["template", "add", "vazio", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert find_template("vazio") is None

    def test_update_on_a_missing_name_is_not_found(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["template", "update", "inexistente", "--description", "x", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_update_preserves_content_not_mentioned(self, tmp_config_dir):
        """The trap: an update must overlay only the flags actually given.
        A plain `--description` must not touch `content` at all."""
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo", "--content", "conteudo original"])
        run_cli(["template", "update", "alvo", "--description", "new description"])

        t = find_template("alvo")
        assert t.description == "new description"
        assert t.content == "conteudo original", "content must survive"

    def test_update_preserves_description_not_mentioned(self, tmp_config_dir):
        """The mirror image of the test above: an update that only touches
        `content` must not clear a `description` set at `add` time."""
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo",
                 "--content", "conteudo original", "--description", "original description"])
        run_cli(["template", "update", "alvo", "--content", "conteudo novo"])

        t = find_template("alvo")
        assert t.content == "conteudo novo"
        assert t.description == "original description", "description must survive"

    def test_update_calls_build_with_only_the_given_flags(self, tmp_config_dir):
        """A white-box guard, the way `dbqm group`'s own test does: spies on
        `template_builder.build` and checks the exact key set `_template_update`
        hands it, so a future refactor that reuses `existing`'s values (which
        would round-trip and pass silently) is still caught."""
        from dbqm.cli import run_cli
        import dbqm.core.template_builder as template_builder

        run_cli(["template", "add", "alvo", "--content", "conteudo original"])

        with patch("dbqm.core.template_builder.build", wraps=template_builder.build) as spy:
            run_cli(["template", "update", "alvo", "--description", "new description"])

        received = spy.call_args[0][0]
        assert set(received.keys()) == {"name", "description"}, \
            "build must receive only the flags actually given on this command line"

    def test_update_empty_description_clears_it_without_touching_content(self, tmp_config_dir):
        """`--description ""` is a deliberate empty value, not "not given" --
        argparse hands the two cases different Python values (`""` vs
        `None`), and `_template_values` must keep them apart."""
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli([
            "template", "add", "alvo", "--content", "conteudo",
            "--description", "nota original",
        ])

        run_cli(["template", "update", "alvo", "--description", ""])

        t = find_template("alvo")
        assert t.description == "", "an explicit empty value must clear the field"
        assert t.content == "conteudo", "an unmentioned field must not change"

    def test_update_with_content_replaces_it(self, tmp_config_dir):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo", "--content", "velho"])
        run_cli(["template", "update", "alvo", "--content", "novo"])

        assert find_template("alvo").content == "novo"

    def test_show_unknown_name_is_not_found(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["template", "show", "inexistente", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_show_returns_to_dict(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo", "--content", "v1"])
        capsys.readouterr()
        run_cli(["template", "show", "alvo", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "template.show"
        assert body["data"] == find_template("alvo").to_dict()

    def test_rm_unknown_name_is_not_found(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["template", "rm", "inexistente", "--yes", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "not_found"

    def test_rm_with_yes_removes(self, tmp_config_dir):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo", "--content", "v1"])
        run_cli(["template", "rm", "alvo", "--yes"])
        assert find_template("alvo") is None

    def test_rm_without_yes_and_without_a_tty_is_usage(self, tmp_config_dir, monkeypatch, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo", "--content", "v1"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["template", "rm", "alvo", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_template("alvo") is not None, "a refusal must not remove"

    def test_rm_on_a_tty_honours_a_no(self, tmp_config_dir, monkeypatch):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        run_cli(["template", "add", "alvo", "--content", "v1"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        run_cli(["template", "rm", "alvo"])
        assert find_template("alvo") is not None, "a cancelled removal must not remove"

    def test_list_returns_templates(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli

        run_cli(["template", "add", "alvo", "--content", "v1"])

        capsys.readouterr()
        run_cli(["template", "list", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "template.list"
        assert [item["name"] for item in body["data"]] == ["alvo"]

    def test_content_and_content_file_are_mutually_exclusive(self, tmp_config_dir, tmp_path, capsys):
        """argparse rejects this one before the command runs, so there is no
        envelope and no token to assert -- the exit code alone would also be
        satisfied by any other bad argument, so pin argparse's own wording."""
        from dbqm.cli import run_cli

        content_path = tmp_path / "conteudo.txt"
        content_path.write_text("Ola {{name}}", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "template", "add", "alvo",
                "--content", "v1", "--content-file", str(content_path),
            ])
        assert exc.value.code == 2
        assert "not allowed with argument" in capsys.readouterr().err

    def test_content_file_pointing_at_a_directory_is_usage(self, tmp_config_dir, tmp_path, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "template", "add", "arq", "--content-file", str(tmp_path), "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_template("arq") is None

    def test_content_file_reads_the_file(self, tmp_config_dir, tmp_path):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        content_path = tmp_path / "conteudo.txt"
        content_path.write_text("Ola {{name}}, tudo bem?", encoding="utf-8")
        run_cli(["template", "add", "arq", "--content-file", str(content_path)])
        assert find_template("arq").content == "Ola {{name}}, tudo bem?"

    def test_unreadable_content_file_is_usage(self, tmp_config_dir, capsys):
        from dbqm.cli import run_cli
        from dbqm.models.template import find_template

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli([
                "template", "add", "arq",
                "--content-file", "path/that/does/not/exist.txt", "-f", "json",
            ])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert find_template("arq") is None, "a failed read must not create the template"

    def test_bare_template_command_exits_2(self, tmp_config_dir):
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["template"])
        assert exc.value.code == 2

    def test_bare_template_command_prints_the_group_help(self, tmp_config_dir, capsys):
        """A bare `dbqm template` must print the group's own help, not a
        one-line usage reminder -- mirrors `TestCmdGroup`'s own bare-command
        test."""
        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["template"])
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "usage:" in out.lower(), "expected argparse's own help, not a one-line reminder"
        assert "Create a template" in out, \
            "expected each subcommand's own help text, e.g. add's, to be listed"


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
        output = capsys.readouterr().out
        assert "Empty password" in output
        assert "--no-password" not in output

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
        body = json.loads(capsys.readouterr().out)

        assert body["ok"] is True
        assert body["command"] == "connection.show"
        assert body["data"]["name"] == "alvo"
        assert body["data"]["password"] == "", "redaction survives the envelope"

    def test_list_wraps_the_array_in_data(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        self._seed()
        capsys.readouterr()
        run_cli(["connection", "list", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert [c["name"] for c in body["data"]] == ["alvo"]

    def test_a_missing_name_leaves_stdout_parseable(self, tmp_config_dir, capsys):
        """The defect this whole sub-project exists for."""
        import json

        import pytest

        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "show", "inexistente", "-f", "json"])
        assert exc.value.code == 2

        output = capsys.readouterr()
        assert output.out == "", "stdout must be empty, not prose"
        error = json.loads(output.err)
        assert error["ok"] is False
        assert error["error"]["code"] == "not_found"

    def test_add_reports_the_outcome_in_the_envelope(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "novo", "--type", "mysql",
                 "--no-password", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "connection.add"
        assert body["data"] == {"name": "novo", "created": True}

    def test_a_failing_test_flag_reports_connection_failed(self, tmp_config_dir, capsys, monkeypatch):
        import json

        import pytest

        from dbqm.cli import run_cli

        monkeypatch.setattr("dbqm.ops.deps.test_connection",
                            lambda conn: (False, "ORA-12154"))
        with pytest.raises(SystemExit) as exc:
            run_cli(["connection", "add", "x", "--type", "mysql",
                     "--no-password", "--test", "-f", "json"])
        assert exc.value.code == 3
        error = json.loads(capsys.readouterr().err)
        assert error["error"]["code"] == "connection_failed"

    def test_table_format_gets_no_envelope(self, tmp_config_dir, capsys):
        """`table` is for a human; the envelope belongs to `json` alone."""
        from dbqm.cli import run_cli

        self._seed()
        capsys.readouterr()
        run_cli(["connection", "show", "alvo"])
        output = capsys.readouterr().out
        assert '"ok"' not in output
        assert "alvo" in output


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
        monkeypatch.setattr("dbqm.ops.deps.test_connection", lambda conn: (True, "OK"))
        capsys.readouterr()
        run_cli(["test", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "test"
        assert body["data"][0]["name"] == "c1"
        assert body["data"][0]["ok"] is True

    def test_list_wraps_its_array(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "c1", "--type", "mysql", "--no-password"])
        capsys.readouterr()
        run_cli(["list", "connections", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["command"] == "list.connections"
        assert [c["name"] for c in body["data"]] == ["c1"]

    def test_history_wraps_its_array(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        capsys.readouterr()
        run_cli(["history", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "history"
        assert isinstance(body["data"], list)

    def test_run_on_a_missing_query_is_not_found(self, tmp_config_dir, capsys):
        import json

        import pytest

        from dbqm.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli(["run", "does-not-exist", "-f", "json"])
        assert exc.value.code == 2
        output = capsys.readouterr()
        assert output.out == ""
        assert json.loads(output.err)["error"]["code"] == "not_found"

    def test_sql_failure_is_a_sql_error(self, tmp_config_dir, capsys, monkeypatch):
        import json

        import pytest

        from dbqm.cli import run_cli
        from dbqm.core.query_engine import AdhocResult

        run_cli(["connection", "add", "c1", "--type", "mysql", "--no-password"])
        monkeypatch.setattr(
            "dbqm.ops.deps.execute_adhoc",
            lambda *a, **k: AdhocResult(sql_type="SELECT", connection_name="c1",
                                        success=False, error="ORA-00942"),
        )
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["sql", "SELECT 1", "c1", "-f", "json"])
        assert exc.value.code == 4
        output = capsys.readouterr()
        assert output.out == ""
        error = json.loads(output.err)
        assert error["error"]["code"] == "sql_error"
        assert "ORA-00942" in error["error"]["message"]

    def test_run_group_missing_group_leaves_stdout_clean(self, tmp_config_dir, capsys):
        import json

        import pytest

        from dbqm.cli import run_cli

        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["run-group", "does-not-exist", "-f", "json"])
        assert exc.value.code == 2
        output = capsys.readouterr()
        assert output.out == ""
        assert json.loads(output.err)["error"]["code"] == "not_found"

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
        monkeypatch.setattr("dbqm.ops.deps.build_group_result",
                            lambda *a, **k: sample_group_result)
        monkeypatch.setattr("dbqm.ops.deps.find_group", lambda n: _make_group())
        monkeypatch.setattr("dbqm.ops.deps.find_query", lambda n: _make_query())
        monkeypatch.setattr("dbqm.ops.deps.find_connection", lambda n: _make_connection())
        monkeypatch.setattr("dbqm.ops.deps.execute_query",
                            lambda *a, **k: _make_query_result())
        monkeypatch.setattr("dbqm.ops.deps.record_group_execution", lambda *a, **k: None)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run_cli(["run-group", "test_group", "-f", "json"])
        assert exc.value.code == 5
        output = capsys.readouterr()
        assert output.err == "", "divergence is ok(), not fail() — nothing on stderr"
        body = json.loads(output.out)
        assert body["ok"] is True
        assert body["command"] == "run-group"
        assert body["data"]["all_match"] is False
        assert body["data"]["comparisons"][0]["column"] == "status"


class TestCmdObjects:
    """The first command over `open_connection`; the other two copy its shape."""

    def test_json_wraps_the_names_in_an_envelope(self, capsys):
        import json
        from unittest.mock import MagicMock, patch

        from dbqm.cli import run_cli

        conn = _make_connection()
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_objects", return_value=["ORDERS", "CUSTOMERS"]):
            run_cli(["objects", "connection", "-f", "json"])

        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "objects"
        assert body["data"]["objects"] == ["ORDERS", "CUSTOMERS"]
        assert body["data"]["obj_type"] == "TABLE", "the default type"

    def test_an_unknown_connection_leaves_stdout_empty(self, capsys):
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=None):
            with pytest.raises(SystemExit) as exited:
                run_cli(["objects", "nao_existe", "-f", "json"])

        captured = capsys.readouterr()
        assert captured.out == "", "the rule the whole contract exists for"
        assert exited.value.code == 2

    def test_a_connect_failure_is_exit_three(self, capsys):
        """`connection_failed` is finally distinguishable here: `run` and `sql`
        cannot tell a refused connection from a rejected statement."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection",
                   side_effect=RuntimeError("ORA-12541: TNS:no listener")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["objects", "connection", "-f", "json"])

        assert capsys.readouterr().out == ""
        assert exited.value.code == 3

    def test_a_package_on_sqlserver_is_usage_not_a_traceback(self, capsys):
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import UnsupportedEngine

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_objects",
                   side_effect=UnsupportedEngine("Packages e rotinas so existem no Oracle.")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["objects", "connection", "--type", "PACKAGE", "-f", "json"])

        assert capsys.readouterr().out == ""
        assert exited.value.code == 2

    def test_a_rejected_statement_is_sql_error_not_connection_failed(self, capsys):
        """The distinction `errors.py` exists to preserve, and the one `run`
        and `sql` cannot make. A connection that opened and then rejected what
        we asked is exit 4; a connection that never opened is exit 3. Reported
        as exit 3, a caller retries forever against a query the engine will
        never accept."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.list_objects",
                   side_effect=RuntimeError("Invalid object name 'sys.objects'")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["objects", "connection", "-f", "json"])

        assert capsys.readouterr().out == ""
        assert exited.value.code == 4

    def test_table_format_prints_the_names(self, capsys):
        from unittest.mock import patch

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.list_objects", return_value=["ORDERS"]):
            run_cli(["objects", "connection"])

        assert "ORDERS" in capsys.readouterr().out


class TestCmdDescribe:
    def test_json_carries_columns_indexes_and_no_row_count(self, capsys):
        """The shape decision: everything the one call returns, and a describe
        never counts rows."""
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import (
            ColumnInfo,
            IndexInfo,
            TableStructure,
            ViewInfo,
        )

        structure = TableStructure(
            table="ORDERS",
            columns=[
                ColumnInfo("ID", "NUMBER", 22, 10, 0, False, is_pk=True),
                ColumnInfo("CLIENTE_ID", "NUMBER", 22, 10, 0, False,
                           fk_ref="CUSTOMERS.ID"),
            ],
            indexes=[IndexInfo("PK_PEDIDOS", ["ID"], True)],
        )
        # A plain table: get_view_definition finds nothing, exactly like the
        # real function against a real table (verified in tests/core and
        # against a live database in Step 6). Left unmocked, a bare MagicMock
        # `db` makes `get_view_definition` return a truthy garbage value
        # instead of "", which would hide a wrong `or` in the not-found check.
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_table_structure", return_value=structure), \
             patch("dbqm.ops.deps.get_view_definition",
                   return_value=ViewInfo(name="ORDERS", owner="")):
            run_cli(["describe", "ORDERS", "connection", "-f", "json"])

        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "describe"
        assert body["data"]["columns"][0]["is_pk"] is True
        assert body["data"]["columns"][1]["fk_ref"] == "CUSTOMERS.ID"
        assert len(body["data"]["indexes"]) == 1
        assert "row_count" not in body["data"], "a describe never scans"
        assert "sql_definition" not in body["data"], "a table has none"

    def test_an_object_with_no_columns_is_not_found(self, capsys):
        """An empty structure means the name matched nothing."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import TableStructure, ViewInfo

        # A real empty ViewInfo, not a MagicMock: every attribute of a bare
        # mock is truthy, which would make the "is it a view" check pass and
        # hide the very conjunction this test is here to pin.
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_table_structure",
                   return_value=TableStructure(table="NAO_EXISTE")), \
             patch("dbqm.ops.deps.get_view_definition",
                   return_value=ViewInfo(name="NAO_EXISTE", owner="", sql_definition="")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["describe", "NAO_EXISTE", "connection", "-f", "json"])

        assert capsys.readouterr().out == ""
        assert exited.value.code == 2

    def test_a_view_also_carries_its_sql(self, capsys):
        """A view has columns like a table and a definition a table has not."""
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import ColumnInfo, TableStructure, ViewInfo

        structure = TableStructure(
            table="V_PEDIDOS",
            columns=[ColumnInfo("ID", "NUMBER", 22, 10, 0, False)],
        )
        view = ViewInfo(name="V_PEDIDOS", owner="APP",
                        sql_definition="SELECT id FROM orders")
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_table_structure", return_value=structure), \
             patch("dbqm.ops.deps.get_view_definition", return_value=view):
            run_cli(["describe", "V_PEDIDOS", "connection", "-f", "json"])

        body = json.loads(capsys.readouterr().out)
        assert body["data"]["sql_definition"] == "SELECT id FROM orders"

    def test_a_view_whose_source_is_unreadable_is_still_a_view(self, capsys):
        """Measured on SQL Server: without the VIEW DEFINITION grant both
        information_schema.views and sys.sql_modules return NULL rather than
        an error, so a real view arrives with its owner set and an empty
        definition. Labelling on the definition alone calls it a TABLE."""
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import ColumnInfo, TableStructure, ViewInfo

        structure = TableStructure(
            table="VW_ALGO",
            columns=[ColumnInfo("ID", "int", 4, 10, 0, False)],
        )
        without_source = ViewInfo(name="VW_ALGO", owner="dbo", sql_definition="")
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.get_table_structure", return_value=structure),              patch("dbqm.ops.deps.get_view_definition", return_value=without_source):
            run_cli(["describe", "VW_ALGO", "connection", "-f", "json"])

        body = json.loads(capsys.readouterr().out)
        assert body["data"]["object_type"] == "VIEW"
        assert "sql_definition" not in body["data"], "nothing to report is not an empty string"

    def test_a_plain_table_says_so(self, capsys):
        """The other half of the same decision: no owner, no definition."""
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import ColumnInfo, TableStructure, ViewInfo

        structure = TableStructure(
            table="ORDERS",
            columns=[ColumnInfo("ID", "int", 4, 10, 0, False)],
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.get_table_structure", return_value=structure),              patch("dbqm.ops.deps.get_view_definition",
                   return_value=ViewInfo(name="ORDERS", owner="", sql_definition="")):
            run_cli(["describe", "ORDERS", "connection", "-f", "json"])

        assert json.loads(capsys.readouterr().out)["data"]["object_type"] == "TABLE"

    def test_table_format_shows_the_same_facts_as_json(self, capsys):
        """The two formats must not disagree. Same call, same content."""
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.object_browser import (
            ColumnInfo,
            IndexInfo,
            TableStructure,
            ViewInfo,
        )

        structure = TableStructure(
            table="ORDERS",
            columns=[ColumnInfo("CLIENTE_ID", "NUMBER", 22, 10, 0, False,
                                fk_ref="CUSTOMERS.ID")],
            indexes=[IndexInfo("IX_PED_CLI", ["CLIENTE_ID"], False)],
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.get_table_structure", return_value=structure), \
             patch("dbqm.ops.deps.get_view_definition",
                   return_value=ViewInfo(name="ORDERS", owner="")):
            run_cli(["describe", "ORDERS", "connection"])

        output = capsys.readouterr().out
        assert "CLIENTE_ID" in output
        assert "CUSTOMERS.ID" in output, "the FK reference reaches the human too"
        assert "IX_PED_CLI" in output, "and so do the indexes"
        assert "TABLE" in output
        assert "VIEW" not in output, "a table with no definition is not a view"


class TestCmdRows:
    def test_json_carries_rows_as_parallel_arrays(self, capsys):
        """Same rule 2.0.0 settled for `run`/`sql`: arrays, not objects keyed
        by column, because a repeated column name drops a value."""
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.table_browser import BrowseResult

        result = BrowseResult(
            table="ORDERS", connection_name="connection",
            columns=["ID", "VALUE"], rows=[[1, "10.50"], [2, "20.00"]],
            row_count=2, total_count=1284, elapsed=0.12, limit=100, offset=0,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table", return_value=result):
            run_cli(["rows", "ORDERS", "connection", "-f", "json"])

        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "rows"
        assert body["data"]["rows"] == [[1, "10.50"], [2, "20.00"]]
        assert body["data"]["total_count"] == 1284

    def test_limit_and_offset_reach_the_core_call(self):
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.table_browser import BrowseResult

        empty_one = BrowseResult(table="T", connection_name="c", columns=[], rows=[],
                             row_count=0, total_count=0, elapsed=0.0,
                             limit=10, offset=50)
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table", return_value=empty_one) as mock_browse:
            run_cli(["rows", "ORDERS", "connection", "--limit", "10",
                     "--offset", "50", "-f", "json"])

        assert mock_browse.call_args.kwargs["limit"] == 10
        assert mock_browse.call_args.kwargs["offset"] == 50

    def test_a_negative_limit_is_usage_not_a_database_call(self, capsys):
        """Validation happens before the connection opens: a bad flag should
        not cost a round trip."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection") as mock_open:
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "ORDERS", "connection", "--limit", "-5", "-f", "json"])

        assert capsys.readouterr().out == ""
        assert exited.value.code == 2
        mock_open.assert_not_called()

    def test_a_rejected_table_name_is_usage_not_sql_error(self, capsys):
        """`browse_table` validates the identifier and raises `ValueError`;
        that is bad input, not a statement the driver rejected. See
        `TestRowsOnAMissingTable` for the fuller case, including that the
        existence check must not run on this path."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table",
                   side_effect=ValueError("Identificador invalido")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "ORDERS; DROP TABLE X", "connection", "-f", "json"])

        assert capsys.readouterr().out == ""
        assert exited.value.code == 2

    def test_table_format_says_there_is_more_beyond_the_page(self, capsys):
        """`QueryResult` has no `total_count`, so the renderer cannot report
        it: without this line a human sees 3 rows of six hundred and nothing
        to suggest a second page exists. The JSON payload has always carried
        the number; this is the same fact for the reader."""
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.table_browser import BrowseResult

        result = BrowseResult(
            table="ORDERS", connection_name="connection",
            columns=["ID"], rows=[[1], [2], [3]],
            row_count=3, total_count=636, elapsed=0.1, limit=3, offset=0,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.browse_table", return_value=result):
            run_cli(["rows", "ORDERS", "connection", "--limit", "3"])

        output = capsys.readouterr().out
        assert "636" in output, "the total must reach the human, not only the JSON"
        assert "--offset 3" in output, "and it must say how to get the next page"

    def test_the_last_page_says_nothing_extra(self, capsys):
        """The counterpart: when the page is the whole table, a line about
        more rows would be a lie."""
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.table_browser import BrowseResult

        result = BrowseResult(
            table="PEQUENA", connection_name="connection",
            columns=["ID"], rows=[[1], [2]],
            row_count=2, total_count=2, elapsed=0.1, limit=100, offset=0,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.browse_table", return_value=result):
            run_cli(["rows", "PEQUENA", "connection"])

        assert "--offset" not in capsys.readouterr().out

    def test_raw_format_prints_values_with_no_decoration(self, capsys):
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.table_browser import BrowseResult

        result = BrowseResult(
            table="T", connection_name="c", columns=["TEXTO"],
            rows=[["linha um"], ["linha dois"]],
            row_count=2, total_count=2, elapsed=0.0, limit=100, offset=0,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table", return_value=result):
            run_cli(["rows", "T", "connection", "-f", "raw"])

        output = capsys.readouterr().out
        # Exact equality, not a substring check: Rich renders `table` format
        # with unicode box-drawing characters here (no ASCII "|"), so a
        # "|" not in saida" check cannot tell raw apart from table -- it
        # would pass even if `args.format` were hardcoded to "table" below.
        assert output == "linha um\nlinha dois\n"


class TestForceWrite:
    """`--force-write` lifts the refusal to send. `--commit` still governs
    persistence, exactly as on every other connection."""

    def _protected(self):
        from dbqm.models.connection import Connection

        return Connection(name="SS", db_type="postgresql", user="u",
                          password="", read_only=True)

    def test_a_write_without_the_flag_is_refused(self, capsys):
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=self._protected()):
            with pytest.raises(SystemExit) as exited:
                run_cli(["sql", "DELETE FROM t", "SS", "-f", "json", "--commit"])

        captured = capsys.readouterr()
        assert captured.out == "", "the rule the whole contract exists for"
        assert exited.value.code == 2
        body = json.loads(captured.err)
        assert body["error"]["code"] == "read_only"
        assert "--force-write" in body["error"]["message"]

    def test_the_flag_lifts_the_refusal(self):
        """What reaches `core/` is a connection whose flag is off -- the CLI
        resolves the override at its own boundary, so `core/` has one rule."""
        from unittest.mock import patch

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=self._protected()), \
             patch("dbqm.ops.deps.execute_adhoc") as mock_exec:
            mock_exec.return_value = _make_adhoc_result()
            run_cli(["sql", "DELETE FROM t", "SS", "--force-write", "--commit"])

        passed = mock_exec.call_args[0][1]
        assert passed.read_only is False, "core sees a writable connection"
        assert passed.name == "SS", "and it is still the same connection"

    def test_the_flag_alone_does_not_commit(self):
        """One flag, one meaning: --force-write answers "may I write here",
        --commit answers "should it persist". Fusing them is what would leave
        DML unprotected, since `sql` has always required --commit for it."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=self._protected()):
            with pytest.raises(SystemExit) as exited:
                run_cli(["sql", "DELETE FROM t", "SS", "--force-write", "-f", "json"])

        assert exited.value.code == 2, "DML still requires --commit"

    def test_the_read_only_refusal_comes_before_the_commit_one(self, capsys):
        """Reporting the missing --commit first sends the user to add it and
        only then meet the real obstacle -- two round trips to learn the
        connection is protected. The guard inside `execute_adhoc` still
        enforces it for every other caller; this is about which refusal the
        user reads."""
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=self._protected()):
            with pytest.raises(SystemExit) as exited:
                run_cli(["sql", "DELETE FROM t", "SS", "-f", "json"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert exited.value.code == 2
        body = json.loads(captured.err)
        assert body["error"]["code"] == "read_only", (
            "not `usage` about --commit: the connection being protected is "
            "the obstacle, and adding --commit would not clear it"
        )

    def test_a_select_needs_no_flag(self, capsys):
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=self._protected()), \
             patch("dbqm.ops.deps.execute_adhoc") as mock_exec:
            mock_exec.return_value = _make_adhoc_result()
            run_cli(["sql", "SELECT 1", "SS", "-f", "json"])

        assert json.loads(capsys.readouterr().out)["ok"] is True

    def test_the_saved_connection_is_not_modified(self):
        """The override is transient. A run with --force-write must not
        persist an unlocked connection."""
        from unittest.mock import patch

        from dbqm.cli import run_cli

        connection = self._protected()
        with patch("dbqm.ops.deps.find_connection", return_value=connection), \
             patch("dbqm.ops.deps.execute_adhoc") as mock_exec:
            mock_exec.return_value = _make_adhoc_result()
            run_cli(["sql", "DELETE FROM t", "SS", "--force-write", "--commit"])

        assert connection.read_only is True, "the stored object is untouched"


class TestConnectionReadOnlyFlag:
    def test_add_marks_the_connection(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "protegida", "--type", "mysql",
                 "--host", "h", "--user", "u", "--no-password", "--read-only"])
        capsys.readouterr()
        run_cli(["connection", "show", "protegida", "-f", "json"])

        assert json.loads(capsys.readouterr().out)["data"]["read_only"] is True

    def test_update_can_unlock(self, tmp_config_dir, capsys):
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "protegida", "--type", "mysql",
                 "--host", "h", "--user", "u", "--no-password", "--read-only"])
        run_cli(["connection", "update", "protegida", "--no-read-only"])
        capsys.readouterr()
        run_cli(["connection", "show", "protegida", "-f", "json"])

        assert json.loads(capsys.readouterr().out)["data"]["read_only"] is False

    def test_an_unrelated_update_does_not_unlock(self, tmp_config_dir, capsys):
        """The rule that makes the field worth having: changing the host must
        not quietly remove the protection."""
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "protegida", "--type", "mysql",
                 "--host", "h", "--user", "u", "--no-password", "--read-only"])
        run_cli(["connection", "update", "protegida", "--host", "outro"])
        capsys.readouterr()
        run_cli(["connection", "show", "protegida", "-f", "json"])

        assert json.loads(capsys.readouterr().out)["data"]["read_only"] is True

    def test_list_reports_it(self, tmp_config_dir, capsys):
        """An agent should be able to ask before it tries."""
        import json

        from dbqm.cli import run_cli

        run_cli(["connection", "add", "protegida", "--type", "mysql",
                 "--host", "h", "--user", "u", "--no-password", "--read-only"])
        capsys.readouterr()
        run_cli(["connection", "list", "-f", "json"])

        lines = json.loads(capsys.readouterr().out)["data"]
        assert lines[0]["read_only"] is True


class TestConnectionFailedIsReachable:
    """Exit 3 has been in the published table since 2.0.0 and `run`/`sql`
    could never produce it: both failures arrived as one string."""

    def test_sql_exits_three_when_the_database_never_answered(self, capsys):
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        failed = _make_adhoc_result(success=False, error="no listener",
                                    error_kind="connection")
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=failed):
            with pytest.raises(SystemExit) as exited:
                run_cli(["sql", "SELECT 1", "connection", "-f", "json"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert exited.value.code == 3
        assert json.loads(captured.err)["error"]["code"] == "connection_failed"

    def test_sql_still_exits_four_when_the_statement_was_rejected(self, capsys):
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        failed = _make_adhoc_result(success=False, error="ORA-00942",
                                    error_kind="statement")
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.execute_adhoc", return_value=failed):
            with pytest.raises(SystemExit) as exited:
                run_cli(["sql", "SELECT 1", "connection", "-f", "json"])

        assert exited.value.code == 4
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "sql_error"

    def test_run_exits_three_too(self, capsys):
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        failed = _make_query_result(success=False, error="no listener",
                                    error_kind="connection")
        with patch("dbqm.ops.deps.find_query", return_value=_make_query()), \
             patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.execute_query", return_value=failed), \
             patch("dbqm.ops.deps.record_query_execution"), \
             patch("dbqm.ops.deps.log_execution"):
            with pytest.raises(SystemExit) as exited:
                run_cli(["run", "test_query", "-f", "json"])

        assert exited.value.code == 3

    def test_the_bad_input_messages_still_map_to_usage(self, capsys):
        """`_sql_error_code`'s existing job must survive: input `core/` never
        sent to a driver is a usage error, not a statement failure.

        Read from `error_kind`, not from the message: the message is a
        translation now, and a classifier that reads one would be right in
        one language and wrong in the others.
        """
        from dbqm.ops.sql import sql_error_code as _sql_error_code

        assert _sql_error_code("qualquer coisa", "usage") == "usage"
        assert _sql_error_code("ORA-00942: tabela inexistente",
                               "statement") == "sql_error"


class TestRowsOnAMissingTable:
    """`describe` and `rows` disagreed about the same missing name: 2 versus
    4. Each is defensible alone -- `describe` reads metadata and finds
    nothing, `rows` runs SELECT COUNT(*) and the driver rejects it -- but an
    agent branches on `error.code`, and the pair is not."""

    def test_a_missing_table_is_not_found(self, capsys):
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table",
                   side_effect=RuntimeError('relation "nada" does not exist')), \
             patch("dbqm.ops.deps.list_objects", return_value=["OUTRA"]):
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "NADA", "connection", "-f", "json"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert exited.value.code == 2
        assert json.loads(captured.err)["error"]["code"] == "not_found"

    def test_a_real_failure_on_a_table_that_exists_stays_sql_error(self, capsys):
        """The check must not swallow genuine SQL failures."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table",
                   side_effect=RuntimeError("ORA-01013: user requested cancel")), \
             patch("dbqm.ops.deps.list_objects", return_value=["ORDERS"]):
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "ORDERS", "connection", "-f", "json"])

        assert exited.value.code == 4

    def test_a_rejected_identifier_is_usage_not_not_found(self, capsys):
        """`_validate_identifier` raises ValueError for a name it refuses to
        put in a statement. That is bad input, not a missing table, and it
        must not send the existence check looking."""
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table",
                   side_effect=ValueError("Identificador invalido")), \
             patch("dbqm.ops.deps.list_objects") as mock_list:
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "X; DROP", "connection", "-f", "json"])

        assert exited.value.code == 2
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "usage"
        # No point asking whether a name the code already refused exists.
        mock_list.assert_not_called()

    def test_a_failing_existence_check_does_not_replace_the_real_error(self, capsys):
        """The diagnosis must never become the diagnosis.

        If `list_objects` itself fails -- no permission on the catalogue, a
        transient outage -- the user has to learn what their own query did
        wrong, not what the check did wrong. A bare `raise` inside the nested
        handler re-raises the inner exception, which is precisely the bug this
        pins: the original is raised by name.
        """
        import json
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.open_connection"),              patch("dbqm.ops.deps.browse_table",
                   side_effect=RuntimeError("ORA-01013: cancelled by the user")),              patch("dbqm.ops.deps.list_objects",
                   side_effect=RuntimeError("ORA-00942: sem permissao em ALL_TABLES")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "T", "connection", "-f", "json"])

        body = json.loads(capsys.readouterr().err)["error"]
        assert exited.value.code == 4
        assert "ORA-01013" in body["message"], "the user's own error survives"
        assert "ALL_TABLES" not in body["message"], (
            "the existence check's failure must not surface as the answer"
        )

    def test_the_existence_check_costs_nothing_on_success(self):
        """It runs only on the error path."""
        from unittest.mock import patch

        from dbqm.cli import run_cli
        from dbqm.core.table_browser import BrowseResult

        ok_result = BrowseResult(
            table="T", connection_name="c", columns=["A"], rows=[[1]],
            row_count=1, total_count=1, elapsed=0.0, limit=100, offset=0,
        )
        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table", return_value=ok_result), \
             patch("dbqm.ops.deps.list_objects") as mock_list:
            run_cli(["rows", "T", "connection", "-f", "json"])

        mock_list.assert_not_called()

    def test_a_view_that_fails_is_not_reported_as_missing(self, capsys):
        """`list_objects(db, db_type, "TABLE")` will not find a view -- a
        genuine failure against a name that is a valid view must not be
        misreported as `not_found` just because it is absent from the TABLE
        list. The check must also ask about `"VIEW"` before concluding the
        object is absent."""
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        def fake_list_objects(db, db_type, obj_type):
            if obj_type == "VIEW":
                return ["V_PEDIDOS"]
            return []

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.open_connection"), \
             patch("dbqm.ops.deps.browse_table",
                   side_effect=RuntimeError("driver rejected the count")), \
             patch("dbqm.ops.deps.list_objects",
                   side_effect=fake_list_objects) as mock_list:
            with pytest.raises(SystemExit) as exited:
                run_cli(["rows", "V_PEDIDOS", "connection", "-f", "json"])

        assert exited.value.code == 4
        assert {c.args[2] for c in mock_list.call_args_list} == {"TABLE", "VIEW"}


class TestDdlAgreesWithTheRest:
    """`ddl` was the pair that still disagreed. A missing object answered
    `sql_error` where `describe` and `rows` both say `not_found`, and an
    unreachable database escaped as an unhandled exception -- exit 1, "a bug
    in dbqm", for a database that was merely down."""

    def _extraction(self, errors, not_found=False):
        from dbqm.core.ddl_extractor import ExtractionResult

        r = ExtractionResult(object_name="OBJ", object_type="TABLE",
                             owner="", connection_name="connection")
        r.errors = errors
        r.not_found = not_found
        return r

    def test_an_unreachable_database_exits_three(self, capsys):
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.extract_ddl",
                   side_effect=RuntimeError("ORA-12541: TNS sem listener")):
            with pytest.raises(SystemExit) as exited:
                run_cli(["ddl", "OBJ", "connection", "-f", "json"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert exited.value.code == 3, "not 1: the database was down, not dbqm"
        assert json.loads(captured.err)["error"]["code"] == "connection_failed"

    def test_a_missing_object_is_not_found(self, capsys):
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.extract_ddl",
                   return_value=self._extraction(["Object 'OBJ' not found."],
                                               not_found=True)):
            with pytest.raises(SystemExit) as exited:
                run_cli(["ddl", "OBJ", "connection", "-f", "json"])

        assert exited.value.code == 2, "the same answer describe and rows give"
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "not_found"

    def test_a_real_extraction_failure_stays_sql_error(self, capsys):
        from unittest.mock import patch

        import pytest

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()),              patch("dbqm.ops.deps.extract_ddl",
                   return_value=self._extraction(["Erro ao extrair TABLE: ORA-01013"])):
            with pytest.raises(SystemExit) as exited:
                run_cli(["ddl", "OBJ", "connection", "-f", "json"])

        assert exited.value.code == 4


class TestDdlStdout:
    """--stdout says "print to stdout instead of saving to a file" in its
    own help text. The json branch never read it."""

    def test_stdout_writes_nothing_to_disk(self, capsys):
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.extract_ddl", return_value=_make_extraction()), \
             patch("dbqm.ops.deps.save_extraction") as mock_save:
            run_cli(["ddl", "OBJ", "connection", "--stdout", "-f", "json"])

        mock_save.assert_not_called()
        body = json.loads(capsys.readouterr().out)
        assert body["data"]["path"] is None, (
            "the same shape either way -- the value carries the answer"
        )

    def test_without_the_flag_it_still_saves(self, capsys):
        import json
        from unittest.mock import patch

        from dbqm.cli import run_cli

        with patch("dbqm.ops.deps.find_connection", return_value=_make_connection()), \
             patch("dbqm.ops.deps.extract_ddl", return_value=_make_extraction()), \
             patch("dbqm.ops.deps.save_extraction", return_value=("/algum/caminho", 2)) as mock_save:
            run_cli(["ddl", "OBJ", "connection", "-f", "json"])

        mock_save.assert_called_once()
        assert json.loads(capsys.readouterr().out)["data"]["path"] is not None


# ---------------------------------------------------------------------------
# describe-cli
# ---------------------------------------------------------------------------

class TestCmdDescribeCli:
    """`describe-cli` must never hand-maintain a list of its own: every
    assertion here reads `COMMAND_MAP` or the live parser, not a list typed
    into this test file.
    """

    def test_describe_lists_every_command_in_the_dispatch_map(self, capsys):
        """Set equality, not containment: a command added later without a
        doc entry must fail this test rather than go silently undescribed.
        """
        run_cli(["describe-cli", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "describe-cli"
        names = {c["name"] for c in body["data"]["commands"]}
        assert names == set(COMMAND_MAP)

    def test_each_command_carries_its_help_and_arguments(self, capsys):
        run_cli(["describe-cli", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        by_name = {c["name"]: c for c in body["data"]["commands"]}

        sql = by_name["sql"]
        assert sql["help"]
        flags = {tuple(arg["flags"]): arg for arg in sql["arguments"]}
        format_ = flags[("-f", "--format")]
        assert format_["choices"] == ["table", "json", "csv", "raw"]
        assert format_["help"]

        # A bare positional (no option strings) is still reported, flagged
        # by its dest, and required.
        positional = flags[("sql",)]
        assert positional["required"] is True
        assert positional["choices"] is None

    def test_nothing_is_hand_written(self, capsys):
        """The payload must come from the parser, so a flag added to an
        existing command appears without anyone editing `describe_cli.py`.
        `--force-write` exists only in the `sql` subparser -- it is never
        mentioned by name in `dbqm/cli/commands/describe_cli.py`.
        """
        import dbqm.cli.commands.describe_cli as describe_cli_module

        source = Path(describe_cli_module.__file__).read_text(encoding="utf-8")
        assert "force-write" not in source
        assert "force_write" not in source

        run_cli(["describe-cli", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        by_name = {c["name"]: c for c in body["data"]["commands"]}
        sql_flags = {tuple(arg["flags"]) for arg in by_name["sql"]["arguments"]}
        assert ("--force-write",) in sql_flags

    def test_nested_subcommands_carry_their_own_arguments(self, capsys):
        """A parser with a subparsers action of its own recurses: each
        subcommand is described
        the same way -- `name`, `help`, `arguments` -- under a `subcommands`
        key, not merely named by an opaque `choices` list. `--read-only`
        exists only on `connection add`/`connection update` and is never
        mentioned in `describe_cli.py`, same trick as `--force-write` above.
        """
        import dbqm.cli.commands.describe_cli as describe_cli_module

        source = Path(describe_cli_module.__file__).read_text(encoding="utf-8")
        assert "read-only" not in source
        assert "read_only" not in source

        run_cli(["describe-cli", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        by_name = {c["name"]: c for c in body["data"]["commands"]}
        connection = by_name["connection"]

        # The nested group itself carries no opaque "subcommand" argument
        # once it has a `subcommands` key -- the flags for its children live
        # under that key instead, described the same way as a top-level one.
        assert {tuple(a["flags"]) for a in connection["arguments"]} == set()

        sub_by_name = {s["name"]: s for s in connection["subcommands"]}
        assert sub_by_name.keys() == {"add", "update", "show", "rm", "list"}
        add = sub_by_name["add"]
        assert add["help"]
        add_flags = {tuple(a["flags"]) for a in add["arguments"]}
        assert ("--read-only",) in add_flags

    def test_an_uninitialized_parser_is_unexpected_not_a_false_success(self, monkeypatch, capsys):
        """`_subparsers_action` is `None` only before `build_parser` has run.
        That must never look like "dbqm has zero commands" -- a confidently
        wrong success -- so it is reported as `unexpected` (exit 1) instead.
        """
        import argparse

        import dbqm.cli.commands.describe_cli as describe_cli_module

        monkeypatch.setattr(describe_cli_module, "_subparsers_action", None)

        with pytest.raises(SystemExit) as exited:
            describe_cli_module.cmd_describe_cli(argparse.Namespace(format="json"))
        assert exited.value.code == 1
        body = json.loads(capsys.readouterr().err)
        assert body["ok"] is False
        assert body["error"]["code"] == "unexpected"

    def test_table_format_prints_a_summary_without_the_envelope(self, capsys):
        run_cli(["describe-cli"])
        output = capsys.readouterr().out
        assert '"ok"' not in output
        # The argument-table header pins that real per-argument tables are
        # printed, and "describe-cli" (its own self-description) pins that
        # the command's name -- not just its help text -- reaches the line:
        # neither string can appear here by accident of some other command's
        # Portuguese help text.
        assert "Flags" in output
        assert "describe-cli" in output


# ---------------------------------------------------------------------------
# oracle-client subcommand
# ---------------------------------------------------------------------------

class TestCmdOracleClient:
    """`install` is the only dbqm command that reaches the internet, so every
    test here patches `deps.install_client` instead of letting it run — a
    real download would be slow, flaky, and dependent on Oracle's CDN
    staying up. `list`/`rm` patch `oracle_client_installer.CLIENTS_DIR`
    itself (same trick as `tests/core/test_oracle_client_installer.py`) so
    nothing touches a real install location either.
    """

    def test_list_on_a_machine_with_none_installed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        run_cli(["oracle-client", "list", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "oracle-client.list"
        assert body["data"] == []

    def test_list_with_a_client_actually_installed(self, tmp_path, monkeypatch, capsys):
        """The empty case above is only meaningful by contrast with this one
        -- an `_oracle_client_list` hardcoded to always return `[]` would
        pass the empty test and fail only here."""
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        target = tmp_path / "instantclient_23_x64"
        target.mkdir()
        (target / "BASIC_README").write_text(
            "Basic Package Information\nClient Shared Library 64-bit - 23.26.1.0.0\n",
            encoding="utf-8",
        )

        run_cli(["oracle-client", "list", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["data"] == [
            {"name": "instantclient_23_x64", "path": str(target), "version": "23.26.1.0.0"},
        ]

    def test_list_table_format_prints_the_version(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        target = tmp_path / "instantclient_23_x64"
        target.mkdir()
        (target / "BASIC_README").write_text(
            "Basic Package Information\nClient Shared Library 64-bit - 23.26.1.0.0\n",
            encoding="utf-8",
        )

        run_cli(["oracle-client", "list"])
        output = capsys.readouterr().out
        assert '"ok"' not in output
        assert "23.26.1.0.0" in output
        assert "instantclient_23_x64" in output

    def test_available_on_an_unsupported_host_is_usage_naming_the_platform(
        self, monkeypatch, capsys,
    ):
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("plan9", "riscv"))
        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client", "available", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert "plan9/riscv" in body["error"]["message"]

    def test_available_table_format_prints_the_catalog(self, monkeypatch, capsys):
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))

        run_cli(["oracle-client", "available"])
        output = capsys.readouterr().out
        assert '"ok"' not in output
        assert "23.26.1.0.0" in output

    def test_install_calls_through_with_the_named_version(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))
        dest = tmp_path / "instantclient_23_x64"
        spy = MagicMock(return_value=dest)
        monkeypatch.setattr("dbqm.ops.deps.install_client", spy)

        run_cli(["oracle-client", "install", "23.26.1.0.0", "-f", "json"])

        spy.assert_called_once()
        called_pkg = spy.call_args.args[0]
        assert called_pkg.version == "23.26.1.0.0"
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is True
        assert body["command"] == "oracle-client.install"
        assert body["data"]["version"] == "23.26.1.0.0"
        assert body["data"]["path"] == str(dest)

    def test_install_on_an_unknown_version_is_usage(self, monkeypatch, capsys):
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))
        spy = MagicMock()
        monkeypatch.setattr("dbqm.ops.deps.install_client", spy)

        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client", "install", "9.9.9.9.9", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        spy.assert_not_called()

    def test_install_whose_underlying_call_raises_is_unexpected(self, monkeypatch, capsys):
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))
        monkeypatch.setattr(
            "dbqm.ops.deps.install_client",
            MagicMock(side_effect=RuntimeError("truncated file")),
        )

        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client", "install", "23.26.1.0.0", "-f", "json"])
        assert exc.value.code == 1
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "unexpected"
        assert "truncated file" in body["error"]["message"]

    def test_install_on_a_dir_that_already_exists_is_usage(self, monkeypatch, capsys):
        """`install_client`'s own `FileExistsError` -- the target directory is
        already occupied -- is a precondition the user can fix (remove it
        first), not something dbqm could not handle. `usage`, not
        `unexpected`."""
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))
        monkeypatch.setattr(
            "dbqm.ops.deps.install_client",
            MagicMock(side_effect=FileExistsError("Directory already exists with content: X")),
        )

        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client", "install", "23.26.1.0.0", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"

    def test_install_progress_goes_to_stderr_under_json_leaving_stdout_the_envelope(
        self, monkeypatch, capsys, tmp_path,
    ):
        """The whole reason `install` routes progress to stderr: the
        envelope on stdout must stay parseable even while progress lines are
        being written."""
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))
        dest = tmp_path / "instantclient_23_x64"

        def fake_install(pkg, progress=None):
            progress(50, 100)
            progress(100, 100)
            return dest

        monkeypatch.setattr("dbqm.ops.deps.install_client", MagicMock(side_effect=fake_install))

        run_cli(["oracle-client", "install", "23.26.1.0.0", "-f", "json"])
        output = capsys.readouterr()
        assert "50%" in output.err
        assert "100%" in output.err
        body = json.loads(output.out)
        assert body["ok"] is True
        assert body["command"] == "oracle-client.install"

    def test_install_progress_reaches_stdout_under_table(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr("dbqm.ops.deps.detect_host_platform", lambda: ("win32", "x64"))
        dest = tmp_path / "instantclient_23_x64"

        def fake_install(pkg, progress=None):
            progress(50, 100)
            progress(100, 100)
            return dest

        monkeypatch.setattr("dbqm.ops.deps.install_client", MagicMock(side_effect=fake_install))

        run_cli(["oracle-client", "install", "23.26.1.0.0"])
        output = capsys.readouterr()
        assert output.err == ""
        assert "50%" in output.out
        assert "100%" in output.out

    def test_rm_with_yes_removes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        target = tmp_path / "instantclient_23_x64"
        target.mkdir()
        (target / "oci.dll").write_text("stub")

        run_cli(["oracle-client", "rm", "instantclient_23_x64", "--yes"])

        assert not target.exists()

    def test_rm_without_yes_and_without_a_tty_is_usage_and_deletes_nothing(
        self, tmp_path, monkeypatch, capsys,
    ):
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        target = tmp_path / "instantclient_23_x64"
        target.mkdir()
        (target / "oci.dll").write_text("stub")
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client", "rm", "instantclient_23_x64", "-f", "json"])
        assert exc.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert target.exists(), "a refusal must not remove"

    def test_rm_on_a_tty_honours_a_no(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        target = tmp_path / "instantclient_23_x64"
        target.mkdir()
        (target / "oci.dll").write_text("stub")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")

        run_cli(["oracle-client", "rm", "instantclient_23_x64"])

        assert target.exists(), "a cancelled removal must not remove"

    def test_bare_oracle_client_command_exits_2(self):
        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client"])
        assert exc.value.code == 2

    def test_bare_oracle_client_command_prints_the_group_help(self, capsys):
        """A bare `dbqm oracle-client` must print the group's own help, not a
        one-line usage reminder -- mirrors `TestCmdTemplate`'s own
        bare-command test."""
        with pytest.raises(SystemExit) as exc:
            run_cli(["oracle-client"])
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "usage:" in out.lower(), "expected argparse's own help, not a one-line reminder"
        assert "Download and install an Oracle Instant Client" in out, \
            "expected each subcommand's own help text, e.g. install's, to be listed"



class TestSqliteFromTheCli:
    """The fifth engine through the commands. `build` and `to_dict` already
    do the work; these pin that the CLI reaches them and that the result
    reads like a file, not like a server with an empty host."""

    def test_add_then_show_carries_the_file_and_no_host(self, tmp_config_dir, capsys):
        run_cli(["connection", "add", "local", "--type", "sqlite",
                 "--database", "meu.db", "--no-password", "-f", "json"])
        capsys.readouterr()
        run_cli(["connection", "show", "local", "-f", "json"])
        body = json.loads(capsys.readouterr().out)
        assert body["data"]["db_type"] == "sqlite"
        assert body["data"]["database"] == "meu.db"
        assert "host" not in body["data"]
        assert "port" not in body["data"]

    def test_a_host_typed_for_sqlite_is_refused_by_name(self, tmp_config_dir, capsys):
        with pytest.raises(SystemExit) as exited:
            run_cli(["connection", "add", "local", "--type", "sqlite",
                     "--database", "meu.db", "--host", "srv", "--no-password", "-f", "json"])
        assert exited.value.code == 2
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "validation"
        assert "host" in body["error"]["message"]

    def test_call_refuses_sqlite_before_any_connection_opens(self, tmp_config_dir, capsys):
        """Same refusal as PostgreSQL gets: an anonymous PL/SQL block has no
        equivalent, and `db_type` is known without opening anything."""
        conn = Connection(name="local", db_type="sqlite", user="", password="",
                          database=":memory:")
        with patch("dbqm.ops.deps.find_connection", return_value=conn), \
             patch("dbqm.ops.deps.open_connection") as mock_open:
            with pytest.raises(SystemExit) as exited:
                run_cli(["call", "PKG.ROUTINE", "local", "-f", "json"])
            assert exited.value.code == 2
            mock_open.assert_not_called()
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["code"] == "usage"
        assert "sqlite" in body["error"]["message"]

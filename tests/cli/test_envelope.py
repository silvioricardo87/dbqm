"""Tests for the JSON envelope.

The rule these protect: under `-f json`, stdout carries the envelope and
nothing else. Before it existed, `dbqm connection show inexistente -f json`
printed Portuguese prose to stdout and `| jq` failed.
"""
from __future__ import annotations

import json

import pytest

from dbqm.cli.envelope import fail, ok


class TestOk:
    def test_success_goes_to_stdout_as_one_object(self, capsys):
        ok("connection.show", {"name": "prod"})
        output = capsys.readouterr()
        assert output.err == "", "success writes nothing to stderr"
        body = json.loads(output.out)
        assert body == {"ok": True, "command": "connection.show",
                         "data": {"name": "prod"}}

    def test_a_list_payload_stays_a_list_under_data(self, capsys):
        ok("list.connections", [{"name": "a"}, {"name": "b"}])
        body = json.loads(capsys.readouterr().out)
        assert body["data"] == [{"name": "a"}, {"name": "b"}]

    def test_warnings_ride_as_data_not_as_prose(self, capsys):
        ok("sql", {"rows": []}, warnings=["2 conjuntos retornados"])
        body = json.loads(capsys.readouterr().out)
        assert body["warnings"] == ["2 conjuntos retornados"]

    def test_no_warnings_key_when_there_are_none(self, capsys):
        ok("sql", {"rows": []})
        assert "warnings" not in json.loads(capsys.readouterr().out)

    def test_accents_survive(self, capsys):
        """ensure_ascii=False: a description may carry them even though UI
        labels do not."""
        ok("connection.show", {"description": "Pre Production é"})
        assert "é" in capsys.readouterr().out


class TestFail:
    def test_failure_goes_to_stderr_and_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            fail("connection.show", "not_found", 'Connection "x" not found.')
        assert exc.value.code == 2

        output = capsys.readouterr()
        assert output.out == "", (
            "stdout must stay empty on failure — this is the whole point: a "
            "consumer parsing stdout must not meet an error there"
        )
        body = json.loads(output.err)
        assert body["ok"] is False
        assert body["command"] == "connection.show"
        assert body["error"]["code"] == "not_found"
        assert body["error"]["exit"] == 2
        assert "not found" in body["error"]["message"]

    def test_detail_is_carried_when_given(self, capsys):
        with pytest.raises(SystemExit):
            fail("sql", "sql_error", "Execution failed.", detail="ORA-00942")
        body = json.loads(capsys.readouterr().err)
        assert body["error"]["detail"] == "ORA-00942"

    def test_no_detail_key_when_absent(self, capsys):
        with pytest.raises(SystemExit):
            fail("sql", "sql_error", "Execution failed.")
        assert "detail" not in json.loads(capsys.readouterr().err)["error"]

    def test_each_code_carries_its_exit(self, capsys):
        for code, expected in [
            ("usage", 2), ("validation", 2), ("connection_failed", 3),
            ("sql_error", 4), ("divergent", 5), ("unexpected", 1),
        ]:
            with pytest.raises(SystemExit) as exc:
                fail("cmd", code, "msg")
            assert exc.value.code == expected
            assert json.loads(capsys.readouterr().err)["error"]["exit"] == expected

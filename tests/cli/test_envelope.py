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
        saida = capsys.readouterr()
        assert saida.err == "", "success writes nothing to stderr"
        corpo = json.loads(saida.out)
        assert corpo == {"ok": True, "command": "connection.show",
                         "data": {"name": "prod"}}

    def test_a_list_payload_stays_a_list_under_data(self, capsys):
        ok("list.connections", [{"name": "a"}, {"name": "b"}])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["data"] == [{"name": "a"}, {"name": "b"}]

    def test_warnings_ride_as_data_not_as_prose(self, capsys):
        ok("sql", {"rows": []}, warnings=["2 conjuntos retornados"])
        corpo = json.loads(capsys.readouterr().out)
        assert corpo["warnings"] == ["2 conjuntos retornados"]

    def test_no_warnings_key_when_there_are_none(self, capsys):
        ok("sql", {"rows": []})
        assert "warnings" not in json.loads(capsys.readouterr().out)

    def test_accents_survive(self, capsys):
        """ensure_ascii=False: a description may carry them even though UI
        labels do not."""
        ok("connection.show", {"description": "Pre Producao é"})
        assert "é" in capsys.readouterr().out


class TestFail:
    def test_failure_goes_to_stderr_and_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            fail("connection.show", "not_found", 'Conexao "x" nao encontrada.')
        assert exc.value.code == 2

        saida = capsys.readouterr()
        assert saida.out == "", (
            "stdout must stay empty on failure — this is the whole point: a "
            "consumer parsing stdout must not meet an error there"
        )
        corpo = json.loads(saida.err)
        assert corpo["ok"] is False
        assert corpo["command"] == "connection.show"
        assert corpo["error"]["code"] == "not_found"
        assert corpo["error"]["exit"] == 2
        assert "nao encontrada" in corpo["error"]["message"]

    def test_detail_is_carried_when_given(self, capsys):
        with pytest.raises(SystemExit):
            fail("sql", "sql_error", "Erro ao executar.", detail="ORA-00942")
        corpo = json.loads(capsys.readouterr().err)
        assert corpo["error"]["detail"] == "ORA-00942"

    def test_no_detail_key_when_absent(self, capsys):
        with pytest.raises(SystemExit):
            fail("sql", "sql_error", "Erro ao executar.")
        assert "detail" not in json.loads(capsys.readouterr().err)["error"]

    def test_each_code_carries_its_exit(self, capsys):
        for code, esperado in [
            ("usage", 2), ("validation", 2), ("connection_failed", 3),
            ("sql_error", 4), ("divergent", 5), ("unexpected", 1),
        ]:
            with pytest.raises(SystemExit) as exc:
                fail("cmd", code, "msg")
            assert exc.value.code == esperado
            assert json.loads(capsys.readouterr().err)["error"]["exit"] == esperado

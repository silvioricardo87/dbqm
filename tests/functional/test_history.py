"""docs/qa/history.md — reading the history back after real runs."""
from __future__ import annotations

import pytest

from tests.functional.conftest import envelope, invoke


@pytest.fixture
def ativos(local_db, capsys) -> str:
    code, _ = envelope(
        ["query", "add", "ativos", "--connection", "local",
         "--sql", "SELECT id FROM clientes WHERE status = 'A'", "-f", "json"],
        capsys,
    )
    assert code == 0
    return "ativos"


def _history(capsys, *extra: str) -> list[dict]:
    code, body = envelope(["history", *extra, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "history"
    return body["data"]


# QA-HIST-001
def test_an_empty_history_is_an_empty_list(local_db, capsys):
    assert _history(capsys) == []


# QA-HIST-002
def test_each_run_is_one_entry_with_its_facts(ativos, capsys):
    for _ in range(2):
        code, _ = envelope(["run", ativos, "-f", "json"], capsys)
        assert code == 0
    registros = _history(capsys)
    assert len(registros) == 2
    for r in registros:
        assert r["entry_type"] == "query"
        assert r["name"] == "ativos"
        assert r["connection"] == "local"
        assert r["success"] is True
        assert r["row_count"] == 2
        assert r["id"] and r["timestamp"]
    assert registros[0]["id"] != registros[1]["id"]


# QA-HIST-003
def test_a_failed_run_is_recorded_with_its_error(local_db, capsys):
    code, _ = envelope(
        ["query", "add", "quebrada", "--connection", "local", "--sql", "SELECT * FROM nao_existe", "-f", "json"], capsys,
    )
    assert code == 0
    code, _ = envelope(["run", "quebrada", "-f", "json"], capsys)
    assert code == 4
    registros = _history(capsys)
    assert len(registros) == 1
    assert registros[0]["success"] is False
    assert registros[0]["error"] == "no such table: nao_existe"


# QA-HIST-004
def test_n_caps_the_count_newest_first(ativos, capsys):
    for _ in range(3):
        code, _ = envelope(["run", ativos, "-f", "json"], capsys)
        assert code == 0
    todos = _history(capsys)
    assert len(todos) == 3
    dois = _history(capsys, "-n", "2")
    assert [r["id"] for r in dois] == [r["id"] for r in todos[:2]]
    assert todos[0]["timestamp"] >= todos[-1]["timestamp"]


# QA-HIST-005
def test_clear_empties_it(ativos, capsys):
    code, _ = envelope(["run", ativos, "-f", "json"], capsys)
    assert code == 0
    assert len(_history(capsys)) == 1
    assert _history(capsys, "--clear") == []
    assert _history(capsys) == []


# QA-HIST-006
def test_table_format_prints_the_entries(ativos, capsys):
    code, _ = envelope(["run", ativos, "-f", "json"], capsys)
    assert code == 0
    code, out, err = invoke(["history"], capsys)
    assert code == 0
    assert "ativos" in out
    assert err == ""


# QA-HIST-007
@pytest.mark.parametrize("valor", ["0", "-5"])
def test_a_limit_below_one_is_refused(ativos, capsys, valor):
    """`-n 0` fell through `args.limit or 20` and silently meant the
    default; `-n -5` reached `entries[:-5]` and silently meant "all but the
    last five". `rows` validates its own limits the same way."""
    code, _ = envelope(["run", ativos, "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["history", "-n", valor, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "-n deve ser maior que zero."


# QA-HIST-008
def test_a_limit_of_one_returns_one(ativos, capsys):
    for _ in range(2):
        code, _ = envelope(["run", ativos, "-f", "json"], capsys)
        assert code == 0
    assert len(_history(capsys, "-n", "1")) == 1

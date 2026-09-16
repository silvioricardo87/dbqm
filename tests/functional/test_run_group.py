"""docs/qa/groups.md — `group add` then `run-group`, over two real files.

`local` and `local2` are the same schema; pedido 13 is the one row that
differs. So `clientes` agrees, `pedidos` diverges, and both verdicts are
produced by the data, not by a mock.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.functional.conftest import envelope, invoke

PED = "SELECT id, valor FROM pedidos ORDER BY id"
CLI = "SELECT id, nome FROM clientes ORDER BY id"


def _add_query(name: str, conn: str, sql: str, capsys) -> None:
    code, _ = envelope(["query", "add", name, "--connection", conn, "--sql", sql, "-f", "json"], capsys)
    assert code == 0


@pytest.fixture
def pedidos(local2_db, capsys) -> str:
    """The group that diverges: 4 keys, 3 equal, 1 different on `valor`."""
    _add_query("ped_local", "local", PED, capsys)
    _add_query("ped_local2", "local2", PED, capsys)
    code, body = envelope(
        ["group", "add", "pedidos", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0 and body["data"] == {"name": "pedidos", "created": True}
    return "pedidos"


@pytest.fixture
def clientes(local2_db, capsys) -> str:
    """The group that agrees."""
    _add_query("cli_local", "local", CLI, capsys)
    _add_query("cli_local2", "local2", CLI, capsys)
    code, body = envelope(
        ["group", "add", "clientes", "--query", "cli_local", "--query", "cli_local2",
         "--join-key", "id", "--compare-column", "nome", "-f", "json"],
        capsys,
    )
    assert code == 0 and body["data"] == {"name": "clientes", "created": True}
    return "clientes"


# QA-GROUP-001
def test_group_add_then_run_group_that_agrees(clientes, capsys):
    code, body = envelope(["run-group", clientes, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "run-group"
    assert body["data"]["group"] == "clientes"
    assert body["data"]["all_match"] is True
    assert body["data"]["comparisons"] == [{
        "column": "nome", "total_keys": 3, "equal_count": 3,
        "diff_count": 0, "absent_count": 0, "normalized_count": 0,
    }]


# QA-GROUP-002, QA-OUT-014
def test_a_real_divergence_exits_5(pedidos, capsys):
    code, out, err = invoke(["run-group", pedidos, "-f", "json"], capsys)
    assert code == 5
    assert err == ""
    body = json.loads(out)
    assert body["ok"] is True
    assert body["data"]["all_match"] is False
    assert body["data"]["comparisons"] == [{
        "column": "valor", "total_keys": 4, "equal_count": 3,
        "diff_count": 1, "absent_count": 0, "normalized_count": 0,
    }]


# QA-GROUP-003
def test_table_format_prints_the_verdict_with_the_same_exit(pedidos, clientes, capsys):
    code, out, _ = invoke(["run-group", pedidos], capsys)
    assert code == 5
    assert "DIVERGENTE" in out
    code, out, _ = invoke(["run-group", clientes], capsys)
    assert code == 0
    assert "CONSISTENTE" in out


# QA-GROUP-004
def test_export_html_still_exits_5_after_writing(pedidos, tmp_path, capsys):
    code, body = envelope(["run-group", pedidos, "-e", "html", "-f", "json"], capsys)
    assert code == 5
    assert body["ok"] is True
    assert body["data"]["format"] == "html"
    exported = Path(body["data"]["exported"])
    assert exported.suffix == ".html"
    assert tmp_path in exported.parents
    assert "<table" in exported.read_text(encoding="utf-8")


# QA-GROUP-005
def test_flat_with_html_is_refused_before_anything_runs(pedidos, capsys):
    code, body = envelope(["run-group", pedidos, "--flat", "-e", "html", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"].startswith("--flat nao tem versao HTML.")
    code, historico = envelope(["history", "-f", "json"], capsys)
    assert code == 0
    assert [e for e in historico["data"] if e["entry_type"] == "group"] == []


# QA-GROUP-006
def test_flat_csv_writes_and_keeps_the_verdict(pedidos, capsys):
    code, body = envelope(["run-group", pedidos, "--flat", "-e", "csv", "-f", "json"], capsys)
    assert code == 5
    exported = Path(body["data"]["exported"])
    assert exported.name.startswith("flat_") and exported.suffix == ".csv"
    assert exported.is_file()


# QA-GROUP-007
def test_an_unknown_group_is_not_found(local_db, capsys):
    code, body = envelope(["run-group", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Grupo 'nope' nao encontrado."


# QA-GROUP-008
def test_a_group_needs_two_queries(local_db, capsys):
    _add_query("cli_local", "local", CLI, capsys)
    code, body = envelope(["group", "add", "um", "--query", "cli_local", "--join-key", "id", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Selecione pelo menos 2 consultas."


# QA-GROUP-009
def test_a_divergent_run_is_still_recorded_in_history(pedidos, capsys):
    code, _ = envelope(["run-group", pedidos, "-f", "json"], capsys)
    assert code == 5
    code, body = envelope(["history", "-f", "json"], capsys)
    assert code == 0
    registros = [e for e in body["data"] if e["entry_type"] == "group"]
    assert len(registros) == 1
    assert registros[0]["name"] == "pedidos"
    assert registros[0]["all_match"] is False


# QA-GROUP-010
def test_a_failing_query_names_itself(local2_db, capsys):
    _add_query("quebrada", "local", "SELECT * FROM nao_existe", capsys)
    _add_query("cli_local2", "local2", CLI, capsys)
    code, _ = envelope(
        ["group", "add", "quebrado", "--query", "quebrada", "--query", "cli_local2", "--join-key", "id", "-f", "json"],
        capsys,
    )
    assert code == 0
    code, body = envelope(["run-group", "quebrado", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"
    assert body["error"]["message"] == "Erro na consulta 'quebrada': no such table: nao_existe"

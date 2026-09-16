"""docs/qa/saved-queries.md — `query add` then `run`, end to end.

The query is created through `run_cli` too: what a person types is what the
test types. The connection `local` comes from the fixture only because the
fixture is not the thing under test.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.functional.conftest import envelope, invoke

ATIVOS = "SELECT id, nome FROM clientes WHERE status = 'A' ORDER BY id"
POR_STATUS = "SELECT id, nome FROM clientes WHERE status = :st ORDER BY id"


@pytest.fixture
def ativos(local_db, capsys) -> str:
    code, body = envelope(["query", "add", "ativos", "--connection", "local", "--sql", ATIVOS, "-f", "json"], capsys)
    assert code == 0 and body["data"] == {"name": "ativos", "created": True}
    return "ativos"


@pytest.fixture
def por_status(local_db, capsys) -> str:
    code, _ = envelope(["query", "add", "por_status", "--connection", "local", "--sql", POR_STATUS, "-f", "json"], capsys)
    assert code == 0
    return "por_status"


# QA-QUERY-001
def test_query_add_then_run_end_to_end(ativos, capsys):
    code, body = envelope(["run", ativos, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "run"
    assert body["data"]["query_name"] == "ativos"
    assert body["data"]["connection_name"] == "local"
    assert body["data"]["rows"] == [[1, "Ana"], [3, "Caio"]]
    assert body["data"]["row_count"] == 2


# QA-QUERY-002
def test_a_param_reaches_the_sql(por_status, capsys):
    code, body = envelope(["run", por_status, "-p", "st=I", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["rows"] == [[2, "Bia"]]


# QA-QUERY-003
def test_a_missing_required_param_is_validation(por_status, capsys):
    code, body = envelope(["run", por_status, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Parametros obrigatorios faltando: st"


# QA-QUERY-004
def test_a_select_runs_on_a_read_only_connection(read_only_db, ativos, capsys):
    code, body = envelope(["run", ativos, "-c", "ro", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["connection_name"] == "ro"
    assert body["data"]["rows"] == [[1, "Ana"], [3, "Caio"]]


# QA-QUERY-005
def test_an_unknown_query_is_not_found(local_db, capsys):
    code, body = envelope(["run", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Consulta 'nope' nao encontrada."


# QA-QUERY-006
def test_an_unknown_connection_override_is_not_found(ativos, capsys):
    code, body = envelope(["run", ativos, "-c", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Conexao 'nope' nao encontrada."


# QA-QUERY-007
def test_a_query_the_driver_rejects_is_sql_error(local_db, capsys):
    code, _ = envelope(
        ["query", "add", "quebrada", "--connection", "local", "--sql", "SELECT * FROM nao_existe", "-f", "json"],
        capsys,
    )
    assert code == 0
    code, body = envelope(["run", "quebrada", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"
    assert body["error"]["message"] == "no such table: nao_existe"


# QA-QUERY-008
def test_export_writes_the_file_and_reports_it(ativos, tmp_path, capsys):
    code, body = envelope(["run", ativos, "-e", "csv", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["format"] == "csv"
    exported = Path(body["data"]["exported"])
    assert exported.suffix == ".csv"
    assert tmp_path in exported.parents
    linhas = exported.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "id,nome"
    assert "Ana" in linhas[1]


# QA-QUERY-009
def test_table_format_prints_the_rows(ativos, capsys):
    code, out, err = invoke(["run", ativos], capsys)
    assert code == 0
    assert "Ana" in out and "Caio" in out
    assert "Bia" not in out
    assert err == ""


# QA-QUERY-010
def test_a_run_is_recorded_in_history(ativos, capsys):
    code, _ = envelope(["run", ativos, "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["history", "-f", "json"], capsys)
    assert code == 0
    registros = [e for e in body["data"] if e["name"] == "ativos"]
    assert len(registros) == 1
    assert registros[0]["connection"] == "local"
    assert registros[0]["entry_type"] == "query"
    assert registros[0]["success"] is True
    assert registros[0]["row_count"] == 2

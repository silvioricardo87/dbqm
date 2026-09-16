"""docs/qa/output-contract.md — the envelope and every exit code, each
produced by a real condition against a real SQLite file.

Exit 5 (`divergent`) is produced by the comparison tests; see
`test_run_group.py`/`test_multi.py` once they exist. Everything else is here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dbqm.cli.errors import ERROR_CODES
from tests.functional.conftest import envelope, invoke

DOC = Path(__file__).resolve().parents[2] / "docs" / "qa" / "output-contract.md"


@pytest.fixture
def por_status(local_db, capsys) -> str:
    code, _ = envelope(
        ["query", "add", "por_status", "--connection", "local",
         "--sql", "SELECT id FROM clientes WHERE status = :st", "-f", "json"],
        capsys,
    )
    assert code == 0
    return "por_status"


# QA-OUT-001
def test_the_success_envelope_has_exactly_three_keys(local_db, capsys):
    code, out, err = invoke(["sql", "SELECT 1 AS um", "local", "-f", "json"], capsys)
    assert code == 0
    assert err == ""
    body = json.loads(out)
    assert set(body) == {"ok", "command", "data"}
    assert body["ok"] is True
    assert body["command"] == "sql"


# QA-OUT-002
def test_the_failure_envelope_has_exactly_three_keys(local_db, capsys):
    code, out, err = invoke(["sql", "SELECT 1", "nope", "-f", "json"], capsys)
    assert code == 2
    assert out == ""
    body = json.loads(err)
    assert set(body) == {"ok", "command", "error"}
    assert body["ok"] is False
    assert body["command"] == "sql"
    assert set(body["error"]) == {"code", "message", "exit"}


# QA-OUT-003
@pytest.mark.parametrize("token,argv", [
    ("usage", ["sql", "UPDATE clientes SET status='X'", "local", "-f", "json"]),
    ("not_found", ["sql", "SELECT 1", "nope", "-f", "json"]),
    ("validation", ["run", "por_status", "-f", "json"]),
    ("read_only", ["sql", "DELETE FROM clientes", "ro", "-f", "json"]),
    ("connection_failed", ["sql", "SELECT 1", "broken", "-f", "json"]),
    ("sql_error", ["sql", "SELECT * FROM nao_existe", "local", "-f", "json"]),
])
def test_the_exit_field_matches_the_process_exit(read_only_db, broken_db, por_status, capsys, token, argv):
    code, body = envelope(argv, capsys)
    assert body["error"]["code"] == token
    assert body["error"]["exit"] == code == int(ERROR_CODES[token])


# QA-OUT-004
def test_exit_0_on_success(local_db, capsys):
    code, body = envelope(["sql", "SELECT 1", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["ok"] is True


# QA-OUT-005
def test_exit_2_usage(local_db, capsys):
    code, body = envelope(["sql", "UPDATE clientes SET status='X'", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"


# QA-OUT-006
def test_exit_2_not_found(local_db, capsys):
    code, body = envelope(["sql", "SELECT 1", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"


# QA-OUT-007
def test_exit_2_validation(por_status, capsys):
    code, body = envelope(["run", por_status, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"


# QA-OUT-008
def test_exit_2_read_only(read_only_db, capsys):
    code, body = envelope(["sql", "DELETE FROM clientes", "ro", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "read_only"


# QA-OUT-009
def test_exit_3_connection_failed(broken_db, capsys):
    code, body = envelope(["sql", "SELECT 1", "broken", "-f", "json"], capsys)
    assert code == 3
    assert body["error"]["code"] == "connection_failed"
    assert body["error"]["message"] == "unable to open database file"


# QA-OUT-010
def test_exit_4_sql_error(local_db, capsys):
    code, body = envelope(["sql", "SELECT * FROM nao_existe", "local", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"


# QA-OUT-011
def test_table_format_prints_the_failure_to_stdout_with_the_same_exit(local_db, capsys):
    code, out, err = invoke(["sql", "SELECT * FROM nao_existe", "local"], capsys)
    assert code == 4
    assert "no such table: nao_existe" in out
    assert err == ""


# QA-OUT-012
def test_json_failure_leaves_stdout_empty(local_db, capsys):
    code, out, err = invoke(["sql", "SELECT * FROM nao_existe", "local", "-f", "json"], capsys)
    assert code == 4
    assert out == ""
    assert json.loads(err)["ok"] is False


# QA-OUT-013
def test_this_document_matches_the_error_table_in_code():
    """The token table in the document is read, not retyped: a token added
    to `ERROR_CODES` without a documented exit, or documented with the
    wrong one, fails here."""
    linhas = re.findall(r"^\| `(\w+)` \| (\d) \|", DOC.read_text(encoding="utf-8"), re.MULTILINE)
    documentado = {token: int(saida) for token, saida in linhas}
    assert documentado == {token: int(saida) for token, saida in ERROR_CODES.items()}

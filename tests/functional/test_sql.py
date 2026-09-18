"""docs/qa/adhoc-sql.md — `dbqm sql` against a real SQLite file.

Every assertion here is on what the program did to the database or what it
printed; nothing is patched. Where a scenario says "the row is unchanged",
the row is read back through a second `run_cli` call, not inferred.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.functional.conftest import envelope, invoke


# QA-SQL-001
def test_select_returns_the_seed_rows(local_db, capsys):
    code, body = envelope(["sql", "SELECT id, nome FROM clientes ORDER BY id", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "sql"
    assert body["data"]["sql_type"] == "SELECT"
    assert body["data"]["columns"] == ["id", "nome"]
    assert body["data"]["rows"] == [[1, "Ana"], [2, "Bia"], [3, "Caio"]]
    assert body["data"]["row_count"] == 3


# QA-SQL-002
def test_a_param_reaches_the_statement(local_db, capsys):
    code, body = envelope(
        ["sql", "SELECT nome FROM clientes WHERE id = :id", "local", "-p", "id=2", "-f", "json"], capsys,
    )
    assert code == 0
    assert body["data"]["rows"] == [["Bia"]]


def _status_of_1(capsys) -> str:
    code, body = envelope(["sql", "SELECT status FROM clientes WHERE id = 1", "local", "-f", "json"], capsys)
    assert code == 0
    return body["data"]["rows"][0][0]


# QA-SQL-003
def test_dml_without_commit_is_refused_before_running(local_db, capsys):
    code, body = envelope(["sql", "UPDATE clientes SET status='X' WHERE id=1", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "DML requires --commit to confirm the operation."
    assert _status_of_1(capsys) == "A"


# QA-SQL-004
def test_dml_with_commit_persists_for_the_next_call(local_db, capsys):
    code, body = envelope(
        ["sql", "UPDATE clientes SET status='X' WHERE id=1", "local", "--commit", "-f", "json"], capsys,
    )
    assert code == 0
    assert body["data"]["sql_type"] == "UPDATE"
    assert body["data"]["rows_affected"] == 1
    assert body["data"]["committed"] is True
    assert _status_of_1(capsys) == "X"


# QA-SQL-005
def test_ddl_creates_a_table_that_objects_then_lists(local_db, capsys):
    code, body = envelope(["sql", "CREATE TABLE auditoria (id INTEGER)", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["sql_type"] == "DDL"
    code, body = envelope(["objects", "local", "--type", "TABLE", "-f", "json"], capsys)
    assert code == 0
    assert "auditoria" in body["data"]["objects"]
    assert "clientes" in body["data"]["objects"]


# QA-SQL-006
def test_a_ddl_the_driver_rejects_is_sql_error(local_db, capsys):
    code, body = envelope(["sql", "CREATE TABLE clientes (id INTEGER)", "local", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"
    assert body["error"]["message"] == "table clientes already exists"


# QA-SQL-007
def test_explain_returns_a_plan(local_db, capsys):
    code, body = envelope(["sql", "SELECT id FROM clientes", "local", "--explain", "-f", "json"], capsys)
    assert code == 0
    plan = body["data"]["plan"]
    assert plan and all(isinstance(line, str) for line in plan)
    assert any("clientes" in line for line in plan)


# QA-SQL-008
def test_a_statement_the_driver_rejects_is_sql_error(local_db, capsys):
    code, body = envelope(["sql", "SELECT * FROM nao_existe", "local", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"
    assert body["error"]["message"] == "no such table: nao_existe"


# QA-SQL-009
def test_an_unknown_verb_is_usage_not_sql_error(local_db, capsys):
    """`SELEC 1` never reaches the driver: `classify_sql` cannot name it, so
    the refusal is bad input, not a rejected statement."""
    code, body = envelope(["sql", "SELEC 1", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"].startswith("Unsupported SQL type.")


# QA-SQL-010
def test_a_sql_file_path_is_read(local_db, tmp_path, capsys):
    arquivo = tmp_path / "consulta.sql"
    arquivo.write_text("SELECT COUNT(*) AS n FROM pedidos", encoding="utf-8")
    code, body = envelope(["sql", str(arquivo), "local", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["rows"] == [[4]]
    assert body["data"]["sql"] == "SELECT COUNT(*) AS n FROM pedidos"


# QA-SQL-011
@pytest.mark.parametrize("fmt,suffix", [("csv", ".csv"), ("json", ".json"), ("txt", ".txt"), ("html", ".html")])
def test_export_writes_a_file_per_format(local_db, tmp_path, capsys, fmt, suffix):
    code, body = envelope(["sql", "SELECT id, nome FROM clientes", "local", "-e", fmt, "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["format"] == fmt
    exported = Path(body["data"]["exported"])
    assert exported.suffix == suffix
    assert exported.is_file()
    # under `tmp_config_dir` every export lands below tmp_path, never in the
    # developer's cwd
    assert tmp_path in exported.parents
    assert "Ana" in exported.read_text(encoding="utf-8")


# QA-SQL-012
def test_a_param_without_equals_is_usage(local_db, capsys):
    code, body = envelope(["sql", "SELECT 1", "local", "-p", "semigual", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "Invalid parameter (use key=value): semigual"


# QA-SQL-013
def test_an_unknown_connection_is_not_found(local_db, capsys):
    code, body = envelope(["sql", "SELECT 1", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Connection "nope" not found.'


# QA-SQL-014
def test_table_format_prints_the_rows(local_db, capsys):
    code, out, err = invoke(["sql", "SELECT nome FROM clientes WHERE id=1", "local"], capsys)
    assert code == 0
    assert "Ana" in out
    assert err == ""


# QA-SQL-016
def test_export_on_a_dml_is_refused_before_the_write(local_db, tmp_path, capsys):
    """Refused before the statement runs, not after: refusing afterwards
    would mean the row was written and the caller still got exit 2."""
    code, body = envelope(
        ["sql", "UPDATE clientes SET status='X' WHERE id=1", "local",
         "--commit", "-e", "csv", "-f", "json"],
        capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == (
        "--export needs a command that returns rows; UPDATE does not return any."
    )
    assert _status_of_1(capsys) == "A"
    assert not list(tmp_path.rglob("*.csv"))


# QA-SQL-017
def test_export_on_a_ddl_is_refused_and_nothing_is_created(local_db, capsys):
    code, body = envelope(
        ["sql", "CREATE TABLE auditoria (id INTEGER)", "local", "-e", "json", "-f", "json"],
        capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == (
        "--export needs a command that returns rows; DDL does not return any."
    )
    code, body = envelope(["objects", "local", "--type", "TABLE", "-f", "json"], capsys)
    assert code == 0
    assert "auditoria" not in body["data"]["objects"]


# QA-SQL-018
def test_a_select_still_exports(local_db, capsys):
    """The guard names statement types, not the flag: what returns rows is
    untouched."""
    code, body = envelope(
        ["sql", "SELECT id, nome FROM clientes", "local", "-e", "csv", "-f", "json"], capsys,
    )
    assert code == 0
    assert Path(body["data"]["exported"]).is_file()


# QA-SQL-019
def test_explain_exports_the_plan(local_db, tmp_path, capsys):
    """A plan is a result set. `--explain` returns before the guard that
    refuses `--export`, so without its own arm the flag would be accepted
    and ignored here -- the bug the guard exists to stop."""
    code, body = envelope(
        ["sql", "SELECT id FROM clientes", "local", "--explain", "-e", "csv", "-f", "json"],
        capsys,
    )
    assert code == 0
    assert body["data"]["format"] == "csv"
    exportado = Path(body["data"]["exported"])
    assert tmp_path in exportado.parents
    conteudo = exportado.read_text(encoding="utf-8")
    assert conteudo.splitlines()[0] == "plan"
    assert "clientes" in conteudo


# QA-SQL-020
def test_the_read_only_refusal_comes_before_the_export_one(read_only_db, capsys):
    """Both are things the caller could fix, but only one of them is the
    connection refusing: reporting the flag first costs a round trip to
    learn the connection is protected."""
    code, body = envelope(
        ["sql", "UPDATE clientes SET status='X' WHERE id=1", "ro", "--commit", "-e", "csv", "-f", "json"],
        capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "read_only"


# QA-SQL-022
def test_a_param_the_statement_never_binds_is_refused(local_db, capsys):
    code, body = envelope(
        ["sql", "SELECT 1 AS um", "local", "-p", "naoexiste=1", "-f", "json"], capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'The SQL does not use the parameter "naoexiste".'


# QA-SQL-023
def test_a_missing_sql_file_says_so(local_db, tmp_path, capsys):
    """A path ending in `.sql` is not a statement. Read as SQL it came back
    "Tipo de SQL nao suportado", which says nothing about the typo."""
    caminho = tmp_path / "nao_existe.sql"
    code, body = envelope(["sql", str(caminho), "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == f'File "{caminho}" not found.'

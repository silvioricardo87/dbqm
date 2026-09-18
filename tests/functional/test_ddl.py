"""docs/qa/ddl.md — ddl from sqlite_master, to stdout and to a file."""
from __future__ import annotations

import json
from pathlib import Path

from tests.functional.conftest import envelope, invoke

CREATE_INDEX = "CREATE UNIQUE INDEX ix_clientes_nome ON clientes(nome);"


def _by_name(body: dict) -> dict[str, dict]:
    return {o["name"]: o for o in body["data"]["objects"]}


# QA-DDL-001
def test_stdout_returns_the_create_table_and_its_index(local_db, capsys):
    code, body = envelope(["ddl", "clientes", "local", "--stdout", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "ddl"
    assert body["data"]["path"] is None
    objetos = _by_name(body)
    assert list(objetos) == ["clientes", "ix_clientes_nome"]
    assert objetos["clientes"]["obj_type"] == "TABLE"
    assert objetos["clientes"]["ddl"].startswith("CREATE TABLE clientes")
    assert objetos["clientes"]["ddl"].rstrip().endswith(";")
    assert objetos["ix_clientes_nome"] == {"name": "ix_clientes_nome", "obj_type": "INDEX", "ddl": CREATE_INDEX}


# QA-DDL-002
def test_json_keeps_the_progress_off_stdout(local_db, capsys):
    code, out, err = invoke(["ddl", "clientes", "local", "--stdout", "-f", "json"], capsys)
    assert code == 0
    assert json.loads(out)["ok"] is True
    assert "[1/2] TABLE: clientes" in err
    assert "[2/2] INDEX: ix_clientes_nome" in err


# QA-DDL-003
def test_stdout_table_format_prints_the_ddl(local_db, capsys):
    code, out, _ = invoke(["ddl", "clientes", "local", "--stdout"], capsys)
    assert code == 0
    assert "CREATE TABLE clientes" in out
    assert "CREATE UNIQUE INDEX ix_clientes_nome" in out


# QA-DDL-004
def test_a_view_is_extracted(local_db, capsys):
    code, body = envelope(["ddl", "v_ativos", "local", "--stdout", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["objects"] == [{
        "name": "v_ativos", "obj_type": "VIEW",
        "ddl": "CREATE VIEW v_ativos AS SELECT id, nome FROM clientes WHERE status = 'A';",
    }]


# QA-DDL-005
def test_without_stdout_a_sql_file_is_written(local_db, tmp_path, capsys):
    code, body = envelope(["ddl", "clientes", "local", "-f", "json"], capsys)
    assert code == 0
    pasta = Path(body["data"]["path"])
    assert pasta.is_dir()
    assert tmp_path in pasta.parents
    arquivos = sorted(pasta.glob("*.sql"))
    assert arquivos, "no .sql written"
    conteudo = "".join(a.read_text(encoding="utf-8") for a in arquivos)
    assert "CREATE TABLE clientes" in conteudo


# QA-DDL-006
def test_an_unknown_object_is_not_found(local_db, capsys):
    code, body = envelope(["ddl", "nao_existe", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Object 'nao_existe' not found."


# QA-DDL-007
def test_an_unknown_connection_is_not_found(local_db, capsys):
    code, body = envelope(["ddl", "clientes", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Conexao 'nope' nao encontrada."

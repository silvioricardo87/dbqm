"""docs/qa/discovery.md — objects, describe and rows over the seed."""
from __future__ import annotations

import pytest

from tests.functional.conftest import envelope, invoke


# QA-DISC-001
def test_objects_lists_the_seed_tables(local_db, capsys):
    code, body = envelope(["objects", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "objects"
    assert body["data"]["obj_type"] == "TABLE"
    assert body["data"]["objects"] == ["clientes", "pedidos"]


# QA-DISC-002
def test_objects_lists_the_seed_view(local_db, capsys):
    code, body = envelope(["objects", "local", "--type", "VIEW", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["objects"] == ["v_ativos"]


# QA-DISC-003
def test_packages_on_sqlite_is_usage_naming_the_engine(local_db, capsys):
    code, body = envelope(["objects", "local", "--type", "PACKAGE", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "Packages only exist on Oracle. This connection is sqlite."


# QA-DISC-004
def test_routines_on_sqlite_is_usage(local_db, capsys):
    code, body = envelope(["objects", "local", "--type", "ROUTINE", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "SQLite has no stored routines."


def _columns(body: dict) -> dict[str, dict]:
    return {c["name"]: c for c in body["data"]["columns"]}


# QA-DISC-005
def test_describe_reports_pk_nullability_and_the_unique_index(local_db, capsys):
    code, body = envelope(["describe", "clientes", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["object_type"] == "TABLE"
    columns = _columns(body)
    assert list(columns) == ["id", "nome", "status"]
    assert columns["id"]["is_pk"] is True and columns["id"]["data_type"] == "INTEGER"
    assert columns["nome"]["nullable"] is False and columns["nome"]["data_type"] == "TEXT"
    assert columns["status"]["is_pk"] is False
    assert body["data"]["indexes"] == [{"name": "ix_clientes_nome", "columns": ["nome"], "is_unique": True}]


# QA-DISC-006
def test_describe_reports_the_foreign_key(local_db, capsys):
    code, body = envelope(["describe", "pedidos", "local", "-f", "json"], capsys)
    assert code == 0
    assert _columns(body)["cliente_id"]["fk_ref"] == "clientes.id"
    assert _columns(body)["id"]["fk_ref"] == ""


# QA-DISC-007
def test_describe_a_view_brings_its_definition(local_db, capsys):
    code, body = envelope(["describe", "v_ativos", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["object_type"] == "VIEW"
    assert list(_columns(body)) == ["id", "nome"]
    assert body["data"]["sql_definition"].startswith("CREATE VIEW v_ativos")


# QA-DISC-008
def test_describe_of_an_unknown_object_is_not_found(local_db, capsys):
    code, body = envelope(["describe", "nao_existe", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == '"nao_existe" is neither a table nor a view in local.'


# QA-DISC-009
def test_describe_table_format_prints_keys_and_indexes(local_db, capsys):
    code, out, err = invoke(["describe", "clientes", "local"], capsys)
    assert code == 0
    assert "PK" in out and "ix_clientes_nome" in out and "UNIQUE" in out
    assert err == ""


# QA-DISC-010
def test_rows_returns_the_seed(local_db, capsys):
    code, body = envelope(["rows", "clientes", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "rows"
    assert body["data"]["columns"] == ["id", "nome", "status"]
    assert body["data"]["rows"] == [[1, "Ana", "A"], [2, "Bia", "I"], [3, "Caio", "A"]]
    assert body["data"]["row_count"] == 3
    assert body["data"]["total_count"] == 3
    assert body["data"]["limit"] == 100
    assert body["data"]["offset"] == 0


# QA-DISC-011
def test_rows_pages_with_limit_and_offset(local_db, capsys):
    code, body = envelope(["rows", "clientes", "local", "--limit", "2", "-f", "json"], capsys)
    assert code == 0
    assert [r[1] for r in body["data"]["rows"]] == ["Ana", "Bia"]
    assert body["data"]["total_count"] == 3
    code, body = envelope(["rows", "clientes", "local", "--limit", "2", "--offset", "2", "-f", "json"], capsys)
    assert code == 0
    assert [r[1] for r in body["data"]["rows"]] == ["Caio"]
    assert body["data"]["row_count"] == 1
    assert body["data"]["offset"] == 2


# QA-DISC-012
@pytest.mark.parametrize("flag, value, message", [
    ("--limit", "0", "--limit must be greater than zero."),
    ("--offset", "-1", "--offset cannot be negative."),
])
def test_rows_refuses_a_bad_page(local_db, capsys, flag, value, message):
    code, body = envelope(["rows", "clientes", "local", flag, value, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == message


# QA-DISC-013
def test_rows_of_an_unknown_table_is_not_found(local_db, capsys):
    code, body = envelope(["rows", "nao_existe", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Table "nao_existe" not found in local.'


# QA-DISC-014
def test_rows_csv_prints_a_header_and_the_rows(local_db, capsys):
    code, out, _ = invoke(["rows", "clientes", "local", "-f", "csv"], capsys)
    assert code == 0
    lines = out.strip().splitlines()
    assert lines[0] == "id,nome,status"
    assert len(lines) == 4
    assert "2,Bia,I" in lines


# QA-DISC-015
def test_objects_of_an_unknown_connection_is_not_found(local_db, capsys):
    code, body = envelope(["objects", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Connection "nope" not found.'

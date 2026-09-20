"""docs/qa/ddl.md — ddl from sqlite_master, to stdout and to a file."""
from __future__ import annotations

import json
from pathlib import Path

from tests.functional.conftest import envelope, invoke

CREATE_INDEX = "CREATE UNIQUE INDEX ix_customers_name ON customers(name);"


def _by_name(body: dict) -> dict[str, dict]:
    return {o["name"]: o for o in body["data"]["objects"]}


# QA-DDL-001
def test_stdout_returns_the_create_table_and_its_index(local_db, capsys):
    code, body = envelope(["ddl", "customers", "local", "--stdout", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "ddl"
    assert body["data"]["path"] is None
    objects = _by_name(body)
    assert list(objects) == ["customers", "ix_customers_name"]
    assert objects["customers"]["obj_type"] == "TABLE"
    assert objects["customers"]["ddl"].startswith("CREATE TABLE customers")
    assert objects["customers"]["ddl"].rstrip().endswith(";")
    assert objects["ix_customers_name"] == {"name": "ix_customers_name", "obj_type": "INDEX", "ddl": CREATE_INDEX}


# QA-DDL-002
def test_json_keeps_the_progress_off_stdout(local_db, capsys):
    code, out, err = invoke(["ddl", "customers", "local", "--stdout", "-f", "json"], capsys)
    assert code == 0
    assert json.loads(out)["ok"] is True
    assert "[1/2] TABLE: customers" in err
    assert "[2/2] INDEX: ix_customers_name" in err


# QA-DDL-003
def test_stdout_table_format_prints_the_ddl(local_db, capsys):
    code, out, _ = invoke(["ddl", "customers", "local", "--stdout"], capsys)
    assert code == 0
    assert "CREATE TABLE customers" in out
    assert "CREATE UNIQUE INDEX ix_customers_name" in out


# QA-DDL-004
def test_a_view_is_extracted(local_db, capsys):
    code, body = envelope(["ddl", "v_active", "local", "--stdout", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["objects"] == [{
        "name": "v_active", "obj_type": "VIEW",
        "ddl": "CREATE VIEW v_active AS SELECT id, name FROM customers WHERE status = 'A';",
    }]


# QA-DDL-005
def test_without_stdout_a_sql_file_is_written(local_db, tmp_path, capsys):
    code, body = envelope(["ddl", "customers", "local", "-f", "json"], capsys)
    assert code == 0
    folder = Path(body["data"]["path"])
    assert folder.is_dir()
    assert tmp_path in folder.parents
    files = sorted(folder.glob("*.sql"))
    assert files, "no .sql written"
    content = "".join(a.read_text(encoding="utf-8") for a in files)
    assert "CREATE TABLE customers" in content


# QA-DDL-006
def test_an_unknown_object_is_not_found(local_db, capsys):
    code, body = envelope(["ddl", "nao_existe", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Object 'nao_existe' not found."


# QA-DDL-007
def test_an_unknown_connection_is_not_found(local_db, capsys):
    code, body = envelope(["ddl", "customers", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Connection "nope" not found.'


# QA-DDL-008
def test_table_format_agrees_with_json_on_a_missing_object(local_db, capsys):
    """Locks format-independence: table format used to exit 4 (`sql_error`)
    for a missing object regardless of `not_found`, while json already said
    2. Both formats now derive the code from the same `ops_schema.extract_ddl`
    call, so table matches json here too."""
    code, out, err = invoke(["ddl", "no_such_object", "local"], capsys)
    assert code == 2
    assert "no_such_object" in out
    assert err == ""

"""A database's shape through ops/, measured against the CLI's `-f json`."""
from __future__ import annotations

import pytest

from dbqm.core.crypto import encrypt
from dbqm.models.connection import Connection
from dbqm.ops import catalogue, schema
from dbqm.ops.errors import OperationError
from tests.ops.conftest import envelope


def test_list_objects_matches_the_cli(local_db, capsys):
    _, body = envelope(["objects", "local", "--type", "TABLE", "-f", "json"], capsys)
    conn = catalogue.connection("local")
    assert schema.list_objects(conn, "table") == body["data"]["objects"]


def test_describe_matches_the_cli(local_db, capsys):
    _, body = envelope(["describe", "customers", "local", "-f", "json"], capsys)
    result = schema.describe(catalogue.connection("local"), "customers")
    # `elapsed` is a real wall-clock measurement of its own query; the CLI's
    # call and this one each measure their own, so only the rest is expected
    # to match bit for bit.
    result.pop("elapsed")
    expected = {k: v for k, v in body["data"].items() if k != "elapsed"}
    assert result == expected


def test_describe_a_view_matches_the_cli(local_db, capsys):
    _, body = envelope(["describe", "v_active", "local", "-f", "json"], capsys)
    result = schema.describe(catalogue.connection("local"), "v_active")
    result.pop("elapsed")
    expected = {k: v for k, v in body["data"].items() if k != "elapsed"}
    assert result == expected


def test_describe_neither_table_nor_view_is_not_found(local_db):
    with pytest.raises(OperationError) as e:
        schema.describe(catalogue.connection("local"), "nothing_here")
    assert e.value.code == "not_found"


def test_rows_matches_the_cli(local_db, capsys):
    _, body = envelope(["rows", "orders", "local", "--limit", "2", "--offset", "1", "-f", "json"], capsys)
    result = schema.rows(catalogue.connection("local"), "orders", limit=2, offset=1).to_dict()
    # `elapsed` is a real wall-clock measurement of its own query; the CLI's
    # call and this one each measure their own, so only the rest is expected
    # to match bit for bit.
    result.pop("elapsed")
    expected = {k: v for k, v in body["data"].items() if k != "elapsed"}
    assert result == expected


@pytest.mark.parametrize("limit,offset,token", [(0, 0, "usage"), (5, -1, "usage")])
def test_rows_refuses_bad_paging(local_db, limit, offset, token):
    with pytest.raises(OperationError) as e:
        schema.rows(catalogue.connection("local"), "orders", limit=limit, offset=offset)
    assert e.value.code == token


def test_rows_of_a_missing_table_is_not_found(local_db):
    with pytest.raises(OperationError) as e:
        schema.rows(catalogue.connection("local"), "no_such_table", limit=5, offset=0)
    assert e.value.code == "not_found"


def test_a_database_that_does_not_answer_is_connection_failed(broken_db):
    with pytest.raises(OperationError) as e:
        schema.list_objects(catalogue.connection("broken"), "TABLE")
    assert e.value.code == "connection_failed"


def test_extract_ddl_matches_the_cli(local_db, capsys):
    _, body = envelope(["ddl", "customers", "local", "--stdout", "-f", "json"], capsys)
    result = schema.extract_ddl(catalogue.connection("local"), "customers")
    assert [o.to_dict() for o in result.objects] == body["data"]["objects"]


def test_extract_ddl_of_a_missing_object_is_not_found(local_db):
    with pytest.raises(OperationError) as e:
        schema.extract_ddl(catalogue.connection("local"), "no_such_object")
    assert e.value.code == "not_found"


def test_extract_ddl_on_a_dead_database_is_connection_failed(broken_db):
    with pytest.raises(OperationError) as e:
        schema.extract_ddl(catalogue.connection("broken"), "customers")
    assert e.value.code == "connection_failed"


class TestConnectionFailureIsMasked:
    """`with_open_connection`'s outer arm and `extract_ddl` both used to
    build `OperationError("connection_failed", str(e))` directly -- a
    driver is free to echo the DSN it was given, password included.
    `core/db_manager.error_text` is what `query_engine` already routes
    through; this pins `ops/schema` doing the same, via `deps.open_connection`
    patched here (a unit test, which `tests/ops/` allows)."""

    def _conn(self) -> Connection:
        return Connection(name="c", db_type="postgresql", host="db.example.com",
                          user="app", password=encrypt("s3cretpw"))

    def test_list_objects_connection_failure_is_masked(self, monkeypatch, tmp_config_dir):
        def boom(_conn):
            raise RuntimeError("login failed for s3cretpw@host")
        monkeypatch.setattr(schema.deps, "open_connection", boom)
        with pytest.raises(OperationError) as e:
            schema.list_objects(self._conn(), "TABLE")
        assert e.value.code == "connection_failed"
        assert "s3cretpw" not in e.value.message
        assert "***" in e.value.message

    def test_extract_ddl_connection_failure_is_masked(self, monkeypatch, tmp_config_dir):
        def boom(_conn, obj, on_progress=None):
            raise RuntimeError("login failed for s3cretpw@host")
        monkeypatch.setattr(schema.deps, "extract_ddl", boom)
        with pytest.raises(OperationError) as e:
            schema.extract_ddl(self._conn(), "customers")
        assert e.value.code == "connection_failed"
        assert "s3cretpw" not in e.value.message
        assert "***" in e.value.message

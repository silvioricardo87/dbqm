"""A failure is the CLI's stderr object, is_error set, exit code included."""
from __future__ import annotations

import pytest
from mcp.client import Client

from dbqm.mcp.options import ServerOptions
from dbqm.mcp.server import build_server
from tests.mcp.test_tools import call


@pytest.mark.asyncio
async def test_unknown_connection_is_not_found(local_db):
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "rows", connection="nope", table="t")
    assert err is True
    assert env["ok"] is False and env["command"] == "rows"
    assert env["error"]["code"] == "not_found" and env["error"]["exit"] == 2
    assert "data" not in env


@pytest.mark.asyncio
async def test_a_rejected_statement_is_sql_error(local_db):
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "sql", connection="local", sql="SELECT * FROM nope")
    assert err is True
    assert env["error"]["code"] == "sql_error" and env["error"]["exit"] == 4


@pytest.mark.asyncio
async def test_a_dead_database_is_connection_failed(broken_db):
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "objects", connection="broken", type="TABLE")
    assert env["error"]["code"] == "connection_failed" and env["error"]["exit"] == 3


@pytest.mark.asyncio
async def test_bad_paging_is_usage(local_db):
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "rows", connection="local", table="orders", limit=0)
    assert env["error"]["code"] == "usage" and env["error"]["exit"] == 2


@pytest.mark.asyncio
async def test_an_undeclared_parameter_is_validation(local_db):
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "sql", connection="local", sql="SELECT 1", params={"x": "1"})
    assert env["error"]["code"] == "validation"


@pytest.mark.asyncio
async def test_a_bug_is_unexpected_exit_1(local_db, monkeypatch):
    """Anything that is not an OperationError is the CLI's 'a bug in dbqm'."""
    from dbqm.ops import schema

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(schema, "rows", boom)
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "rows", connection="local", table="orders")
    assert err is True
    assert env["error"]["code"] == "unexpected" and env["error"]["exit"] == 1
    assert "boom" in env["error"]["message"]


@pytest.mark.asyncio
async def test_a_schema_violation_is_refused_by_the_sdk(local_db):
    """Not our envelope: the SDK validates the arguments before the tool runs."""
    async with Client(build_server(ServerOptions())) as client:
        result = await client.call_tool("objects", {"connection": "local", "type": "BAD"})
    assert result.is_error is True
    assert result.structured_content is None

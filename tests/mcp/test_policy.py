"""What the two server options do, observed through tool calls."""
from __future__ import annotations

import pytest
from mcp.client import Client

from dbqm.cli import run_cli
from dbqm.mcp.options import ServerOptions
from dbqm.mcp.server import build_server
from tests.mcp.test_tools import call


@pytest.mark.asyncio
async def test_by_default_a_writable_connection_cannot_write(local_db):
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "sql", connection="local",
                              sql="DELETE FROM orders WHERE id = 13", commit=True)
        _, count = await call(client, "sql", connection="local", sql="SELECT COUNT(*) FROM orders")
    assert err is True and env["error"]["code"] == "read_only"
    assert count["data"]["rows"] == [[4]]


@pytest.mark.asyncio
async def test_by_default_list_reports_read_only_true(local_db):
    async with Client(build_server(ServerOptions())) as client:
        _, env = await call(client, "list", kind="connections")
    assert [c["read_only"] for c in env["data"]] == [True]


@pytest.mark.asyncio
async def test_allow_write_lets_the_connection_decide(local_db, read_only_db):
    async with Client(build_server(ServerOptions(allow_write=True))) as client:
        err, env = await call(client, "sql", connection="local",
                              sql="DELETE FROM orders WHERE id = 13", commit=True)
        _, count = await call(client, "sql", connection="local", sql="SELECT COUNT(*) FROM orders")
        err_ro, env_ro = await call(client, "sql", connection="ro",
                                    sql="DELETE FROM orders WHERE id = 12", commit=True)
    assert err is False and env["data"]["rows_affected"] == 1
    assert count["data"]["rows"] == [[3]]
    assert err_ro is True and env_ro["error"]["code"] == "read_only"


@pytest.mark.asyncio
async def test_the_allowlist_hides_and_refuses(local2_db):
    options = ServerOptions(connections=frozenset({"local"}))
    async with Client(build_server(options)) as client:
        _, listed = await call(client, "list", kind="connections")
        err, env = await call(client, "rows", connection="local2", table="orders")
        _, tested = await call(client, "test_connection")
    assert [c["name"] for c in listed["data"]] == ["local"]
    assert err is True and env["error"]["code"] == "not_found"
    assert [d["name"] for d in tested["data"]] == ["local"]


@pytest.mark.asyncio
async def test_the_allowlist_applies_through_a_group(local2_db, capsys):
    """The resolver is applied where the group resolves its connections,
    not only at the tool's front door."""
    sql = "SELECT id, value FROM orders ORDER BY id"
    run_cli(["group", "add", "adhoc", "--adhoc-sql", sql, "--connection", "local",
             "--connection", "local2", "-f", "json"])
    capsys.readouterr()
    async with Client(build_server(ServerOptions(connections=frozenset({"local"})))) as client:
        err, env = await call(client, "run_group", group="adhoc")
    assert err is True and env["error"]["code"] == "not_found"
    assert "local2" in env["error"]["message"]


@pytest.mark.asyncio
async def test_a_saved_query_runs_read_only_by_default(local_db, capsys):
    """A SELECT is unaffected by the forced flag; the run is recorded."""
    run_cli(["query", "add", "q", "--sql", "SELECT COUNT(*) FROM orders", "--connection", "local", "-f", "json"])
    capsys.readouterr()
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "run", query="q")
    assert err is False and env["data"]["rows"] == [[4]]

"""Every tool answers with the CLI's envelope, and its data is the CLI's data."""
from __future__ import annotations

from typing import Any

import pytest
from mcp.client import Client

from dbqm.cli import run_cli
from dbqm.mcp.options import ServerOptions
from dbqm.mcp.server import TOOL_NAMES, build_server
from tests.mcp.conftest import envelope


async def call(client: Client, name: str, **arguments: Any) -> tuple[bool, dict[str, Any]]:
    result = await client.call_tool(name, arguments)
    assert result.structured_content is not None
    return bool(result.is_error), result.structured_content


def _without_elapsed(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k != "elapsed"}


@pytest.mark.asyncio
async def test_the_eleven_tools_and_nothing_else(local_db):
    async with Client(build_server(ServerOptions())) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
    assert names == list(TOOL_NAMES)
    assert len(names) == 11


@pytest.mark.asyncio
async def test_every_tool_but_sql_is_read_only_annotated(local_db):
    async with Client(build_server(ServerOptions())) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    for name, tool in tools.items():
        assert tool.annotations is not None, name
        assert tool.annotations.read_only_hint is True, name
    async with Client(build_server(ServerOptions(allow_write=True))) as client:
        sql = next(t for t in (await client.list_tools()).tools if t.name == "sql")
    assert sql.annotations is not None
    assert sql.annotations.read_only_hint is False
    assert sql.annotations.destructive_hint is True


@pytest.mark.asyncio
async def test_descriptions_come_from_the_catalogue(local_db):
    from dbqm.i18n import t
    async with Client(build_server(ServerOptions())) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert tools["rows"].description == t("mcp.tool.rows")


@pytest.mark.asyncio
async def test_list_matches_the_cli(local2_db, capsys):
    _, body = envelope(["list", "connections", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions(allow_write=True))) as client:
        err, env = await call(client, "list", kind="connections")
    assert err is False
    assert env["command"] == "list.connections"
    assert env["data"] == body["data"]


@pytest.mark.asyncio
async def test_objects_describe_rows_match_the_cli(local_db, capsys):
    _, objects = envelope(["objects", "local", "--type", "TABLE", "-f", "json"], capsys)
    _, describe = envelope(["describe", "customers", "local", "-f", "json"], capsys)
    _, rows = envelope(["rows", "orders", "local", "--limit", "2", "--offset", "1", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        _, o = await call(client, "objects", connection="local", type="TABLE")
        _, d = await call(client, "describe", connection="local", object="customers")
        _, r = await call(client, "rows", connection="local", table="orders", limit=2, offset=1)
    assert o["data"] == objects["data"]
    assert _without_elapsed(d["data"]) == _without_elapsed(describe["data"])
    assert _without_elapsed(r["data"]) == _without_elapsed(rows["data"])


@pytest.mark.asyncio
async def test_ddl_matches_the_cli_and_writes_nothing(local_db, capsys, tmp_path):
    _, body = envelope(["ddl", "customers", "local", "--stdout", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        _, env = await call(client, "ddl", connection="local", object="customers")
    assert env["data"]["objects"] == body["data"]["objects"]
    assert env["data"]["path"] is None


@pytest.mark.asyncio
async def test_sql_matches_the_cli(local_db, capsys):
    sql = "SELECT id, name FROM customers WHERE id > :min ORDER BY id"
    _, body = envelope(["sql", sql, "local", "-p", "min=1", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        err, env = await call(client, "sql", connection="local", sql=sql, params={"min": "1"})
    assert err is False
    assert _without_elapsed(env["data"]) == _without_elapsed(body["data"])


@pytest.mark.asyncio
async def test_sql_explain_matches_the_cli(local_db, capsys):
    _, body = envelope(["sql", "SELECT * FROM customers", "local", "--explain", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        _, env = await call(client, "sql", connection="local", sql="SELECT * FROM customers", explain=True)
    assert env["data"]["plan"] == body["data"]["plan"]


@pytest.mark.asyncio
async def test_run_and_history_match_the_cli(local_db, capsys):
    run_cli(["query", "add", "by-id", "--sql", "SELECT name FROM customers WHERE id = :id",
             "--connection", "local", "-f", "json"])
    capsys.readouterr()
    _, body = envelope(["run", "by-id", "-p", "id=1", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        _, env = await call(client, "run", query="by-id", params={"id": "1"})
        _, hist = await call(client, "history", limit=5)
    assert _without_elapsed(env["data"]) == _without_elapsed(body["data"])
    # The MCP run was recorded like a CLI run: two entries now, newest first.
    assert [h["name"] for h in hist["data"][:2]] == ["by-id", "by-id"]


@pytest.mark.asyncio
async def test_multi_and_run_group_match_the_cli(local2_db, capsys):
    sql = "SELECT id, value FROM orders ORDER BY id"
    run_cli(["group", "add", "adhoc", "--adhoc-sql", sql, "--connection", "local",
             "--connection", "local2", "-f", "json"])
    capsys.readouterr()
    code, multi = envelope(["multi", sql, "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 5
    _, group = envelope(["run-group", "adhoc", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        err, m = await call(client, "multi", sql=sql, connections=["local", "local2"])
        err2, g = await call(client, "run_group", group="adhoc")
    # Divergence is a completed run, not an error -- as on the CLI's stdout.
    assert err is False and err2 is False
    assert m["data"] == multi["data"]
    assert g["data"] == group["data"]
    assert m["data"]["all_match"] is False


@pytest.mark.asyncio
async def test_test_connection_matches_the_cli(local_db, capsys):
    _, body = envelope(["test", "local", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        _, env = await call(client, "test_connection", connection="local")
        _, every = await call(client, "test_connection")
    assert env["data"] == body["data"]
    assert [d["name"] for d in every["data"]] == ["local"]


@pytest.mark.asyncio
async def test_warnings_travel_in_the_envelope(local2_db, capsys):
    """`multi` over rows with a repeated key warns on the CLI; the same
    warning reaches the MCP envelope under the same key."""
    sql = "SELECT customer_id AS id, value FROM orders ORDER BY id"
    _, body = envelope(["multi", sql, "-c", "local", "-c", "local2", "-f", "json"], capsys)
    async with Client(build_server(ServerOptions())) as client:
        _, env = await call(client, "multi", sql=sql, connections=["local", "local2"])
    assert env.get("warnings") == body.get("warnings")

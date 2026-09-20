"""The server: eleven tools, one envelope, no stdout.

Each tool is the CLI command of the same name minus the parsing and the
rendering: it resolves its connection through the policy's resolver, calls
the `ops` function the CLI calls, and returns the CLI's envelope as a
`CallToolResult` -- built here rather than raised, because that is the
only way (measured on SDK 2.2.0) to set `is_error` and keep the content
free of the SDK's "Error executing tool" prefix. The aliases below are the
CLI's (`catalogue`, `ops_schema`, `ops_sql`, `queries`, `compare`) on
purpose: `tests/design/test_mcp_parity.py` matches `alias.function` text
between the two front ends.

Tool functions are synchronous: the SDK runs them in a worker thread, which
is right for drivers that block. Logging goes to stderr at WARNING; under
stdio, stdout belongs to the protocol.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Final, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from dbqm._version import __version__
from dbqm.cli.errors import ERROR_CODES, ExitCode
from dbqm.i18n import t
from dbqm.mcp import policy
from dbqm.mcp.options import ServerOptions
from dbqm.ops import catalogue, compare, queries
from dbqm.ops import schema as ops_schema
from dbqm.ops import sql as ops_sql
from dbqm.ops.errors import OperationError

#: Registration order; `list_tools` reports them in it.
TOOL_NAMES: Final[tuple[str, ...]] = ("list", "test_connection", "objects", "describe",
                                      "rows", "ddl", "history", "run", "run_group",
                                      "multi", "sql")

_READ_ONLY = ToolAnnotations(read_only_hint=True)


def _json_safe(data: Any) -> Any:
    """`envelope.py` dumps with `default=str`; the same rule here, so a
    `datetime` or a `Decimal` in a row never fails serialisation."""
    return json.loads(json.dumps(data, default=str))


def _result(payload: dict[str, Any], *, is_error: bool) -> CallToolResult:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return CallToolResult(content=[TextContent(type="text", text=text)],
                          structured_content=payload, is_error=is_error)


def _ok(command: str, data: Any, *, warnings: list[str] | None = None) -> CallToolResult:
    payload: dict[str, Any] = {"ok": True, "command": command, "data": _json_safe(data)}
    if warnings:
        payload["warnings"] = list(warnings)
    return _result(payload, is_error=False)


def _fail(command: str, code: str, message: str) -> CallToolResult:
    # `.get` with a fallback rather than `exit_for`: an unknown token here
    # would raise from inside `_guarded`'s own `except OperationError`
    # handler, past the catch-all meant to stop exactly that.
    exit_code = int(ERROR_CODES.get(code, ExitCode.UNEXPECTED))
    payload = {"ok": False, "command": command,
               "error": {"code": code, "message": message, "exit": exit_code}}
    return _result(payload, is_error=True)


def _guarded(command: str, action: Callable[[], CallToolResult]) -> CallToolResult:
    """Run *action*; an `OperationError` is the CLI's failure envelope, and
    anything else is `unexpected` -- the CLI's "a bug in dbqm", exit 1."""
    try:
        return action()
    except OperationError as e:
        return _fail(command, e.code, e.message)
    except Exception as e:  # the whole point: nothing escapes to the protocol
        return _fail(command, "unexpected", t("common.unexpected_error", error=e))


def build_server(options: ServerOptions) -> MCPServer:
    """An `MCPServer` with the eleven tools bound to *options*."""
    server = MCPServer(name="dbqm", version=__version__,
                       instructions=t("mcp.server_description"), log_level="WARNING")
    resolve = policy.resolver(options)
    sql_annotations = ToolAnnotations(read_only_hint=not options.allow_write,
                                      destructive_hint=options.allow_write)

    @server.tool(name="list", description=t("mcp.tool.list"), annotations=_READ_ONLY)
    def list_saved(kind: Literal["connections", "queries", "groups"]) -> CallToolResult:
        def action() -> CallToolResult:
            if kind == "connections":
                items = [catalogue.connection_summary(c) for c in catalogue.connections()]
                return _ok("list.connections", policy.visible(options, items))
            if kind == "queries":
                shown_queries = policy.visible_queries(options, catalogue.queries())
                return _ok("list.queries", [catalogue.query_summary(q) for q in shown_queries])
            shown_groups = policy.visible_groups(options, catalogue.groups(), catalogue.queries())
            return _ok("list.groups", [catalogue.group_summary(g) for g in shown_groups])
        return _guarded(f"list.{kind}", action)

    @server.tool(name="test_connection", description=t("mcp.tool.test_connection"), annotations=_READ_ONLY)
    def test_connection(connection: str | None = None) -> CallToolResult:
        def action() -> CallToolResult:
            names = [connection] if connection else policy.exposed_names(options)
            return _ok("test", catalogue.test_connections(names, resolve=resolve))
        return _guarded("test", action)

    @server.tool(name="objects", description=t("mcp.tool.objects"), annotations=_READ_ONLY)
    def objects(connection: str, type: Literal["TABLE", "VIEW", "PACKAGE", "ROUTINE"]) -> CallToolResult:
        def action() -> CallToolResult:
            conn = resolve(connection)
            names = ops_schema.list_objects(conn, type)
            return _ok("objects", {"connection_name": conn.name, "obj_type": type, "objects": names})
        return _guarded("objects", action)

    @server.tool(name="describe", description=t("mcp.tool.describe"), annotations=_READ_ONLY)
    def describe(connection: str, object: str) -> CallToolResult:
        return _guarded("describe", lambda: _ok("describe", ops_schema.describe(resolve(connection), object)))

    @server.tool(name="rows", description=t("mcp.tool.rows"), annotations=_READ_ONLY)
    def rows(connection: str, table: str, limit: int = 100, offset: int = 0) -> CallToolResult:
        return _guarded("rows", lambda: _ok(
            "rows", ops_schema.rows(resolve(connection), table, limit=limit, offset=offset).to_dict()))

    @server.tool(name="ddl", description=t("mcp.tool.ddl"), annotations=_READ_ONLY)
    def ddl(connection: str, object: str) -> CallToolResult:
        def action() -> CallToolResult:
            result = ops_schema.extract_ddl(resolve(connection), object)
            return _ok("ddl", {"objects": [o.to_dict() for o in result.objects], "path": None},
                       warnings=result.errors or None)
        return _guarded("ddl", action)

    @server.tool(name="history", description=t("mcp.tool.history"), annotations=_READ_ONLY)
    def history(limit: int = 20) -> CallToolResult:
        return _guarded("history", lambda: _ok("history", [e.to_dict() for e in catalogue.history(limit)]))

    @server.tool(name="run", description=t("mcp.tool.run"), annotations=_READ_ONLY)
    def run(query: str, params: dict[str, str] | None = None, connection: str | None = None) -> CallToolResult:
        return _guarded("run", lambda: _ok(
            "run", queries.run_query(query, params or {}, connection=connection, resolve=resolve).to_dict()))

    @server.tool(name="run_group", description=t("mcp.tool.run_group"), annotations=_READ_ONLY)
    def run_group(group: str, params: dict[str, str] | None = None) -> CallToolResult:
        def action() -> CallToolResult:
            comparison = compare.run_group(group, params or {}, resolve=resolve)
            return _ok("run-group", compare.run_group_data(comparison), warnings=comparison.warnings or None)
        return _guarded("run-group", action)

    @server.tool(name="multi", description=t("mcp.tool.multi"), annotations=_READ_ONLY)
    def multi(sql: str, connections: list[str], params: dict[str, str] | None = None,
              key: str | None = None) -> CallToolResult:
        def action() -> CallToolResult:
            comparison = compare.multi(sql, connections, params or {}, key=key, resolve=resolve)
            return _ok("multi", compare.multi_data(comparison), warnings=comparison.warnings or None)
        return _guarded("multi", action)

    @server.tool(name="sql", description=t("mcp.tool.sql"), annotations=sql_annotations)
    def sql(connection: str, sql: str, params: dict[str, str] | None = None,
            commit: bool = False, explain: bool = False) -> CallToolResult:
        def action() -> CallToolResult:
            conn = resolve(connection)
            values = params or {}
            if explain:
                result = ops_sql.explain(conn, sql, values)
                plan = [row[0] if row else "" for row in result.rows]
                return _ok("sql", {"connection_name": conn.name, "elapsed": round(result.elapsed, 3), "plan": plan})
            result = ops_sql.run_sql(conn, sql, values, commit=commit)
            return _ok("sql", result.to_dict(), warnings=result.output_lines or None)
        return _guarded("sql", action)

    return server


def run(options: ServerOptions) -> None:
    """Serve on stdio until the client hangs up."""
    build_server(options).run(transport="stdio")

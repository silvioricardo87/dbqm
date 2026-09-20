"""The two rules the server applies on top of `ops/`: which connections it
exposes, and whether any of them may write.

Both hang on the one seam `ops/` offers -- the resolver -- so `ops/` never
learns the MCP server exists. The forced read-only copy is
`dataclasses.replace`, transient, and never reaches `save_connections`.
Because `core/` reads only `conn.read_only`, and `get_connection` pins
read-only on the server for PostgreSQL, MySQL, Oracle and SQLite, the copy
is read-only end to end on those engines; on SQL Server it is enforced by
`check_read_only` alone (`docs/MCP.md` says so).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from dbqm.i18n import t
from dbqm.mcp.options import ServerOptions
from dbqm.models.connection import Connection
from dbqm.models.group import Group
from dbqm.models.query import Query
from dbqm.ops import catalogue
from dbqm.ops.catalogue import Resolver
from dbqm.ops.errors import OperationError


def resolver(options: ServerOptions) -> Resolver:
    """Name -> Connection under *options*: allowlist first, then the stored
    connection, forced read-only unless `--allow-write`."""

    def resolve(name: str) -> Connection:
        if options.connections is not None and name not in options.connections:
            raise OperationError("not_found", t("mcp.connection_not_exposed", name=name))
        conn = catalogue.connection(name)
        return conn if options.allow_write else replace(conn, read_only=True)

    return resolve


def exposed_names(options: ServerOptions) -> list[str] | None:
    """The allowlist, sorted, or `None` for every configured connection."""
    return None if options.connections is None else sorted(options.connections)


def visible(options: ServerOptions, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`list connections` as this server sees it: the allowlist applied,
    and `read_only` reporting the EFFECTIVE value, not the stored one."""
    shown = [dict(i) for i in items
             if options.connections is None or i["name"] in options.connections]
    if not options.allow_write:
        for item in shown:
            item["read_only"] = True
    return shown


def visible_queries(options: ServerOptions, queries: list[Query]) -> list[Query]:
    """The allowlist scopes the catalogue too: a query against a connection
    this server does not expose is not something an agent should learn
    exists."""
    if options.connections is None:
        return list(queries)
    return [q for q in queries if q.connection in options.connections]


def visible_groups(options: ServerOptions, groups: list[Group], queries: list[Query]) -> list[Group]:
    """A group is visible only when every connection it touches is: every
    ad-hoc connection it names directly, and every saved query it runs
    (through that query's own connection)."""
    if options.connections is None:
        return list(groups)
    visible_query_names = {q.name for q in visible_queries(options, queries)}
    shown = []
    for g in groups:
        if any(c not in options.connections for c in g.connections):
            continue
        if any(name not in visible_query_names for name in g.queries):
            continue
        shown.append(g)
    return shown

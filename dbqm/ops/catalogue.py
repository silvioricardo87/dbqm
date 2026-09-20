"""What is configured: connections, saved queries, groups, history.

The summaries here are the exact dicts `dbqm list -f json` emits per item,
so the CLI and the MCP server cannot disagree about a field name. The
objects themselves are returned too, because the CLI's tables read fields
the summary does not carry.
"""
from __future__ import annotations

from typing import Any, Callable

from dbqm.core.history import HistoryEntry
from dbqm.i18n import t
from dbqm.models.connection import Connection
from dbqm.models.group import Group
from dbqm.models.query import Query
from dbqm.ops import deps
from dbqm.ops.errors import OperationError

#: Name -> Connection. The one seam a front end can wrap: the MCP server
#: hands in a resolver that applies its allowlist and forces read-only.
Resolver = Callable[[str], Connection]


def connection(name: str) -> Connection:
    """The stored connection called *name*, or `not_found`."""
    conn = deps.find_connection(name)
    if not conn:
        raise OperationError("not_found", t("connection.not_found_named", name=name))
    return conn


def resolver_or_default(resolve: Resolver | None) -> Resolver:
    """*resolve* itself, or `connection` -- decided at call time on purpose,
    so a test that patches `deps.find_connection` is honoured."""
    return resolve if resolve is not None else connection


def connections() -> list[Connection]:
    return deps.load_connections()


def queries() -> list[Query]:
    return deps.load_queries()


def groups() -> list[Group]:
    return deps.load_groups()


def connection_summary(c: Connection) -> dict[str, Any]:
    return {"name": c.name, "db_type": c.db_type, "target": c.display_target(),
            "read_only": c.read_only}


def query_summary(q: Query) -> dict[str, Any]:
    return {"name": q.name, "connection": q.connection, "folder": q.folder,
            "description": q.description, "params": [p.name for p in q.params]}


def group_summary(g: Group) -> dict[str, Any]:
    return {"name": g.name, "description": g.description, "queries": g.queries,
            "join_key": g.join_key, "compare_columns": g.compare_columns}


def test_connections(
    names: list[str] | None, *, resolve: Resolver | None = None,
) -> list[dict[str, Any]]:
    """Try each connection and say what happened to it.

    A connection that fails to connect is an item with `ok: false`, never
    an error: the job is to report each one, not to fail because one is
    down. `names` of `None` means every stored connection; a list goes
    through *resolve*, so a name that is not there is `not_found`.

    A front end with a policy always gets it applied: with a resolver,
    every stored connection goes through it too. Without one, `names=None`
    takes the stored connections as stored -- what the CLI's own unit
    tests, which patch `deps.load_connections` alone, rely on.
    """
    if names is None:
        if resolve is not None:
            targets = [resolve(c.name) for c in connections()]
        else:
            targets = connections()
    else:
        resolver = resolver_or_default(resolve)
        targets = [resolver(name) for name in names]
    data = []
    for conn in targets:
        succeeded, msg = deps.test_connection(conn)
        data.append({"name": conn.name, "ok": succeeded, "message": msg})
    return data


def history(limit: int | None) -> list[HistoryEntry]:
    """The most recent *limit* entries (default 20). `usage` below 1: `-n 0`
    used to mean the default and `-n -5` meant all but the last five."""
    if limit is not None and limit < 1:
        raise OperationError("usage", t("history.limit_positive"))
    return deps.load_history()[: limit or 20]

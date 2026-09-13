"""The guard that makes a connection query-only.

It sits at classification, before the statement is sent -- never "send it and
skip the commit". No driver dbqm uses sets autocommit, so nothing persists
without an explicit commit, which makes refusing to commit look sufficient. It
is not: a stored routine can COMMIT internally and Oracle DDL commits itself,
and both bypass the commit gate. Classifying first is right either way.

This is a rail against mistakes, not a security boundary. Whoever can connect
can write with another client; what this stops is the wrong connection name,
the generated statement, the careless paste.
"""
from __future__ import annotations

import sqlparse

#: What a query-only connection may carry.
ALLOWED = frozenset({"SELECT", "EXPLAIN"})


class ReadOnlyViolation(RuntimeError):
    """A statement that could modify was aimed at a query-only connection."""


def _statement_count(sql: str) -> int:
    """How many statements the driver would see.

    `classify_sql` inspects only the first one while the whole string is sent,
    so `SELECT 1; DROP TABLE alvo` classifies as SELECT and both would run on
    PostgreSQL and SQL Server. A trailing semicolon is not a second statement,
    and neither is one inside a string literal -- `sqlparse` handles both,
    which is why the count is not a `str.count(";")`.
    """
    return len([s for s in sqlparse.parse(sql) if s.token_first() is not None])


def check_read_only(sql: str, conn) -> None:
    """Raise `ReadOnlyViolation` if `conn` is read-only and `sql` could write.

    Does nothing when the connection is writable, so callers can invoke it
    unconditionally.
    """
    # Imported here, not at module scope: `query_engine` imports this module
    # to call the guard, so a top-level import back into it is a cycle.
    from dbqm.core.query_engine import classify_sql

    if not getattr(conn, "read_only", False):
        return

    recusa = (
        f"Conexao '{conn.name}' e somente leitura. "
        "Use --force-write para enviar assim mesmo."
    )

    if _statement_count(sql) > 1:
        raise ReadOnlyViolation(
            f"Conexao '{conn.name}' e somente leitura e o comando tem mais de "
            "um statement, que nao podem ser verificados separadamente. "
            "Use --force-write para enviar assim mesmo."
        )

    if classify_sql(sql) not in ALLOWED:
        raise ReadOnlyViolation(recusa)

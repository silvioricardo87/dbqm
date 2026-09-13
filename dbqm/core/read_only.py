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

import re
from typing import TYPE_CHECKING

import sqlparse

if TYPE_CHECKING:
    from dbqm.models.connection import Connection

#: What a query-only connection may carry. `EXPLAIN` is here only as a
#: prefix — see `_explains_a_query`, which is what decides whether a given
#: EXPLAIN is actually read-only.
ALLOWED = frozenset({"SELECT", "EXPLAIN"})

#: Everything an engine may put between `EXPLAIN` and the statement it
#: explains. PostgreSQL takes `ANALYZE`, `VERBOSE` and a parenthesised option
#: list; MySQL takes `ANALYZE` and `FORMAT=JSON`; Oracle spells it
#: `EXPLAIN PLAN FOR`, optionally with `SET STATEMENT_ID = '...'`.
_EXPLAIN_PREFIX = re.compile(
    r"""^\s*EXPLAIN\s+
        (?:\(\s*[^)]*\)\s*)?              # PostgreSQL: (FORMAT JSON, ANALYZE)
        (?:ANALYZE\s+)?
        (?:VERBOSE\s+)?
        (?:FORMAT\s*=\s*\w+\s+)?          # MySQL: FORMAT=JSON
        (?:PLAN\s+                        # Oracle: PLAN [SET STATEMENT_ID=x] FOR
           (?:SET\s+STATEMENT_ID\s*=\s*\S+\s+)?
           FOR\s+)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


class ReadOnlyViolation(RuntimeError):
    """A statement that could modify was aimed at a query-only connection."""


def statement_count(sql: str) -> int:
    """How many statements the driver would see.

    `classify_sql` inspects only the first one while the whole string is sent,
    so `SELECT 1; DROP TABLE alvo` classifies as SELECT and both would run on
    PostgreSQL and SQL Server. A trailing semicolon is not a second statement,
    and neither is one inside a string literal -- `sqlparse` handles both,
    which is why the count is not a `str.count(";")`.
    """
    return len([
        s for s in sqlparse.parse(sql)
        if s.token_first() is not None  # type: ignore[no-untyped-call]  # sqlparse ships py.typed, but Statement.token_first() itself is unannotated upstream
    ])


def _explains_a_query(sql: str) -> bool:
    """Whether an `EXPLAIN` explains something that only reads.

    `EXPLAIN` alone is not read-only. On PostgreSQL and MySQL,
    `EXPLAIN ANALYZE DELETE FROM t` **runs the delete** -- the plan is
    produced by executing the statement, not by predicting it. `classify_sql`
    reports the whole thing as `EXPLAIN`, so without this the guard would wave
    through a write on two of the four engines.

    Fail closed: anything that does not reduce to a `SELECT` is refused,
    including an `EXPLAIN` whose prefix this does not recognise.
    """
    from dbqm.core.query_engine import classify_sql

    restante = _EXPLAIN_PREFIX.sub("", sql, count=1)
    if restante == sql:
        # The prefix did not match at all, so there is nothing to vouch for.
        return False
    return classify_sql(restante) == "SELECT"


def check_read_only(sql: str, conn: "Connection") -> None:
    """Raise `ReadOnlyViolation` if `conn` is read-only and `sql` could write.

    Does nothing when the connection is writable, so callers can invoke it
    unconditionally. `conn` is read directly rather than through a defaulted
    `getattr`: every call site passes a real `Connection`, and a guard that
    silently approves whatever it does not recognise is the failure mode this
    module exists to prevent.
    """
    # Imported here, not at module scope: `query_engine` imports this module
    # to call the guard, so a top-level import back into it is a cycle.
    from dbqm.core.query_engine import classify_sql

    if not conn.read_only:
        return

    recusa = (
        f"Conexao '{conn.name}' e somente leitura. "
        "Use --force-write para enviar assim mesmo."
    )

    if statement_count(sql) > 1:
        raise ReadOnlyViolation(
            f"Conexao '{conn.name}' e somente leitura e o comando tem mais de "
            "um statement, que nao podem ser verificados separadamente. "
            "Use --force-write para enviar assim mesmo."
        )

    tipo = classify_sql(sql)
    if tipo not in ALLOWED:
        raise ReadOnlyViolation(recusa)

    if tipo == "EXPLAIN" and not _explains_a_query(sql):
        raise ReadOnlyViolation(
            f"Conexao '{conn.name}' e somente leitura e este EXPLAIN executa o "
            "comando que explica. Use --force-write para enviar assim mesmo."
        )

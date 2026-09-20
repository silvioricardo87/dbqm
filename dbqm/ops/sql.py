"""Ad-hoc statements: classify, guard, run, explain.

The refusals happen in the order the CLI has always used and the
functional tests measure: an undeclared parameter first (a typo that would
run unfiltered), then the read-only question (a flag the caller can fix is
not the real obstacle), then `commit` for DML.
"""
from __future__ import annotations

from dbqm.core.query_engine import AdhocResult
from dbqm.i18n import t
from dbqm.models.connection import Connection
from dbqm.ops import deps
from dbqm.ops.errors import OperationError

_DML = ("INSERT", "UPDATE", "DELETE")


def sql_error_code(message: str | None, error_kind: str = "") -> str:
    """The token for a failed result.

    `connection` wins over everything: the database never answered, so
    nothing about the statement is known. `read_only` is next -- the guard
    refused to send the statement at all, which `cmd_sql` already reports as
    `read_only`/exit 2, and `execute_across` (`group_engine.py`) tags the
    same way so the two commands agree about what the same event is.
    Otherwise `usage` when `core/` tagged the result that way -- bad input
    that never reached a driver -- and `sql_error` for the rest, which the
    driver rejected or failed on.

    Read from `error_kind` rather than by recognising the message: the
    message is a translation now, so matching its wording would classify
    correctly in one language and silently wrongly in every other.
    """
    if error_kind == "connection":
        return "connection_failed"
    if error_kind == "read_only":
        return "read_only"
    if error_kind == "usage":
        return "usage"
    return "sql_error"


def refuse_undeclared_params(sql: str, params: dict[str, str]) -> None:
    """Refuse a `-p` whose name the SQL never binds.

    The statement is right there, so the set of names it accepts is exactly
    knowable -- and a name outside it is a typo that would otherwise run
    unfiltered and be reported as a result.
    """
    if not params:
        return
    declared = set(deps.detect_params(sql))
    unknown = sorted(set(params) - declared)
    if unknown:
        raise OperationError("validation", t("param.not_in_sql", name=unknown[0]))


def classify_and_guard(conn: Connection, sql: str, params: dict[str, str]) -> str:
    """The statement's type, after the two refusals that need no driver."""
    refuse_undeclared_params(sql, params)
    sql_type: str = deps.classify_sql(sql)
    try:
        deps.check_read_only(sql, conn)
    except deps.ReadOnlyViolation as e:
        raise OperationError("read_only", str(e)) from e
    return sql_type


def _failed(result: AdhocResult, default_key: str) -> OperationError:
    return OperationError(sql_error_code(result.error, result.error_kind),
                          result.error or t(default_key))


def run_sql(conn: Connection, sql: str, params: dict[str, str], *, commit: bool) -> AdhocResult:
    """Run *sql* and return its result, or raise with the token the CLI exits on.

    `execute_adhoc` returns a `(result, connection)` tuple only for DML left
    uncommitted; the `commit` refusal below runs first, so the call always
    yields a plain `AdhocResult` here.
    """
    sql_type = classify_and_guard(conn, sql, params)
    if sql_type in _DML and not commit:
        raise OperationError("usage", t("sql.dml_needs_commit"))
    try:
        outcome = deps.execute_adhoc(sql, conn, params, auto_commit=commit)
    except deps.ReadOnlyViolation as e:
        raise OperationError("read_only", str(e)) from e
    if isinstance(outcome, tuple):  # pragma: no cover - unreachable, see docstring
        raise RuntimeError("execute_adhoc returned a manual-commit tuple despite auto_commit=True")
    result = outcome
    if not result.success:
        if result.sql_type == "DDL":
            raise _failed(result, "sql.ddl_failed")
        if result.sql_type == "PLSQL":
            raise _failed(result, "sql.block_failed")
        raise _failed(result, "sql.execute_failed")
    return result


def explain(conn: Connection, sql: str, params: dict[str, str]) -> AdhocResult:
    refuse_undeclared_params(sql, params)
    try:
        result = deps.execute_explain(sql, conn, params)
    except deps.ReadOnlyViolation as e:
        raise OperationError("read_only", str(e)) from e
    if not result.success:
        raise _failed(result, "sql.explain_failed")
    return result

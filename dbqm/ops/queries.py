"""Saved queries: resolve, validate parameters, run, record."""
from __future__ import annotations

from dbqm.core.query_engine import QueryResult
from dbqm.i18n import t
from dbqm.ops import deps
from dbqm.ops.catalogue import Resolver, resolver_or_default
from dbqm.ops.errors import OperationError
from dbqm.ops.sql import sql_error_code


def run_query(
    name: str, params: dict[str, str], *,
    connection: str | None = None, resolve: Resolver | None = None,
) -> QueryResult:
    """Run the saved query *name*; `connection` overrides the query's own.

    `execute_query` is SELECT-only by construction: a saved query that is
    not a SELECT never reaches a driver, it comes back `success=False,
    error_kind="usage"` and is reported as such below, so this function
    raises no `ReadOnlyViolation`.
    """
    query = deps.find_query(name)
    if not query:
        raise OperationError("not_found", t("query.not_found_named", name=name))
    conn = resolver_or_default(resolve)(connection or query.connection)
    param_values = dict(params)

    # A name the query does not declare is a typo, and accepting it means
    # running unfiltered and calling it a result.
    declared = {p.name for p in query.params}
    unknown = sorted(set(param_values) - declared)
    if unknown:
        raise OperationError(
            "validation",
            t("run.param_not_declared", query=query.name, parameter=unknown[0]),
        )

    # Fill missing params with defaults, then validate required params.
    for p in query.params:
        if p.name not in param_values and p.default:
            param_values[p.name] = p.default
    missing = [p.name for p in query.params if p.name not in param_values]
    if missing:
        raise OperationError("validation", t("run.params_missing", names=", ".join(missing)))

    result = deps.execute_query(query, conn, param_values)

    if result.success and query.column_maps:
        query.apply_column_maps(result.rows, result.columns)

    deps.record_query_execution(
        query.name, conn.name, param_values,
        result.row_count, result.elapsed, result.success, result.error,
    )
    deps.log_execution("query", query.name, conn.name, param_values,
                        row_count=result.row_count, success=result.success, error=result.error)

    if not result.success:
        raise OperationError(sql_error_code(result.error, result.error_kind),
                              result.error or t("run.execute_failed"))
    return result

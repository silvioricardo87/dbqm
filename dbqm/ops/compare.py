"""Comparisons: one statement across connections, or a saved group.

Divergence is a result, not an error: `Comparison.group_result.all_match`
says what happened, and the CLI maps False to exit 5. Everything that
stops a comparison from being meaningful -- one connection, a statement
that returns no rows, a key not common to every side, zero columns to
compare -- is refused before or after the run with the token the CLI has
always used.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from dbqm.core.group_engine import GroupResult, duplicate_key_warnings
from dbqm.i18n import t
from dbqm.models.connection import Connection
from dbqm.ops import deps
from dbqm.ops.catalogue import Resolver, resolver_or_default
from dbqm.ops.errors import OperationError
from dbqm.ops.sql import refuse_undeclared_params, sql_error_code


@dataclass
class Comparison:
    group_result: GroupResult
    warnings: list[str]
    #: The key that was used when it was derived at run time (multi, ad-hoc
    #: group) -- reported so a caller is not left guessing. None for a
    #: saved group, which has the key it was given.
    join_key: str | None = None
    #: Per-connection results, keyed by name in the order given; the table
    #: header of `multi` lists them. Empty for a saved group.
    results: dict[str, Any] = field(default_factory=dict)
    #: The parameters the comparison actually ran with: the caller's, plus
    #: a group's `shared_params` defaults. What an export embeds and a
    #: history record stores.
    params: dict[str, str] = field(default_factory=dict)


def comparison_data(comparison: Comparison) -> list[dict[str, Any]]:
    """The `comparisons` array both `multi -f json` and `run-group -f json` emit."""
    return [
        {
            "column": c.column,
            "total_keys": c.total_keys,
            "equal_count": c.equal_count,
            "diff_count": c.diff_count,
            "absent_count": c.absent_count,
            "normalized_count": c.normalized_count,
            "duplicate_rows": dict(c.duplicate_rows),
        }
        for c in comparison.group_result.comparisons
    ]


def multi_failure_code(codes: list[str]) -> str:
    """The one exit token for a set of failing connections.

    Order-independent on purpose: `-c a -c b` and `-c b -c a` over the same
    failures must exit the same way, so this looks at the whole set rather
    than the first entry. `connection_failed` outranks everything else --
    the database never answered, which is the more urgent fact to report --
    and `usage` outranks `sql_error` so a statement that never reached any
    driver is not reported as one the driver rejected.
    """
    if "connection_failed" in codes:
        return "connection_failed"
    if "read_only" in codes:
        return "read_only"
    if "usage" in codes:
        return "usage"
    return "sql_error"


def compare_across(
    sql: str,
    resolved: list[tuple[str, Connection]],
    params: dict[str, str],
    *,
    key: str | None,
) -> Comparison:
    """Run one statement on every resolved connection and compare the results.

    The half of `multi` that `run_group` needs too, once a saved ad-hoc
    group is a thing the CLI can run: everything from opening the
    connections to a `GroupResult`, including the refusals on the way --
    a connection that fails, a key that is not common to every side, a
    comparison that would look at zero columns. What it deliberately does
    NOT do is print or exit; the two callers report the same result under
    different names and different envelopes, and that stays theirs.
    """
    # `execute_across` (core/) still accepts a `None` connection -- other
    # callers resolve their own way and may hand it a gap to skip. Every
    # `resolved` this module builds comes from a `Resolver`, which raises
    # rather than returning one, so the narrower type here is honest; this
    # is the one seam where it widens back for the call.
    conns: list[tuple[str, Connection | None]] = list(resolved)
    results = deps.execute_across(sql, conns, params)

    failing = [(name, result) for name, result in results.items() if not result.success]
    if failing:
        # Named per connection with what actually happened -- a statement
        # error is the database answering, not the connection failing, a
        # read-only refusal is neither (the guard never sent the statement
        # at all -- `cmd_sql` reports the identical condition as `read_only`,
        # exit 2, and the two commands must not disagree about what the same
        # event is), and `sql_error_code` is what tells all of these apart
        # (it also catches the messages `core/` returns for a statement
        # never sent to any driver, which a plain connection/sql_error
        # dichotomy mislabelled as `sql_error`). The aggregate exit code
        # does not depend on which failing connection happens to come first
        # -- see `multi_failure_code` -- and every failing connection is
        # named, not just one.
        codes = [sql_error_code(result.error, result.error_kind) for _, result in failing]
        parts = []
        for (name, result), code in zip(failing, codes, strict=True):
            if code == "connection_failed":
                parts.append(t("multi.connection_failed", name=name, error=result.error))
            elif code == "read_only":
                parts.append(t("multi.read_only", name=name, error=result.error))
            elif code == "usage":
                parts.append(t("multi.usage_error", name=name, error=result.error))
            else:
                parts.append(t("multi.query_error", name=name, error=result.error))
        raise OperationError(multi_failure_code(codes), "; ".join(parts))

    try:
        join_key, compare_columns = deps.derive_comparison_columns(results)
    except deps.NoComparableColumns as e:
        raise OperationError("validation", str(e)) from e

    common = [join_key, *compare_columns]

    if key:
        # A key that is not common to every result is the same trap as
        # passing no `compare_columns` at all: `run_comparison` would index
        # it to `None` in every result, every key set would come back empty,
        # and `all([])` is `True` over rows it never actually looked at.
        # Refused here rather than left to that indexing, naming the column.
        if key not in common:
            raise OperationError(
                "validation",
                t("multi.key_not_common", column=key),
            )
        # Re-deriving instead of trusting `build_adhoc_group_result`'s own
        # `join_key`-given branch to leave `compare_columns` alone: that
        # branch defaults `compare_columns` to `[]` when none is passed,
        # which silently compares nothing -- `--key` would report
        # CONSISTENTE over data it never looked at. Removing the requested
        # key from the derived common-column list keeps every other common
        # column in the comparison instead.
        compare_columns = [c for c in common if c != key]
        join_key = key

    if not compare_columns:
        # Reachable with or without `--key`: when the only column common to
        # every result is the join key itself, `derive_comparison_columns`
        # deliberately returns `(key, [])` -- core decides nothing about
        # whether that is enough, on purpose (see
        # `test_one_common_column_compares_nothing_but_still_has_a_key`).
        # This decides for itself: a comparison of zero columns would
        # report CONSISTENTE regardless of what the rows actually say, so it
        # refuses instead of running one.
        raise OperationError(
            "validation",
            t("multi.only_common_column", column=join_key),
        )

    group_result = deps.build_adhoc_group_result(
        results, join_key=join_key, compare_columns=compare_columns,
    )

    warnings = duplicate_key_warnings(group_result)
    return Comparison(group_result, warnings, join_key, results)


def multi(
    sql: str,
    names: list[str],
    params: dict[str, str],
    *,
    key: str | None,
    resolve: Resolver | None = None,
) -> Comparison:
    """Run one ad-hoc SQL across several connections and compare the results.

    Order matters here and is the whole point: fewer than two *distinct*
    connections, and any SQL that is not a query are both refused before
    anything opens -- a comparison has no result set to compare if the
    statement never returns one, so this refuses DML, DDL and PL/SQL
    outright rather than running them across every connection first and
    discovering that after the fact. Every connection name is then
    resolved before any of them is opened, so a bad name is reported
    without a single query having run; and once `compare_across` has run
    every resolved connection, any unsuccessful one fails the whole call --
    a comparison over a subset would silently answer a different question
    than the one asked.
    """
    # Order-preserving de-duplication: `-c prod -c prod` collapses to one
    # entry once `execute_across` keys its result dict by connection name,
    # so a comparison would run over a single result and could only ever
    # report OK -- the same class of silent wrong answer as the other
    # refusals below, reached through dict collapse instead of `all([])`.
    seen: dict[str, int] = {}
    for name in names:
        seen[name] = seen.get(name, 0) + 1
    distinct_names = list(seen)
    if len(distinct_names) < 2:
        repeated = [name for name, count in seen.items() if count > 1]
        if repeated:
            raise OperationError(
                "usage",
                t("multi.connection_repeated", name=repeated[0]),
            )
        raise OperationError("usage", t("multi.two_connections_required"))
    names = distinct_names

    # A comparison needs a result set to compare, and only SELECT/EXPLAIN
    # produce one. Refusing here -- before any connection is even resolved,
    # let alone opened -- is what keeps `multi("DELETE FROM t", ...)` from
    # running the delete on every connection and only then discovering
    # there is nothing to compare.
    sql_type = deps.classify_sql(sql)
    if sql_type not in ("SELECT", "EXPLAIN"):
        raise OperationError(
            "usage",
            t("multi.queries_only", type=sql_type),
        )

    resolver = resolver_or_default(resolve)
    resolved: list[tuple[str, Connection]] = [(name, resolver(name)) for name in names]

    refuse_undeclared_params(sql, params)

    comparison = compare_across(sql, resolved, params, key=key)
    comparison.params = dict(params)
    return comparison


def run_group(
    name: str,
    params: dict[str, str],
    *,
    resolve: Resolver | None = None,
) -> Comparison:
    """Run a saved group -- ad-hoc connections or saved queries -- and compare.

    A divergent comparison still writes its history record -- a divergence
    is a completed run, not an aborted one.
    """
    group = deps.find_group(name)
    if not group:
        raise OperationError("not_found", t("group.not_found_named", name=name))
    resolver = resolver_or_default(resolve)
    param_values = dict(params)

    # Fill from shared_params defaults
    for pname, pdef in group.shared_params.items():
        if pname not in param_values and pdef:
            param_values[pname] = pdef

    if group.adhoc_sql:
        # The other shape of a group: one statement over a set of
        # connections, saved by Multi-Exec or by `group add --adhoc-sql`.
        # It runs exactly the way `multi` runs -- same refusals, same
        # derived key -- through the half of `multi` that was extracted for
        # this purpose; only the name on the envelope and the history record
        # differ. The join key is derived, so the caller is told which one
        # was used, for the reason `multi` gives: a key chosen by a rule the
        # caller cannot see turns every number downstream into a guess.
        total_start = time.time()
        resolved: list[tuple[str, Connection]] = [
            (cname, resolver(cname)) for cname in group.connections
        ]
        refuse_undeclared_params(group.adhoc_sql, param_values)
        comparison = compare_across(group.adhoc_sql, resolved, param_values, key=None)
        comparison.params = param_values
        # `build_adhoc_group_result` names the result after its connections;
        # the history and the header are about the GROUP the user ran.
        comparison.group_result.group_name = group.name
        total_elapsed = time.time() - total_start
        summary = "\n".join(comparison.group_result.summary_lines)
        deps.record_group_execution(group.name, param_values, comparison.group_result.all_match,
                                    summary, total_elapsed)
        return comparison

    # Execute all queries in the group
    query_results = {}
    total_start = time.time()
    for qname in group.queries:
        query = deps.find_query(qname)
        if not query:
            raise OperationError(
                "not_found",
                t("group.query_not_found_in_group", name=qname),
            )
        conn = resolver(query.connection)

        result = deps.execute_query(query, conn, param_values)
        if not result.success:
            raise OperationError(
                sql_error_code(result.error, result.error_kind),
                t("group.query_failed", query=qname, error=result.error),
            )

        # Apply column maps
        if query.column_maps:
            query.apply_column_maps(result.rows, result.columns)

        query_results[qname] = result

    total_elapsed = time.time() - total_start

    # `--compare-column` is optional, so a group can name none -- and
    # `run_comparison` over zero columns produces zero `ComparisonResult`,
    # which makes `all(...)` vacuously True: CONSISTENTE, exit 0, over data
    # nothing ever looked at. `multi` has refused this since it shipped;
    # this answers it for a saved group. The columns are derived the same
    # way `multi` derives them, and the caller is told that is what happened.
    compare_columns = list(group.compare_columns)
    derived: list[str] = []
    if not compare_columns:
        try:
            _, derived = deps.derive_comparison_columns(query_results)
        except deps.NoComparableColumns as e:
            raise OperationError("validation", str(e)) from e
        compare_columns = [c for c in derived if c != group.join_key]
        if not compare_columns:
            raise OperationError(
                "validation",
                t("group.no_common_columns", name=group.name, key=group.join_key),
            )

    group_result = deps.build_group_result(
        group.name, query_results, group.join_key,
        compare_columns, group.column_mapping, group.normalize,
    )

    # Record history -- unconditionally: a divergence is a completed run.
    summary = "\n".join(group_result.summary_lines)
    deps.record_group_execution(group.name, param_values, group_result.all_match, summary, total_elapsed)

    # `ds.text.muted` is this design system's warning ink (see
    # `ui/theme.py`): a warning with no colour of its own, because the
    # result it qualifies is still the headline.
    warnings = duplicate_key_warnings(group_result)
    if derived:
        warnings.insert(0, (
            t("group.comparing_common", name=group.name, columns=", ".join(compare_columns))
        ))

    return Comparison(group_result, warnings, params=param_values)

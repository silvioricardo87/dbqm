"""Commands for running saved queries, group comparisons and ad-hoc SQL."""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, NoReturn

from rich.markup import escape

from dbqm.i18n import t
from dbqm.cli import render
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.params import _parse_params
from dbqm.cli.render import console
from dbqm.ops import catalogue, compare, deps, queries
from dbqm.ops import sql as ops_sql
from dbqm.ops.errors import OperationError
from dbqm.core.group_engine import GroupResult
from dbqm.core.object_browser import RoutineInfo
from dbqm.models.connection import Connection

def _fail_or_print(
    args: argparse.Namespace,
    command: str,
    code: str,
    message: str,
    *,
    extra: str | None = None,
) -> NoReturn:
    """Mirrors `connection._fail_or_print`: same branch point for `-f json`
    versus `table`, same exit code either way — only what gets printed, and
    where, differs.
    """
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    if extra:
        console.print(extra)
    sys.exit(int(exit_for(code)))


def _export_group(
    args: argparse.Namespace,
    command: str,
    group_result: GroupResult,
    param_values: dict[str, str],
) -> str:
    """Both export arms (flat and full) for a `GroupResult`, and both
    `usage` fall-throughs, shared by every command that exports one.

    `command` names the caller in the failure envelope — `run-group` and
    `multi` are different commands, and a hard-coded name here would make
    one of them lie about which command produced the failure.

    Does not include the `--flat`-with-`html` refusal: that fires as the
    caller's first statement, before any query runs, so it stays there.
    """
    fmt = args.export
    if args.flat:
        if fmt == "csv":
            path = deps.export_group_flat_csv(group_result, param_values)
        elif fmt == "json":
            path = deps.export_group_flat_json(group_result, param_values)
        elif fmt == "txt":
            path = deps.export_group_flat_txt(group_result, param_values)
        else:
            _fail_or_print(args, command, "usage", t("export.format_invalid", format=fmt))
    else:
        if fmt == "csv":
            path = deps.export_group_csv(group_result, param_values)
        elif fmt == "json":
            path = deps.export_group_json(group_result, param_values)
        elif fmt == "txt":
            path = deps.export_group_txt(group_result, param_values)
        elif fmt == "html":
            path = deps.export_group_html(group_result, param_values)
        else:
            _fail_or_print(args, command, "usage", t("export.format_invalid", format=fmt))
    return path


def _sql_or_file(sql: str) -> str:
    """The SQL to run: `sql` itself, or the contents of the file it names.

    `dbqm sql` and `dbqm multi` both take "SQL text or a path to a .sql
    file" and both implemented it in place, byte for byte. A path that is
    not a file is SQL: a statement is never a file name by accident, and
    letting the driver reject it says more than a guess here would.
    """
    path = Path(sql)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".sql":
        # Nothing that ends in `.sql` is a statement. Left as SQL it reached
        # `classify_sql` and came back "unsupported SQL type", which
        # says nothing about the typo in the path.
        raise FileNotFoundError(str(path))
    return sql


def _export_result(
    args: argparse.Namespace,
    result: Any,
    conn: Connection,
    param_values: dict[str, str],
) -> str:
    """Export an `AdhocResult`'s rows, in the format `--export` names.

    The four format arms were written once inside `cmd_sql`'s SELECT
    branch; every other statement type that returns rows needs the same
    four, and a second copy is how one of them drifts.
    """
    qr = deps.QueryResult(
        query_name="adhoc",
        connection_name=conn.name,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        elapsed=result.elapsed,
    )
    fmt = args.export
    if fmt == "csv":
        return str(deps.export_query_csv(qr, "adhoc", param_values))
    if fmt == "json":
        return str(deps.export_query_json(qr, "adhoc", param_values))
    if fmt == "txt":
        return str(deps.export_query_txt(qr, "adhoc", param_values))
    if fmt == "html":
        return str(deps.export_query_html(qr, "adhoc", param_values))
    _fail_or_print(args, "sql", "usage", t("export.format_invalid", format=fmt))


def cmd_run(args: argparse.Namespace) -> None:
    """Execute a saved query."""
    param_values = _parse_params(args.param, args, "run")

    try:
        result = queries.run_query(args.query, param_values, connection=args.connection)
    except OperationError as e:
        # Both `run` validation failures -- an undeclared parameter and a
        # missing one -- are about parameters, and the CLI cannot tell
        # which raised from just `e.code`; the hint fits either, so it is
        # printed for every `validation` failure of `run`.
        extra = f"[dim]{t('run.params_hint')}[/dim]" if e.code == "validation" else None
        _fail_or_print(args, "run", e.code, e.message, extra=extra)

    # Export if requested
    if args.export:
        fmt = args.export
        # `run_query` no longer hands back the `Query` object; it exists
        # (ops just ran it), so look it up again for its export table name.
        query = deps.find_query(args.query)
        if query is None:
            _fail_or_print(args, "run", "not_found", t("query.not_found_named", name=args.query))
        table_name = query.table or query.name
        # `run_query` fills a saved query's declared defaults into its own
        # copy of `param_values` before running -- this local dict never
        # saw them. Without this, an export whose file name and body embed
        # `param_values` misses any parameter that only a default supplied.
        param_values = queries.effective_params(query, param_values)
        if fmt == "csv":
            path = deps.export_query_csv(result, table_name, param_values)
        elif fmt == "json":
            path = deps.export_query_json(result, table_name, param_values)
        elif fmt == "txt":
            path = deps.export_query_txt(result, table_name, param_values)
        elif fmt == "html":
            path = deps.export_query_html(result, table_name, param_values)
        else:
            _fail_or_print(args, "run", "usage", t("export.format_invalid", format=fmt))
        if args.format == "json":
            ok("run", {"exported": str(path), "format": fmt})
            return
        console.print(t("export.done", path=path))
        return

    if args.format == "json":
        ok("run", result.to_dict())
        return

    render._print_query_result(result, args.format)


def cmd_run_group(args: argparse.Namespace) -> None:
    """Execute a group comparison.

    A divergent comparison still writes its history record — a divergence is
    a completed run, not an aborted one — and it always exits 5, `--export`
    and `table` included: the exit code is part of the contract, not a
    JSON-only or no-flags-given convenience.

    Divergence itself is `ok()`, not `fail()`: the command did its job and
    the answer is "no", and that answer — the full comparison counts — is
    exactly what an agent runs this command to get, so it belongs in `data`
    on stdout. The exit code alone is what lets a shell branch on the verdict
    without parsing anything.
    """
    # An argument combination that can never be valid is refused before any
    # work happens -- before the group is even resolved, let alone any query
    # run or any history record written.
    if args.export == "html" and args.flat:
        _fail_or_print(args, "run-group", "usage",
                       t("export.flat_no_html"))

    param_values = _parse_params(args.param, args, "run-group")

    try:
        comparison = compare.run_group(args.group, param_values)
    except OperationError as e:
        _fail_or_print(args, "run-group", e.code, e.message)

    _report_group_result(args, comparison)


def _report_group_result(
    args: argparse.Namespace,
    comparison: compare.Comparison,
) -> None:
    """The tail of `run-group`: export, envelope or table, and exit 5.

    Shared by the two shapes of group -- saved queries and ad-hoc -- so
    that a divergence exits the same way and the JSON carries the same
    counts whichever was run.
    """
    group_result = comparison.group_result
    warnings = comparison.warnings
    if args.export:
        fmt = args.export
        path = _export_group(args, "run-group", group_result, comparison.params)
        # `join_key` only for the ad-hoc shape, which derives it at run
        # time; a saved group has the key it was given and does not
        # report one -- same rule `run_group_data` applies to the
        # non-export branch below.
        extra = {"join_key": comparison.join_key} if comparison.join_key is not None else {}
        if args.format == "json":
            ok("run-group", {"exported": str(path), "format": fmt, **extra},
               warnings=warnings or None)
        else:
            console.print(t("export.done", path=path))
            for warning in warnings:
                console.print(f"[ds.text.muted]{escape(warning)}[/ds.text.muted]")
        if not group_result.all_match:
            sys.exit(int(exit_for("divergent")))
        return

    if args.format == "json":
        data = compare.run_group_data(comparison)
        ok("run-group", data, warnings=warnings or None)
        if not group_result.all_match:
            sys.exit(int(exit_for("divergent")))
        return

    status = (f"[ds.verdict.match]{t('verdict.consistent')}[/]" if group_result.all_match
              else f"[ds.verdict.diff]{t('verdict.divergent')}[/]")
    console.print(t("group.header", name=group_result.group_name, status=status))
    for line in render._colored_comparison_lines(group_result.comparisons):
        console.print(f"  {line}")
    for warning in warnings:
        console.print(f"[ds.text.muted]{escape(warning)}[/ds.text.muted]")
    if not group_result.all_match:
        sys.exit(int(exit_for("divergent")))


def cmd_multi(args: argparse.Namespace) -> None:
    """Run one ad-hoc SQL across several connections and compare the results."""
    if args.export == "html" and args.flat:
        _fail_or_print(args, "multi", "usage",
                       t("export.flat_no_html"))

    try:
        sql = _sql_or_file(args.sql)
    except FileNotFoundError as e:
        _fail_or_print(args, "multi", "not_found", t("file.not_found_named", name=e))

    param_values = _parse_params(args.param, args, "multi")

    try:
        comparison = compare.multi(sql, args.connection or [], param_values, key=args.key)
    except OperationError as e:
        _fail_or_print(args, "multi", e.code, e.message)

    if args.export:
        fmt = args.export
        path = _export_group(args, "multi", comparison.group_result, comparison.params)
        if args.format == "json":
            ok("multi", {"exported": str(path), "format": fmt, "join_key": comparison.join_key},
               warnings=comparison.warnings or None)
        else:
            console.print(t("export.done", path=path))
            for warning in comparison.warnings:
                console.print(f"[ds.text.muted]{escape(warning)}[/ds.text.muted]")
        if not comparison.group_result.all_match:
            sys.exit(int(exit_for("divergent")))
        return

    if args.format == "json":
        data = compare.multi_data(comparison)
        ok("multi", data, warnings=comparison.warnings or None)
        if not comparison.group_result.all_match:
            sys.exit(int(exit_for("divergent")))
        return

    status = (f"[ds.verdict.match]{t('verdict.consistent')}[/]" if comparison.group_result.all_match
              else f"[ds.verdict.diff]{t('verdict.divergent')}[/]")
    connections = ", ".join(comparison.results)
    console.print(t("multi.header", connections=connections, key=comparison.join_key, status=status))
    for line in render._colored_comparison_lines(comparison.group_result.comparisons):
        console.print(f"  {line}")
    for warning in comparison.warnings:
        console.print(f"[ds.text.muted]{escape(warning)}[/ds.text.muted]")
    if not comparison.group_result.all_match:
        sys.exit(int(exit_for("divergent")))


def cmd_sql(args: argparse.Namespace) -> None:
    """Execute ad-hoc SQL."""
    try:
        conn = catalogue.connection(args.connection)
    except OperationError as e:
        _fail_or_print(args, "sql", e.code, e.message)

    if getattr(args, "force_write", False) and conn.read_only:
        # Resolve the override here, at the CLI's own boundary, instead of
        # threading a flag through five `core/` signatures. `core/` reads
        # `conn.read_only` and nothing else, so a future caller cannot forget
        # to pass something it never had to know about. The replacement is
        # transient and never reaches `save_connections`.
        conn = replace(conn, read_only=False)

    try:
        sql = _sql_or_file(args.sql)
    except FileNotFoundError as e:
        _fail_or_print(args, "sql", "not_found", t("file.not_found_named", name=e))

    param_values = _parse_params(args.param, args, "sql")

    if args.explain:
        try:
            result = ops_sql.explain(conn, sql, param_values)
        except OperationError as e:
            _fail_or_print(args, "sql", e.code, e.message)
        # A plan is a result set -- one `plan` column, one row per line --
        # so `--export` writes it like any other. This branch returns before
        # the guard below ever runs, so without this the flag would be
        # accepted and ignored here: exactly what the guard exists to stop.
        if args.export:
            path = _export_result(args, result, conn, param_values)
            if args.format == "json":
                ok("sql", {"exported": str(path), "format": args.export})
                return
            console.print(t("export.done", path=path))
            return
        if args.format == "json":
            plano = [row[0] if row else "" for row in result.rows]
            ok("sql", {"connection_name": conn.name, "elapsed": round(result.elapsed, 3), "plan": plano})
            return
        for row in result.rows:
            print(row[0] if row else "")
        console.print(f"[dim]({result.elapsed:.2f}s)[/dim]")
        return

    try:
        sql_type = ops_sql.classify_and_guard(conn, sql, param_values)
    except OperationError as e:
        _fail_or_print(args, "sql", e.code, e.message)

    # `--export` writes a result set, and these statement types do not
    # return one. Until 2.10.0 the flag was accepted and silently ignored --
    # the export block sits inside the SELECT branch -- so a DML run with
    # `--commit -e csv` wrote the row and no file, and said nothing about
    # it. Before --commit, because dropping `-e` is required either way,
    # and before the statement runs: refusing afterwards would mean the
    # write happened and the caller still got exit 2.
    if args.export and sql_type in ("INSERT", "UPDATE", "DELETE", "DDL"):
        _fail_or_print(
            args, "sql", "usage",
            t("sql.export_needs_rows", type=sql_type),
        )

    try:
        result = ops_sql.run_sql(conn, sql, param_values, commit=args.commit)
    except OperationError as e:
        _fail_or_print(args, "sql", e.code, e.message)

    # For non-SELECT results (always AdhocResult with auto_commit=True at this point)
    if result.sql_type in ("INSERT", "UPDATE", "DELETE"):
        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return
        console.print(t("sql.rows_affected_committed", count=result.rows_affected))
        return

    # DDL results
    if result.sql_type == "DDL":
        if args.format == "json":
            ok("sql", result.to_dict())
            return
        console.print(t("sql.ddl_ok", seconds=f"{result.elapsed:.2f}"))
        return

    # PL/SQL anonymous block results
    if result.sql_type == "PLSQL":
        # A block is the one type whose result set is not knowable from its
        # text: it may open a cursor and return rows, and then `--export` is
        # exactly right. Only a block that returned nothing is refused, and
        # only after the fact -- there was nothing to decide earlier.
        if args.export and not result.rows:
            _fail_or_print(
                args, "sql", "usage",
                t("sql.export_needs_rows_block"),
            )
        if args.export:
            path = _export_result(args, result, conn, param_values)
            if args.format == "json":
                ok("sql", {"exported": str(path), "format": args.export})
                return
            console.print(t("export.done", path=path))
            return
        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return
        from dbqm.core.query_engine import block_label

        console.print(
            t("sql.block_ran", label=block_label(result.db_type),
              seconds=f"{result.elapsed:.2f}")
        )
        if result.rows:
            render._print_query_result(
                deps.QueryResult(
                    query_name="adhoc",
                    connection_name=conn.name,
                    columns=result.columns,
                    rows=result.rows,
                    row_count=result.row_count,
                    elapsed=result.elapsed,
                ),
                args.format,
            )
        for line in result.output_lines:
            console.print(line, markup=False, highlight=False)
        return

    if result.sql_type == "SELECT":
        # Convert AdhocResult to QueryResult for display/export
        qr = deps.QueryResult(
            query_name="adhoc",
            connection_name=conn.name,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed=result.elapsed,
        )

        if args.export:
            path = _export_result(args, result, conn, param_values)
            if args.format == "json":
                ok("sql", {"exported": str(path), "format": args.export})
                return
            console.print(t("export.done", path=path))
            return

        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return

        render._print_query_result(qr, args.format)
    else:
        # Statement types `execute_adhoc` doesn't special-case above but
        # still ran successfully (e.g. a type sqlparse can't name) — same
        # shape as the DML success branch, so json still gets an envelope
        # instead of falling through to a bare `print`.
        if args.export and not result.rows:
            _fail_or_print(
                args, "sql", "usage",
                t("sql.export_returned_no_rows", type=result.sql_type),
            )
        if args.export:
            path = _export_result(args, result, conn, param_values)
            if args.format == "json":
                ok("sql", {"exported": str(path), "format": args.export})
                return
            console.print(t("export.done", path=path))
            return
        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return
        console.print(t("sql.rows_affected", count=result.rows_affected))


def _resolve_call_routine(db: object, conn: Connection, routine_name: str) -> tuple[str, RoutineInfo]:
    """Resolve `routine_name` to `(package, RoutineInfo)`.

    A `.` in the name means a package routine: `list_package_routines`
    parses the package spec and the routine is picked out of
    `PackageInfo.routines` by name -- a name that spec does not list is a
    definite `not_found`, since the source names every routine the package
    declares.

    No dot means a standalone routine, via `get_standalone_routine_info`.
    That function never raises for a name that does not exist -- ALL_ARGUMENTS
    simply returns no rows for it -- but an empty `params` and no
    `return_type` is indistinguishable from a real, callable procedure
    declared with no arguments and no return value (`PROCEDURE P IS BEGIN
    ... END;`). Refusing that as "not found" would be wrong far more often
    than it would catch an actual typo, so existence is not second-guessed
    here at all: a name that truly does not exist reaches `execute_routine`,
    which sends it to Oracle and gets back `PLS-00201: identifier ... must
    be declared`, reported as any other rejected statement (`sql_error`, 4).
    Verifying existence up front belongs in `core/get_standalone_routine_info`
    itself, not in a CLI-side guess.

    `get_standalone_routine_info` takes a `routine_type` argument and honours
    it -- the TUI passes the real type, because the user picked it from a
    list. A command line has no such list, so this calls the lookup with its
    default of PROCEDURE and re-tags afterwards: a non-empty `return_type` is
    the tell that it is really a FUNCTION. `execute_routine` has to be told
    explicitly, or it emits the call as a bare statement (`FN(args);`)
    instead of an assignment into a return variable, and Oracle rejects that
    with `PLS-00221`.
    """
    if "." in routine_name:
        package, _, short_name = routine_name.partition(".")
        pkg_info = deps.list_package_routines(db, conn.db_type, package)
        for r in pkg_info.routines:
            if r.name.upper() == short_name.upper():
                return pkg_info.name, r
        raise deps.ObjectNotFound(t("call.routine_not_found", name=routine_name))
    routine = deps.get_standalone_routine_info(db, routine_name)
    if routine.return_type:
        routine = replace(routine, routine_type="FUNCTION")
    return "", routine


def _validate_call_params(routine: RoutineInfo, param_values: dict[str, str]) -> dict[str, str]:
    """Validate `param_values` against `routine.params` and return them
    re-keyed to the routine's own spelling.

    Oracle declares parameter names in upper case; a caller typing
    `-p p_id=...` is not making a mistake. Matching is case-insensitive
    against `routine.params`, and what is returned uses the DECLARED
    spelling -- `execute_routine` looks values up by exact `p.name`, so a
    value left lower-case would not fail loudly there, it would silently be
    dropped in favour of the parameter's default instead.

    Every `IN`/`IN OUT` parameter with no default must be supplied; a
    supplied name the routine does not declare is almost always a typo, so
    it is refused rather than silently running with a default the caller
    did not intend. An `OUT` parameter is written by the routine, not
    required from the caller.
    """
    declared = {p.name.upper(): p.name for p in routine.params}
    folded: dict[str, str] = {}
    for name, value in param_values.items():
        real_name = declared.get(name.upper())
        if real_name is None:
            # A standalone routine with neither parameters nor a return type
            # is indistinguishable from one that does not exist: both produce
            # no ALL_ARGUMENTS rows. Blaming the parameter would send the
            # reader to fix the wrong thing, so say what is actually known.
            if not routine.params and not routine.return_type:
                raise ValueError(t("call.routine_param_or_missing",
                                   routine=routine.name, parameter=name))
            raise ValueError(t("call.param_unknown", parameter=name, routine=routine.name))
        folded[real_name] = value
    for p in routine.params:
        if p.direction in ("IN", "IN OUT") and not p.default and p.name not in folded:
            raise ValueError(t("call.param_required_missing", name=p.name))
    return folded


def _rollback_quietly(db: Any) -> None:
    """Roll back, and never let the rollback's own failure replace the error
    that caused it.

    A driver that cannot roll back has usually already lost the connection,
    which is the condition the caller is about to be told about anyway. The
    original diagnosis is the useful one.
    """
    try:
        db.rollback()
    except Exception:
        pass


def cmd_call(args: argparse.Namespace) -> None:
    """Execute a stored procedure or function (Oracle only).

    Order is the design. The connection is resolved first, and then, while
    it is still just configuration and nothing has opened, the Oracle-only
    refusal: `execute_routine` builds an anonymous PL/SQL block, which the
    other three engines have no equivalent of, and `conn.db_type` is known
    for free. Only then does the connection actually open, following the
    same nesting `_with_open_connection` (schema.py) uses to keep a failure
    to connect (`connection_failed`, 3) apart from everything that can go
    wrong once it is open.

    From there, three separately scoped `try` blocks -- resolve, validate,
    execute -- each own just the exception vocabulary they were written
    for, rather than one handler shared across all three. That matters
    concretely: a bare `except ValueError` around all three would also
    catch anything `execute_routine` itself might raise and report it as
    `validation` (a caller mistake) when it is actually a statement
    failure (`sql_error`). Each block still ends in a catch-all mapped to
    the statement-failure token it would otherwise fall through to, so
    nothing unexpected leaks out to the outer handler and gets misreported
    as a connection failure.
    """
    conn = deps.find_connection(args.connection)
    if not conn:
        _fail_or_print(args, "call", "not_found", t("connection.not_found_named", name=args.connection))

    if conn.db_type != "oracle":
        _fail_or_print(
            args, "call", "usage",
            t("call.oracle_only", name=conn.name, type=conn.db_type),
        )

    param_values = _parse_params(args.param, args, "call")

    try:
        with deps.open_connection(conn) as db:
            try:
                package, routine = _resolve_call_routine(db, conn, args.routine)
            except deps.ObjectNotFound as e:
                _fail_or_print(args, "call", "not_found", str(e))
            except deps.UnsupportedEngine as e:
                # Unreachable today: the Oracle-only refusal above already
                # guarantees `conn.db_type == "oracle"` by this point. Kept
                # so this vocabulary does not silently drift to `sql_error`
                # if that pre-check ever moves.
                _fail_or_print(args, "call", "usage", str(e))
            except Exception as e:
                _fail_or_print(args, "call", "sql_error", str(e))

            try:
                param_values = _validate_call_params(routine, param_values)
            except ValueError as e:
                _fail_or_print(args, "call", "validation", str(e))

            try:
                result = deps.execute_routine(db, package, routine, param_values, conn=conn)
            except deps.ReadOnlyViolation as e:
                _fail_or_print(args, "call", "read_only", str(e))
            except Exception as e:
                # The block may have executed in part before raising. Undo it
                # here rather than leaving it to the driver's close-time
                # behaviour -- that behaviour is exactly what `--commit`
                # exists to stop anyone from having to trust.
                _rollback_quietly(db)
                _fail_or_print(args, "call", "sql_error", str(e))

            # `execute_routine`'s own comment says the caller handles commit;
            # until now no caller did (see the module-level docstring on
            # `cmd_call`). A CLI process opens, runs and exits -- there is no
            # later moment in which anything could commit -- so the decision
            # is made here, explicitly, on the still-open handle, while `db`
            # is still in scope. Relying on the driver's close-time behaviour
            # would be a rollback nobody could see in a test. `--commit` is
            # not a promise to keep a failure: an unsuccessful routine is
            # rolled back regardless of the flag.
            committed = bool(args.commit and result.success)
            if committed:
                try:
                    db.commit()
                except Exception as e:
                    # A commit that failed is the one outcome a caller must
                    # not have to guess at: the routine ran, and nothing was
                    # kept. Saying so beats letting the outer handler call it
                    # a connection failure.
                    _rollback_quietly(db)
                    _fail_or_print(
                        args, "call", "sql_error",
                        t("call.commit_failed", error=e),
                    )
            else:
                try:
                    db.rollback()
                except Exception as e:
                    # Symmetric with the commit arm above. Nothing was kept
                    # either way, so the outcome is unchanged -- but letting
                    # this reach the outer handler would report a successful
                    # routine as a connection failure, which is the wrong
                    # thing to tell someone reading an exit code.
                    _fail_or_print(
                        args, "call", "sql_error",
                        t("call.rollback_failed", error=e),
                    )
    except Exception as e:
        _fail_or_print(args, "call", "connection_failed", str(e))

    if not result.success:
        _fail_or_print(args, "call", "sql_error", result.error or t("call.execute_failed"))

    if args.format == "json":
        data = {**result.to_dict(), "committed": committed}
        ok("call", data, warnings=result.output_lines or None)
        return

    if result.return_value is not None:
        console.print(t("call.return_value", value=result.return_value),
                      markup=False, highlight=False)
    for name, value in result.out_values.items():
        console.print(f"{name}: {value}", markup=False, highlight=False)
    for line in result.output_lines:
        console.print(line, markup=False, highlight=False)
    if committed:
        console.print(f'[dim]{t("exec_routine.committed")}[/dim]')
    else:
        console.print(f'[dim]{t("exec_routine.rolled_back")}[/dim]')
    console.print(f"[dim]({result.elapsed:.2f}s)[/dim]")

"""Commands for running saved queries, group comparisons and ad-hoc SQL."""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

from rich.markup import escape

from dbqm.cli import deps, render
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.params import _parse_params
from dbqm.cli.render import console

# `core/` reports these two conditions as a plain `AdhocResult`/`QueryResult`
# error string — the statement was never sent to the driver, so calling it
# `sql_error` (the database rejected something) would be a lie. `core/` stays
# free of `errors.py`'s vocabulary, so the CLI recognizes the exact wording
# by text and remaps it here; anything else really is `sql_error`.
_USAGE_SQL_MESSAGES = (
    "Apenas comandos SELECT sao permitidos.",
    "Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE, DELETE, DDL "
    "(CREATE/ALTER/DROP...) ou EXPLAIN PLAN.",
    "Passe apenas a query (sem EXPLAIN PLAN FOR) ao usar --explain.",
)

#: `--explain` on an engine that has none. A capability the engine does not
#: have, which `schema.py` already answers with `usage` for the same class of
#: condition -- reporting it as `sql_error` would say a statement was
#: rejected when none was ever sent. Matched by prefix because the message
#: names the engine.
_UNSUPPORTED_EXPLAIN_PREFIX = "--explain ainda nao e suportado para "


def _sql_error_code(message: str | None, error_kind: str = "") -> str:
    """The token for a failed result.

    `connection` wins over everything: the database never answered, so
    nothing about the statement is known. Otherwise `usage` for the two
    known bad-input messages `core/` can return, and `sql_error` for the
    rest -- the driver rejected or failed on a statement actually sent.
    """
    if error_kind == "connection":
        return "connection_failed"
    if message in _USAGE_SQL_MESSAGES:
        return "usage"
    if message and message.startswith(_UNSUPPORTED_EXPLAIN_PREFIX):
        return "usage"
    return "sql_error"


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


def cmd_run(args: argparse.Namespace) -> None:
    """Execute a saved query."""
    query = deps.find_query(args.query)
    if not query:
        _fail_or_print(args, "run", "not_found", f"Consulta '{args.query}' nao encontrada.")

    conn_name = args.connection or query.connection
    conn = deps.find_connection(conn_name)
    if not conn:
        _fail_or_print(args, "run", "not_found", f"Conexao '{conn_name}' nao encontrada.")

    param_values = _parse_params(args.param, args, "run")

    # Fill missing params with defaults
    for p in query.params:
        if p.name not in param_values and p.default:
            param_values[p.name] = p.default

    # Validate required params
    missing = [p.name for p in query.params if p.name not in param_values]
    if missing:
        _fail_or_print(
            args, "run", "validation",
            f"Parametros obrigatorios faltando: {', '.join(missing)}",
            extra="[dim]Use -p chave=valor para cada parametro[/dim]",
        )

    result = deps.execute_query(query, conn, param_values)

    # Apply column maps
    if result.success and query.column_maps:
        query.apply_column_maps(result.rows, result.columns)

    # Record history & audit
    deps.record_query_execution(
        query.name, conn.name, param_values,
        result.row_count, result.elapsed, result.success, result.error,
    )
    deps.log_execution("query", query.name, conn.name, param_values,
                  row_count=result.row_count, success=result.success, error=result.error)

    # A failed query is a failure regardless of `--export`/`-f`: check it
    # once here, before either branch, so `table`/`csv`/`raw` exit with the
    # same mapped code as `json` instead of rendering an empty result.
    if not result.success:
        _fail_or_print(args, "run", _sql_error_code(result.error, result.error_kind),
                        result.error or "Erro ao executar consulta.")

    # Export if requested
    if args.export:
        fmt = args.export
        table_name = query.table or query.name
        if fmt == "csv":
            path = deps.export_query_csv(result, table_name, param_values)
        elif fmt == "json":
            path = deps.export_query_json(result, table_name, param_values)
        elif fmt == "txt":
            path = deps.export_query_txt(result, table_name, param_values)
        else:
            _fail_or_print(args, "run", "usage", f"Formato de export invalido: {fmt}")
        if args.format == "json":
            ok("run", {"exported": str(path), "format": fmt})
            return
        console.print(f"Exportado: {path}")
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
    group = deps.find_group(args.group)
    if not group:
        _fail_or_print(args, "run-group", "not_found", f"Grupo '{args.group}' nao encontrado.")

    param_values = _parse_params(args.param, args, "run-group")

    # Fill from shared_params defaults
    for pname, pdef in group.shared_params.items():
        if pname not in param_values and pdef:
            param_values[pname] = pdef

    # Execute all queries in the group
    query_results = {}
    total_start = time.time()
    for qname in group.queries:
        query = deps.find_query(qname)
        if not query:
            _fail_or_print(args, "run-group", "not_found",
                            f"Consulta '{qname}' do grupo nao encontrada.")
        conn = deps.find_connection(query.connection)
        if not conn:
            _fail_or_print(args, "run-group", "not_found",
                            f"Conexao '{query.connection}' nao encontrada.")

        result = deps.execute_query(query, conn, param_values)
        if not result.success:
            _fail_or_print(args, "run-group", _sql_error_code(result.error, result.error_kind),
                            f"Erro na consulta '{qname}': {result.error}")

        # Apply column maps
        if query.column_maps:
            query.apply_column_maps(result.rows, result.columns)

        query_results[qname] = result

    total_elapsed = time.time() - total_start

    group_result = deps.build_group_result(
        group.name, query_results, group.join_key,
        group.compare_columns, group.column_mapping, group.normalize,
    )

    # Record history — unconditionally: a divergence is a completed run.
    summary = "\n".join(group_result.summary_lines)
    deps.record_group_execution(group.name, param_values, group_result.all_match, summary, total_elapsed)

    # Export if requested — this must still fall through to the same
    # divergence exit as every other path; it does not get to opt the
    # headline behaviour of this release out with a flag.
    if args.export:
        fmt = args.export
        flat = args.flat
        if flat:
            if fmt == "csv":
                path = deps.export_group_flat_csv(group_result, param_values)
            elif fmt == "json":
                path = deps.export_group_flat_json(group_result, param_values)
            else:
                path = deps.export_group_flat_txt(group_result, param_values)
        else:
            if fmt == "csv":
                path = deps.export_group_csv(group_result, param_values)
            elif fmt == "json":
                path = deps.export_group_json(group_result, param_values)
            else:
                path = deps.export_group_txt(group_result, param_values)
        if args.format == "json":
            ok("run-group", {"exported": str(path), "format": fmt})
        else:
            console.print(f"Exportado: {path}")
        if not group_result.all_match:
            sys.exit(int(exit_for("divergent")))
        return

    if args.format == "json":
        data = {
            "group": group_result.group_name,
            "all_match": group_result.all_match,
            "comparisons": [
                {
                    "column": c.column,
                    "total_keys": c.total_keys,
                    "equal_count": c.equal_count,
                    "diff_count": c.diff_count,
                    "absent_count": c.absent_count,
                    "normalized_count": c.normalized_count,
                }
                for c in group_result.comparisons
            ],
        }
        ok("run-group", data)
        if not group_result.all_match:
            sys.exit(int(exit_for("divergent")))
        return

    status = "[ds.verdict.match]CONSISTENTE[/]" if group_result.all_match else "[ds.verdict.diff]DIVERGENTE[/]"
    console.print(f"Grupo: {group_result.group_name} — {status}")
    for line in render._colored_comparison_lines(group_result.comparisons):
        console.print(f"  {line}")
    if not group_result.all_match:
        sys.exit(int(exit_for("divergent")))


def cmd_sql(args: argparse.Namespace) -> None:
    """Execute ad-hoc SQL."""
    conn = deps.find_connection(args.connection)
    if not conn:
        _fail_or_print(args, "sql", "not_found", f"Conexao '{args.connection}' nao encontrada.")

    if getattr(args, "force_write", False) and conn.read_only:
        # Resolve the override here, at the CLI's own boundary, instead of
        # threading a flag through five `core/` signatures. `core/` reads
        # `conn.read_only` and nothing else, so a future caller cannot forget
        # to pass something it never had to know about. The replacement is
        # transient and never reaches `save_connections`.
        conn = replace(conn, read_only=False)

    sql = args.sql
    # If argument is a file path, read SQL from it
    sql_path = Path(sql)
    if sql_path.is_file():
        sql = sql_path.read_text(encoding="utf-8")

    param_values = _parse_params(args.param, args, "sql")

    if args.explain:
        try:
            result = deps.execute_explain(sql, conn, param_values)
        except deps.ReadOnlyViolation as e:
            _fail_or_print(args, "sql", "read_only", str(e))
        if not result.success:
            _fail_or_print(args, "sql", _sql_error_code(result.error, result.error_kind),
                            result.error or "Erro ao gerar plano de execucao.")
        if args.format == "json":
            plano = [row[0] if row else "" for row in result.rows]
            ok("sql", {"connection_name": conn.name, "elapsed": round(result.elapsed, 3), "plan": plano})
            return
        for row in result.rows:
            print(row[0] if row else "")
        console.print(f"[dim]({result.elapsed:.2f}s)[/dim]")
        return

    sql_type = deps.classify_sql(sql)

    # Ask the read-only question before the --commit one. `execute_adhoc`
    # enforces the guard either way, and that is what protects every other
    # caller -- this call is purely about which refusal the user reads first.
    # Reporting the missing --commit sends them to add it and only then meet
    # the real obstacle: two round trips to learn the connection is protected.
    try:
        deps.check_read_only(sql, conn)
    except deps.ReadOnlyViolation as e:
        _fail_or_print(args, "sql", "read_only", str(e))

    # Require --commit for DML operations
    if sql_type in ("INSERT", "UPDATE", "DELETE") and not args.commit:
        _fail_or_print(args, "sql", "usage", "DML requer --commit para confirmar a operacao.")

    try:
        result = deps.execute_adhoc(sql, conn, param_values, auto_commit=args.commit)
    except deps.ReadOnlyViolation as e:
        _fail_or_print(args, "sql", "read_only", str(e))

    # For non-SELECT results (always AdhocResult with auto_commit=True at this point)
    if not isinstance(result, tuple) and result.sql_type in ("INSERT", "UPDATE", "DELETE"):
        if not result.success:
            _fail_or_print(args, "sql", _sql_error_code(result.error, result.error_kind),
                            result.error or "Erro ao executar SQL.")
        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return
        console.print(f"{result.rows_affected} registros afetados (committed)")
        return

    # DDL results
    if not isinstance(result, tuple) and result.sql_type == "DDL":
        if not result.success:
            code = _sql_error_code(result.error, result.error_kind)
            if args.format == "json":
                fail("sql", code, result.error or "Erro ao executar DDL.")
            console.print(f"[ds.op.failure]DDL executado com erros de compilacao ({result.elapsed:.2f}s)[/ds.op.failure]")
            console.print(f"[ds.op.failure]{result.error}[/ds.op.failure]")
            sys.exit(int(exit_for(code)))
        if args.format == "json":
            ok("sql", result.to_dict())
            return
        console.print(f"DDL executado com sucesso ({result.elapsed:.2f}s)")
        return

    # PL/SQL anonymous block results
    if not isinstance(result, tuple) and result.sql_type == "PLSQL":
        if not result.success:
            _fail_or_print(args, "sql", _sql_error_code(result.error, result.error_kind),
                            result.error or "Erro ao executar bloco.")
        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return
        from dbqm.core.query_engine import block_label

        console.print(
            f"{block_label(result.db_type)} executado ({result.elapsed:.2f}s)"
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

    if not result.success:
        _fail_or_print(args, "sql", _sql_error_code(result.error, result.error_kind),
                        result.error or "Erro ao executar SQL.")

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
            fmt = args.export
            if fmt == "csv":
                path = deps.export_query_csv(qr, "adhoc", param_values)
            elif fmt == "json":
                path = deps.export_query_json(qr, "adhoc", param_values)
            else:
                path = deps.export_query_txt(qr, "adhoc", param_values)
            if args.format == "json":
                ok("sql", {"exported": str(path), "format": fmt})
                return
            console.print(f"Exportado: {path}")
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
        if args.format == "json":
            ok("sql", result.to_dict(), warnings=result.output_lines or None)
            return
        console.print(f"{result.rows_affected} registros afetados")

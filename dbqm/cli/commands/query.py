"""Commands for running saved queries, group comparisons and ad-hoc SQL."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import NoReturn

from rich.markup import escape

from dbqm.cli import deps, render
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.params import _parse_params
from dbqm.cli.render import console


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

    param_values = _parse_params(args.param)

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
            console.print(f"[ds.op.failure]Formato de export invalido: {fmt}[/ds.op.failure]")
            sys.exit(1)
        console.print(f"Exportado: {path}")
        return

    if args.format == "json":
        if not result.success:
            fail("run", "sql_error", result.error or "Erro ao executar consulta.")
        data = {
            "query": result.query_name,
            "connection": result.connection_name,
            "columns": result.columns,
            "rows": [dict(zip(result.columns, row)) for row in result.rows],
            "row_count": result.row_count,
            "elapsed": round(result.elapsed, 3),
        }
        ok("run", data)
        return

    render._print_query_result(result, args.format)


def cmd_run_group(args: argparse.Namespace) -> None:
    """Execute a group comparison.

    A divergent comparison still writes its history record before it fails —
    a divergence is a completed run, not an aborted one — and it exits 5
    either way, `table` included: the exit code is part of the contract, not
    a JSON-only convenience.
    """
    group = deps.find_group(args.group)
    if not group:
        _fail_or_print(args, "run-group", "not_found", f"Grupo '{args.group}' nao encontrado.")

    param_values = _parse_params(args.param)

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
            _fail_or_print(args, "run-group", "sql_error",
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

    # Export if requested
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
        console.print(f"Exportado: {path}")
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
        if not group_result.all_match:
            fail("run-group", "divergent", f"Grupo '{group_result.group_name}' divergente.")
        ok("run-group", data)
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

    sql = args.sql
    # If argument is a file path, read SQL from it
    sql_path = Path(sql)
    if sql_path.is_file():
        sql = sql_path.read_text(encoding="utf-8")

    param_values = _parse_params(args.param)

    if args.explain:
        result = deps.execute_explain(sql, conn, param_values)
        if not result.success:
            _fail_or_print(args, "sql", "sql_error", result.error or "Erro ao gerar plano de execucao.")
        if args.format == "json":
            plano = [row[0] if row else "" for row in result.rows]
            ok("sql", {"connection": conn.name, "elapsed": round(result.elapsed, 3), "plan": plano})
            return
        for row in result.rows:
            print(row[0] if row else "")
        console.print(f"[dim]({result.elapsed:.2f}s)[/dim]")
        return

    sql_type = deps.classify_sql(sql)

    # Require --commit for DML operations
    if sql_type in ("INSERT", "UPDATE", "DELETE") and not args.commit:
        _fail_or_print(args, "sql", "usage", "DML requer --commit para confirmar a operacao.")

    result = deps.execute_adhoc(sql, conn, param_values, auto_commit=args.commit)

    # For non-SELECT results (always AdhocResult with auto_commit=True at this point)
    if not isinstance(result, tuple) and result.sql_type in ("INSERT", "UPDATE", "DELETE"):
        if not result.success:
            _fail_or_print(args, "sql", "sql_error", result.error or "Erro ao executar SQL.")
        if args.format == "json":
            data = {
                "connection": conn.name,
                "sql_type": result.sql_type,
                "rows_affected": result.rows_affected,
                "committed": result.committed,
                "elapsed": round(result.elapsed, 3),
            }
            ok("sql", data, warnings=result.output_lines or None)
            return
        console.print(f"{result.rows_affected} registros afetados (committed)")
        return

    # DDL results
    if not isinstance(result, tuple) and result.sql_type == "DDL":
        if not result.success:
            if args.format == "json":
                fail("sql", "sql_error", result.error or "Erro ao executar DDL.")
            console.print(f"[ds.op.failure]DDL executado com erros de compilacao ({result.elapsed:.2f}s)[/ds.op.failure]")
            console.print(f"[ds.op.failure]{result.error}[/ds.op.failure]")
            sys.exit(1)
        if args.format == "json":
            ok("sql", {"connection": conn.name, "sql_type": "DDL", "elapsed": round(result.elapsed, 3)})
            return
        console.print(f"DDL executado com sucesso ({result.elapsed:.2f}s)")
        return

    # PL/SQL anonymous block results
    if not isinstance(result, tuple) and result.sql_type == "PLSQL":
        if not result.success:
            _fail_or_print(args, "sql", "sql_error", result.error or "Erro ao executar bloco.")
        if args.format == "json":
            data = {
                "connection": conn.name,
                "sql_type": "PLSQL",
                "columns": result.columns,
                "rows": [dict(zip(result.columns, row)) for row in result.rows],
                "row_count": result.row_count,
                "elapsed": round(result.elapsed, 3),
            }
            ok("sql", data, warnings=result.output_lines or None)
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
        _fail_or_print(args, "sql", "sql_error", result.error or "Erro ao executar SQL.")

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
            console.print(f"Exportado: {path}")
            return

        if args.format == "json":
            data = {
                "query": sql,
                "connection": qr.connection_name,
                "columns": qr.columns,
                "rows": [dict(zip(qr.columns, row)) for row in qr.rows],
                "row_count": qr.row_count,
                "elapsed": round(qr.elapsed, 3),
            }
            ok("sql", data, warnings=result.output_lines or None)
            return

        render._print_query_result(qr, args.format)
    else:
        console.print(f"{result.rows_affected} registros afetados")

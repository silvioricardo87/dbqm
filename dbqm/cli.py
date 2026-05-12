"""Command-line interface for non-interactive execution of dbqm operations."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from dbqm.models.query import find_query, load_queries
from dbqm.models.connection import find_connection, load_connections
from dbqm.models.group import find_group, load_groups
from dbqm.core.query_engine import execute_query, execute_adhoc, classify_sql, QueryResult
from dbqm.core.group_engine import build_group_result
from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt,
    export_group_csv, export_group_json, export_group_txt,
    export_group_flat_csv, export_group_flat_json, export_group_flat_txt,
)
from dbqm.core.history import load_history, clear_history, record_query_execution, record_group_execution
from dbqm.core.audit import log_execution
from dbqm.core.db_manager import test_connection
from dbqm.core.ddl_extractor import extract_ddl, save_extraction
from dbqm.core.config_portability import export_configs, import_configs

console = Console()


def _parse_params(param_list: list[str] | None) -> dict:
    """Parse key=value parameter pairs from CLI arguments."""
    if not param_list:
        return {}
    params = {}
    for p in param_list:
        if "=" not in p:
            console.print(f"[red]Parametro invalido (use chave=valor): {p}[/red]")
            sys.exit(1)
        key, value = p.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def _materialize(value: Any) -> str:
    """Materialize CLOB/LONG/etc. to plain text for `--format raw`."""
    if value is None:
        return ""
    read = getattr(value, "read", None)
    if callable(read):
        try:
            return str(read())
        except Exception:
            return str(value)
    return str(value)


def _print_query_result(result: Any, output_format: str = "table") -> None:
    """Print query result in the specified format."""
    from dbqm.core.query_engine import QueryResult
    if not result.success:
        console.print(f"[red]Erro: {result.error}[/red]")
        sys.exit(1)

    if output_format == "json":
        data = {
            "query": result.query_name,
            "connection": result.connection_name,
            "columns": result.columns,
            "row_count": result.row_count,
            "elapsed": round(result.elapsed, 3),
            "rows": [dict(zip(result.columns, row)) for row in result.rows],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    elif output_format == "csv":
        import csv
        import io
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(result.columns)
        writer.writerows(result.rows)
        print(out.getvalue(), end="")
    elif output_format == "raw":
        # No headers, no decoration. CLOB/LONG materialized to text.
        # 1 column → bare value per row. >1 column → tab-separated.
        for row in result.rows:
            values = [_materialize(v) for v in row]
            if len(values) == 1:
                print(values[0])
            else:
                print("\t".join(values))
    else:
        table = Table(show_lines=False)
        for col in result.columns:
            table.add_column(col)
        for row in result.rows:
            table.add_row(*[str(v) if v is not None else "" for v in row])
        console.print(table)
        console.print(f"[dim]{result.row_count} registros em {result.elapsed:.2f}s[/dim]")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Execute a saved query."""
    query = find_query(args.query)
    if not query:
        console.print(f"[red]Consulta '{args.query}' nao encontrada.[/red]")
        sys.exit(1)

    conn_name = args.connection or query.connection
    conn = find_connection(conn_name)
    if not conn:
        console.print(f"[red]Conexao '{conn_name}' nao encontrada.[/red]")
        sys.exit(1)

    param_values = _parse_params(args.param)

    # Fill missing params with defaults
    for p in query.params:
        if p.name not in param_values and p.default:
            param_values[p.name] = p.default

    # Validate required params
    missing = [p.name for p in query.params if p.name not in param_values]
    if missing:
        console.print(f"[red]Parametros obrigatorios faltando: {', '.join(missing)}[/red]")
        console.print("[dim]Use -p chave=valor para cada parametro[/dim]")
        sys.exit(1)

    result = execute_query(query, conn, param_values)

    # Apply column maps
    if result.success and query.column_maps:
        query.apply_column_maps(result.rows, result.columns)

    # Record history & audit
    record_query_execution(
        query.name, conn.name, param_values,
        result.row_count, result.elapsed, result.success, result.error,
    )
    log_execution("query", query.name, conn.name, param_values,
                  row_count=result.row_count, success=result.success, error=result.error)

    # Export if requested
    if args.export:
        fmt = args.export
        table_name = query.table or query.name
        if fmt == "csv":
            path = export_query_csv(result, table_name, param_values)
        elif fmt == "json":
            path = export_query_json(result, table_name, param_values)
        elif fmt == "txt":
            path = export_query_txt(result, table_name, param_values)
        else:
            console.print(f"[red]Formato de export invalido: {fmt}[/red]")
            sys.exit(1)
        console.print(f"[green]Exportado: {path}[/green]")
        return

    _print_query_result(result, args.format)


def cmd_run_group(args: argparse.Namespace) -> None:
    """Execute a group comparison."""
    group = find_group(args.group)
    if not group:
        console.print(f"[red]Grupo '{args.group}' nao encontrado.[/red]")
        sys.exit(1)

    param_values = _parse_params(args.param)

    # Fill from shared_params defaults
    for pname, pdef in group.shared_params.items():
        if pname not in param_values and pdef:
            param_values[pname] = pdef

    # Execute all queries in the group
    query_results = {}
    total_start = time.time()
    for qname in group.queries:
        query = find_query(qname)
        if not query:
            console.print(f"[red]Consulta '{qname}' do grupo nao encontrada.[/red]")
            sys.exit(1)
        conn = find_connection(query.connection)
        if not conn:
            console.print(f"[red]Conexao '{query.connection}' nao encontrada.[/red]")
            sys.exit(1)

        result = execute_query(query, conn, param_values)
        if not result.success:
            console.print(f"[red]Erro na consulta '{qname}': {result.error}[/red]")
            sys.exit(1)

        # Apply column maps
        if query.column_maps:
            query.apply_column_maps(result.rows, result.columns)

        query_results[qname] = result

    total_elapsed = time.time() - total_start

    group_result = build_group_result(
        group.name, query_results, group.join_key,
        group.compare_columns, group.column_mapping, group.normalize,
    )

    # Record history
    summary = "\n".join(group_result.summary_lines)
    record_group_execution(group.name, param_values, group_result.all_match, summary, total_elapsed)

    # Export if requested
    if args.export:
        fmt = args.export
        flat = args.flat
        if flat:
            if fmt == "csv":
                path = export_group_flat_csv(group_result, param_values)
            elif fmt == "json":
                path = export_group_flat_json(group_result, param_values)
            else:
                path = export_group_flat_txt(group_result, param_values)
        else:
            if fmt == "csv":
                path = export_group_csv(group_result, param_values)
            elif fmt == "json":
                path = export_group_json(group_result, param_values)
            else:
                path = export_group_txt(group_result, param_values)
        console.print(f"[green]Exportado: {path}[/green]")
        return

    # Print result
    if args.format == "json":
        data = {
            "group": group_result.group_name,
            "all_match": group_result.all_match,
            "summary": group_result.summary_lines,
        }
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        status = "[green]CONSISTENTE[/green]" if group_result.all_match else "[red]DIVERGENTE[/red]"
        console.print(f"Grupo: {group_result.group_name} — {status}")
        for line in group_result.summary_lines:
            console.print(f"  {line}")


def cmd_sql(args: argparse.Namespace) -> None:
    """Execute ad-hoc SQL."""
    conn = find_connection(args.connection)
    if not conn:
        console.print(f"[red]Conexao '{args.connection}' nao encontrada.[/red]")
        sys.exit(1)

    sql = args.sql
    # If argument is a file path, read SQL from it
    sql_path = Path(sql)
    if sql_path.is_file():
        sql = sql_path.read_text(encoding="utf-8")

    param_values = _parse_params(args.param)

    sql_type = classify_sql(sql)

    # Require --commit for DML operations
    if sql_type in ("INSERT", "UPDATE", "DELETE") and not args.commit:
        console.print("[red]DML requer --commit para confirmar a operacao.[/red]")
        sys.exit(1)

    result = execute_adhoc(sql, conn, param_values, auto_commit=args.commit)

    # For non-SELECT results (always AdhocResult with auto_commit=True at this point)
    if not isinstance(result, tuple) and result.sql_type in ("INSERT", "UPDATE", "DELETE"):
        if not result.success:
            console.print(f"[red]Erro: {result.error}[/red]")
            sys.exit(1)
        console.print(f"[green]{result.rows_affected} registros afetados (committed)[/green]")
        return

    # DDL results
    if not isinstance(result, tuple) and result.sql_type == "DDL":
        if result.success:
            console.print(f"[green]DDL executado com sucesso ({result.elapsed:.2f}s)[/green]")
        else:
            console.print(f"[yellow]DDL executado com erros de compilacao ({result.elapsed:.2f}s)[/yellow]")
            console.print(f"[red]{result.error}[/red]")
            sys.exit(1)
        return

    if not result.success:
        console.print(f"[red]Erro: {result.error}[/red]")
        sys.exit(1)

    if result.sql_type == "SELECT":
        # Convert AdhocResult to QueryResult for display/export
        qr = QueryResult(
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
                path = export_query_csv(qr, "adhoc", param_values)
            elif fmt == "json":
                path = export_query_json(qr, "adhoc", param_values)
            else:
                path = export_query_txt(qr, "adhoc", param_values)
            console.print(f"[green]Exportado: {path}[/green]")
            return

        _print_query_result(qr, args.format)
    else:
        console.print(f"[green]{result.rows_affected} registros afetados[/green]")


def cmd_test(args: argparse.Namespace) -> None:
    """Test a database connection."""
    if args.connection == "__all__":
        connections = load_connections()
        if not connections:
            console.print("[yellow]Nenhuma conexao configurada.[/yellow]")
            return
        for conn in connections:
            ok, msg = test_connection(conn)
            icon = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
            console.print(f"  {icon}  {conn.name}: {msg.splitlines()[0]}")
        return

    conn = find_connection(args.connection)
    if not conn:
        console.print(f"[red]Conexao '{args.connection}' nao encontrada.[/red]")
        sys.exit(1)

    ok, msg = test_connection(conn)
    if ok:
        console.print(f"[green]{msg}[/green]")
    else:
        console.print(f"[red]{msg}[/red]")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List connections, queries, or groups."""
    resource = args.resource

    if resource == "connections":
        items = load_connections()
        if not items:
            console.print("[yellow]Nenhuma conexao configurada.[/yellow]")
            return
        if args.format == "json":
            data = [{"name": c.name, "db_type": c.db_type, "target": c.display_target()} for c in items]
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        table = Table(title="Conexoes")
        table.add_column("Nome")
        table.add_column("Tipo")
        table.add_column("Destino")
        for c in items:
            table.add_row(c.name, c.db_type, c.display_target())
        console.print(table)

    elif resource == "queries":
        items = load_queries()
        if not items:
            console.print("[yellow]Nenhuma consulta configurada.[/yellow]")
            return
        if args.format == "json":
            data = [{"name": q.name, "connection": q.connection, "folder": q.folder,
                      "description": q.description,
                      "params": [p.name for p in q.params]} for q in items]
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        table = Table(title="Consultas")
        table.add_column("Nome")
        table.add_column("Descricao")
        table.add_column("Conexao")
        table.add_column("Pasta")
        table.add_column("Parametros")
        table.add_column("Fav")
        for q in items:
            params = ", ".join(p.name for p in q.params) or "-"
            fav = "*" if q.is_favorite else ""
            desc = q.description[:50] + "..." if len(q.description) > 50 else q.description
            table.add_row(q.name, desc or "-", q.connection, q.folder or "-", params, fav)
        console.print(table)

    elif resource == "groups":
        items = load_groups()
        if not items:
            console.print("[yellow]Nenhum grupo configurado.[/yellow]")
            return
        if args.format == "json":
            data = [{"name": g.name, "description": g.description, "queries": g.queries,
                      "join_key": g.join_key, "compare_columns": g.compare_columns} for g in items]
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        table = Table(title="Grupos")
        table.add_column("Nome")
        table.add_column("Descricao")
        table.add_column("Consultas")
        table.add_column("Chave")
        table.add_column("Colunas")
        for g in items:
            desc = g.description[:50] + "..." if len(g.description) > 50 else g.description
            table.add_row(g.name, desc or "-", ", ".join(g.queries), g.join_key,
                         ", ".join(g.compare_columns))
        console.print(table)

    else:
        console.print(f"[red]Recurso desconhecido: {resource}[/red]")
        sys.exit(1)


def cmd_ddl(args: argparse.Namespace) -> None:
    """Extract DDL for a database object."""
    conn = find_connection(args.connection)
    if not conn:
        console.print(f"[red]Conexao '{args.connection}' nao encontrada.[/red]")
        sys.exit(1)

    def on_progress(current, total, obj_type, obj_name):
        console.print(f"  [{current}/{total}] {obj_type}: {obj_name}", style="dim")

    result = extract_ddl(conn, args.object, on_progress=on_progress)

    if result.errors:
        for err in result.errors:
            console.print(f"[red]{err}[/red]")
        if not result.objects:
            sys.exit(1)

    if args.stdout:
        for obj in result.objects:
            print(f"-- {obj.obj_type}: {obj.name}")
            print(obj.ddl)
            print()
    else:
        dir_path, _ = save_extraction(result)
        console.print(f"[green]DDL salvo em: {dir_path}[/green]")


def cmd_export_config(args: argparse.Namespace) -> None:
    """Export configurations to a .dbqm bundle."""
    password = args.password or getpass.getpass("Senha para o bundle: ")
    path = export_configs(
        password,
        include_connections=not args.no_connections,
        include_queries=not args.no_queries,
        include_groups=not args.no_groups,
    )
    console.print(f"[green]Configuracoes exportadas: {path}[/green]")


def cmd_import_config(args: argparse.Namespace) -> None:
    """Import configurations from a .dbqm bundle."""
    password = args.password or getpass.getpass("Senha do bundle: ")
    try:
        summary = import_configs(args.file, password)
    except Exception as e:
        console.print(f"[red]Erro ao importar: {e}[/red]")
        sys.exit(1)

    console.print(f"[green]Importado: {summary['connections']} conexoes, "
                  f"{summary['queries']} consultas, {summary['groups']} grupos "
                  f"({summary['skipped']} duplicados ignorados)[/green]")


def cmd_history(args: argparse.Namespace) -> None:
    """View or clear execution history."""
    if args.clear:
        clear_history()
        console.print("[green]Historico limpo.[/green]")
        return

    entries = load_history()
    if not entries:
        console.print("[yellow]Historico vazio.[/yellow]")
        return

    limit = args.limit or 20
    entries = entries[:limit]

    if args.format == "json":
        data = [e.to_dict() for e in entries]
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return

    table = Table(title=f"Historico (ultimos {len(entries)})")
    table.add_column("Data")
    table.add_column("Tipo")
    table.add_column("Nome")
    table.add_column("Conexao")
    table.add_column("Registros")
    table.add_column("Tempo")
    table.add_column("Status")
    for e in entries:
        status = "[green]OK[/green]" if e.success else f"[red]ERRO[/red]"
        if e.all_match is not None:
            status = "[green]CONSISTENTE[/green]" if e.all_match else "[red]DIVERGENTE[/red]"
        table.add_row(
            e.timestamp, e.entry_type, e.name, e.connection or "-",
            str(e.row_count) if e.entry_type == "query" else "-",
            f"{e.elapsed:.2f}s", status,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbqm",
        description="DB Query Manager — ferramenta CLI para consultas em banco de dados",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- run ---
    p_run = subparsers.add_parser("run", help="Executar uma consulta salva")
    p_run.add_argument("query", help="Nome da consulta")
    p_run.add_argument("-c", "--connection", help="Conexao (sobrescreve a padrao da consulta)")
    p_run.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro (pode repetir)")
    p_run.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help="Formato de saida (padrao: table). 'raw' imprime valores sem decoracao.")
    p_run.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")

    # --- run-group ---
    p_grp = subparsers.add_parser("run-group", help="Executar comparacao de grupo")
    p_grp.add_argument("group", help="Nome do grupo")
    p_grp.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro compartilhado (pode repetir)")
    p_grp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help="Formato de saida")
    p_grp.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")
    p_grp.add_argument("--flat", action="store_true",
                       help="Usar formato flat (um bloco por coluna)")

    # --- sql ---
    p_sql = subparsers.add_parser("sql", help="Executar SQL ad-hoc")
    p_sql.add_argument("sql", help="SQL a executar (ou caminho para arquivo .sql)")
    p_sql.add_argument("connection", help="Nome da conexao")
    p_sql.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro (pode repetir)")
    p_sql.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help="Formato de saida. 'raw' imprime valores sem decoracao.")
    p_sql.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")
    p_sql.add_argument("--commit", action="store_true",
                       help="Auto-commit para DML (INSERT/UPDATE/DELETE)")

    # --- test ---
    p_test = subparsers.add_parser("test", help="Testar conexao com banco de dados")
    p_test.add_argument("connection", nargs="?", default="__all__",
                        help="Nome da conexao (ou omita para testar todas)")

    # --- list ---
    p_list = subparsers.add_parser("list", help="Listar conexoes, consultas ou grupos")
    p_list.add_argument("resource", choices=["connections", "queries", "groups"],
                        help="O que listar")
    p_list.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")

    # --- ddl ---
    p_ddl = subparsers.add_parser("ddl", help="Extrair DDL de objeto do banco")
    p_ddl.add_argument("object", help="Nome do objeto")
    p_ddl.add_argument("connection", help="Nome da conexao")
    p_ddl.add_argument("--stdout", action="store_true",
                       help="Imprimir DDL no stdout em vez de salvar em arquivo")

    # --- export-config ---
    p_exp = subparsers.add_parser("export-config", help="Exportar configuracoes para bundle .dbqm")
    p_exp.add_argument("--password", help="Senha (ou sera solicitada interativamente)")
    p_exp.add_argument("--no-connections", action="store_true", help="Excluir conexoes")
    p_exp.add_argument("--no-queries", action="store_true", help="Excluir consultas")
    p_exp.add_argument("--no-groups", action="store_true", help="Excluir grupos")

    # --- import-config ---
    p_imp = subparsers.add_parser("import-config", help="Importar configuracoes de bundle .dbqm")
    p_imp.add_argument("file", help="Caminho do arquivo .dbqm")
    p_imp.add_argument("--password", help="Senha (ou sera solicitada interativamente)")

    # --- history ---
    p_hist = subparsers.add_parser("history", help="Ver historico de execucoes")
    p_hist.add_argument("-n", "--limit", type=int, help="Numero de entradas (padrao: 20)")
    p_hist.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")
    p_hist.add_argument("--clear", action="store_true", help="Limpar historico")

    return parser


COMMAND_MAP = {
    "run": cmd_run,
    "run-group": cmd_run_group,
    "sql": cmd_sql,
    "test": cmd_test,
    "list": cmd_list,
    "ddl": cmd_ddl,
    "export-config": cmd_export_config,
    "import-config": cmd_import_config,
    "history": cmd_history,
}


def run_cli(argv: list[str] | None = None) -> bool:
    """Parse CLI args and execute command. Returns True if a command was handled."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        return False

    handler = COMMAND_MAP.get(args.command)
    if handler:
        handler(args)
        return True

    return False

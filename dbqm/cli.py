"""Command-line interface for non-interactive execution of dbqm operations."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.theme import Theme as _RichTheme

from dbqm.design.tokens import DARK_TOKENS
from dbqm.models.query import find_query, load_queries
from dbqm.models.connection import find_connection, load_connections
from dbqm.models.group import find_group, load_groups
from dbqm.core.query_engine import execute_query, execute_adhoc, execute_explain, classify_sql, QueryResult
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

def rich_theme() -> _RichTheme:
    """Tema do Rich construido a partir dos design tokens.

    O CLI roda em terminal de fundo desconhecido, entao usa sempre a variante
    escura: ela e a unica cuja legibilidade nao depende de o terminal ser claro.
    Os nomes trocam '-' por '.' para seguir a convencao de estilo do Rich.
    """
    return _RichTheme(
        {chave.replace("-", "."): valor for chave, valor in DARK_TOKENS.items()}
    )


console = Console(theme=rich_theme())


def _parse_params(param_list: list[str] | None) -> dict:
    """Parse key=value parameter pairs from CLI arguments."""
    if not param_list:
        return {}
    params = {}
    for p in param_list:
        if "=" not in p:
            console.print(f"[ds.op.failure]Parametro invalido (use chave=valor): {escape(p)}[/ds.op.failure]")
            sys.exit(1)
        key, value = p.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def _add_connection_fields(parser: argparse.ArgumentParser) -> None:
    """The connection fields, shared by `connection add` and `connection update`.

    Nothing here is `required` and `--type` carries no `choices`: a missing or
    invalid value is reported by `connection_builder.validate`, so the user
    meets one error vocabulary instead of argparse's next to dbqm's.
    """
    parser.add_argument("--type", dest="db_type",
                        help="Tipo de banco: oracle, sqlserver, postgresql ou mysql")
    parser.add_argument("--mode", help="Modo Oracle: direct ou tns (padrao: direct)")
    parser.add_argument("--host", help="Host do servidor")
    parser.add_argument("--port", help="Porta (padrao: a do tipo de banco)")
    parser.add_argument("--service", dest="service_name",
                        help="Service name (Oracle, modo direct)")
    parser.add_argument("--database", help="Nome do banco (SQL Server/PostgreSQL/MySQL)")
    parser.add_argument("--tns-path", dest="tns_path",
                        help="Caminho do tnsnames.ora (Oracle, modo tns)")
    parser.add_argument("--tns-name", dest="tns_name",
                        help="Entrada do tnsnames.ora (Oracle, modo tns)")
    parser.add_argument("--user", help="Usuario do banco")
    parser.add_argument("--description", help="Anotacao livre sobre a conexao")
    senha = parser.add_mutually_exclusive_group()
    senha.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help="Ler a senha de uma linha na entrada padrao")
    senha.add_argument("--no-password", action="store_true", dest="no_password",
                       help="Gravar sem senha (ou, em update, apagar a guardada)")
    parser.add_argument("--test", action="store_true", dest="test_before_save",
                        help="Testar a conexao antes de gravar; se falhar, nao grava")
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")


def resolve_password(
    args: argparse.Namespace, env_var: str, prompt: str, *, required: bool,
    use_env: bool = True,
) -> str | None:
    """The password for this command, from the first source that has one.

    Order: `--password-stdin`, `--password` (only where the command has it),
    then `env_var` — unless `use_env` is False, in which case the environment
    is never consulted. `connection update` passes `use_env=False`: its whole
    contract is that a flag not given on THIS command line changes nothing,
    and an ambient `DBQM_PASSWORD` exported for an unrelated `add` is not
    something the user said on this command; `--password-stdin` or
    `--no-password` remain the only ways to change a stored password.
    `add`, `export-config` and `import-config` keep reading the environment
    (`use_env` defaults to True).

    If none of the sources hit and the value is `required`, prompt — but only
    on a TTY, because `getpass` on a pipe blocks forever, which is exactly how
    an agent hangs. An optional password with no source returns None and
    never prompts.

    An empty read from `--password-stdin` is always an error, regardless of
    `required`: a closed/empty pipe is far more often a broken script than an
    intended empty password, and silently falling through would mean `update`
    clears a stored password without `--no-password` ever being said.
    """
    from_stdin = getattr(args, "password_stdin", False)
    direct = getattr(args, "password", None)

    if from_stdin and direct:
        console.print(
            "[ds.op.failure]Use --password-stdin ou --password, nao os dois."
            "[/ds.op.failure]"
        )
        sys.exit(2)

    if from_stdin:
        # Only the line terminator comes off: a password may end in a space.
        value = sys.stdin.readline().rstrip("\r\n")
        if not value:
            console.print(
                "[ds.op.failure]Senha vazia na entrada padrao. Use "
                "--no-password para gravar sem senha.[/ds.op.failure]"
            )
            sys.exit(2)
        return value
    if direct:
        return direct

    if use_env:
        from_env = os.environ.get(env_var)
        if from_env:
            return from_env

    if not required:
        return None

    if sys.stdin.isatty():
        return getpass.getpass(prompt)

    console.print(
        f"[ds.op.failure]Senha nao informada. Use --password-stdin ou "
        f"defina {env_var}.[/ds.op.failure]"
    )
    sys.exit(2)


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
        console.print(f"[ds.op.failure]Erro: {result.error}[/ds.op.failure]")
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
        console.print(f"[ds.op.failure]Consulta '{escape(args.query)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    conn_name = args.connection or query.connection
    conn = find_connection(conn_name)
    if not conn:
        console.print(f"[ds.op.failure]Conexao '{escape(conn_name)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    param_values = _parse_params(args.param)

    # Fill missing params with defaults
    for p in query.params:
        if p.name not in param_values and p.default:
            param_values[p.name] = p.default

    # Validate required params
    missing = [p.name for p in query.params if p.name not in param_values]
    if missing:
        console.print(f"[ds.op.failure]Parametros obrigatorios faltando: {', '.join(missing)}[/ds.op.failure]")
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
            console.print(f"[ds.op.failure]Formato de export invalido: {fmt}[/ds.op.failure]")
            sys.exit(1)
        console.print(f"Exportado: {path}")
        return

    _print_query_result(result, args.format)


def _colored_comparison_lines(comparisons: list) -> list[str]:
    """Linhas de resumo do grupo, coloridas pelo eixo de veredito.

    Reconstroi o texto a partir de `ComparisonResult` (contagens), em vez de
    reimprimir `group_result.summary_lines` cru: assim cada contagem recebe
    o token do eixo a que pertence (igual/diferente/ausente) sem depender do
    texto que o core escreve — core/ permanece livre de markup.
    """
    linhas: list[str] = []
    for comp in comparisons:
        linhas.append(f"Coluna: {comp.column}")
        linhas.append(f"  [ds.verdict.match]Iguais:[/]       {comp.equal_count}")
        if comp.normalized_count > 0:
            linhas.append(f"  [ds.verdict.match]Iguais (norm):[/] {comp.normalized_count}")
        linhas.append(f"  [ds.verdict.diff]Diferentes:[/]   {comp.diff_count}")
        linhas.append(f"  [ds.verdict.absent]Ausentes:[/]     {comp.absent_count}")
    return linhas


def cmd_run_group(args: argparse.Namespace) -> None:
    """Execute a group comparison."""
    group = find_group(args.group)
    if not group:
        console.print(f"[ds.op.failure]Grupo '{escape(args.group)}' nao encontrado.[/ds.op.failure]")
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
            console.print(f"[ds.op.failure]Consulta '{escape(qname)}' do grupo nao encontrada.[/ds.op.failure]")
            sys.exit(1)
        conn = find_connection(query.connection)
        if not conn:
            console.print(f"[ds.op.failure]Conexao '{escape(query.connection)}' nao encontrada.[/ds.op.failure]")
            sys.exit(1)

        result = execute_query(query, conn, param_values)
        if not result.success:
            console.print(f"[ds.op.failure]Erro na consulta '{qname}': {result.error}[/ds.op.failure]")
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
        console.print(f"Exportado: {path}")
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
        status = "[ds.verdict.match]CONSISTENTE[/]" if group_result.all_match else "[ds.verdict.diff]DIVERGENTE[/]"
        console.print(f"Grupo: {group_result.group_name} — {status}")
        for line in _colored_comparison_lines(group_result.comparisons):
            console.print(f"  {line}")


def cmd_sql(args: argparse.Namespace) -> None:
    """Execute ad-hoc SQL."""
    conn = find_connection(args.connection)
    if not conn:
        console.print(f"[ds.op.failure]Conexao '{escape(args.connection)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    sql = args.sql
    # If argument is a file path, read SQL from it
    sql_path = Path(sql)
    if sql_path.is_file():
        sql = sql_path.read_text(encoding="utf-8")

    param_values = _parse_params(args.param)

    if args.explain:
        result = execute_explain(sql, conn, param_values)
        if not result.success:
            console.print(f"[ds.op.failure]Erro: {result.error}[/ds.op.failure]")
            sys.exit(1)
        for row in result.rows:
            print(row[0] if row else "")
        console.print(f"[dim]({result.elapsed:.2f}s)[/dim]")
        return

    sql_type = classify_sql(sql)

    # Require --commit for DML operations
    if sql_type in ("INSERT", "UPDATE", "DELETE") and not args.commit:
        console.print("[ds.op.failure]DML requer --commit para confirmar a operacao.[/ds.op.failure]")
        sys.exit(1)

    result = execute_adhoc(sql, conn, param_values, auto_commit=args.commit)

    # For non-SELECT results (always AdhocResult with auto_commit=True at this point)
    if not isinstance(result, tuple) and result.sql_type in ("INSERT", "UPDATE", "DELETE"):
        if not result.success:
            console.print(f"[ds.op.failure]Erro: {result.error}[/ds.op.failure]")
            sys.exit(1)
        console.print(f"{result.rows_affected} registros afetados (committed)")
        return

    # DDL results
    if not isinstance(result, tuple) and result.sql_type == "DDL":
        if result.success:
            console.print(f"DDL executado com sucesso ({result.elapsed:.2f}s)")
        else:
            console.print(f"[ds.op.failure]DDL executado com erros de compilacao ({result.elapsed:.2f}s)[/ds.op.failure]")
            console.print(f"[ds.op.failure]{result.error}[/ds.op.failure]")
            sys.exit(1)
        return

    # PL/SQL anonymous block results
    if not isinstance(result, tuple) and result.sql_type == "PLSQL":
        if not result.success:
            console.print(f"[ds.op.failure]Erro: {result.error}[/ds.op.failure]")
            sys.exit(1)
        from dbqm.core.query_engine import block_label

        console.print(
            f"{block_label(result.db_type)} executado ({result.elapsed:.2f}s)"
        )
        if result.rows:
            _print_query_result(
                QueryResult(
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
        console.print(f"[ds.op.failure]Erro: {result.error}[/ds.op.failure]")
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
            console.print(f"Exportado: {path}")
            return

        _print_query_result(qr, args.format)
    else:
        console.print(f"{result.rows_affected} registros afetados")


def cmd_test(args: argparse.Namespace) -> None:
    """Test a database connection."""
    if args.connection == "__all__":
        connections = load_connections()
        if not connections:
            console.print("[ds.text.muted]Nenhuma conexao configurada.[/ds.text.muted]")
            return
        for conn in connections:
            ok, msg = test_connection(conn)
            icon = "OK" if ok else "[ds.op.failure]FAIL[/ds.op.failure]"
            console.print(f"  {icon}  [ds.identity]{escape(conn.name)}[/]: {escape(msg.splitlines()[0])}")
        return

    conn = find_connection(args.connection)
    if not conn:
        console.print(f"[ds.op.failure]Conexao '{escape(args.connection)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    ok, msg = test_connection(conn)
    if ok:
        console.print(escape(msg))
    else:
        console.print(f"[ds.op.failure]{escape(msg)}[/ds.op.failure]")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List connections, queries, or groups."""
    resource = args.resource

    if resource == "connections":
        items = load_connections()
        if not items:
            console.print("[ds.text.muted]Nenhuma conexao configurada.[/ds.text.muted]")
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
            table.add_row(f"[ds.identity]{escape(c.name)}[/]", c.db_type, escape(c.display_target()))
        console.print(table)

    elif resource == "queries":
        items = load_queries()
        if not items:
            console.print("[ds.text.muted]Nenhuma consulta configurada.[/ds.text.muted]")
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
            table.add_row(q.name, desc or "-", f"[ds.identity]{q.connection}[/]", q.folder or "-", params, fav)
        console.print(table)

    elif resource == "groups":
        items = load_groups()
        if not items:
            console.print("[ds.text.muted]Nenhum grupo configurado.[/ds.text.muted]")
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
        console.print(f"[ds.op.failure]Recurso desconhecido: {resource}[/ds.op.failure]")
        sys.exit(1)


def cmd_ddl(args: argparse.Namespace) -> None:
    """Extract DDL for a database object."""
    conn = find_connection(args.connection)
    if not conn:
        console.print(f"[ds.op.failure]Conexao '{escape(args.connection)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    def on_progress(current, total, obj_type, obj_name):
        console.print(f"  [{current}/{total}] {escape(obj_type)}: {escape(obj_name)}", style="dim")

    result = extract_ddl(conn, args.object, on_progress=on_progress)

    if result.errors:
        for err in result.errors:
            console.print(f"[ds.op.failure]{escape(err)}[/ds.op.failure]")
        if not result.objects:
            sys.exit(1)

    if args.stdout:
        for obj in result.objects:
            print(f"-- {obj.obj_type}: {obj.name}")
            print(obj.ddl)
            print()
    else:
        dir_path, _ = save_extraction(result)
        console.print(f"DDL salvo em: {dir_path}")


def cmd_export_config(args: argparse.Namespace) -> None:
    """Export configurations to a .dbqm bundle."""
    password = resolve_password(
        args, "DBQM_BUNDLE_PASSWORD", "Senha para o bundle: ", required=True
    )
    path = export_configs(
        password,
        include_connections=not args.no_connections,
        include_queries=not args.no_queries,
        include_groups=not args.no_groups,
    )
    console.print(f"Configuracoes exportadas: {path}")


def cmd_import_config(args: argparse.Namespace) -> None:
    """Import configurations from a .dbqm bundle."""
    password = resolve_password(
        args, "DBQM_BUNDLE_PASSWORD", "Senha do bundle: ", required=True
    )
    try:
        summary = import_configs(args.file, password)
    except Exception as e:
        console.print(f"[ds.op.failure]Erro ao importar: {escape(str(e))}[/ds.op.failure]")
        sys.exit(1)

    console.print(f"Importado: {summary['connections']} conexoes, "
                  f"{summary['queries']} consultas, {summary['groups']} grupos "
                  f"({summary['skipped']} duplicados ignorados)")


def cmd_history(args: argparse.Namespace) -> None:
    """View or clear execution history."""
    if args.clear:
        clear_history()
        console.print("Historico limpo.")
        return

    entries = load_history()
    if not entries:
        console.print("[ds.text.muted]Historico vazio.[/ds.text.muted]")
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
        status = "OK" if e.success else "[ds.op.failure]ERRO[/ds.op.failure]"
        if e.all_match is not None:
            status = "[ds.verdict.match]CONSISTENTE[/]" if e.all_match else "[ds.verdict.diff]DIVERGENTE[/]"
        table.add_row(
            e.timestamp, e.entry_type, e.name,
            f"[ds.identity]{e.connection}[/]" if e.connection else "-",
            str(e.row_count) if e.entry_type == "query" else "-",
            f"{e.elapsed:.2f}s", status,
        )
    console.print(table)


_CONNECTION_OUTCOME_TEXT = {
    "created": "criada",
    "updated": "atualizada",
    "removed": "removida",
}


def _print_connection_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        print(json.dumps({"name": name, outcome: True}, ensure_ascii=False))
        return
    console.print(f'Conexao "{escape(name)}" {_CONNECTION_OUTCOME_TEXT[outcome]}.')


def _connection_values(args: argparse.Namespace, password: str | None) -> dict:
    """Only the flags actually given. A flag left out must not overwrite.

    `None` means "not mentioned on this command line" — dropped here so that
    `build` sees an absent key, which for the password is what means "keep the
    stored one".
    """
    values = {
        "name": args.name,
        "db_type": args.db_type,
        "mode": args.mode,
        "host": args.host,
        "port": args.port,
        "service_name": args.service_name,
        "database": args.database,
        "tns_path": args.tns_path,
        "tns_name": args.tns_name,
        "user": args.user,
        "description": args.description,
        "password": password,
    }
    return {key: value for key, value in values.items() if value is not None}


def _exit_with_errors(errors: list[str]) -> None:
    for error in errors:
        console.print(f"[ds.op.failure]{escape(error)}[/ds.op.failure]")
    sys.exit(2)


def _connection_add(args: argparse.Namespace) -> None:
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import find_connection, load_connections, save_connections

    if find_connection(args.name) is not None:
        console.print(f'[ds.op.failure]Conexao "{escape(args.name)}" ja existe.[/ds.op.failure]')
        sys.exit(2)

    # Validate everything but the password first: a terminal user should
    # learn about a bad --type before being asked to type a secret that
    # turns out not to matter.
    values = _connection_values(args, None)
    errors = validate(values)
    if errors:
        _exit_with_errors(errors)

    if args.no_password:
        password = ""
    else:
        password = resolve_password(
            args, "DBQM_PASSWORD", "Senha da conexao: ", required=True
        )
    values["password"] = password

    conn = build(values)

    if args.test_before_save:
        ok, msg = test_connection(conn)
        if not ok:
            console.print(f"[ds.op.failure]{msg}[/ds.op.failure]")
            console.print("[dim]Conexao nao gravada.[/dim]")
            sys.exit(3)

    connections = load_connections()
    connections.append(conn)
    save_connections(connections)
    _print_connection_outcome(args.format, conn.name, "created")


def _connection_update(args: argparse.Namespace) -> None:
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import find_connection, load_connections, save_connections

    existing = find_connection(args.name)
    if existing is None:
        console.print(
            f'[ds.op.failure]Conexao "{escape(args.name)}" nao encontrada.[/ds.op.failure]'
        )
        sys.exit(2)

    if args.no_password:
        password = ""  # an explicit empty value clears the stored password
    else:
        # use_env=False: an ambient DBQM_PASSWORD is not something the user
        # said on THIS command line, and update's contract is that what you
        # did not pass does not change. --password-stdin or --no-password
        # are the only ways to change the stored password here.
        password = resolve_password(
            args, "DBQM_PASSWORD", "Senha da conexao: ", required=False,
            use_env=False,
        )

    # Start from what is stored and lay the given flags on top: on a command
    # line, what was not said was not changed. `created_at` and the stored
    # password are dropped from the base because `build` reads them from
    # `existing` — re-encrypting the ciphertext would double-wrap it.
    merged = existing.to_dict()
    merged.pop("password", None)
    merged.pop("created_at", None)
    merged.update(_connection_values(args, password))

    errors = validate(merged)
    if errors:
        _exit_with_errors(errors)

    conn = build(merged, existing)

    if args.test_before_save:
        ok, msg = test_connection(conn)
        if not ok:
            console.print(f"[ds.op.failure]{msg}[/ds.op.failure]")
            console.print("[dim]Conexao nao alterada.[/dim]")
            sys.exit(3)

    connections = load_connections()
    index = next(i for i, c in enumerate(connections) if c.name == conn.name)
    connections[index] = conn
    save_connections(connections)
    _print_connection_outcome(args.format, conn.name, "updated")


def _connection_show(args: argparse.Namespace) -> None:
    from dbqm.models.connection import find_connection

    conn = find_connection(args.name)
    if conn is None:
        console.print(
            f'[ds.op.failure]Conexao "{escape(args.name)}" nao encontrada.[/ds.op.failure]'
        )
        sys.exit(2)

    data = conn.to_dict()
    # Never the ciphertext: the Fernet key lives next to the config, so
    # printing it puts a decryptable password into whatever captured stdout.
    data["password"] = "***" if conn.password else ""

    if args.format == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    table = Table(title=f"Conexao: {escape(conn.name)}")
    table.add_column("Campo")
    table.add_column("Valor")
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _connection_rm(args: argparse.Namespace) -> None:
    from dbqm.models.connection import delete_connection, find_connection

    if find_connection(args.name) is None:
        console.print(
            f'[ds.op.failure]Conexao "{escape(args.name)}" nao encontrada.[/ds.op.failure]'
        )
        sys.exit(2)

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            console.print(
                "[ds.op.failure]Use --yes para remover sem confirmacao."
                "[/ds.op.failure]"
            )
            sys.exit(2)
        resposta = input(f'Remover a conexao "{args.name}"? [s/N] ').strip().lower()
        if resposta not in ("s", "sim"):
            if args.format == "json":
                print(json.dumps({"name": args.name, "removed": False}, ensure_ascii=False))
            else:
                console.print("Cancelado.")
            return

    delete_connection(args.name)
    _print_connection_outcome(args.format, args.name, "removed")


def _connection_list(args: argparse.Namespace) -> None:
    """The same listing as `dbqm list connections`.

    Three lines of delegation so that `dbqm connection --help` shows a whole
    CRUD; without it, whoever reads that help cannot find the listing verb.
    """
    cmd_list(argparse.Namespace(resource="connections", format=args.format))


_CONNECTION_SUBCOMMANDS = {
    "add": _connection_add,
    "update": _connection_update,
    "rm": _connection_rm,
    "show": _connection_show,
    "list": _connection_list,
}


def cmd_connection(args: argparse.Namespace) -> None:
    """Manage saved connections."""
    handler = _CONNECTION_SUBCOMMANDS.get(getattr(args, "subcommand", None))
    if handler is None:
        # A bare `dbqm connection` prints the group's own help (add/update/
        # rm/show/list, with their flags) rather than a one-line reminder.
        if _connection_parser is not None:
            _connection_parser.print_help()
        else:
            console.print(
                "[ds.op.failure]Use: dbqm connection add|update|rm|show|list"
                "[/ds.op.failure]"
            )
        sys.exit(2)
    handler(args)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Set by `build_parser` so `cmd_connection` can print the group's own help
# (add/update/rm/show/list) on a bare `dbqm connection` instead of a one-line
# reminder. Simplest way to reach a subparser created deep inside the
# function without threading it through `COMMAND_MAP`/`args`.
_connection_parser: argparse.ArgumentParser | None = None


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
    p_sql = subparsers.add_parser(
        "sql",
        help="Executar SQL ad-hoc (SELECT, CTE, DML, DDL, PL/SQL ou EXPLAIN PLAN)",
    )
    p_sql.add_argument(
        "sql",
        help=(
            "SQL a executar (ou caminho para arquivo .sql). "
            "Aceita SELECT (incluindo CTE WITH ... SELECT), INSERT/UPDATE/DELETE "
            "(com --commit), DDL (CREATE/ALTER/DROP/...), blocos PL/SQL anonimos "
            "(DECLARE/BEGIN/END;) com captura de DBMS_OUTPUT, os atalhos "
            "EXEC/EXECUTE/CALL <proc>, e EXPLAIN PLAN. Use --explain para "
            "obter o plano automaticamente."
        ),
    )
    p_sql.add_argument("connection", help="Nome da conexao")
    p_sql.add_argument("-p", "--param", action="append", metavar="CHAVE=VALOR",
                       help="Parametro (pode repetir)")
    p_sql.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help="Formato de saida. 'raw' imprime valores sem decoracao.")
    p_sql.add_argument("-e", "--export", choices=["csv", "json", "txt"],
                       help="Exportar resultado para arquivo")
    p_sql.add_argument("--commit", action="store_true",
                       help="Auto-commit para DML (INSERT/UPDATE/DELETE)")
    p_sql.add_argument("--explain", action="store_true",
                       help=(
                           "Mostra o plano de execucao da query (EXPLAIN PLAN + DBMS_XPLAN.DISPLAY no Oracle, "
                           "EXPLAIN nativo em PostgreSQL/MySQL). Passe apenas a query, sem EXPLAIN PLAN FOR."
                       ))

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
    p_exp.add_argument("--password",
                       help="Senha (desaconselhado: fica no historico do shell "
                            "e na tabela de processos; prefira --password-stdin)")
    p_exp.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help="Ler a senha de uma linha na entrada padrao")
    p_exp.add_argument("--no-connections", action="store_true", help="Excluir conexoes")
    p_exp.add_argument("--no-queries", action="store_true", help="Excluir consultas")
    p_exp.add_argument("--no-groups", action="store_true", help="Excluir grupos")

    # --- import-config ---
    p_imp = subparsers.add_parser("import-config", help="Importar configuracoes de bundle .dbqm")
    p_imp.add_argument("file", help="Caminho do arquivo .dbqm")
    p_imp.add_argument("--password",
                       help="Senha (desaconselhado: fica no historico do shell "
                            "e na tabela de processos; prefira --password-stdin)")
    p_imp.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help="Ler a senha de uma linha na entrada padrao")

    # --- history ---
    p_hist = subparsers.add_parser("history", help="Ver historico de execucoes")
    p_hist.add_argument("-n", "--limit", type=int, help="Numero de entradas (padrao: 20)")
    p_hist.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")
    p_hist.add_argument("--clear", action="store_true", help="Limpar historico")

    # --- connection ---
    global _connection_parser
    p_conn = subparsers.add_parser(
        "connection",
        help="Gerenciar conexoes (criar, alterar, remover, ver, listar)",
    )
    _connection_parser = p_conn
    conn_sub = p_conn.add_subparsers(dest="subcommand")

    p_conn_add = conn_sub.add_parser("add", help="Criar uma conexao")
    p_conn_add.add_argument("name", help="Nome da conexao")
    _add_connection_fields(p_conn_add)

    p_conn_update = conn_sub.add_parser("update", help="Alterar uma conexao existente")
    p_conn_update.add_argument("name", help="Nome da conexao")
    _add_connection_fields(p_conn_update)

    p_conn_show = conn_sub.add_parser("show", help="Ver uma conexao (senha omitida)")
    p_conn_show.add_argument("name", help="Nome da conexao")
    p_conn_show.add_argument("-f", "--format", choices=["table", "json"],
                             default="table", help="Formato de saida")

    p_conn_rm = conn_sub.add_parser("rm", help="Remover uma conexao")
    p_conn_rm.add_argument("name", help="Nome da conexao")
    p_conn_rm.add_argument("--yes", action="store_true",
                           help="Remover sem confirmacao (obrigatorio fora do terminal)")
    p_conn_rm.add_argument("-f", "--format", choices=["table", "json"],
                           default="table", help="Formato de saida")

    p_conn_list = conn_sub.add_parser("list", help="Listar conexoes")
    p_conn_list.add_argument("-f", "--format", choices=["table", "json"],
                             default="table", help="Formato de saida")

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
    "connection": cmd_connection,
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

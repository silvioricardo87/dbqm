"""Main interactive menu."""
from __future__ import annotations

from rich.console import Console

from dbqm.core.query_engine import execute_query, QueryResult
from dbqm.core.group_engine import build_group_result, GroupResult
from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt,
    export_group_csv, export_group_json, export_group_txt,
)
from dbqm.models.connection import load_connections, find_connection
from dbqm.models.query import load_queries, find_query
from dbqm.models.group import load_groups, find_group
from dbqm.ui.display import (
    show_banner, show_success, show_error, show_warning, show_info,
    show_query_result, show_group_result,
)
from dbqm.ui.prompts import select, text, is_esc
from dbqm.ui.config_wizard import connection_wizard
from dbqm.ui.query_wizard import query_wizard
from dbqm.ui.group_wizard import group_wizard

console = Console()


def main_menu():
    """Main application loop."""
    show_banner()

    # First-run check
    connections = load_connections()
    if not connections:
        show_info("Nenhuma conexao configurada. Vamos configurar a primeira?")
        connection_wizard()

    while True:
        console.print()
        action = select(
            message="Menu principal:",
            choices=[
                {"name": "Executar consulta", "value": "exec_query"},
                {"name": "Executar grupo de consultas", "value": "exec_group"},
                {"name": "Configurar conexoes", "value": "config_conn"},
                {"name": "Configurar consultas", "value": "config_query"},
                {"name": "Configurar grupos", "value": "config_group"},
                {"name": "Sair", "value": "exit"},
            ],
        )

        if is_esc(action) or action == "exit":
            console.print("\n[dim]Ate logo![/dim]\n")
            break
        elif action == "config_conn":
            connection_wizard()
        elif action == "config_query":
            query_wizard()
        elif action == "config_group":
            group_wizard()
        elif action == "exec_query":
            _execute_query_flow()
        elif action == "exec_group":
            _execute_group_flow()


def _execute_query_flow():
    """Flow to execute a single query."""
    queries = load_queries()
    if not queries:
        show_warning("Nenhuma consulta configurada.")
        return

    choices = [
        {"name": f"{q.name} ({q.connection} -> {q.table})", "value": q.name}
        for q in queries
    ]

    selected = select(message="Selecione a consulta:", choices=choices)
    if is_esc(selected):
        return

    query = find_query(selected)
    if not query:
        show_error("Consulta nao encontrada.")
        return

    conn = find_connection(query.connection)
    if not conn:
        show_error(f'Conexao "{query.connection}" nao encontrada.')
        return

    # Gather parameters
    param_values = {}
    for p in query.params:
        prompt = f"{p.name}"
        if p.description:
            prompt += f" ({p.description})"
        val = text(message=f"  {prompt}:", default=p.default)
        if is_esc(val):
            return
        param_values[p.name] = val

    # Execute
    with console.status(f"Executando {query.name} em {conn.name}..."):
        result = execute_query(query, conn, param_values)

    if result.success and result.rows:
        query.apply_column_maps(result.rows, result.columns)

    show_query_result(result)

    if result.success and result.rows:
        _post_result_actions(result, query.table)


def _post_result_actions(result: QueryResult, table: str = ""):
    """Actions after displaying a query result."""
    while True:
        action = select(
            message="Acao:",
            choices=[
                {"name": "Exportar resultado", "value": "export"},
                {"name": "Reexecutar", "value": "reexec"},
                {"name": "Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "reexec":
            return
        elif action == "export":
            _export_result(result, table)


def _export_result(result: QueryResult, table: str = ""):
    """Export a single query result."""
    fmt = select(
        message="Formato:",
        choices=[
            {"name": "CSV", "value": "csv"},
            {"name": "JSON", "value": "json"},
            {"name": "TXT (tabela formatada)", "value": "txt"},
        ],
    )

    if is_esc(fmt):
        return

    if fmt == "csv":
        path = export_query_csv(result, table)
    elif fmt == "json":
        path = export_query_json(result, table)
    else:
        path = export_query_txt(result, table)

    show_success(f"Exportado: {path}")


def _execute_group_flow():
    """Flow to execute a query group."""
    groups = load_groups()
    if not groups:
        show_warning("Nenhum grupo configurado.")
        return

    choices = [
        {"name": f"{g.name} ({', '.join(g.queries)})", "value": g.name}
        for g in groups
    ]

    selected = select(message="Selecione o grupo:", choices=choices)
    if is_esc(selected):
        return

    group = find_group(selected)
    if not group:
        show_error("Grupo nao encontrado.")
        return

    # Gather shared params
    param_values = {}
    for param_name, param_info in group.shared_params.items():
        desc = param_info.get("description", "")
        default = param_info.get("default", "")
        prompt = f"{param_name}"
        if desc:
            prompt += f" ({desc})"
        val = text(message=f"  {prompt}:", default=default)
        if is_esc(val):
            return
        param_values[param_name] = val

    # Execute each query in sequence
    console.print(f"\n[bold]Executando {len(group.queries)} consultas...[/bold]\n")

    query_results = {}
    all_ok = True

    for i, qname in enumerate(group.queries, 1):
        query = find_query(qname)
        if not query:
            show_error(f"[{i}/{len(group.queries)}] Consulta '{qname}' nao encontrada.")
            all_ok = False
            continue

        conn = find_connection(query.connection)
        if not conn:
            show_error(f"[{i}/{len(group.queries)}] Conexao '{query.connection}' nao encontrada.")
            all_ok = False
            continue

        # Build params for this query (shared + query-specific defaults)
        q_params = dict(param_values)
        for p in query.params:
            if p.name not in q_params:
                q_params[p.name] = p.default

        console.print(f"  [{i}/{len(group.queries)}] {qname} ({conn.name})")
        with console.status(f"    Conectando e executando..."):
            result = execute_query(query, conn, q_params)

        if result.success:
            if result.rows:
                query.apply_column_maps(result.rows, result.columns)
            show_success(f"{result.row_count} registros ({result.elapsed:.2f}s)")
        else:
            show_error(f"ERRO - {result.error}")
            all_ok = False

        query_results[qname] = result

    if not query_results:
        show_error("Nenhuma consulta executada com sucesso.")
        return

    # Build comparison
    group_result = build_group_result(
        group_name=group.name,
        query_results=query_results,
        join_key=group.join_key,
        compare_columns=group.compare_columns,
        column_mapping=group.column_mapping or None,
        normalize=group.normalize or None,
    )

    show_group_result(group_result, param_values)

    # Post-group actions
    _post_group_actions(group_result, param_values)


def _post_group_actions(group_result: GroupResult, params: dict):
    """Actions after displaying a group result."""
    while True:
        action = select(
            message="Acao:",
            choices=[
                {"name": "Exportar resultado completo", "value": "export"},
                {"name": "Ver resultados individuais", "value": "detail"},
                {"name": "Reexecutar", "value": "reexec"},
                {"name": "Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "reexec":
            return
        elif action == "export":
            _export_group(group_result, params)
        elif action == "detail":
            _show_individual_results(group_result)


def _export_group(group_result: GroupResult, params: dict):
    """Export group result."""
    fmt = select(
        message="Formato:",
        choices=[
            {"name": "CSV", "value": "csv"},
            {"name": "JSON", "value": "json"},
            {"name": "TXT (tabela formatada)", "value": "txt"},
        ],
    )

    if is_esc(fmt):
        return

    if fmt == "csv":
        path = export_group_csv(group_result, params)
    elif fmt == "json":
        path = export_group_json(group_result, params)
    else:
        path = export_group_txt(group_result, params)

    show_success(f"Exportado: {path}")


def _show_individual_results(group_result: GroupResult):
    """Show individual query results from a group execution."""
    choices = [
        {"name": f"{qname} ({r.row_count} registros)", "value": qname}
        for qname, r in group_result.query_results.items()
        if r.success
    ]

    selected = select(message="Qual resultado?", choices=choices)
    if is_esc(selected):
        return

    result = group_result.query_results[selected]
    show_query_result(result)
